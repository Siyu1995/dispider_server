from fastapi import Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import Callable

from src.database import get_db
from src.projects.members.models import ProjectMember, ProjectRole
from src.auth.dependencies import get_current_user
from src.auth.models import User

# 创建一个标准的403禁止访问异常，以便在多个地方重用
FORBIDDEN_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="您没有足够的权限来执行此操作。"
)

def get_project_member(
    project_id: int = Path(..., title="项目ID", description="目标项目的唯一标识符"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectMember:
    """
    一个 FastAPI 依赖，用于从数据库中获取当前用户在指定项目中的成员关系。

    - 如果用户是超级管理员，它将构造一个临时的 ProjectMember 对象，并赋予最高权限（PROJECT_ADMIN），
      这样可以确保超级管理员能够通过所有基于角色的权限检查，即使他们不是项目的显式成员。
    - 如果用户不是项目的成员（且不是超级管理员），则会引发 404 Not Found 异常。
    - 如果找到了成员关系，则返回该 ProjectMember 对象。

    Args:
        project_id: 从路径参数中自动提取的项目ID。
        db: 数据库会话依赖。
        current_user: 当前已认证的用户依赖。

    Returns:
        与当前用户和项目关联的 ProjectMember ORM 对象。

    Raises:
        HTTPException: 如果当前用户不是该项目的成员且不是超级管理员。
    """
    # 如果是超级管理员，则直接授予管理员权限，无需查询数据库
    if current_user.is_super_admin:
        # 创建一个临时的、未提交到数据库的ProjectMember实例，用于权限检查
        return ProjectMember(
            user_id=current_user.id,
            project_id=project_id,
            role=ProjectRole.PROJECT_ADMIN
        )

    member = db.query(ProjectMember).filter_by(
        project_id=project_id,
        user_id=current_user.id
    ).first()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="您不是该项目的成员，或者项目不存在。"
        )
    return member

def ProjectAccessChecker(required_role: ProjectRole) -> Callable[[ProjectMember], ProjectMember]:
    """
    权限校验器工厂函数 (Dependency Factory)。

    这是一个高阶函数，它接收一个所需的最低角色，然后返回一个 FastAPI 依赖函数。
    返回的依赖函数会校验用户的实际角色是否满足要求。

    由于 get_project_member 已经处理了超级管理员的情况，
    因此此处的逻辑可以保持不变，它会自动处理超级管理员的权限。

    用法:
    @router.post("/", dependencies=[Depends(ProjectAccessChecker(ProjectRole.PROJECT_OWNER))])
    """
    # 定义角色层级，用于权限比较
    role_hierarchy = {
        ProjectRole.PROJECT_MEMBER: 1,
        ProjectRole.PROJECT_OWNER: 2,
        ProjectRole.PROJECT_ADMIN: 3
    }

    def check_access(member: ProjectMember = Depends(get_project_member)) -> ProjectMember:
        """
        这是实际的 FastAPI 依赖函数。
        它依赖于 get_project_member 来获取用户的成员关系。
        然后，它会比较用户的角色等级和要求的角色等级。
        """
        user_role_level = role_hierarchy.get(member.role, 0)
        required_role_level = role_hierarchy.get(required_role, 0)

        if user_role_level < required_role_level:
            raise FORBIDDEN_EXCEPTION
        
        return member

    return check_access

# The get_super_admin function has been moved to src/auth/dependencies.py
# to be a globally available dependency. 