from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Dict, Any

from src.database import get_db
from src.projects.schemas import (
    ProjectCreate, 
    ProjectResponse, 
    ProjectStatusUpdate,
    MemberResponse,
    MemberCreate,
    MemberRoleUpdate,
    ProjectWithRoleResponse,
    ProjectFilesResponse,
    MessageResponse
)
from src.projects.service import project_service
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.projects.dependencies import ProjectAccessChecker
from src.auth.dependencies import get_super_admin
from src.projects.members.models import ProjectRole

import logging

# 配置日志记录
logger = logging.getLogger(__name__)

# 创建一个 API 路由器
router = APIRouter(tags=["projects"])

@router.get(
    "/",
    response_model=List[ProjectWithRoleResponse],
    summary="获取项目列表",
    description="获取项目列表。超级管理员可以查看所有项目，其他用户只能查看自己参与的项目。返回结果会包含当前用户在每个项目中的角色。",
)
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    根据用户角色返回项目列表。

    - **超级管理员**: 返回所有项目，并标注自己在每个项目中的角色（如果有）。
    - **普通用户**: 返回自己作为成员的所有项目及其角色。
    """
    try:
        projects = project_service.list_projects(db, current_user)
        return projects
    except Exception as e:
        logger.error(f"用户 {current_user.username} 获取项目列表时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取项目列表时发生意外错误。"
        )

@router.get(
    "/{project_id}",
    response_model=ProjectWithRoleResponse,
    summary="获取单个项目的详细信息",
    description="获取指定ID的项目的详细信息。需要用户是该项目的成员或超级管理员。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_MEMBER))]
)
def get_project_details(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取单个项目的详细信息。

    通过 `ProjectAccessChecker` 依赖确保了只有项目成员及以上权限的用户或超级管理员才能访问。
    """
    logger.info(f"用户 {current_user.username} (ID: {current_user.id}) 正在请求项目 {project_id} 的详细信息。")
    
    project = project_service.get_project_by_id(db=db, project_id=project_id, current_user=current_user)

    if not project:
        logger.warning(f"请求的项目 {project_id} 未找到。注意：权限检查已在 ProjectAccessChecker 中完成。")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ID为 {project_id} 的项目未找到。"
        )
    
    return project

@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建一个新项目 (仅限超级管理员)",
    description="仅限超级管理员可以创建一个新项目。创建成功后，创建者将自动成为该项目的管理员。",
    dependencies=[Depends(get_super_admin)]
)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_super_admin)
):
    try:
        logger.info(f"超级管理员 {current_user.username} 正在请求创建项目: {project.name}")
        new_project = project_service.create_project(
            db=db,
            project_data=project,
            creator=current_user
        )
        logger.info(f"项目 '{new_project.name}' (ID: {new_project.id}) 已成功创建。")
        return new_project
    except SQLAlchemyError as e:
        logger.error(f"创建项目时发生数据库错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建项目时发生内部错误，请稍后重试。"
        )
    except Exception as e:
        logger.error(f"创建项目时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建项目时发生意外错误。"
        )

@router.patch(
    "/{project_id}/status",
    response_model=ProjectResponse,
    summary="更新项目状态 (激活/归档) (仅限超级管理员)",
    description="更新一个项目的状态。此操作仅限超级管理员。",
    dependencies=[Depends(get_super_admin)]
)
def update_project_status(
    project_id: int,
    status_update: ProjectStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_super_admin)
):
    try:
        updated_project = project_service.update_project_status(
            db=db,
            project_id=project_id,
            new_status=status_update.status
        )
        return updated_project
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"更新项目 {project_id} 状态时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新项目状态时发生意外错误。"
        )

