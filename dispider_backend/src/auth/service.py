# 这个文件将包含与认证和用户管理相关的业务逻辑
# 例如：
# - 创建用户的函数 (hashing password, etc.)
# - 验证用户凭据的函数
# - 根据用户ID获取用户的函数

# 保持业务逻辑与路由处理程序分离是一种很好的做法。
# 这使得代码更易于测试、维护和重用。

from sqlalchemy.orm import Session
import bcrypt
from src.auth import models, schemas
from src.auth.security import verify_password


# 根据用户名或邮箱查找用户
def get_user_by_username(db: Session, username: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        user = db.query(models.User).filter(models.User.email == username).first()
    return user


# 创建新用户
def create_user(db: Session, user: schemas.UserCreate):
    # 使用 bcrypt 生成哈希密码，增加安全性
    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
    # 创建 User 模型实例，注意要解码 hashed_password
    db_user = models.User(username=user.username, 
                          hashed_password=hashed_password.decode('utf-8'), 
                          is_super_admin=user.is_super_admin,
                          pushme_key=user.pushme_key,
                          email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# 认证用户
def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user 

def get_users(db: Session, skip: int = 0, limit: int = 100):
    """
    获取用户列表。

    Args:
        db (Session): 数据库会话。
        skip (int): 要跳过的用户数。
        limit (int): 要返回的最大用户数。

    Returns:
        list[models.User]: 用户对象列表。
    """
    return db.query(models.User).offset(skip).limit(limit).all() 