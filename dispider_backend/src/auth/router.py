from datetime import timedelta
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth import schemas, service
from src.auth.security import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from src.auth.dependencies import get_current_user, get_super_admin
from src.schemas import Response  # 导入新的标准响应模型

# 创建一个 API 路由实例
# 我们可以在这里定义所有与认证/用户相关的路由
# 例如：登录、注册、获取用户信息等
router = APIRouter(
    tags=["auth"],  # 在 OpenAPI 文档中为这些路由分组
)

# 在这里可以添加路由...
@router.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    用户登录以获取访问令牌。

    Args:
        form_data (OAuth2PasswordRequestForm): FastAPI 提供的表单依赖，包含 username 和 password。
        db (Session): 数据库会话依赖。

    Raises:
        HTTPException: 如果认证失败，则抛出 401 未授权错误。

    Returns:
        schemas.Token: 包含访问令牌和令牌类型的 Pydantic 模型，FastAPI 会将其序列化为 JSON。
    """
    user = service.authenticate_user(db, username=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    token_data = schemas.Token(access_token=access_token, token_type="bearer")
    return token_data

@router.get("/users/me", response_model=Response[schemas.User])
def read_users_me(current_user: schemas.User = Depends(get_current_user)):
    """
    获取当前登录用户的信息。

    Args:
        current_user (schemas.User): 当前登录用户信息的依赖。

    Returns:
        Response[schemas.User]: 包含用户信息的标准响应。
    """
    return Response(data=current_user)

@router.get("/users/me/admin", response_model=Response[dict])
def read_own_items(
    current_user: schemas.User = Depends(get_super_admin)
):
    """
    一个仅限超级管理员访问的端点。
    """
    return Response(data={"message": f"Welcome super admin {current_user.username}"})

@router.post("/users/register", response_model=Response[schemas.User])
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    注册一个新用户。

    Args:
        user (schemas.UserCreate): 创建新用户所需的数据。
        db (Session): 数据库会话依赖。

    Raises:
        HTTPException: 如果用户名已存在，则抛出 400 错误。

    Returns:
        Response[schemas.User]: 包含新创建用户信息的标准响应。
    """
    # 检查用户名是否已存在
    db_user = service.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    # 创建新用户
    new_user = service.create_user(db=db, user=user)
    return Response(data=new_user)


@router.get("/users", response_model=Response[List[schemas.User]])
def read_users(db: Session = Depends(get_db), current_user: schemas.User = Depends(get_super_admin)):
    """
    获取所有用户的列表。

    - **仅限超级管理员访问**

    Args:
        db (Session): 数据库会话依赖。
        current_user (schemas.User): 当前登录用户，通过 get_super_admin 依赖注入，确保是超级管理员。

    Returns:
        Response[List[schemas.User]]: 包含用户列表的标准响应。
    """
    users = service.get_users(db=db)
    return Response(data=users)