@router.post(
    "/{project_id}/code",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="上传项目代码包 (项目所有者及以上)",
    description="上传一个 ZIP 格式的代码包到指定的项目。需要用户认证。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_OWNER))]
)
def upload_project_code(
    project_id: int,
    file: UploadFile = File(..., description="要上传的 ZIP 代码包"),
    current_user: User = Depends(get_current_user)
):
    # 放宽对 ZIP 文件内容类型的校验，以兼容不同客户端
    accepted_zip_types = ["application/zip", "application/x-zip-compressed"]
    if file.content_type not in accepted_zip_types:
        logger.warning(
            f"用户 {current_user.id} 尝试为项目 {project_id} 上传无效的文件类型: {file.content_type}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件格式无效 ({file.content_type})，请上传 ZIP 格式的压缩包。"
        )

    try:
        logger.info(
            f"用户 {current_user.id} 正在为项目 {project_id} 上传代码包: {file.filename}"
        )
        result = project_service.upload_code(project_id=project_id, file=file)
        logger.info(
            f"项目 {project_id} 的代码包 '{file.filename}' 上传成功。"
        )
        return result
    except IOError as e:
        logger.error(f"为项目 {project_id} 保存代码包时发生 I/O 错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="存储代码包时发生服务器内部错误。"
        )
    except Exception as e:
        logger.error(f"上传代码包时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传代码包时发生意外错误。{e}"
        )

@router.get(
    "/{project_id}/files",
    response_model=ProjectFilesResponse,
    summary="获取项目代码文件列表",
    description="获取指定项目代码目录下的所有文件名。需要至少是项目成员才能查看。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_MEMBER))]
)
def list_project_files(
    project_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    列出项目代码目录下的所有文件名。
    """
    try:
        logger.info(f"用户 {current_user.username} 正在请求项目 {project_id} 的文件列表。")
        file_list = project_service.list_project_files(project_id=project_id)
        return {"files": file_list}
    except HTTPException as e:
        # 直接重新抛出由服务层引发的已知HTTP异常
        raise e
    except Exception as e:
        logger.error(f"获取项目 {project_id} 文件列表时发生未知错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取文件列表时发生意外错误。"
        )

@router.get(
    "/{project_id}/members",
    response_model=List[MemberResponse],
    summary="获取项目成员列表",
    description="获取指定项目的所有成员及其角色。需要至少是项目成员才能查看。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_MEMBER))]
)
def list_project_members(project_id: int, db: Session = Depends(get_db)):
    members = project_service.list_members(db=db, project_id=project_id)
    return members

@router.post(
    "/{project_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="邀请新成员加入项目 (仅限项目管理员)",
    description="邀请一个已注册的用户加入项目并为其分配角色。只有项目管理员可以执行此操作。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_ADMIN))]
)
def add_project_member(
    project_id: int,
    member_data: MemberCreate,
    db: Session = Depends(get_db)
):
    try:
        new_member = project_service.add_member(
            db=db,
            project_id=project_id,
            user_id=member_data.user_id,
            role=member_data.role
        )
        return new_member
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"邀请成员加入项目 {project_id} 时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="邀请成员时发生未知错误。")

@router.put(
    "/{project_id}/members/{user_id}",
    response_model=MemberResponse,
    summary="更新项目成员的角色 (仅限项目管理员)",
    description="更新指定项目成员的角色。只有项目管理员可以执行此操作，且不能修改其他管理员的角色。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_ADMIN))]
)
def update_project_member_role(
    project_id: int,
    user_id: int,
    role_update: MemberRoleUpdate,
    db: Session = Depends(get_db)
):
    try:
        updated_member = project_service.update_member_role(
            db=db,
            project_id=project_id,
            user_id=user_id,
            new_role=role_update.role
        )
        return updated_member
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"更新项目 {project_id} 成员 {user_id} 角色时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新成员角色时发生未知错误。")

@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="从项目中移除成员 (仅限项目管理员)",
    description="从项目中移除一个成员。只有项目管理员可以执行此操作，且不能移除其他管理员。",
    dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_ADMIN))]
)
def remove_project_member(project_id: int, user_id: int, db: Session = Depends(get_db)):
    try:
        project_service.remove_member(db=db, project_id=project_id, user_id=user_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"移除项目 {project_id} 成员 {user_id} 时发生未知错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="移除成员时发生未知错误。")
