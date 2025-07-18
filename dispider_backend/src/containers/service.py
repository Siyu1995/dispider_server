# 容器服务的业务逻辑将在这里实现 

import docker
import os
import logging
from uuid import uuid4
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
import redis # 导入 redis
import json # 导入 json 用于序列化
import httpx
import logging

from src.containers.models import Container
from src.containers.schemas import BatchStartRequest
from src.redis_client import get_redis_client # 导入 Redis 客户端
from src.projects.models import Project # 导入 Project 模型
from src.auth.models import User # 导入 User 模型
from src.projects.members.models import ProjectMember, ProjectRole # 导入项目成员及角色模型

from src.config import settings

# 配置日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VNC_PORT_START = 30000  # VNC 端口的起始分配号
REDIS_ALERT_PREFIX = "container_alert:" # 定义 Redis 中警报键的前缀

async def _send_push_notification(push_key: str, title: str, content: str):
    """
    发送推送通知到 PushMe 服务。
    """
    if not push_key:
        logger.warning(f"尝试发送推送通知，但目标用户没有配置 pushme_key。标题: {title}")
        return

    logger.info(f"正在向 PushMe (Key: {push_key[:4]}...) 发送推送通知...")
    logger.info(f"  - 标题: {title}")
    logger.info(f"  - 内容: {content}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://push.i-i.me",
                data={
                    "push_key": push_key,
                    "title": title,
                    "content": content
                }
            )
            response.raise_for_status()  # 如果状态码是 4xx 或 5xx，则引发异常
            
            if response.text == "success":
                logger.info("推送通知已成功发送。")
            else:
                logger.error(f"发送推送通知失败，PushMe 返回: {response.text}")

        except httpx.HTTPStatusError as e:
            logger.error(f"发送推送通知请求失败，状态码: {e.response.status_code}，响应: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"发送推送通知时发生网络请求错误: {e}")


class ContainerService:
    """
    处理与 Docker 容器相关的业务逻辑。
    """

    def _get_docker_client(self):
        """
        获取并验证 Docker 客户端。
        """
        try:
            client = docker.from_env()
            client.ping()
            return client
        except docker.errors.DockerException as e:
            logger.error(f"无法连接到 Docker 守护进程: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Docker 服务不可用，请确保 Docker 正在运行。"
            )

    def _get_next_available_port(self, db: Session) -> int:
        """
        计算下一个可用的宿主机端口号。
        通过查询数据库中最新的记录并解析其端口号来确保唯一性。
        """
        # 按 ID 降序查询最新的容器记录
        latest_container = db.query(Container).order_by(Container.id.desc()).first()
        
        # 如果数据库中还没有任何容器，则从起始端口开始
        if not latest_container or not latest_container.host_port:
            logger.info(f"数据库中无容器记录，将从起始端口 {VNC_PORT_START} 开始分配。")
            return VNC_PORT_START
        
        try:
            # 从 "http://hostname:port" 格式的字符串中解析出端口号
            latest_port_str = latest_container.host_port.split(':')[-1]
            latest_port = int(latest_port_str)
            logger.info(f"找到当前最大端口号: {latest_port}，下一个可用端口将是 {latest_port + 1}。")
            return latest_port + 1
        except (ValueError, IndexError):
            # 如果解析失败（例如格式不正确），则记录警告并返回起始端口
            logger.warning(
                f"无法从 host_port ('{latest_container.host_port}') 中解析出有效的端口号。"
                f"将回退到起始端口 {VNC_PORT_START}。"
            )
            return VNC_PORT_START

    def start_container_batch(self, db: Session, project_id: int, request: BatchStartRequest) -> List[Container]:
        """
        为指定项目启动一批爬虫容器，并将信息存入数据库。

        Args:
            db: 数据库会话。
            project_id: 项目的 ID。
            request: 包含启动数量和镜像信息的请求对象。

        Returns:
            一个包含所有成功创建的 Container ORM 对象的列表。
        """
        client = self._get_docker_client()
        
        try:
            client.images.get(request.image)
        except docker.errors.ImageNotFound:
            logger.error(f"爬虫镜像 '{request.image}' 不存在。")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"必需的爬虫镜像 '{request.image}' 未找到，请先构建或拉取镜像。"
            )

        api_base_url = settings.API_BASE_URL
        
        # 为本次批量操作获取起始端口号
        next_port = self._get_next_available_port(db)

        created_containers_orm = []
        for i in range(request.container_count):
            worker_id = str(uuid4())
            container_name = f"dispider-worker-{project_id}-{worker_id[:8]}"
            
            # 计算当前容器要使用的端口
            current_host_port = next_port + i

            environment = {
                'PROJECT_ID': str(project_id),
                'API_BASE_URL': api_base_url,
                'WORKER_ID': worker_id
            }

            # 如果提供了代理配置，则将其合并到环境变量中
            if request.proxy_config:
                environment.update(request.proxy_config)

            # 准备卷挂载参数
            volumes_mapping = {}

            # 1. 自动挂载项目的工作目录
            # DOCKER_SPACE_OUTER 是宿主机上为各项目准备的根目录
            # 此时我们假定该目录已在项目创建时被正确生成，这里不再重复创建。
            host_project_path = os.path.join(settings.DOCKER_SPACE_OUTER, str(project_id))
            container_project_path = "/home/user/task"
            
            volumes_mapping[host_project_path] = {'bind': container_project_path, 'mode': 'rw'}
            logger.info(f"为容器 {container_name} 自动挂载项目目录: {host_project_path} -> {container_project_path}")

            # 2. 如果用户在请求中提供了额外的卷，则合并它们
            if request.volumes:
                # 将 {"host_path": "container_path"} 转换为 docker-py 需要的格式
                # 并合并到总的挂载配置中
                logger.info(f"合并用户为容器 {container_name} 提供的自定义挂载卷: {request.volumes}")
                user_volumes = {
                    host_path: {'bind': container_path, 'mode': 'rw'}
                    for host_path, container_path in request.volumes.items()
                }
                volumes_mapping.update(user_volumes)
            
            # 1. 在数据库中创建一个记录，状态为 'creating'
            db_container = Container(
                container_name=container_name,
                image=request.image,
                status='creating',
                project_id=project_id,
                worker_id=worker_id,
                container_id='pending', # 临时值
                host_port=settings.CONTAINER_HOST + ":" + str(current_host_port), # 记录分配的url
            )
            db.add(db_container)
            
            try:
                db.commit()
                db.refresh(db_container)

                # 准备端口映射参数
                ports_mapping = {'8080/tcp': current_host_port}

                # 2. 启动 Docker 容器
                docker_container = client.containers.run(
                    image=request.image,
                    detach=True,
                    environment=environment,
                    name=container_name,
                    ports=ports_mapping,
                    volumes=volumes_mapping,
                )

                # 3. 更新数据库记录，填入真实的 container_id 和状态
                db_container.container_id = docker_container.id
                db_container.status = 'running'
                db.commit()
                db.refresh(db_container)

                created_containers_orm.append(db_container)
                logger.info(f"容器 {container_name} (ID: {docker_container.short_id}) 已成功启动并记录到数据库。")

            except (docker.errors.APIError, SQLAlchemyError) as e:
                logger.error(f"启动容器 {container_name} 或更新数据库时出错: {e}", exc_info=True)
                db.rollback()
                # 尝试将失败的容器记录状态更新为 error
                db_container.status = 'error'
                db.commit()
                # 此处可以决定是继续尝试下一个还是直接失败
                # 我们选择直接抛出异常，中断本次批量操作
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"启动容器 {container_name} 时发生错误: {e}"
                )
        
        logger.info(f"成功为项目 {project_id} 启动并记录了 {len(created_containers_orm)} 个容器。")
        return created_containers_orm

    def list_containers(self, db: Session, current_user: User) -> List[Container]:
        """
        列出对当前用户可见的容器列表。
        - 如果是超级管理员，则返回所有项目的所有容器。
        - 如果是普通用户，则只返回其参与的项目下的容器。

        Args:
            db: 数据库会话。
            current_user: 当前登录的用户。

        Returns:
            一个对用户可见的 Container 对象的列表。
        """
        if current_user.is_super_admin:
            logger.info(f"超级管理员 {current_user.username} 请求获取所有容器列表。")
            return db.query(Container).order_by(Container.id.desc()).all()
        else:
            logger.info(f"用户 {current_user.username} 请求获取其参与项目的容器列表。")
            # 1. 查找用户参与的所有项目 ID
            user_project_ids = db.query(ProjectMember.project_id).filter(
                ProjectMember.user_id == current_user.id
            ).all()
            
            # 将元组列表 [(id1,), (id2,)] 转换为 [id1, id2]
            project_ids = [pid for pid, in user_project_ids]

            if not project_ids:
                return []

            # 2. 查询这些项目下的所有容器
            return db.query(Container).filter(
                Container.project_id.in_(project_ids)
            ).order_by(Container.id.desc()).all()

    def _get_container_and_client(self, db: Session, container_db_id: int):
        """
        一个辅助方法，根据数据库ID获取容器的 ORM 实例和 Docker 客户端。
        """
        db_container = db.query(Container).filter(Container.id == container_db_id).first()
        if not db_container:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据库中未找到该容器记录。")
        
        client = self._get_docker_client()
        return db_container, client

    def stop_container(self, db: Session, container_db_id: int) -> Container:
        """停止单个 Docker 容器并更新数据库状态。"""
        db_container, client = self._get_container_and_client(db, container_db_id)
        
        try:
            container = client.containers.get(db_container.container_id)
            container.stop()
            db_container.status = 'exited'
            db.commit()
            logger.info(f"容器 {db_container.container_name} (ID: {db_container.id}) 已成功停止。")
        except docker.errors.NotFound:
            logger.warning(f"尝试停止容器时，Docker 中未找到 ID 为 {db_container.container_id} 的容器。可能已被手动移除。")
            db_container.status = 'unknown' # 标记为未知状态
            db.commit()
        except docker.errors.APIError as e:
            logger.error(f"停止容器 {db_container.container_name} 时发生 Docker API 错误: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="停止容器时发生 Docker API 错误。")
        
        db.refresh(db_container)
        return db_container

    def restart_container(self, db: Session, container_db_id: int) -> Container:
        """重启单个 Docker 容器并更新数据库状态。"""
        db_container, client = self._get_container_and_client(db, container_db_id)

        try:
            container = client.containers.get(db_container.container_id)
            container.restart()
            db_container.status = 'running'
            db.commit()
            logger.info(f"容器 {db_container.container_name} (ID: {db_container.id}) 已成功重启。")
        except docker.errors.NotFound:
            logger.warning(f"尝试重启容器时，Docker 中未找到 ID 为 {db_container.container_id} 的容器。")
            db_container.status = 'unknown'
            db.commit()
        except docker.errors.APIError as e:
            logger.error(f"重启容器 {db_container.container_name} 时发生 Docker API 错误: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="重启容器时发生 Docker API 错误。")
        
        db.refresh(db_container)
        return db_container

    def remove_container(self, db: Session, container_db_id: int):
        """停止、移除 Docker 容器，并从数据库中删除记录。"""
        db_container, client = self._get_container_and_client(db, container_db_id)

        try:
            container = client.containers.get(db_container.container_id)
            container.stop()
            container.remove()
            logger.info(f"Docker 容器 {db_container.container_name} 已成功停止并移除。")
        except docker.errors.NotFound:
            logger.warning(f"尝试移除容器时，Docker 中未找到 ID 为 {db_container.container_id} 的容器，将仅删除数据库记录。")
        except docker.errors.APIError as e:
            logger.error(f"移除容器 {db_container.container_name} 时发生 Docker API 错误: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="移除容器时发生 Docker API 错误。")
        
        # 从数据库中删除记录
        db.delete(db_container)
        db.commit()
        logger.info(f"容器 {db_container.container_name} (ID: {db_container.id}) 的数据库记录已删除。")

    def stop_all_containers_for_project(self, db: Session, project_id: int) -> int:
        """
        停止一个项目下所有处于活动状态的容器。

        Returns:
            成功停止的容器数量。
        """
        active_statuses = ['running', 'creating', 'restarting']
        containers_to_stop = db.query(Container).filter(
            Container.project_id == project_id,
            Container.status.in_(active_statuses)
        ).all()

        if not containers_to_stop:
            logger.info(f"项目 {project_id} 中没有需要停止的活动容器。")
            return 0

        stopped_count = 0
        for db_container in containers_to_stop:
            try:
                # 调用单个停止方法，复用其逻辑
                self.stop_container(db, db_container.id)
                stopped_count += 1
            except Exception as e:
                # 即使单个容器停止失败，也继续尝试停止其他容器
                logger.error(f"在批量停止项目 {project_id} 的容器时，停止容器 {db_container.id} 失败: {e}", exc_info=True)
        
        return stopped_count

    async def report_status(
        self,
        db: Session,
        redis_client: redis.Redis,
        project_id: int,
        worker_id: str,
        status: str,
        message: Optional[str] = None
    ):
        """
        处理来自容器的状态报告。

        Args:
            db: 数据库会话。
            redis_client: Redis 客户端实例。
            project_id: 容器所属的项目 ID。
            worker_id: 报告状态的容器的 worker_id。
            status: 报告的状态，如 'needs_manual_intervention' 或 'running'。
            message: 附带的信息，例如错误描述。
        """
        redis_key = f"{REDIS_ALERT_PREFIX}{worker_id}"

        if status == 'needs_manual_intervention':
            # 1. 将警报信息存入 Redis
            alert_data = {"status": status, "message": message, "project_id": project_id}
            redis_client.set(redis_key, json.dumps(alert_data))
            logger.info(f"Worker {worker_id} 的警报状态已记录到 Redis。")

            # 2. 查询项目的所有者和管理员以发送通知
            try:
                # 根据新的多对多关系模型，查询项目中所有角色为"所有者"或"管理员"或成员的用户
                project_managers = db.query(User).join(
                    ProjectMember, User.id == ProjectMember.user_id
                ).filter(
                    ProjectMember.project_id == project_id,
                    ProjectMember.role.in_([ProjectRole.PROJECT_OWNER, ProjectRole.PROJECT_ADMIN, ProjectRole.PROJECT_MEMBER])
                ).all()

                if not project_managers:
                    logger.error(f"无法找到项目 {project_id} 的所有者或管理员来发送通知。")
                else:
                    title = f"容器需要人工干预 (项目ID: {project_id})"
                    body = f"Worker ID: {worker_id}"
                    
                    for user in project_managers:
                        if user.pushme_key:
                            await _send_push_notification(user.pushme_key, title, body)
                        else:
                            logger.warning(f"项目 {project_id} 的管理员/所有者 {user.username} 没有配置 pushme_key，无法发送通知。")

            except SQLAlchemyError as e:
                logger.error(f"查询项目所有者或管理员以发送通知时发生数据库错误: {e}", exc_info=True)
                # 即使通知失败，状态也已记录，所以不抛出异常

        elif status == 'running':
            # 如果状态恢复正常，则从 Redis 中删除警报
            if redis_client.exists(redis_key):
                redis_client.delete(redis_key)
                logger.info(f"已收到 Worker {worker_id} 的恢复信号，警报已从 Redis 中移除。")
        else:
            logger.warning(f"收到了一个未知的容器状态报告: '{status}' from worker {worker_id}。")

    def get_all_alerts(self, redis_client: redis.Redis) -> List[Dict[str, Any]]:
        """
        从 Redis 中获取所有当前的警报。

        Args:
            redis_client: Redis 客户端实例。

        Returns:
            一个包含所有警报信息的字典列表。
        """
        alert_keys = redis_client.keys(f"{REDIS_ALERT_PREFIX}*")
        alerts = []
        if not alert_keys:
            return alerts

        alert_values = redis_client.mget(alert_keys)
        
        for i, value in enumerate(alert_values):
            if value:
                try:
                    worker_id = alert_keys[i].replace(REDIS_ALERT_PREFIX, "")
                    alert_data = json.loads(value)
                    alert_data['worker_id'] = worker_id
                    alerts.append(alert_data)
                except (json.JSONDecodeError, IndexError) as e:
                    logger.error(f"解析 Redis 中的警报数据时出错 (Key: {alert_keys[i]}): {e}", exc_info=True)
        
        logger.info(f"获取到的警报列表: {alerts}")
        return alerts


# 创建一个服务实例，以便在其他地方重用
container_service = ContainerService() 