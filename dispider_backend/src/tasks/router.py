from fastapi import APIRouter, Depends, HTTPException, status, Response, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from src.database import get_db
from src.tasks.schemas import (
    BulkInsertResponse,
    TaskResponse,
    TableInitializationRequest,
    ProjectTablesStructureResponse,
)
from src.tasks.service import task_service
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.projects.dependencies import ProjectAccessChecker
from src.projects.members.models import ProjectRole

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/{project_id}/tasks", 
    tags=["tasks"]
)

@router.get(
    "/schema",
    response_model=ProjectTablesStructureResponse,
    summary="获取项目表结构",
    description="获取指定项目任务表和结果表的用户自定义列的列表。需要用户是该项目的成员。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_MEMBER))]
)
def get_project_tables_structure(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目任务表和结果表的列结构。

    此端点返回用户在初始化表时定义的动态列，排除了系统自动管理的标准列（如 `id`, `status` 等）。
    """
    logger.info(f"用户 {current_user.username} (ID: {current_user.id}) 正在请求项目 {project_id} 的表结构。")
    try:
        structure = task_service.get_project_tables_structure(db=db, project_id=project_id)
        return structure
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"获取项目 {project_id} 表结构时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取表结构时发生意外错误。"
        )

@router.post(
    "/table",
    status_code=status.HTTP_200_OK,
    summary="初始化或重建项目任务表 (项目所有者及以上)",
    description="根据提供的列名列表，为项目创建或重建其专属的任务表。此操作会删除任何已存在的同名表及其数据。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_OWNER))]
)
def initialize_tasks_table(
    project_id: int,
    request: TableInitializationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(f"用户 {current_user.id} 正在为项目 {project_id} 初始化任务表，列名: {request.columns}")
        task_service.initialize_tasks_table(db=db, project_id=project_id, columns=request.columns)
        return {"message": "任务表已成功初始化。"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"初始化任务表时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"初始化任务表时发生意外错误: {e}"
        )

@router.post(
    "/results/table",
    status_code=status.HTTP_200_OK,
    summary="初始化或重建项目结果表 (项目所有者及以上)",
    description="根据提供的列名列表，为项目创建或重建其专属的结果表。此操作会删除任何已存在的同名表及其数据。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_OWNER))]
)
def initialize_results_table(
    project_id: int,
    request: TableInitializationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(f"用户 {current_user.id} 正在为项目 {project_id} 初始化结果表，列名: {request.columns}")
        task_service.initialize_results_table(db=db, project_id=project_id, columns=request.columns)
        return {"message": "结果表已成功初始化。"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"初始化结果表时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="初始化结果表时发生意外错误。"
        )

@router.post(
    "/",
    response_model=BulkInsertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="批量添加任务 (项目成员及以上)",
    description="向指定项目的任务表中批量添加结构化数据。需要先初始化任务表。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_MEMBER))]
)
def add_tasks(
    project_id: int,
    tasks: Dict[str, List[Any]] = Body(..., example={
        "url": ["http://example.com/page1", "http://example.com/page2"],
        "user_id": [101, 102]
    }),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        logger.info(f"用户 {current_user.id} 正在为项目 {project_id} 批量添加任务。")
        inserted_count = task_service.add_tasks(db=db, project_id=project_id, tasks_data=tasks)
        logger.info(f"项目 {project_id} 的任务批量添加处理完毕，共插入 {inserted_count} 条记录。")
        return {
            "message": "任务批量添加成功",
            "inserted_count": inserted_count
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"批量添加任务时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="批量添加任务时发生意外错误。"
        )

@router.get(
    "/next",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="原子化地获取下一个待处理任务",
    description="为工作节点（爬虫）提供一个端点，以原子方式获取下一个可用任务，防止多个节点获取到同一个任务。如果没有可用任务，则返回 204 No Content。",
    responses={
        204: {"description": "当前没有待处理的任务"},
    }
)
def get_next_task(
    project_id: int,
    worker_id: str,
    db: Session = Depends(get_db)
):
    try:
        next_task = task_service.get_next_task(
            db=db, project_id=project_id, worker_id=worker_id
        )
        if not next_task:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        return next_task
    except Exception as e:
        logger.error(f"获取下一个任务时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取下一个任务时发生意外错误。"
        )

@router.post(
    "/{task_id}/result",
    status_code=status.HTTP_200_OK,
    summary="提交任务结果",
    description="工作节点（爬虫）调用此端点，提交已完成任务的结果。提交成功后，任务状态将被标记为 'completed'。"
)
def submit_task_result(
    project_id: int,
    task_id: int,
    result_data: Dict[str, Any] = Body(..., example={"url": "http://example.com", "title": "Example Domain"}),
    db: Session = Depends(get_db)
):
    try:
        task_service.submit_task_result(db, project_id, task_id, result_data)
        return {"message": f"任务 {task_id} 的结果已成功提交。"}
    except Exception as e:
        logger.error(f"提交任务 {task_id} 结果时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="提交任务结果时发生意外错误。"
        )

@router.post(
    "/{task_id}/fail",
    status_code=status.HTTP_200_OK,
    summary="报告任务失败",
    description="工作节点（爬虫）在执行任务失败时调用此端点。系统将根据重试策略处理该任务。"
)
def report_task_failure(
    project_id: int,
    task_id: int,
    payload: Dict[str, str] = Body(None, example={"error": "A description of what went wrong."}),
    db: Session = Depends(get_db)
):
    error_message = payload.get("error") if payload else None
    try:
        task_service.report_task_failure(db, project_id, task_id, error_message)
        return {"message": f"已收到任务 {task_id} 的失败报告。"}
    except Exception as e:
        logger.error(f"报告任务 {task_id} 失败时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="报告任务失败时发生意外错误。"
        )

@router.get(
    "/columns",
    response_model=List[str],
    summary="获取任务表列名",
    description="获取指定项目任务表的用户自定义列名列表。需要用户是该项目的成员。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_MEMBER))]
)
def get_task_columns(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目任务表的列结构。
    """
    logger.info(f"用户 {current_user.username} 正在请求项目 {project_id} 的任务表列名。")
    try:
        columns = task_service.get_task_columns(db=db, project_id=project_id)
        return columns
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"获取项目 {project_id} 任务表列名时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取任务表列名时发生意外错误。"
        )

