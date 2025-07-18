from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth import schemas, models
from src.config import settings

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
        print(token)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        print(payload)
        username: str = payload.get("sub")
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

def get_super_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """
    一个简单的依赖，用于校验当前用户是否为超级管理员。
    """
    if not current_user.is_super_admin:
        raise FORBIDDEN_EXCEPTION
    return current_user 