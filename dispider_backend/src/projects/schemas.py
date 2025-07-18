from pydantic import BaseModel, Json, Field
from typing import Optional, Any, List, Dict

from src.projects.models import ProjectStatus # 导入项目状态枚举
from src.projects.members.models import ProjectRole # 导入项目角色枚举

# 定义创建项目时请求体的 Pydantic 模型
class ProjectCreate(BaseModel):
    name: str  # 项目名称，必填字段
    settings: Optional[dict[str, Any]] = None  # 项目设置，可选字段，可以是任意 JSON 对象

# 定义显示项目信息时的 Pydantic 模型
class ProjectResponse(BaseModel):
    id: int  # 项目 ID
    name: str  # 项目名称
    status: ProjectStatus # 项目状态
    settings: Optional[dict[str, Any]] = None  # 项目设置

    # Pydantic V2 使用 from_attributes 替代 orm_mode
    # 这允许模型从对象的属性（而不仅仅是字典）中读取数据，方便地将 SQLAlchemy 模型转换为 Pydantic 模型
    class Config:
        from_attributes = True

class ProjectWithRoleResponse(ProjectResponse):
    """项目信息，包含当前用户的角色。"""
    role: Optional[ProjectRole] = Field(None, description="当前用户在此项目中的角色，如果不是成员则为 null。")

# 定义代码包上传成功后的响应模型
class CodeUploadResponse(BaseModel):
    message: str
    file_path: str

# 定义批量启动容器时的请求体模型
class BatchStartRequest(BaseModel):
    container_count: int  # 要启动的容器数量

class ProjectStatusUpdate(BaseModel):
    """
    用于更新项目状态的请求体模型。
    """
    status: ProjectStatus

# --- 成员管理相关 Schema ---

class MemberBase(BaseModel):
    """成员信息的基础模型，用于信息展示。"""
    user_id: int
    role: ProjectRole

class MemberResponse(MemberBase):
    """标准的成员响应模型，包含关联记录的ID。"""
    id: int
    username: str # 用户名
    project_id: int

    class Config:
        from_attributes = True

class MemberCreate(BaseModel):
    """邀请新成员时的请求体模型。"""
    user_id: int = Field(..., description="要邀请的用户的ID。")
    role: ProjectRole = Field(..., description="要分配给该用户的角色。")

class MemberRoleUpdate(BaseModel):
    """更新成员角色时的请求体模型。"""
    role: ProjectRole = Field(..., description="要为该成员设置的新角色。")

class ProjectFilesResponse(BaseModel):
    """响应模型，用于返回项目的文件列表。"""
    files: List[str]

class MessageResponse(BaseModel):
    """通用的消息响应模型。"""
    message: str
