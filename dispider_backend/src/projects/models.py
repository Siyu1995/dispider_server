import enum # 导入 enum
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Enum as SQLAlchemyEnum # 导入 Enum
from sqlalchemy.orm import relationship

from src.database import Base
# User 模型现在通过 secondary 关系间接引用，不再需要直接导入
# from src.auth.models import User

# 定义项目状态的枚举类型
class ProjectStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"

# 定义 Project 模型
class Project(Base):
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    # 移除了 owner_id，项目所有者/成员关系由 ProjectMember 表管理
    # owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    settings = Column(JSON, nullable=True) # 使用 JSON 类型来存储项目设置，例如 max_retries, timeout
    status = Column(SQLAlchemyEnum(ProjectStatus), default=ProjectStatus.ACTIVE, nullable=False) # 新增的状态字段

    # 移除了旧的 owner 关系
    # owner = relationship("User", back_populates="projects")

    # 新的关系：通过 ProjectMember 关联到多个用户，并级联删除
    member_associations = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    
    # 新增的辅助关系：方便直接通过 project.members 访问关联的 User 对象列表
    members = relationship(
        "User",
        secondary="project_members", # 指定中间表
        back_populates="projects",
        viewonly=True # 这是一个只读视图，实际的添加/删除应通过 member_associations 操作
    )

    # 定义 Project 和 CodePackage 之间的一对多关系
    code_packages = relationship("CodePackage", back_populates="project", cascade="all, delete-orphan")

    # 定义 Project 和 Container 之间的一对多关系
    containers = relationship("src.containers.models.Container", back_populates="project", cascade="all, delete-orphan")


# 定义 CodePackage 模型
class CodePackage(Base):
    __tablename__ = 'code_packages'

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False) # 外键，关联到 projects 表的 id
    version = Column(String, nullable=False)
    file_path = Column(String, nullable=False) # 存储代码包（如 .zip 文件）的路径

    # 定义 CodePackage 和 Project 之间的多对一关系
    project = relationship("Project", back_populates="code_packages")
