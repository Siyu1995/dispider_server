from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database import Base

class Container(Base):
    """
    数据库模型，用于存储和跟踪由本应用创建的 Docker 容器的状态。
    """
    __tablename__ = "containers"

    # --- 核心字段 ---
    id = Column(Integer, primary_key=True, index=True, comment="数据库内部主键")
    container_id = Column(String, unique=True, index=True, nullable=False, comment="Docker 返回的唯一容器ID")
    container_name = Column(String, unique=True, nullable=False, comment="我们为容器指定的名称")
    image = Column(String, nullable=False, comment="容器所使用的镜像")
    status = Column(String, default='creating', nullable=False, comment="容器的当前状态 (e.g., creating, running, exited, error)")
    host_port = Column(String, unique=True, nullable=True, comment="映射到宿主机的VNC端口url (http://localhost:8080)")
    worker_id = Column(String, unique=True, nullable=False, index=True, comment="分配给容器内部爬虫的唯一工作节点ID")

    # --- 关联关系 ---
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, comment="容器所属项目的外键ID")
    project = relationship("src.projects.models.Project", back_populates="containers") # 定义与 Project 模型的关系

    # --- 时间戳 ---
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="记录创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="记录更新时间")

    def __repr__(self):
        return f"<Container(id={self.id}, name='{self.container_name}', status='{self.status}')>" 