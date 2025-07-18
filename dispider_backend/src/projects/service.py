from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import logging
import os
import shutil
import re
import zipfile
from fastapi import UploadFile, HTTPException, status
from typing import Optional, List, Dict, Any
import docker # 导入 docker 库
from uuid import uuid4 # 用于生成唯一的 worker_id
from datetime import datetime, timedelta

from src.database import get_db
from src.projects.models import Project
from src.auth.models import User # 确保 User 被导入
from src.projects.schemas import ProjectCreate
from src.projects.models import ProjectStatus # 导入新的 Project 模型和状态枚举
from src.projects.members.models import ProjectMember, ProjectRole # 导入成员模型和角色
from src.containers.service import container_service # 导入容器服务
from src.config import settings

# 配置日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProjectService:
    """
    处理与项目相关的业务逻辑。
    """

    def create_project(self, db: Session, project_data: ProjectCreate, creator: User) -> Project:
        """
        创建一个新项目，并自动将创建者设置为项目的管理员。
        此操作要求创建者必须是系统超级管理员。
        成功创建项目后，会根据项目ID在DOCKER_SPACE下创建对应的工作目录。

        Args:
            db: 数据库会话。
            project_data: 项目创建所需的数据模型。
            creator: 创建项目的用户 ORM 对象。

        Returns:
            新创建的 Project ORM 对象。
            
        Raises:
            SQLAlchemyError: 如果发生数据库错误。
            OSError: 如果创建项目目录失败。
        """
        # 权限校验已移至路由层的依赖中，这里假设调用者已验证过权限
        try:
            # 使用 with db.begin_nested() 来确保项目创建和成员添加在同一个事务块中
            with db.begin_nested():
                logger.info(f"超级管理员 {creator.username} (ID: {creator.id}) 正在创建项目 '{project_data.name}'...")
                new_project = Project(
                    name=project_data.name,
                    settings=project_data.settings
                )
                db.add(new_project)
                db.flush()  # 刷新会话以获取 new_project.id

                # 自动将创建者添加为项目的 ADMIN
                new_member = ProjectMember(
                    project_id=new_project.id,
                    user_id=creator.id,
                    role=ProjectRole.PROJECT_ADMIN
                )
                db.add(new_member)

            # 在提交数据库事务之前，执行文件系统操作
            # 如果这里失败，可以回滚整个事务
            project_docker_space = os.path.join(settings.DOCKER_SPACE, str(new_project.id))
            os.makedirs(project_docker_space, exist_ok=True)
            logger.info(f"为项目 ID {new_project.id} 创建了 Docker 空间目录: {project_docker_space}")

            db.commit()
            db.refresh(new_project)
            
            logger.info(f"项目 '{project_data.name}' (ID: {new_project.id}) 已成功创建，并将用户 {creator.id} 设置为管理员。")
            return new_project

        except (SQLAlchemyError, OSError) as e:
            logger.error(f"创建项目过程中发生错误: {e}", exc_info=True)
            db.rollback()
            raise

    def get_project_by_id(self, db: Session, project_id: int, current_user: User) -> Optional[Project]:
        """
        根据ID获取单个项目的详细信息。
        返回的项目对象会包含当前用户的角色信息。

        Args:
            db: 数据库会话。
            project_id: 项目的ID。
            current_user: 当前登录的用户。

        Returns:
            如果找到项目，则返回附带角色信息的 Project 对象，否则返回 None。
        """
        # 使用 LEFT JOIN 来获取当前用户在项目中的角色
        # 这样即使用户不是成员（例如超级管理员查看非自己成员项目），也能获取项目信息
        query = (
            db.query(
                Project,
                ProjectMember.role
            )
            .outerjoin(ProjectMember, (Project.id == ProjectMember.project_id) & (ProjectMember.user_id == current_user.id))
            .filter(Project.id == project_id)
        )

        result = query.first()

        if result:
            project, role = result
            project.role = role # 动态添加 role 属性
            return project
        
        return None

    def add_member(self, db: Session, project_id: int, user_id: int, role: ProjectRole) -> ProjectMember:
        """
        向项目中添加一个新成员。

        Args:
            db: 数据库会话。
            project_id: 目标项目ID。
            user_id: 要添加的用户ID。
            role: 分配给用户的角色。

        Returns:
            新创建的 ProjectMember 关联对象。
        """
        # 检查用户和项目是否存在
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="要邀请的用户不存在。")
        
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在。")

        # 检查用户是否已经是成员
        existing_member = db.query(ProjectMember).filter_by(project_id=project_id, user_id=user_id).first()
        if existing_member:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该用户已经是此项目的成员。")

        try:
            new_member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
            db.add(new_member)
            db.commit()
            db.refresh(new_member)
            logger.info(f"已成功将用户 {user_id} 作为 '{role.value}' 添加到项目 {project_id}。")
            return new_member
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"添加成员到项目 {project_id} 时发生数据库错误: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="添加成员时发生数据库错误。")

    def remove_member(self, db: Session, project_id: int, user_id: int) -> None:
        """
        从项目中移除一个成员。

        Args:
            db: 数据库会话。
            project_id: 目标项目ID。
            user_id: 要移除的用户ID。
        """
        member_to_remove = db.query(ProjectMember).filter_by(project_id=project_id, user_id=user_id).first()

        if not member_to_remove:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该用户不是此项目的成员。")
        
        # 项目管理员不能被移除，只能由超级管理员删除整个项目
        if member_to_remove.role == ProjectRole.PROJECT_ADMIN:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能移除项目的管理员。")

        try:
            db.delete(member_to_remove)
            db.commit()
            logger.info(f"已从项目 {project_id} 中成功移除用户 {user_id}。")
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"从项目 {project_id} 移除成员时发生数据库错误: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="移除成员时发生数据库错误。")

    def update_member_role(self, db: Session, project_id: int, user_id: int, new_role: ProjectRole) -> ProjectMember:
        """
        更新项目成员的角色。

        Args:
            db: 数据库会话。
            project_id: 目标项目ID。
            user_id: 要更新角色的用户ID。
            new_role: 新的角色。
        
        Returns:
            更新后的 ProjectMember 对象。
        """
        member_to_update = db.query(ProjectMember).filter_by(project_id=project_id, user_id=user_id).first()

        if not member_to_update:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该用户不是此项目的成员。")

        # 禁止将自己降级或修改管理员角色
        if member_to_update.role == ProjectRole.PROJECT_ADMIN:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改项目管理员的角色。")

        try:
            member_to_update.role = new_role
            db.commit()
            db.refresh(member_to_update)
            logger.info(f"已成功将项目 {project_id} 中用户 {user_id} 的角色更新为 '{new_role.value}'。")
            return member_to_update
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"更新项目成员角色时发生数据库错误: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新角色时发生数据库错误。")

    def list_members(self, db: Session, project_id: int) -> List[ProjectMember]:
        """
        列出项目的所有成员，并预加载用户信息以便获取用户名。

        Args:
            db: 数据库会话。
            project_id: 目标项目ID。

        Returns:
            项目成员ORM对象列表，其中关联的 User 对象已被加载。
        """
        return (
            db.query(ProjectMember)
            .options(joinedload(ProjectMember.user))
            .filter(ProjectMember.project_id == project_id)
            .all()
        )

    def list_projects(self, db: Session, current_user: User) -> List[Project]:
        """
        列出项目列表。
        - 如果是超级管理员，则返回所有项目。
        - 如果是普通用户，则只返回其参与的项目。
        每个项目对象都会被附加一个 'role' 属性，表示当前用户在该项目中的角色。

        Args:
            db: 数据库会话。
            current_user: 当前登录的用户。

        Returns:
            一个 Project 对象的列表，每个对象都带有 'role' 属性。
        """
        if current_user.is_super_admin:
            logger.info(f"超级管理员 {current_user.username} 请求获取所有项目列表。")
            # 超级管理员获取所有项目
            # 使用 LEFT JOIN 来获取当前用户在每个项目中的角色（如果有）
            query = (
                db.query(
                    Project,
                    ProjectMember.role
                )
                .outerjoin(ProjectMember, (Project.id == ProjectMember.project_id) & (ProjectMember.user_id == current_user.id))
                .order_by(Project.id.desc())
            )
            results = query.all()
            
            # 将 (Project, role) 元组列表转换为 Project 对象列表，并附加 role 属性
            projects_with_roles = []
            for project, role in results:
                project.role = role # 动态添加 role 属性
                projects_with_roles.append(project)
            return projects_with_roles

        else:
            logger.info(f"用户 {current_user.username} 请求获取其参与的项目列表。")
            # 普通用户只获取他们是成员的项目
            # 直接查询 ProjectMember，然后通过 relationship 加载 Project
            query = (
                db.query(Project, ProjectMember.role)
                .join(ProjectMember, Project.id == ProjectMember.project_id)
                .filter(ProjectMember.user_id == current_user.id)
                .order_by(Project.id.desc())
            )

            results = query.all()

            # 同样地，转换数据结构
            projects_with_roles = []
            for project, role in results:
                project.role = role
                projects_with_roles.append(project)
            return projects_with_roles

    def update_project_status(self, db: Session, project_id: int, new_status: ProjectStatus) -> Project:
        """
        更新项目的状态。如果项目被归档，则停止所有关联的容器。

        Args:
            db: 数据库会话。
            project_id: 项目的 ID。
            new_status: 新的项目状态。

        Returns:
            更新后的 Project ORM 对象。

        Raises:
            HTTPException: 如果项目未找到。
        """
        # 使用 with_for_update 来锁定项目行，防止在处理过程中其他事务修改项目
        project = db.query(Project).filter(Project.id == project_id).with_for_update().first()

        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目未找到")

        # 检查状态是否真的改变了
        if project.status == new_status:
            return project # 如果状态没变，直接返回

        logger.info(f"正在将项目 {project_id} 的状态从 '{project.status.value}' 更新为 '{new_status.value}'...")

        # 核心逻辑：如果项目被归档，则停止所有相关容器
        if new_status == ProjectStatus.ARCHIVED:
            logger.info(f"项目 {project_id} 已归档，开始停止所有关联的活动容器...")
            # 注意：我们在这里直接调用了 container_service 的方法
            # 这要求 container_service 必须有一个可以批量停止容器的方法
            # 我们将在下一步中实现它
            stopped_count = container_service.stop_all_containers_for_project(db=db, project_id=project_id)
            logger.info(f"为项目 {project_id} 停止了 {stopped_count} 个容器。")

        # 更新项目状态
        project.status = new_status
        db.commit()
        db.refresh(project)

        logger.info(f"项目 {project_id} 的状态已成功更新为 '{new_status.value}'。")
        return project

    def upload_code(self, project_id: int, file: UploadFile) -> dict:
        """
        上传、解压并验证项目的代码包。
        1. 清空项目现有的代码。
        2. 将上传的 ZIP 包保存到项目专属的 Docker 空间。
        3. 解压 ZIP 包。
        4. 验证解压后的代码中是否包含 main.py。
        5. 如果验证失败，则清空目录并报错。

        Args:
            project_id: 项目的 ID。
            file: 用户上传的 UploadFile 对象 (必须是 ZIP 格式)。

        Returns:
            一个包含成功信息的字典。
        
        Raises:
            IOError: 如果文件操作失败。
            zipfile.BadZipFile: 如果上传的不是一个有效的 ZIP 文件。
            HTTPException: 如果验证失败或发生其他错误。
        """
        project_dir = os.path.join(settings.DOCKER_SPACE, str(project_id))
        
        try:
            # 1. 确保项目目录存在，并清空旧内容
            if os.path.exists(project_dir):
                logger.info(f"项目 {project_id} 目录已存在，正在清空旧文件...")
                for filename in os.listdir(project_dir):
                    file_path = os.path.join(project_dir, filename)
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
            else:
                os.makedirs(project_dir)

            # 2. 保存上传的 zip 文件
            zip_path = os.path.join(project_dir, "temp_upload.zip")
            logger.info(f"正在将项目 {project_id} 的代码包保存到: {zip_path}")
            with open(zip_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # 3. 解压 zip 文件
            logger.info(f"正在解压文件: {zip_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(project_dir)

            # 4. 验证 main.py 是否存在
            main_py_path = os.path.join(project_dir, 'main.py')
            if not os.path.isfile(main_py_path):
                logger.error(f"项目 {project_id} 的代码包验证失败：未找到 main.py 文件。")
                # 清理已解压的文件
                shutil.rmtree(project_dir)
                os.makedirs(project_dir) # 重新创建空目录
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="代码包不合规：必须在根目录包含一个 main.py 文件。"
                )

            logger.info(f"项目 {project_id} 的代码包上传并验证成功。")
            return {"message": "代码包上传、解压并验证成功。"}

        except zipfile.BadZipFile:
            logger.error(f"为项目 {project_id} 上传的文件不是一个有效的 ZIP 文件。")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传的文件格式无效，必须是 ZIP 格式。")
        except (IOError, os.error) as e:
            logger.error(f"处理项目 {project_id} 的代码包时发生 I/O 错误: {e}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="存储或解压代码包时发生服务器内部错误。")
        finally:
            # 确保关闭上传的文件对象
            if file and not file.file.closed:
                file.file.close()
            # 确保删除临时的 zip 文件
            if 'zip_path' in locals() and os.path.exists(zip_path):
                os.remove(zip_path)

    def list_project_files(self, project_id: int) -> List[str]:
        """
        列出指定项目代码目录下的所有文件名。

        Args:
            project_id: 项目的 ID。

        Returns:
            一个包含所有文件名的字符串列表。如果目录不存在，则返回空列表。
        """
        project_dir = os.path.join(settings.DOCKER_SPACE, str(project_id))
        
        if not os.path.isdir(project_dir):
            logger.info(f"请求列出项目 {project_id} 的文件，但其目录不存在: {project_dir}")
            return []
        
        try:
            files = os.listdir(project_dir)
            logger.info(f"成功列出项目 {project_id} 目录下的 {len(files)} 个文件。")
            return files
        except OSError as e:
            logger.error(f"列出项目 {project_id} 的文件时发生 OS 错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="列出项目文件时发生服务器错误。"
            )


# 创建一个服务实例，以便在其他地方重用
project_service = ProjectService()
