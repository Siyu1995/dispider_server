# 容器相关的 API 路由将在这里定义 

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging
from typing import List, Dict, Any
import redis

from src.database import get_db
from src.redis_client import get_redis_client
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.containers.service import container_service
from src.containers.schemas import (
    BatchStartRequest, 
    BatchStartResponse,
    ContainerStatusRequest,
    AlertResponse,
    ContainerResponse,
)

# 配置日志记录
logger = logging.getLogger(__name__)

# 创建一个 API 路由器，所有与容器相关的端点都在这里定义
# 移除了 prefix="/projects"，将前缀统一到 main.py 中管理
router = APIRouter(tags=["containers_by_project"])

@router.post(
    "/{project_id}/containers/batch/start",
    response_model=BatchStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="为项目批量创建并启动容器",
    description="为指定的项目启动一批爬虫工作容器，并将它们的状态记录到数据库。需要用户认证。"
)
def start_project_container_batch(
    project_id: int,
    request: BatchStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    为指定项目批量启动爬虫容器的 API 端点。

    - **project_id**: 容器所属项目的 ID。
    - **request**: 包含 `container_count` 和 `image` 的请求体。
    - **db**: 数据库会话依赖。
    - **current_user**: 确保操作者已认证。
    """
    try:
        logger.info(f"用户 {current_user.username} (ID: {current_user.id}) 正在为项目 {project_id} 请求启动 {request.container_count} 个容器...")
        
        started_containers = container_service.start_container_batch(
            db=db,
            project_id=project_id,
            request=request
        )
        
        logger.info(f"为项目 {project_id} 成功启动 {len(started_containers)} 个容器。")
        return {
            "message": f"成功请求启动 {len(started_containers)} 个容器。",
            "started_containers": started_containers
        }
    except HTTPException as e:
        # 直接向上抛出由服务层或依赖项引发的 HTTP 异常
        raise e
    except Exception as e:
        # 捕捉所有其他意外错误
        logger.error(f"为项目 {project_id} 批量启动容器时在路由层发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量启动容器时发生意外的服务器错误。{e}"
        )

@router.post(
    "/{project_id}/containers/{worker_id}/status",
    status_code=status.HTTP_200_OK,
    summary="接收并处理来自容器的状态报告",
    description="容器可以调用此端点来报告其当前状态。如果状态为 'needs_manual_intervention'，系统将记录警报并通知管理员。"
)
async def report_container_status(
    project_id: int,
    worker_id: str,
    request: ContainerStatusRequest,
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    处理容器状态报告的 API 端点。

    - **project_id**: 容器所属项目的 ID。
    - **worker_id**: 报告状态的容器的 worker_id。
    - **request**: 包含 `status` 和可选 `message` 的请求体。
    - **db**: 数据库会话依赖。
    - **redis_client**: Redis 客户端依赖。
    """
    try:
        await container_service.report_status(
            db=db,
            redis_client=redis_client,
            project_id=project_id,
            worker_id=worker_id,
            status=request.status,
            message=request.message
        )
        return {"message": "状态已成功记录。"}
    except Exception as e:
        logger.error(f"处理来自 worker {worker_id} 的状态报告时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="处理容器状态报告时发生服务器错误。"
        )

@router.get(
    "/{project_id}/containers/alerts",
    response_model=List[AlertResponse],
    summary="获取所有需要人工干预的容器警报",
    description="返回一个当前所有处于 'needs_manual_intervention' 状态的容器列表，供前端展示或监控使用。"
)
def get_all_container_alerts(
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: User = Depends(get_current_user)
):
    """
    获取所有容器警报的 API 端点。

    - **redis_client**: Redis 客户端依赖。
    - **current_user**: 确保只有登录用户才能访问。
    """
    try:
        alerts = container_service.get_all_alerts(redis_client=redis_client)
        return alerts
    except Exception as e:
        logger.error(f"获取容器警报列表时出错: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取容器警报时发生服务器错误。"
        )

# --- 单个容器管理的独立路由 ---
# 移除了 prefix="/containers"，将前缀统一到 main.py 中管理
container_router = APIRouter(tags=["containers_standalone"])

@container_router.get(
    "/",
    response_model=List[ContainerResponse],
    summary="获取对用户可见的容器列表",
    description="获取容器列表。超级管理员可以查看所有容器，其他用户只能查看自己参与的项目下的容器。"
)
def list_containers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        containers = container_service.list_containers(db=db, current_user=current_user)
        return containers
    except Exception as e:
        logger.error(f"获取容器列表时发生错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取容器列表时发生服务器错误。"
        )

@container_router.post(
    "/{container_db_id}/stop",
    response_model=ContainerResponse,
    summary="停止一个独立的容器"
)
def stop_container(
    container_db_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return container_service.stop_container(db, container_db_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"停止容器 {container_db_id} 时路由层发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="停止容器时发生未知错误。")

@container_router.post(
    "/{container_db_id}/restart",
    response_model=ContainerResponse,
    summary="重启一个独立的容器"
)
def restart_container(
    container_db_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return container_service.restart_container(db, container_db_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"重启容器 {container_db_id} 时路由层发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="重启容器时发生未知错误。")

@container_router.delete(
    "/{container_db_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="停止并移除一个独立的容器"
)
def remove_container(
    container_db_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        return container_service.remove_container(db, container_db_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"移除容器 {container_db_id} 时路由层发生错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="移除容器时发生未知错误。") 