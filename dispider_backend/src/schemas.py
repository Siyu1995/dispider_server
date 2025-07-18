from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field

# 创建一个泛型 T，用于表示 data 字段的类型
# TypeVar 用于定义一个类型变量，可以在泛型类中使用
T = TypeVar('T')


class Response(BaseModel, Generic[T]):
    """
    标准 API 响应模型。
    使用 Pydantic 的 GenericModel 来创建一个可以接受不同数据类型的响应结构。

    Attributes:
        code (int): HTTP 状态码，默认为 200。
        msg (str): 响应消息，默认为 "success"。
        data (Optional[T]): 实际的响应数据，可以是任何类型（由泛型 T 定义），也可以是 None。
    """
    code: int = Field(200, description="业务状态码, 200-成功")
    msg: str = Field("success", description="响应消息")
    data: Optional[T] = Field(None, description="响应数据") 