from fastapi import Depends, HTTPException, status, WebSocket, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth import schemas, models
from src.config import settings
from src.auth.models import User

# OAuth2 anquan fangshi ,zhiding token de URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

FORBIDDEN_EXCEPTION = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="The user does not have enough privileges",
)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_user_from_websocket(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
) -> User:
    """
    一个专门用于 WebSocket 连接的依赖项，用于从查询参数中获取和验证用户身份。
    
    Args:
        websocket: WebSocket 连接对象。
        token: 从查询参数 `?token=...` 中自动提取的 JWT。
        db: 数据库会话依赖。
        
    Returns:
        如果 token 有效，返回 User ORM 对象。
        
    Raises:
        WebSocketException: 如果 token 无效或用户不存在，则关闭连接。
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        # 从 payload 中获取用户名 (subject)
        username: str = payload.get("sub")
        if username is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token 无效: 缺少用户信息")
            return None

    except JWTError:
        # 如果 token 解码失败
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token 无效: 解码失败")
        return None
    except ValidationError:
        # 如果 token 格式不正确
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token 无效: 格式错误")
        return None

    # 从数据库中查找用户
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        # 如果数据库中不存在该用户
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="用户不存在")
        return None
        
    return user

def get_super_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """
    一个简单的依赖，用于校验当前用户是否为超级管理员。
    """
    if not current_user.is_super_admin:
        raise FORBIDDEN_EXCEPTION
    return current_user 