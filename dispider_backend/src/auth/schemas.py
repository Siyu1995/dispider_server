from pydantic import BaseModel


# Pydantic 模型的基础类，包含所有用户模型共有的字段
# 通过这种方式，我们可以避免在多个地方重复定义相同的字段。
class UserBase(BaseModel):
    username: str
    pushme_key: str | None = None
    is_super_admin: bool


# 用于创建新用户的 Pydantic 模型
# 这个模型将用于 API 请求体验证，确保客户端发送的数据包含 username 和 password
class UserCreate(BaseModel):
    username: str
    password: str
    pushme_key: str
    is_super_admin: bool = False
    email: str

# 用于响应中返回 token 的 Pydantic 模型
class Token(BaseModel):
    access_token: str
    token_type: str


# 用于解码 JWT token 后获取的数据的 Pydantic 模型
class TokenData(BaseModel):
    username: str | None = None


# 用于从数据库读取用户数据并返回给客户端的 Pydantic 模型
# 它继承自 UserBase，并添加了 id 字段。
# 在 Pydantic V2 中，`orm_mode` 已被 `from_attributes` 取代。
class User(UserBase):
    id: int

    model_config = {
        "from_attributes": True
    }