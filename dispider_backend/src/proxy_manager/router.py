from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
import shutil
from . import service as proxy_manager_service
from .service import PROVIDERS_PATH
from ..auth.dependencies import get_super_admin
from ..auth.models import User
import logging
from typing import Optional

# 获取一个logger实例
logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["proxies"],
    dependencies=[Depends(get_super_admin)]
)

@router.post("/refresh", summary="刷新并热加载Clash配置")
async def refresh_clash_configuration():
    """
    手动触发Clash配置的刷新流程。

    该接口会执行以下操作:
    1. 从 `clash/providers` 目录读取所有供应商的配置文件。
    2. 合并所有代理节点。
    3. 自动生成优化的代理组 (`proxy-groups`)。
    4. 将最终生成的完整配置通过API热加载到正在运行的Clash服务中。
    """
    try:
        proxy_manager_service.merge_and_update_clash_config()
        return {"message": "Clash configuration refresh triggered successfully."}
    except Exception as e:
        # 记录详细的异常信息
        logger.error(f"Failed to refresh Clash configuration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to refresh Clash configuration: {str(e)}")

@router.post("/providers", summary="上传供应商配置文件")
async def upload_provider_configuration(file: UploadFile = File(...)):
    """
    上传一个新的供应商配置文件 (例如 a.yml)。

    文件将被保存到 `clash/providers/` 目录下。
    上传后，您可以选择性地调用 `/refresh` 接口来使配置生效。
    """
    # 确保 providers 目录存在
    PROVIDERS_PATH.mkdir(parents=True, exist_ok=True)
    
    # 定义文件的保存路径
    file_path = PROVIDERS_PATH / file.filename
    
    # 检查文件名是否安全，防止路径遍历攻击 (简单的实现)
    if ".." in file.filename or "/" in file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    try:
        # 将上传的文件内容写入到目标路径
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
    finally:
        file.file.close()

    return {
        "message": f"Successfully uploaded {file.filename} to providers directory.",
        "filepath": str(file_path)
    }

@router.get("/health/groups", summary="获取代理组健康状态")
async def get_proxy_groups_health():
    """
    获取所有代理组的详细健康状态。
    
    返回信息包括：
    - 每个代理组的健康状态
    - 响应时间
    - 失败次数
    - 是否在黑名单中
    - 最后检查时间
    """
    try:
        health_status = proxy_manager_service.get_proxy_groups_health_status()
        return health_status
    except Exception as e:
        logger.error(f"Failed to get proxy groups health status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get health status: {str(e)}")

@router.get("/health/containers", summary="获取容器代理映射")
async def get_container_proxy_mappings():
    """
    获取所有容器的代理映射关系。
    
    返回信息包括：
    - 容器IP和对应的代理组
    - 按代理组分组的容器列表
    - 总的容器数量
    """
    try:
        mappings = proxy_manager_service.get_container_proxy_mappings()
        return mappings
    except Exception as e:
        logger.error(f"Failed to get container proxy mappings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get container mappings: {str(e)}")

@router.get("/health/summary", summary="获取系统健康摘要")
async def get_system_health_summary():
    """
    获取整个代理系统的健康状况摘要。
    
    返回信息包括：
    - 整体健康状态
    - 健康率
    - 代理组统计
    - 容器统计
    - 服务状态
    - 配置参数
    """
    try:
        summary = proxy_manager_service.get_system_health_summary()
        return summary
    except Exception as e:
        logger.error(f"Failed to get system health summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get health summary: {str(e)}")

@router.post("/containers/{container_ip}/reassign", summary="手动重新分配容器代理")
async def force_reassign_container_proxy(container_ip: str):
    """
    强制重新分配指定容器的代理组。
    
    这个接口会：
    1. 释放容器当前的代理规则
    2. 重新分配一个健康的代理组
    3. 更新Clash配置并重启服务
    
    适用场景：
    - 容器分配到的代理组不稳定
    - 需要手动均衡负载
    - 故障恢复
    """
    try:
        result = proxy_manager_service.force_reassign_container(container_ip)
        if result.get('success', False):
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('message', 'Reassignment failed'))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to force reassign container {container_ip}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reassign container: {str(e)}")

@router.delete("/health/blacklist", summary="清理代理组黑名单")
async def clear_proxy_blacklist(group_name: Optional[str] = None):
    """
    清理代理组黑名单。
    
    参数：
    - group_name: 要清理的特定组名，不提供则清理所有过期项
    
    这个接口会：
    1. 从黑名单中移除指定的或过期的代理组
    2. 重置失败计数
    3. 使这些组重新可用于分配
    """
    try:
        result = proxy_manager_service.clear_proxy_group_blacklist(group_name)
        if result.get('success', False):
            return result
        else:
            raise HTTPException(status_code=400, detail=result.get('message', 'Blacklist clearing failed'))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear proxy blacklist: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to clear blacklist: {str(e)}")

@router.post("/health/initialize", summary="初始化健康监控服务")
async def initialize_health_services():
    """
    初始化代理健康监控服务。
    
    这个接口会启动：
    1. 代理组健康检查后台服务
    2. 容器自动重新分配后台服务
    
    注意：通常在应用启动时自动调用，这里提供手动初始化的选项。
    """
    try:
        proxy_manager_service.initialize_proxy_health_services()
        return {"message": "Proxy health monitoring services initialized successfully."}
    except Exception as e:
        logger.error(f"Failed to initialize health services: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initialize health services: {str(e)}")

@router.post("/health/reassign-all", summary="重新分配所有不健康容器")
async def reassign_unhealthy_containers():
    """
    手动触发重新分配所有使用不健康代理组的容器。
    
    这个接口会：
    1. 检查所有容器的代理分配
    2. 识别使用黑名单代理组的容器
    3. 重新分配这些容器到健康的代理组
    
    适用场景：
    - 大量代理组故障后的批量修复
    - 定期维护和优化
    """
    try:
        proxy_manager_service.reassign_unhealthy_containers()
        return {"message": "Unhealthy container reassignment process completed."}
    except Exception as e:
        logger.error(f"Failed to reassign unhealthy containers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reassign containers: {str(e)}")

@router.get("/health/clash-status", summary="检查Clash服务状态")
async def get_clash_service_status():
    """
    检查Clash服务的整体状态和基本信息。
    
    返回信息包括：
    - Clash服务可达性
    - API响应时间
    - Clash版本信息
    - 代理节点统计
    - 当前配置模式
    - 发现的错误列表
    """
    try:
        status = proxy_manager_service.check_clash_service_status()
        return status
    except Exception as e:
        logger.error(f"Failed to check Clash service status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check Clash status: {str(e)}")

@router.get("/health/diagnose", summary="系统问题诊断")
async def diagnose_proxy_system():
    """
    对整个代理系统进行全面诊断。
    
    返回信息包括：
    - 发现的问题列表
    - 针对性的修复建议
    - Clash服务状态
    - 代理组健康状况
    - 整体健康评级
    
    适用场景：
    - 系统故障排查
    - 定期健康检查
    - 性能优化分析
    """
    try:
        diagnosis = proxy_manager_service.diagnose_proxy_issues()
        return diagnosis
    except Exception as e:
        logger.error(f"Failed to diagnose proxy system: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to run diagnosis: {str(e)}")

@router.post("/recovery/container-mappings", summary="恢复容器代理映射数据")
async def recover_container_mappings():
    """
    从 Clash 配置文件中恢复丢失的容器代理映射数据到 Redis。
    
    适用场景：
    - Redis 重启后映射数据丢失
    - 系统重启后需要恢复映射关系
    - 数据不一致时的修复操作
    
    此接口会：
    1. 读取 Clash 配置文件中的 SRC-IP-CIDR 规则
    2. 解析出容器IP和代理组的映射关系
    3. 将映射关系恢复到 Redis 中
    """
    try:
        proxy_manager_service.recover_container_mappings_from_config()
        return {"message": "Container proxy mappings recovery completed successfully."}
    except Exception as e:
        logger.error(f"Failed to recover container mappings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to recover container mappings: {str(e)}")

@router.post("/initialize", summary="完整初始化代理管理器")
async def initialize_proxy_manager():
    """
    执行代理管理器的完整初始化流程。
    
    此接口会依次执行：
    1. 恢复容器映射数据（从配置文件到Redis）
    2. 检查并更新代理组数据
    3. 初始化健康监控服务
    
    适用场景：
    - 系统启动后的首次初始化
    - 服务重启后的数据恢复
    - 系统故障后的完整重建
    
    注意：这是一个重量级操作，包含多个步骤，执行时间可能较长。
    """
    try:
        proxy_manager_service.initialize_proxy_manager()
        return {"message": "Proxy manager initialization completed successfully."}
    except Exception as e:
        logger.error(f"Failed to initialize proxy manager: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initialize proxy manager: {str(e)}")
