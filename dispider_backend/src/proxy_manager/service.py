import re
from typing import List, Dict, Any, Optional, Tuple
import yaml
import requests
import os
from pathlib import Path
import redis
import logging
import time
import concurrent.futures
import threading
from datetime import datetime, timedelta

# 获取一个logger实例
logger = logging.getLogger(__name__)

# 定义地区关键词，用于从节点名称中识别地理位置
# 键是标准的地区名称，值是可能出现在节点名称中的关键词列表
REGION_KEYWORDS: Dict[str, List[str]] = {
    '香港': ['香港', 'HK', 'Hong Kong', 'HGC', 'HKT'],
    '台湾': ['台湾', 'TW', 'Taiwan', 'Hinet', '台'],
    '日本': ['日本', 'JP', 'Japan', '大阪', '东京', 'softbank', 'au', 'jp'],
    '新加坡': ['新加坡', 'SG', 'Singapore', '狮城', 'sgp'],
    '美国': ['美国', 'US', 'United States', 'LA', 'us'],
    '韩国': ['韩国', 'KR', 'Korea', '首尔', 'kr'],
    '虚拟': ['虚拟'],
    '加拿大':['加拿大', 'CA', 'Canada', '多伦多', 'toronto', 'ca'],
    '英国':['英国', 'GB', 'United Kingdom', '伦敦', 'london', 'gb'],
    '德国':['德国', 'DE', 'Germany', '法兰克福', 'frankfurt', 'de'],
    '法国':['法国', 'FR', 'France', '巴黎', 'paris', 'fr'],
    '意大利':['意大利', 'IT', 'Italy', '罗马', 'rome', 'it'],
    '西班牙':['西班牙', 'ES', 'Spain', '马德里', 'madrid', 'es'],
    '荷兰':['荷兰', 'NL', 'Netherlands', '阿姆斯特丹', 'amsterdam', 'nl'],
    '比利时':['比利时', 'BE', 'Belgium', '布鲁塞尔', 'brussels', 'be'],
}

# 代理组健康状态管理
PROXY_GROUP_HEALTH_KEY = "proxy_group_health"
PROXY_GROUP_FAILURE_COUNT_KEY = "proxy_group_failure_count"
PROXY_GROUP_LAST_CHECK_KEY = "proxy_group_last_check"
PROXY_GROUP_BLACKLIST_KEY = "proxy_group_blacklist"

# 健康检查配置
HEALTH_CHECK_TIMEOUT = 10  # 秒
HEALTH_CHECK_INTERVAL = 60  # 秒  
MAX_FAILURE_COUNT = 3  # 最大失败次数
BLACKLIST_DURATION = 600  # 黑名单持续时间（秒）
REASSIGN_CHECK_INTERVAL = 120  # 重新分配检查间隔（秒）

