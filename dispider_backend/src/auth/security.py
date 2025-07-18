from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext
from src.config import settings

# JWT 配置
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2PasswordBearer 用于从请求的 Authorization 头中提取 Bearer Token
# tokenUrl 指向获取 token 的端点路径。
# 注意: 这里的路径是相对于应用根目录的相对路径，不应以 "/" 开头。
# 否则 Swagger UI 可能无法正确地将登录后获取的 token 应用于后续的 API 请求。
# 正确的路径由 main.py 中的 prefix 和 router.py 中的 path 组成。
# 例如: prefix="/api/auth" + path="/token" => "api/auth/token"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/token")

# 创建一个 passlib 上下文实例，用于密码哈希
# 我们指定 bcrypt 作为默认的哈希算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# 验证密码
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码是否与哈希后的密码匹配。

    Args:
        plain_password: 用户输入的明文密码。
        hashed_password: 数据库中存储的哈希密码。

    Returns:
        如果密码匹配则返回 True，否则返回 False。
    """
    return pwd_context.verify(plain_password, hashed_password)


# 创建访问令牌
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    根据给定的数据和可选的过期时间创建一个新的 JWT 访问令牌。

    Args:
        data: 要编码到令牌中的数据（通常包含用户标识）。
        expires_delta: 令牌的有效期。如果未提供，则使用默认值。

    Returns:
        编码后的 JWT 令牌字符串。
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt 