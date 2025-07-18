import enum
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship

from src.database import Base


# 定义 User 模型，它将映射到数据库中的 'users' 表
class User(Base):
    __tablename__ = 'users'

    # 定义表的列
    id = Column(Integer, primary_key=True, index=True)  # 主键，并创建索引以加快查询速度
    username = Column(String, unique=True, index=True, nullable=False)  # 用户名，必须唯一且非空
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)  # 存储哈希后的密码，非空
    # 根据要求，将角色枚举替换为布尔值以区分超级管理员
    is_super_admin = Column(Boolean, default=False, nullable=False)
    pushme_key = Column(String, nullable=True)  # 用于推送通知的 key，可以为空

    # 移除了旧的、直接指向 Project 的 'projects' 关系
    # projects = relationship("Project", back_populates="owner")

    # 新的关系：通过 ProjectMember 关联，能获取用户在所有项目中的成员身份记录
    project_associations = relationship("ProjectMember", back_populates="user", cascade="all, delete-orphan")

    # 新增的辅助关系：方便直接通过 user.projects 访问该用户参与的所有 Project 对象列表
    projects = relationship(
        "Project",
        secondary="project_members", # 指定中间表
        back_populates="members",
        viewonly=True # 这是一个只读视图，实际的添加/删除应通过 project_associations 操作
    ) 