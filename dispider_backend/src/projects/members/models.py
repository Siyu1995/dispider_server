import enum
from sqlalchemy import Column, Integer, ForeignKey, Enum as SQLAlchemyEnum, UniqueConstraint
from sqlalchemy.orm import relationship

from src.database import Base

class ProjectRole(str, enum.Enum):
    """
    定义用户在项目中的角色。

    - PROJECT_ADMIN: 项目管理员，拥有项目的完全控制权限，包括修改、删除项目以及管理成员。
    - PROJECT_OWNER: 项目所有者，拥有项目内部的所有操作权限，例如定义和修改任务、结果表结构，但不能删除项目本身。
    - PROJECT_MEMBER: 项目成员，可以执行项目内的任务，但不能改动关键结构（如任务表和结果表）。
    """
    PROJECT_ADMIN = "project_admin"
    PROJECT_OWNER = "project_owner"
    PROJECT_MEMBER = "project_member"

class ProjectMember(Base):
    """
    项目成员关联表，用于建立用户和项目之间的多对多关系，并定义其角色。
    """
    __tablename__ = 'project_members'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=False)
    role = Column(SQLAlchemyEnum(ProjectRole), nullable=False, default=ProjectRole.PROJECT_MEMBER)

    # 建立与 User 和 Project 的直接关系
    user = relationship("User", back_populates="project_associations")
    project = relationship("Project", back_populates="member_associations")

    # 确保一个用户在一个项目中只能有一个角色，避免数据冗余
    __table_args__ = (UniqueConstraint('project_id', 'user_id', name='_project_user_uc'),)

    @property
    def username(self) -> str:
        """提供关联用户的用户名，方便序列化。"""
        return self.user.username if self.user else ""

    def __repr__(self):
        return f"<ProjectMember(user_id={self.user_id}, project_id={self.project_id}, role='{self.role.value}')>" 