@router.get(
    "/results/columns",
    response_model=List[str],
    summary="获取结果表列名",
    description="获取指定项目结果表的用户自定义列名列表。需要用户是该项目的成员。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_MEMBER))]
)
def get_result_columns(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取项目结果表的列结构。
    """
    logger.info(f"用户 {current_user.username} 正在请求项目 {project_id} 的结果表列名。")
    try:
        columns = task_service.get_result_columns(db=db, project_id=project_id)
        return columns
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"获取项目 {project_id} 结果表列名时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取结果表列名时发生意外错误。"
        )

@router.get(
    "/progress",
    response_model=float,
    summary="获取任务完成度",
    description="获取项目当前任务的完成比例（0.0 到 1.0 之间），保留四位小数。需要用户是该项目的成员。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_MEMBER))]
)
def get_task_progress(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    计算并返回任务完成进度。
    """
    logger.info(f"用户 {current_user.username} 正在请求项目 {project_id} 的任务完成度。")
    try:
        progress = task_service.get_task_progress(db=db, project_id=project_id)
        return progress
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"获取项目 {project_id} 任务进度时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取任务进度时发生意外错误。"
        )

@router.get(
    "/results/count",
    response_model=int,
    summary="获取结果总数",
    description="获取项目结果表的总行数。需要用户是该项目的成员。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_MEMBER))]
)
def get_results_count(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取结果表中的记录总数。
    """
    logger.info(f"用户 {current_user.username} 正在请求项目 {project_id} 的结果总数。")
    try:
        count = task_service.get_results_count(db=db, project_id=project_id)
        return count
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"获取项目 {project_id} 结果总数时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取结果总数时发生意外错误。"
        )