def generate_proxy_groups(proxies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    根据proxies列表自动生成proxy-groups。

    通过解析节点名称中的关键词，将节点按地区进行分组，
    然后将每个地区的节点进一步细分为最多5个节点的小组，
    每个小组使用 `url-test` 类型以实现自动测速和故障转移。
    
    优化后的配置：
    - 缩短测试间隔至30秒，提高故障检测速度
    - 增加容忍度配置，避免频繁切换
    - 添加备用测试URL，提高可靠性

    Args:
        proxies: 包含所有代理节点信息的列表。

    Returns:
        生成好的proxy-groups列表，全部为 url-test 类型的子组。
    """
    if not proxies:
        return []

    # 按地区对节点进行分类
    regional_nodes: Dict[str, List[str]] = {region: [] for region in REGION_KEYWORDS}
    regional_nodes['其他'] = []

    for proxy in proxies:
        # 健壮性检查：确保 'proxy' 是一个字典，以防止配置文件格式错误导致崩溃
        if not isinstance(proxy, dict):
            logger.warning(f"跳过无效的代理项 (期望字典类型，得到 {type(proxy)}): {proxy}")
            continue

        proxy_name = proxy.get('name', '')
        found_region = False
        for region, keywords in REGION_KEYWORDS.items():
            # 使用正则表达式进行不区分大小写的匹配
            if any(re.search(keyword, proxy_name, re.IGNORECASE) for keyword in keywords):
                regional_nodes[region].append(proxy_name)
                found_region = True
                break
        if not found_region:
            regional_nodes['其他'].append(proxy_name)

    # 创建 proxy-groups，只创建 url-test 类型的子组
    proxy_groups = []
    total_groups_created = 0

    for region, nodes in regional_nodes.items():
        if not nodes:
            continue
        
        # 如果节点数量 <= 5，创建单个组
        if len(nodes) <= 5:
            group_name = f'[Auto] {region}'

            region_group = {
                'name': group_name,
                'type': 'url-test',
                'proxies': nodes,
                'url': 'http://www.gstatic.com/generate_204',
                'interval': 30,  # 优化：缩短测试间隔至30秒
                'tolerance': 50,  # 新增：容忍度50ms，避免频繁切换
                'timeout': 3000,  # 新增：3秒超时
                'lazy': False  # 新增：立即进行健康检查
            }
            proxy_groups.append(region_group)
            total_groups_created += 1
            logger.info(f"创建单个组: {group_name} (节点数: {len(nodes)})")
        
        else:
            # 如果节点数量 > 5，按照最多5个节点一组进行分割
            max_nodes_per_group = 5
            total_sub_groups = (len(nodes) + max_nodes_per_group - 1) // max_nodes_per_group  # 向上取整
            
            # 创建子组
            for i in range(total_sub_groups):
                start_idx = i * max_nodes_per_group
                end_idx = min(start_idx + max_nodes_per_group, len(nodes))
                group_nodes = nodes[start_idx:end_idx]
                
                # 生成子组名称
                sub_group_name = f'[Auto] {region}-{i+1:02d}'
                
                # 创建子组，优化配置参数
                sub_group = {
                    'name': sub_group_name,
                    'type': 'url-test',
                    'proxies': group_nodes,
                    'url': 'http://www.gstatic.com/generate_204',
                    'interval': 30,  # 优化：缩短测试间隔至30秒
                    'tolerance': 50,  # 新增：容忍度50ms，避免频繁切换
                    'timeout': 3000,  # 新增：3秒超时
                    'lazy': False  # 新增：立即进行健康检查
                }
                proxy_groups.append(sub_group)
                total_groups_created += 1
                logger.info(f"创建子组: {sub_group_name} (节点数: {len(group_nodes)})")

    logger.info(f"代理组生成完成，共创建 {total_groups_created} 个 url-test 组，容器将轮询分配到这些组中")
    return proxy_groups

CLASH_API_URL = "http://clash:9090/configs"
CONFIG_BASE_PATH = Path("clash")
PROVIDERS_PATH = CONFIG_BASE_PATH / "providers"

REDIS_CLIENT = redis.Redis(host='redis', port=6379, decode_responses=True)
CONTAINER_PROXY_RULES_KEY = "container_proxy_rules"

def test_proxy_group_health(group_name: str) -> Tuple[bool, float]:
    """
    测试代理组的健康状态。
    
    Args:
        group_name: 代理组名称
        
    Returns:
        (is_healthy, response_time): 健康状态和响应时间
    """
    try:
        # 通过Clash API测试代理组
        test_url = "http://clash:9090/proxies"
        start_time = time.time()
        
        response = requests.get(f"{test_url}/{group_name}/delay", 
                              params={'timeout': HEALTH_CHECK_TIMEOUT * 1000, 
                                     'url': 'http://www.gstatic.com/generate_204'},
                              timeout=HEALTH_CHECK_TIMEOUT)
        
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            delay = data.get('delay', 999999)  # 使用大数值替代无穷大
            # 如果延迟小于5秒，认为是健康的
            is_healthy = delay < 5000
            logger.debug(f"代理组 {group_name} 健康检查: {'健康' if is_healthy else '不健康'}, 延迟: {delay}ms")
            return is_healthy, min(delay / 1000.0, 999.999)  # 转换为秒，限制最大值
        else:
            logger.warning(f"代理组 {group_name} 健康检查失败: HTTP {response.status_code}")
            return False, 999.999  # 使用大数值替代无穷大
            
    except Exception as e:
        logger.error(f"代理组 {group_name} 健康检查异常: {e}")
        return False, 999.999  # 使用大数值替代无穷大

def update_proxy_group_health(group_name: str, is_healthy: bool, response_time: float):
    """
    更新代理组健康状态到Redis。
    
    Args:
        group_name: 代理组名称
        is_healthy: 是否健康
        response_time: 响应时间
    """
    try:
        current_time = time.time()
        
        # 更新健康状态
        REDIS_CLIENT.hset(PROXY_GROUP_HEALTH_KEY, group_name, 
                         f"{is_healthy}:{response_time}:{current_time}")
        
        # 更新失败计数
        if not is_healthy:
            failure_count = REDIS_CLIENT.hincrby(PROXY_GROUP_FAILURE_COUNT_KEY, group_name, 1)
            logger.warning(f"代理组 {group_name} 失败计数: {failure_count}")
            
            # 如果失败次数超过阈值，加入黑名单
            if failure_count >= MAX_FAILURE_COUNT:
                blacklist_until = current_time + BLACKLIST_DURATION
                REDIS_CLIENT.hset(PROXY_GROUP_BLACKLIST_KEY, group_name, blacklist_until)
                logger.error(f"代理组 {group_name} 已加入黑名单，持续时间: {BLACKLIST_DURATION}秒")
        else:
            # 健康时重置失败计数
            REDIS_CLIENT.hdel(PROXY_GROUP_FAILURE_COUNT_KEY, group_name)
            # 从黑名单中移除
            REDIS_CLIENT.hdel(PROXY_GROUP_BLACKLIST_KEY, group_name)
            
        # 更新最后检查时间
        REDIS_CLIENT.hset(PROXY_GROUP_LAST_CHECK_KEY, group_name, current_time)
        
    except Exception as e:
        logger.error(f"更新代理组 {group_name} 健康状态失败: {e}")

def get_healthy_proxy_groups() -> List[str]:
    """
    获取健康的代理组列表，排除黑名单中的组。
    
    Returns:
        健康的代理组名称列表
    """
    try:
        # 获取所有代理组
        all_groups = REDIS_CLIENT.lrange('proxy_groups_list', 0, -1)
        
        # 获取黑名单
        blacklist = REDIS_CLIENT.hgetall(PROXY_GROUP_BLACKLIST_KEY)
        current_time = time.time()
        
        # 清理过期的黑名单项
        expired_groups = []
        for group_name, blacklist_until_str in blacklist.items():
            try:
                blacklist_until = float(blacklist_until_str)
                if current_time > blacklist_until:
                    expired_groups.append(group_name)
            except (ValueError, TypeError):
                expired_groups.append(group_name)  # 无效数据也清理
        
        for group_name in expired_groups:
            REDIS_CLIENT.hdel(PROXY_GROUP_BLACKLIST_KEY, group_name)
            logger.info(f"代理组 {group_name} 从黑名单中移除（已过期）")
        
        # 获取更新后的黑名单
        current_blacklist = set(REDIS_CLIENT.hkeys(PROXY_GROUP_BLACKLIST_KEY))
        
        # 返回不在黑名单中的组
        healthy_groups = [group for group in all_groups if group not in current_blacklist]
        
        logger.debug(f"健康代理组数量: {len(healthy_groups)}/{len(all_groups)}, "
                    f"黑名单: {list(current_blacklist)}")
        
        return healthy_groups
        
    except Exception as e:
        logger.error(f"获取健康代理组失败: {e}")
        # 降级：返回所有组
        return REDIS_CLIENT.lrange('proxy_groups_list', 0, -1)

def health_check_worker():
    """
    后台健康检查工作线程。
    定期检查所有代理组的健康状态。
    """
    logger.info("代理组健康检查工作线程启动")
    
    while True:
        try:
            # 获取所有代理组
            proxy_groups = REDIS_CLIENT.lrange('proxy_groups_list', 0, -1)
            
            if proxy_groups:
                logger.debug(f"开始健康检查，共 {len(proxy_groups)} 个代理组")
                
                # 并行检查所有代理组
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    future_to_group = {
                        executor.submit(test_proxy_group_health, group): group 
                        for group in proxy_groups
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_group):
                        group_name = future_to_group[future]
                        try:
                            is_healthy, response_time = future.result()
                            update_proxy_group_health(group_name, is_healthy, response_time)
                        except Exception as e:
                            logger.error(f"检查代理组 {group_name} 时发生异常: {e}")
                            update_proxy_group_health(group_name, False, 999.999)
                
                logger.debug("健康检查轮次完成")
            
            # 等待下次检查
            time.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"健康检查工作线程异常: {e}")
            time.sleep(30)  # 异常时短暂等待后重试

def start_health_checker():
    """
    启动健康检查后台线程。
    """
    health_thread = threading.Thread(target=health_check_worker, daemon=True)
    health_thread.start()
    logger.info("代理组健康检查服务已启动")

def reassign_unhealthy_containers():
    """
    重新分配使用不健康代理组的容器。
    """
    try:
        # 获取所有容器代理规则映射
        container_rules = REDIS_CLIENT.hgetall(CONTAINER_PROXY_RULES_KEY)
        
        # 获取黑名单代理组
        blacklisted_groups = set(REDIS_CLIENT.hkeys(PROXY_GROUP_BLACKLIST_KEY))
        
        if not blacklisted_groups:
            return  # 没有黑名单组，无需重新分配
        
        reassigned_count = 0
        
        for container_ip, rule in container_rules.items():
            try:
                # 解析规则获取代理组名称
                rule_parts = rule.split(',')
                if len(rule_parts) >= 3:
                    assigned_group = rule_parts[2].strip()
                    
                    # 如果容器使用的代理组在黑名单中，重新分配
                    if assigned_group in blacklisted_groups:
                        logger.info(f"重新分配容器 {container_ip} (当前使用黑名单组: {assigned_group})")
                        
                        # 先释放当前规则
                        release_proxy_from_container(container_ip)
                        
                        # 重新分配新的代理组
                        new_group = assign_proxy_to_container(container_ip)
                        
                        logger.info(f"容器 {container_ip} 已重新分配到代理组: {new_group}")
                        reassigned_count += 1
                        
            except Exception as e:
                logger.error(f"重新分配容器 {container_ip} 时发生错误: {e}")
        
        if reassigned_count > 0:
            logger.info(f"共重新分配了 {reassigned_count} 个容器的代理")
            
    except Exception as e:
        logger.error(f"重新分配不健康容器时发生错误: {e}")

def container_reassign_worker():
    """
    容器重新分配工作线程。
    定期检查并重新分配使用不健康代理组的容器。
    """
    logger.info("容器重新分配工作线程启动")
    
    while True:
        try:
            reassign_unhealthy_containers()
            time.sleep(REASSIGN_CHECK_INTERVAL)
        except Exception as e:
            logger.error(f"容器重新分配工作线程异常: {e}")
            time.sleep(60)  # 异常时等待1分钟

def start_container_reassigner():
    """
    启动容器重新分配后台线程。
    """
    reassign_thread = threading.Thread(target=container_reassign_worker, daemon=True)
    reassign_thread.start()
    logger.info("容器重新分配服务已启动")

def assign_proxy_to_container(container_ip: str) -> str:
    """
    为指定的容器IP分配一个代理组，并动态更新到Clash配置中。

    优化后的分配策略：
    1. 优先分配健康的代理组（不在黑名单中）
    2. 如果所有组都不健康，选择失败次数最少的组
    3. 使用轮询算法在健康组中分配
    4. 动态更新Clash配置并重启服务

    Args:
        container_ip: 容器在Docker网络中的IP地址。

    Returns:
        分配给该容器的代理组名称。
    """
    # 1. 获取健康的代理组进行轮询分配
    healthy_groups = get_healthy_proxy_groups()
    
    if healthy_groups:
        # 使用健康组进行轮询分配
        current_index = REDIS_CLIENT.incr('proxy_group_rr_index')
        assigned_group = healthy_groups[(current_index - 1) % len(healthy_groups)]
        logger.info(f"为容器 {container_ip} 分配健康代理组: {assigned_group}")
    else:
        # 如果没有健康组，选择失败次数最少的组作为兜底
        all_groups = REDIS_CLIENT.lrange('proxy_groups_list', 0, -1)
        if not all_groups:
            # 如果Redis中没有，尝试从本地配置文件获取
            try:
                clash_config_path = CONFIG_BASE_PATH / "config.yml"
                if clash_config_path.exists():
                    with open(clash_config_path, 'r', encoding='utf-8') as f:
                        current_config = yaml.safe_load(f)
                    groups = current_config.get('proxy-groups', [])
                    all_groups = [g['name'] for g in groups if g['type'] == 'url-test']
                    if all_groups:
                        REDIS_CLIENT.delete('proxy_groups_list')
                        REDIS_CLIENT.rpush('proxy_groups_list', *all_groups)
                        logger.info(f"从配置文件加载了 {len(all_groups)} 个 url-test 代理组")
                else:
                    raise FileNotFoundError("Clash配置文件不存在")
            except Exception as e:
                raise Exception(f"无法获取代理组列表: {e}")
        
        if not all_groups:
            raise Exception("Clash配置中没有可用的 'url-test' 类型代理组。")
        
        # 选择失败次数最少的组
        failure_counts = REDIS_CLIENT.hgetall(PROXY_GROUP_FAILURE_COUNT_KEY)
        min_failures = 999999  # 使用大数值替代无穷大
        best_group = all_groups[0]  # 默认值
        
        for group in all_groups:
            failures = int(failure_counts.get(group, 0))
            if failures < min_failures:
                min_failures = failures
                best_group = group
        
        assigned_group = best_group
        logger.warning(f"所有代理组都不健康，为容器 {container_ip} 分配失败次数最少的组: {assigned_group} (失败次数: {min_failures})")

    # 2. 直接读取本地Clash配置文件
    clash_config_path = CONFIG_BASE_PATH / "config.yml"
    if not clash_config_path.exists():
        raise FileNotFoundError(f"Clash配置文件不存在: {clash_config_path}")
        
    with open(clash_config_path, 'r', encoding='utf-8') as f:
        current_config = yaml.safe_load(f)

    # 3. 创建并添加新规则
    new_rule = f"SRC-IP-CIDR,{container_ip}/32,{assigned_group}"
    rules = current_config.get('rules', [])
    # 插入到列表顶部，使其优先级最高
    rules.insert(0, new_rule)
    current_config['rules'] = rules

    # 4. 更新配置到本地文件
    updated_payload = yaml.dump(current_config, allow_unicode=True, indent=2, sort_keys=False, default_flow_style=False)
    
    try:
        with open(clash_config_path, 'w', encoding='utf-8') as f:
            f.write(updated_payload)
        
        # 重启Clash容器
        import docker
        docker_client = docker.from_env()
        clash_container = docker_client.containers.get('clash')
        clash_container.restart()
        logger.info(f"为容器 {container_ip} 分配代理组 {assigned_group}，规则已添加并重启Clash")
    except Exception as e:
        logger.error(f"Failed to update Clash config in assign_proxy_to_container: {e}")
        raise
    
    # 5. 记录映射关系
    REDIS_CLIENT.hset(CONTAINER_PROXY_RULES_KEY, container_ip, new_rule)

    return assigned_group

def release_proxy_from_container(container_ip: str):
    """
    当容器被销毁时，从Clash配置中移除其对应的代理规则。
    
    增强的清理逻辑：
    1. 更强的错误处理
    2. 即使部分操作失败也继续执行
    3. 详细的日志记录
    """
    rule_to_remove = REDIS_CLIENT.hget(CONTAINER_PROXY_RULES_KEY, container_ip)
    if not rule_to_remove:
        logger.info(f"容器 {container_ip} 没有对应的代理规则，无需清理")
        return # 规则不存在，直接返回

    try:
        # 直接读取本地配置文件
        clash_config_path = CONFIG_BASE_PATH / "config.yml"
        if not clash_config_path.exists():
            logger.warning(f"Clash配置文件不存在: {clash_config_path}")
            # 即使文件不存在，也要清理Redis记录
            REDIS_CLIENT.hdel(CONTAINER_PROXY_RULES_KEY, container_ip)
            return
            
        with open(clash_config_path, 'r', encoding='utf-8') as f:
            current_config = yaml.safe_load(f)

        # 移除规则
        rules = current_config.get('rules', [])
        if rule_to_remove in rules:
            rules.remove(rule_to_remove)
            current_config['rules'] = rules

            # 写回本地文件
            updated_payload = yaml.dump(current_config, allow_unicode=True, indent=2, sort_keys=False, default_flow_style=False)
            
            try:
                with open(clash_config_path, 'w', encoding='utf-8') as f:
                    f.write(updated_payload)
                
                # 重启Clash容器
                import docker
                docker_client = docker.from_env()
                clash_container = docker_client.containers.get('clash')
                clash_container.restart()
                logger.info(f"成功移除容器 {container_ip} 的代理规则: {rule_to_remove}")
            except Exception as e:
                logger.error(f"Failed to update Clash config in release_proxy_from_container: {e}")
                # 这里不抛出异常，因为清理操作应该继续
        else:
            logger.warning(f"规则 {rule_to_remove} 在配置文件中未找到")

        # 从Redis中删除记录
        REDIS_CLIENT.hdel(CONTAINER_PROXY_RULES_KEY, container_ip)
        logger.info(f"Successfully released proxy rule for {container_ip}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during proxy release for {container_ip}: {e}")
        # 即使出错，也尝试清理Redis记录
        REDIS_CLIENT.hdel(CONTAINER_PROXY_RULES_KEY, container_ip)


def merge_and_update_clash_config():
    """
    合并所有提供商的配置，只更新 proxies 和 proxy-groups 部分，保持其他配置不变。
    
    此函数专门用于：
    1. 从 providers 目录读取所有代理节点
    2. 自动生成代理组
    3. 只更新现有配置文件的 proxies 和 proxy-groups 字段
    4. 保持 rules、端口等其他配置完全不变
    """
    clash_config_path = CONFIG_BASE_PATH / "config.yml"
    
    # 1. 读取现有的完整配置，如果不存在则创建基础配置
    if clash_config_path.exists():
        try:
            with open(clash_config_path, 'r', encoding='utf-8') as f:
                current_config = yaml.safe_load(f)
            if not isinstance(current_config, dict):
                current_config = {}
            logger.info("读取现有 Clash 配置文件成功")
        except Exception as e:
            logger.error(f"读取现有配置文件失败: {e}")
            current_config = {}
    else:
        # 如果配置文件不存在，创建基础配置
        current_config = {
            'port': 7890,
            'socks-port': 7891,
            'allow-lan': True,
            'mode': 'Rule',
            'log-level': 'info',
            'external-controller': '0.0.0.0:9090',
            'secret': '',
            'rules': ['GEOIP,CN,DIRECT', 'MATCH,DIRECT']
        }
        logger.info("创建新的基础 Clash 配置")

    # 2. 从 providers 目录合并所有代理节点
    all_proxies = []
    seen_proxy_names = set()  # 用于检测和移除重复名称的节点
    
    if os.path.exists(PROVIDERS_PATH):
        for provider_file in os.listdir(PROVIDERS_PATH):
            if provider_file.endswith((".yml", ".yaml")):
                file_path = PROVIDERS_PATH / provider_file
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        provider_data = yaml.safe_load(f)
                        
                        if isinstance(provider_data, dict) and 'proxies' in provider_data:
                            proxies_list = provider_data.get('proxies', [])
                            if isinstance(proxies_list, list):
                                for proxy in proxies_list:
                                    # 确保节点是字典并有名字
                                    if isinstance(proxy, dict) and 'name' in proxy:
                                        proxy_name = proxy['name']
                                        if proxy_name not in seen_proxy_names:
                                            all_proxies.append(proxy)
                                            seen_proxy_names.add(proxy_name)
                                        else:
                                            logger.warning(f"跳过重复的代理名称 '{proxy_name}' 来自 {provider_file}")
                            else:
                                logger.warning(f"跳过 {provider_file}: 'proxies' 键不包含列表")
                        else:
                            logger.warning(f"跳过 {provider_file}: 文件不是字典或不包含 'proxies' 键")

                except Exception as e:
                    logger.error(f"加载或解析 {provider_file} 时出错: {e}", exc_info=True)
    else:
        logger.warning(f"Providers 目录不存在: {PROVIDERS_PATH}")

    # 3. 只更新 proxies 和 proxy-groups 字段，保持其他配置不变
    current_config['proxies'] = all_proxies
    current_config['proxy-groups'] = generate_proxy_groups(all_proxies)
    
    # 4. 清理和修复 rules 字段
    existing_rules = current_config.get('rules', [])
    
    # 获取所有有效的代理组名称
    valid_proxy_groups = set()
    for group in current_config.get('proxy-groups', []):
        valid_proxy_groups.add(group['name'])
    valid_proxy_groups.add('DIRECT')  # DIRECT 是内置的有效目标
    
    # 过滤掉无效的规则（引用不存在的代理组）
    valid_rules = []
    invalid_rules_removed = 0
    
    for rule in existing_rules:
        if isinstance(rule, str):
            rule_parts = rule.split(',')
            if len(rule_parts) >= 3:
                rule_target = rule_parts[-1].strip()  # 规则的目标（最后一部分）
                if rule_target in valid_proxy_groups:
                    valid_rules.append(rule)
                else:
                    logger.warning(f"移除无效规则（引用不存在的代理组 '{rule_target}'）: {rule}")
                    invalid_rules_removed += 1
            elif len(rule_parts) == 2 and rule_parts[0].strip() in ['GEOIP', 'MATCH', 'FINAL']:
                # 处理 GEOIP,CN,DIRECT 或 MATCH,DIRECT 这样的规则
                rule_target = rule_parts[-1].strip()
                if rule_target in valid_proxy_groups:
                    valid_rules.append(rule)
                else:
                    logger.warning(f"移除无效规则（引用不存在的代理组 '{rule_target}'）: {rule}")
                    invalid_rules_removed += 1
            else:
                # 保留其他格式的规则
                valid_rules.append(rule)
        else:
            # 保留非字符串规则
            valid_rules.append(rule)
    
    if invalid_rules_removed > 0:
        logger.info(f"清理了 {invalid_rules_removed} 个无效规则")
    
    # 确保至少有基础规则
    if not valid_rules:
        valid_rules = ['GEOIP,CN,DIRECT', 'MATCH,DIRECT']
        logger.info("添加了基础代理规则到配置")
    else:
        # 确保有 GEOIP 和 MATCH 兜底规则
        has_geoip = any('GEOIP,CN,DIRECT' in str(rule) for rule in valid_rules)
        has_match = any(str(rule).startswith('MATCH,') for rule in valid_rules)
        
        if not has_geoip:
            valid_rules.append('GEOIP,CN,DIRECT')
            logger.info("添加 GEOIP,CN,DIRECT 兜底规则")
            
        if not has_match:
            valid_rules.append('MATCH,DIRECT')
            logger.info("添加 MATCH,DIRECT 兜底规则")
    
    current_config['rules'] = valid_rules

    # 5. 将所有 url-test 代理组存入Redis，供assign_proxy_to_container轮询使用
    url_test_groups = [g['name'] for g in current_config.get('proxy-groups', []) if g['type'] == 'url-test']
    if url_test_groups:
        REDIS_CLIENT.delete('proxy_groups_list')
        REDIS_CLIENT.rpush('proxy_groups_list', *url_test_groups)
        logger.info(f"更新了 {len(url_test_groups)} 个 url-test 代理组到 Redis 供轮询分配")

    # 6. 手动构建YAML配置字符串以确保正确的格式
    def format_yaml_value(value):
        """格式化YAML值，对包含特殊字符的字符串添加引号"""
        if isinstance(value, str):
            # 如果字符串包含特殊字符，需要用引号包围
            special_chars = ['[', ']', '{', '}', ':', '#', '&', '*', '!', '|', '>', "'", '"', '%', '@', '`']
            if any(char in value for char in special_chars) or value.startswith(' ') or value.endswith(' '):
                # 使用双引号并转义内部的双引号
                escaped_value = value.replace('"', '\\"')
                return f'"{escaped_value}"'
        return value

    def format_proxy(proxy):
        """格式化单个代理配置，支持复杂嵌套结构"""
        name = format_yaml_value(proxy.get('name', ''))
        lines = [f"  - name: {name}"]
        
        for key, value in proxy.items():
            if key != 'name':
                if isinstance(value, bool):
                    lines.append(f"    {key}: {str(value).lower()}")
                elif isinstance(value, dict):
                    # 处理嵌套字典，如 ws-opts
                    lines.append(f"    {key}:")
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, dict):
                            lines.append(f"      {sub_key}:")
                            for sub_sub_key, sub_sub_value in sub_value.items():
                                formatted_sub_sub_value = format_yaml_value(sub_sub_value)
                                lines.append(f"        {sub_sub_key}: {formatted_sub_sub_value}")
                        else:
                            formatted_sub_value = format_yaml_value(sub_value)
                            lines.append(f"      {sub_key}: {formatted_sub_value}")
                elif isinstance(value, list):
                    # 处理列表
                    lines.append(f"    {key}:")
                    for item in value:
                        if isinstance(item, dict):
                            lines.append(f"      -")
                            for item_key, item_value in item.items():
                                formatted_item_value = format_yaml_value(item_value)
                                lines.append(f"        {item_key}: {formatted_item_value}")
                        else:
                            formatted_item = format_yaml_value(item)
                            lines.append(f"      - {formatted_item}")
                else:
                    formatted_value = format_yaml_value(value)
                    lines.append(f"    {key}: {formatted_value}")
        return '\n'.join(lines)
    
    def format_proxy_group(group):
        """格式化代理组配置"""
        name = format_yaml_value(group.get('name', ''))
        lines = [f"  - name: {name}"]
        for key, value in group.items():
            if key != 'name':
                if key == 'proxies' and isinstance(value, list):
                    lines.append(f"    {key}:")
                    for proxy_name in value:
                        formatted_proxy_name = format_yaml_value(proxy_name)
                        lines.append(f"      - {formatted_proxy_name}")
                else:
                    formatted_value = format_yaml_value(value)
                    lines.append(f"    {key}: {formatted_value}")
        return '\n'.join(lines)
    
    # 7. 构建完整的YAML配置
    yaml_parts = []
    
    # 添加基础配置（除了 proxies, proxy-groups, rules）
    for key, value in current_config.items():
        if key not in ['proxies', 'proxy-groups', 'rules']:
            if isinstance(value, bool):
                yaml_parts.append(f"{key}: {str(value).lower()}")
            elif isinstance(value, str) and value == '':
                yaml_parts.append(f"{key}: ''")
            else:
                yaml_parts.append(f"{key}: {value}")
    
    # 添加proxies
    yaml_parts.append("proxies:")
    for proxy in current_config.get('proxies', []):
        yaml_parts.append(format_proxy(proxy))
    
    # 添加proxy-groups
    yaml_parts.append("proxy-groups:")
    for group in current_config.get('proxy-groups', []):
        yaml_parts.append(format_proxy_group(group))
    
    # 添加rules（保持原有规则不变）
    yaml_parts.append("rules:")
    for rule in current_config.get('rules', []):
        yaml_parts.append(f"  - {rule}")
    
    updated_payload = '\n'.join(yaml_parts)

    # 8. 写入配置文件并重启服务
    try:
        logger.info(f"正在更新 Clash 配置文件: {clash_config_path}")
        logger.debug(f"配置大小: {len(updated_payload)} 字符, 代理节点数: {len(all_proxies)}")
        
        with open(clash_config_path, 'w', encoding='utf-8') as f:
            f.write(updated_payload)
        
        logger.info("Clash 配置文件更新成功")
        
        # 重启Clash容器以重新加载配置
        import docker
        try:
            docker_client = docker.from_env()
            clash_container = docker_client.containers.get('clash')
            logger.info("正在重启 Clash 容器以重新加载配置...")
            clash_container.restart()
            logger.info("Clash 容器重启成功")
        except docker.errors.NotFound:
            logger.warning("未找到名为 'clash' 的容器，配置已更新但需要手动重启")
        except Exception as docker_error:
            logger.error(f"重启 Clash 容器失败: {docker_error}")
            # 即使重启失败，配置文件已经更新，所以不抛出异常
            
    except Exception as e:
        logger.error(f"更新 Clash 配置文件失败: {e}")
        logger.debug(f"失败的配置内容（前2000字符）:\n{updated_payload[:2000]}")
        if len(updated_payload) > 2000:
            logger.debug(f"配置继续... (总长度: {len(updated_payload)})")
        raise

def initialize_proxy_health_services():
    """
    初始化代理健康监控服务。
    应在应用启动时调用此函数。
    """
    try:
        logger.info("正在初始化代理健康监控服务...")
        
        # 启动健康检查服务
        start_health_checker()
        
        # 启动容器重新分配服务
        start_container_reassigner()
        
        logger.info("代理健康监控服务初始化完成")
        
    except Exception as e:
        logger.error(f"代理健康监控服务初始化失败: {e}")
        raise

def get_proxy_groups_health_status() -> Dict[str, Any]:
    """
    获取所有代理组的健康状态。
    
    Returns:
        包含代理组健康状态的字典
    """
    try:
        # 获取所有代理组
        all_groups = REDIS_CLIENT.lrange('proxy_groups_list', 0, -1)
        
        # 获取健康状态
        health_data = REDIS_CLIENT.hgetall(PROXY_GROUP_HEALTH_KEY)
        failure_counts = REDIS_CLIENT.hgetall(PROXY_GROUP_FAILURE_COUNT_KEY)
        blacklist = REDIS_CLIENT.hgetall(PROXY_GROUP_BLACKLIST_KEY)
        last_checks = REDIS_CLIENT.hgetall(PROXY_GROUP_LAST_CHECK_KEY)
        
        current_time = time.time()
        result = {
            'total_groups': len(all_groups),
            'healthy_groups': 0,
            'unhealthy_groups': 0,
            'blacklisted_groups': 0,
            'groups_status': [],
            'summary': {
                'last_update': current_time,
                'health_check_interval': HEALTH_CHECK_INTERVAL,
                'reassign_check_interval': REASSIGN_CHECK_INTERVAL
            }
        }
        
        for group_name in all_groups:
            group_status = {
                'name': group_name,
                'is_healthy': False,
                'response_time': 999.999,  # 使用大数值替代无穷大
                'failure_count': int(failure_counts.get(group_name, 0)),
                'is_blacklisted': group_name in blacklist,
                'last_check': None,
                'blacklist_until': None
            }
            
            # 解析健康状态
            health_info = health_data.get(group_name, '')
            if health_info:
                try:
                    parts = health_info.split(':')
                    if len(parts) >= 3:
                        group_status['is_healthy'] = parts[0] == 'True'
                        group_status['response_time'] = float(parts[1])
                        group_status['last_check'] = float(parts[2])
                except (ValueError, IndexError):
                    logger.warning(f"解析代理组 {group_name} 健康状态失败: {health_info}")
            
            # 解析黑名单信息
            if group_status['is_blacklisted']:
                try:
                    group_status['blacklist_until'] = float(blacklist[group_name])
                except (ValueError, KeyError):
                    group_status['blacklist_until'] = None
            
            result['groups_status'].append(group_status)
            
            # 统计
            if group_status['is_blacklisted']:
                result['blacklisted_groups'] += 1
            elif group_status['is_healthy']:
                result['healthy_groups'] += 1
            else:
                result['unhealthy_groups'] += 1
        
        return result
        
    except Exception as e:
        logger.error(f"获取代理组健康状态失败: {e}")
        return {
            'error': str(e),
            'total_groups': 0,
            'healthy_groups': 0,
            'unhealthy_groups': 0,
            'blacklisted_groups': 0,
            'groups_status': []
        }

def get_container_proxy_mappings() -> Dict[str, Any]:
    """
    获取所有容器的代理映射关系。
    
    Returns:
        包含容器代理映射的字典
    """
    try:
        container_rules = REDIS_CLIENT.hgetall(CONTAINER_PROXY_RULES_KEY)
        
        result = {
            'total_containers': len(container_rules),
            'mappings': [],
            'rules_by_group': {}
        }
        
        for container_ip, rule in container_rules.items():
            try:
                # 解析规则获取代理组名称
                rule_parts = rule.split(',')
                if len(rule_parts) >= 3:
                    assigned_group = rule_parts[2].strip()
                    
                    mapping = {
                        'container_ip': container_ip,
                        'assigned_group': assigned_group,
                        'rule': rule
                    }
                    result['mappings'].append(mapping)
                    
                    # 按组统计
                    if assigned_group not in result['rules_by_group']:
                        result['rules_by_group'][assigned_group] = []
                    result['rules_by_group'][assigned_group].append(container_ip)
                    
            except Exception as e:
                logger.warning(f"解析容器 {container_ip} 规则失败: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"获取容器代理映射失败: {e}")
        return {
            'error': str(e),
            'total_containers': 0,
            'mappings': []
        }

def force_reassign_container(container_ip: str) -> Dict[str, Any]:
    """
    强制重新分配指定容器的代理组。
    
    Args:
        container_ip: 容器IP地址
        
    Returns:
        操作结果
    """
    try:
        # 检查容器是否存在映射
        current_rule = REDIS_CLIENT.hget(CONTAINER_PROXY_RULES_KEY, container_ip)
        if not current_rule:
            return {
                'success': False,
                'message': f'容器 {container_ip} 没有代理规则',
                'container_ip': container_ip
            }
        
        # 获取当前分配的组
        rule_parts = current_rule.split(',')
        old_group = rule_parts[2].strip() if len(rule_parts) >= 3 else '未知'
        
        # 释放当前规则
        release_proxy_from_container(container_ip)
        
        # 重新分配
        new_group = assign_proxy_to_container(container_ip)
        
        logger.info(f"手动重新分配容器 {container_ip}: {old_group} -> {new_group}")
        
        return {
            'success': True,
            'message': f'容器 {container_ip} 已从 {old_group} 重新分配到 {new_group}',
            'container_ip': container_ip,
            'old_group': old_group,
            'new_group': new_group
        }
        
    except Exception as e:
        logger.error(f"强制重新分配容器 {container_ip} 失败: {e}")
        return {
            'success': False,
            'message': f'重新分配失败: {str(e)}',
            'container_ip': container_ip
        }

def clear_proxy_group_blacklist(group_name: Optional[str] = None) -> Dict[str, Any]:
    """
    清理代理组黑名单。
    
    Args:
        group_name: 要清理的特定组名，None 表示清理所有过期项
        
    Returns:
        操作结果
    """
    try:
        if group_name:
            # 清理特定组
            removed = REDIS_CLIENT.hdel(PROXY_GROUP_BLACKLIST_KEY, group_name)
            REDIS_CLIENT.hdel(PROXY_GROUP_FAILURE_COUNT_KEY, group_name)
            
            if removed:
                logger.info(f"手动清理代理组 {group_name} 的黑名单状态")
                return {
                    'success': True,
                    'message': f'代理组 {group_name} 已从黑名单中移除',
                    'cleared_groups': [group_name]
                }
            else:
                return {
                    'success': False,
                    'message': f'代理组 {group_name} 不在黑名单中',
                    'cleared_groups': []
                }
        else:
            # 清理所有过期项
            blacklist = REDIS_CLIENT.hgetall(PROXY_GROUP_BLACKLIST_KEY)
            current_time = time.time()
            expired_groups = []
            
            for group_name, blacklist_until_str in blacklist.items():
                try:
                    blacklist_until = float(blacklist_until_str)
                    if current_time > blacklist_until:
                        expired_groups.append(group_name)
                except (ValueError, TypeError):
                    expired_groups.append(group_name)  # 无效数据也清理
            
            for group_name in expired_groups:
                REDIS_CLIENT.hdel(PROXY_GROUP_BLACKLIST_KEY, group_name)
            
            logger.info(f"清理了 {len(expired_groups)} 个过期的黑名单代理组")
            
            return {
                'success': True,
                'message': f'清理了 {len(expired_groups)} 个过期的黑名单代理组',
                'cleared_groups': expired_groups
            }
            
    except Exception as e:
        logger.error(f"清理代理组黑名单失败: {e}")
        return {
            'success': False,
            'message': f'清理失败: {str(e)}',
            'cleared_groups': []
        }

def get_system_health_summary() -> Dict[str, Any]:
    """
    获取整个代理系统的健康状况摘要。
    
    Returns:
        系统健康状况摘要
    """
    try:
        proxy_health = get_proxy_groups_health_status()
        container_mappings = get_container_proxy_mappings()
        
        # 计算健康率
        total_groups = proxy_health.get('total_groups', 0)
        healthy_groups = proxy_health.get('healthy_groups', 0)
        health_rate = (healthy_groups / total_groups * 100) if total_groups > 0 else 0
        
        # 检查服务状态
        current_time = time.time()
        
        return {
            'overall_status': 'healthy' if health_rate >= 80 else 'degraded' if health_rate >= 50 else 'unhealthy',
            'health_rate': round(health_rate, 2),
            'proxy_groups': {
                'total': total_groups,
                'healthy': healthy_groups,
                'unhealthy': proxy_health.get('unhealthy_groups', 0),
                'blacklisted': proxy_health.get('blacklisted_groups', 0)
            },
            'containers': {
                'total': container_mappings.get('total_containers', 0),
                'active_mappings': len(container_mappings.get('mappings', []))
            },
            'services': {
                'health_checker': 'running',  # 简化状态，实际可以检查线程状态
                'container_reassigner': 'running'
            },
            'configuration': {
                'health_check_interval': HEALTH_CHECK_INTERVAL,
                'reassign_check_interval': REASSIGN_CHECK_INTERVAL,
                'max_failure_count': MAX_FAILURE_COUNT,
                'blacklist_duration': BLACKLIST_DURATION
            },
            'timestamp': current_time
        }
        
    except Exception as e:
        logger.error(f"获取系统健康摘要失败: {e}")
        return {
            'overall_status': 'error',
            'error': str(e),
            'timestamp': time.time()
        }

def check_clash_service_status() -> Dict[str, Any]:
    """
    检查Clash服务的整体状态。
    
    Returns:
        Clash服务状态信息
    """
    try:
        status = {
            'service_reachable': False,
            'api_response_time': 999.999,
            'clash_version': None,
            'total_proxies': 0,
            'proxy_groups_count': 0,
            'current_mode': None,
            'external_controller': None,
            'log_level': None,
            'errors': []
        }
        
        # 1. 检查基本连接
        try:
            start_time = time.time()
            response = requests.get('http://clash:9090/version', timeout=5)
            api_response_time = time.time() - start_time
            
            if response.status_code == 200:
                status['service_reachable'] = True
                status['api_response_time'] = api_response_time
                version_data = response.json()
                status['clash_version'] = version_data.get('version', 'unknown')
            else:
                status['errors'].append(f"Clash API 返回错误状态码: {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            status['errors'].append(f"无法连接到Clash服务: {e}")
        except requests.exceptions.Timeout:
            status['errors'].append("连接Clash服务超时")
        except Exception as e:
            status['errors'].append(f"检查Clash连接时发生异常: {e}")
        
        # 2. 获取配置信息
        if status['service_reachable']:
            try:
                config_response = requests.get('http://clash:9090/configs', timeout=5)
                if config_response.status_code == 200:
                    config_data = config_response.json()
                    status['current_mode'] = config_data.get('mode', 'unknown')
                    status['external_controller'] = config_data.get('external-controller', 'unknown')
                    status['log_level'] = config_data.get('log-level', 'unknown')
                else:
                    status['errors'].append(f"获取Clash配置失败: HTTP {config_response.status_code}")
            except Exception as e:
                status['errors'].append(f"获取Clash配置时发生异常: {e}")
        
        # 3. 获取代理信息
        if status['service_reachable']:
            try:
                proxies_response = requests.get('http://clash:9090/proxies', timeout=10)
                if proxies_response.status_code == 200:
                    proxies_data = proxies_response.json()
                    proxies = proxies_data.get('proxies', {})
                    
                    # 统计代理节点
                    proxy_count = 0
                    group_count = 0
                    
                    for name, proxy_info in proxies.items():
                        if proxy_info.get('type') == 'URLTest':
                            group_count += 1
                        elif proxy_info.get('type') not in ['Direct', 'Reject', 'Selector']:
                            proxy_count += 1
                    
                    status['total_proxies'] = proxy_count
                    status['proxy_groups_count'] = group_count
                else:
                    status['errors'].append(f"获取代理信息失败: HTTP {proxies_response.status_code}")
            except Exception as e:
                status['errors'].append(f"获取代理信息时发生异常: {e}")
        
        return status
        
    except Exception as e:
        logger.error(f"检查Clash服务状态时发生异常: {e}")
        return {
            'service_reachable': False,
            'api_response_time': 999.999,
            'clash_version': None,
            'total_proxies': 0,
            'proxy_groups_count': 0,
            'current_mode': None,
            'external_controller': None,
            'log_level': None,
            'errors': [f"状态检查异常: {e}"]
        }

def diagnose_proxy_issues() -> Dict[str, Any]:
    """
    诊断代理系统的常见问题。
    
    Returns:
        诊断结果和建议
    """
    try:
        diagnosis = {
            'timestamp': time.time(),
            'overall_health': 'unknown',
            'clash_status': {},
            'proxy_health': {},
            'issues_found': [],
            'recommendations': []
        }
        
        # 1. 检查Clash服务状态
        clash_status = check_clash_service_status()
        diagnosis['clash_status'] = clash_status
        
        if not clash_status['service_reachable']:
            diagnosis['issues_found'].append('Clash服务无法访问')
            diagnosis['recommendations'].extend([
                '检查Clash容器是否正在运行',
                '检查Docker网络连接',
                '验证Clash配置文件语法',
                '查看Clash容器日志'
            ])
            diagnosis['overall_health'] = 'critical'
        
        # 2. 检查代理组健康状态
        if clash_status['service_reachable']:
            proxy_health = get_proxy_groups_health_status()
            diagnosis['proxy_health'] = proxy_health
            
            if proxy_health.get('total_groups', 0) == 0:
                diagnosis['issues_found'].append('没有找到任何代理组')
                diagnosis['recommendations'].append('检查代理配置文件是否正确加载')
            else:
                unhealthy_ratio = proxy_health.get('unhealthy_groups', 0) / proxy_health.get('total_groups', 1)
                blacklisted_ratio = proxy_health.get('blacklisted_groups', 0) / proxy_health.get('total_groups', 1)
                
                if unhealthy_ratio > 0.5:
                    diagnosis['issues_found'].append(f'超过50%的代理组不健康 ({proxy_health.get("unhealthy_groups", 0)}/{proxy_health.get("total_groups", 0)})')
                    diagnosis['recommendations'].extend([
                        '检查代理节点的网络连接',
                        '验证代理服务器是否正常工作',
                        '考虑更换代理供应商',
                        '调整健康检查参数'
                    ])
                
                if blacklisted_ratio > 0.3:
                    diagnosis['issues_found'].append(f'超过30%的代理组被加入黑名单 ({proxy_health.get("blacklisted_groups", 0)}/{proxy_health.get("total_groups", 0)})')
                    diagnosis['recommendations'].extend([
                        '清理过期的黑名单',
                        '检查代理节点质量',
                        '考虑调整黑名单策略'
                    ])
        
        # 3. 检查容器映射
        container_mappings = get_container_proxy_mappings()
        if container_mappings.get('total_containers', 0) == 0:
            diagnosis['issues_found'].append('没有找到任何容器代理映射')
            diagnosis['recommendations'].append('检查是否有容器正在使用代理')
        
        # 4. 确定整体健康状态
        if diagnosis['overall_health'] == 'unknown':
            if len(diagnosis['issues_found']) == 0:
                diagnosis['overall_health'] = 'healthy'
            elif len(diagnosis['issues_found']) <= 2:
                diagnosis['overall_health'] = 'degraded'
            else:
                diagnosis['overall_health'] = 'unhealthy'
        
        return diagnosis
        
    except Exception as e:
        logger.error(f"诊断代理问题时发生异常: {e}")
        return {
            'timestamp': time.time(),
            'overall_health': 'error',
            'clash_status': {},
            'proxy_health': {},
            'issues_found': [f'诊断过程异常: {e}'],
            'recommendations': ['请检查系统日志并联系管理员']
        }

def recover_container_mappings_from_config():
    """
    从 Clash 配置文件中恢复容器代理映射关系到 Redis。
    
    当 Redis 重启后，容器映射数据会丢失，但 Clash 配置文件中的规则仍然存在。
    此函数会：
    1. 读取当前的 Clash 配置文件
    2. 解析其中的 SRC-IP-CIDR 规则
    3. 将容器IP和代理组的映射关系恢复到 Redis 中
    
    应在服务启动时调用此函数。
    """
    try:
        # 读取 Clash 配置文件
        clash_config_path = CONFIG_BASE_PATH / "config.yml"
        if not clash_config_path.exists():
            logger.warning(f"Clash 配置文件不存在: {clash_config_path}")
            return
            
        with open(clash_config_path, 'r', encoding='utf-8') as f:
            current_config = yaml.safe_load(f)
        
        rules = current_config.get('rules', [])
        recovered_count = 0
        
        # 解析所有的 SRC-IP-CIDR 规则
        for rule in rules:
            if isinstance(rule, str) and rule.startswith('SRC-IP-CIDR,'):
                try:
                    # 解析规则格式: SRC-IP-CIDR,172.22.0.6/32,[Auto] 香港-07
                    rule_parts = rule.split(',', 2)  # 限制分割为3部分，处理代理组名中可能包含逗号的情况
                    if len(rule_parts) == 3:
                        ip_cidr = rule_parts[1].strip()
                        proxy_group = rule_parts[2].strip()
                        
                        # 从 CIDR 中提取容器 IP（去掉 /32 后缀）
                        if ip_cidr.endswith('/32'):
                            container_ip = ip_cidr[:-3]  # 移除 '/32'
                            
                            # 恢复映射关系到 Redis
                            REDIS_CLIENT.hset(CONTAINER_PROXY_RULES_KEY, container_ip, rule)
                            recovered_count += 1
                            logger.info(f"恢复容器映射: {container_ip} -> {proxy_group}")
                        else:
                            logger.warning(f"跳过非容器规则 (不是/32 CIDR): {rule}")
                    else:
                        logger.warning(f"跳过格式不正确的规则: {rule}")
                except Exception as e:
                    logger.error(f"解析规则时出错 '{rule}': {e}")
        
        if recovered_count > 0:
            logger.info(f"成功从配置文件恢复 {recovered_count} 个容器代理映射")
        else:
            logger.info("配置文件中没有找到容器代理规则，无需恢复")
            
    except Exception as e:
        logger.error(f"从配置文件恢复容器映射时出错: {e}")

def initialize_proxy_manager():
    """
    初始化代理管理器的完整启动流程。
    
    包含：
    1. 恢复容器映射数据
    2. 初始化健康监控服务
    3. 确保 Redis 中有代理组数据
    
    应在应用启动时调用此函数。
    """
    try:
        logger.info("开始初始化代理管理器...")
        
        # 1. 恢复容器映射数据
        logger.info("步骤 1: 恢复容器映射数据...")
        recover_container_mappings_from_config()
        
        # 2. 确保 Redis 中有代理组数据
        logger.info("步骤 2: 检查并更新代理组数据...")
        try:
            # 检查 Redis 中是否有代理组数据
            existing_groups = REDIS_CLIENT.lrange('proxy_groups_list', 0, -1)
            if not existing_groups:
                logger.info("Redis 中没有代理组数据，正在从配置文件加载...")
                merge_and_update_clash_config()
            else:
                logger.info(f"Redis 中已有 {len(existing_groups)} 个代理组")
        except Exception as e:
            logger.warning(f"更新代理组数据时出错: {e}")
        
        # 3. 初始化健康监控服务
        logger.info("步骤 3: 初始化健康监控服务...")
        initialize_proxy_health_services()
        
        logger.info("代理管理器初始化完成")
        
    except Exception as e:
        logger.error(f"代理管理器初始化失败: {e}")
        raise
