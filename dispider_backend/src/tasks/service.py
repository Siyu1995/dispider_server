from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import logging
import re
from fastapi import HTTPException, status
from typing import List, Dict, Any, Optional

from src.projects.models import Project
from src.tasks.schemas import TaskResponse

# 配置日志记录
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskService:
    """
    处理与项目任务相关的业务逻辑。
    """
    def _validate_column_names(self, columns: List[str]):
        """
        验证列名是否符合安全规范。

        Args:
            columns: 待验证的列名列表。

        Raises:
            HTTPException: 如果列名无效。
        """
        RESERVED_WORDS = {'id', 'status', 'worker_id', 'claimed_at', 'retry_count', 'note'}
        
        for name in columns:
            # 修改正则表达式以支持 Unicode 字符 (包括中文), 但仍然禁止以数字开头
            # ^[^\d\W] 匹配任何非数字和非“非单词”字符（即字母和下划线，以及Unicode字符）
            # [\w\u4e00-\u9fa5]* 匹配后续的字母、数字、下划线和中文字符
            if not re.match(r'^[^\d\W][\w\u4e00-\u9fa5]*$', name, re.UNICODE):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"列名 '{name}' 包含无效字符或以数字开头。")
            if name.upper() in RESERVED_WORDS:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"列名 '{name}' 是一个保留关键字，请使用其他名称。")

    def get_project_tables_structure(self, db: Session, project_id: int) -> Dict[str, List[str]]:
        """
        获取指定项目任务表和结果表的列结构。
        仅返回用户自定义的列，排除系统内置列。

        Args:
            db: 数据库会话。
            project_id: 项目ID。

        Returns:
            一个包含 task_columns 和 result_columns 的字典。
        """
        tasks_table_name = f'project_{project_id}_tasks'
        results_table_name = f'project_{project_id}_results'

        def get_table_columns(table_name: str) -> List[str]:
            """辅助函数，用于查询指定表的列名。"""
            table_exists_query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = :table_name
                );
            """)
            if not db.execute(table_exists_query, {'table_name': table_name}).scalar():
                logger.warning(f"尝试查询一个不存在的表: {table_name}")
                return []

            columns_query = text("""
                SELECT column_name 
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table_name
                ORDER BY ordinal_position;
            """)
            return [row[0] for row in db.execute(columns_query, {'table_name': table_name}).fetchall()]

        try:
            project_exists = db.query(Project).filter(Project.id == project_id).first()
            if not project_exists:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID为 {project_id} 的项目未找到。")

            all_task_columns = get_table_columns(tasks_table_name)
            all_result_columns = get_table_columns(results_table_name)
            
            task_excluded_columns = {'id', 'status', 'worker_id', 'claimed_at', 'retry_count'}
            result_excluded_columns = {'id', 'task_id', 'note'}

            task_columns = [col for col in all_task_columns if col not in task_excluded_columns]
            result_columns = [col for col in all_result_columns if col not in result_excluded_columns]

            return {
                "task_columns": task_columns,
                "result_columns": result_columns,
            }
        except SQLAlchemyError as e:
            logger.error(f"查询项目 {project_id} 表结构时发生数据库错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="查询表结构时发生数据库错误。"
            )

    def initialize_tasks_table(self, db: Session, project_id: int, columns: List[str]):
        """
        初始化项目的任务表。如果表已存在，则删除重建。
        """
        self._validate_column_names(columns)
        tasks_table_name = f'project_{project_id}_tasks'
        
        column_definitions = ", ".join([f'"{col}" TEXT' for col in columns])

        try:
            logger.info(f"正在为项目 {project_id} 初始化任务表 {tasks_table_name}...")
            db.execute(text(f"DROP TABLE IF EXISTS {tasks_table_name} CASCADE;"))
            
            create_sql = text(f"""
                CREATE TABLE {tasks_table_name} (
                    id SERIAL PRIMARY KEY,
                    status VARCHAR(50) DEFAULT 'pending',
                    worker_id VARCHAR(255),
                    claimed_at TIMESTAMP,
                    retry_count INTEGER DEFAULT 0,
                    {column_definitions}
                );
            """)
            db.execute(create_sql)
            db.commit()
            logger.info(f"任务表 {tasks_table_name} 已成功初始化。")
        except SQLAlchemyError as e:
            logger.error(f"初始化任务表 {tasks_table_name} 时发生数据库错误: {e}", exc_info=True)
            db.rollback()
            raise

    def initialize_results_table(self, db: Session, project_id: int, columns: List[str]):
        """
        初始化项目的结果表。如果表已存在，则删除重建。
        """
        self._validate_column_names(columns)
        results_table_name = f'project_{project_id}_results'

        column_definitions = [
            "id SERIAL PRIMARY KEY",
            "task_id INTEGER"
        ]
        if columns:
            user_columns = [f'"{col}" TEXT' for col in columns]
            column_definitions.extend(user_columns)
        
        column_definitions.append("note TEXT")

        try:
            logger.info(f"正在为项目 {project_id} 初始化结果表 {results_table_name}...")
            db.execute(text(f"DROP TABLE IF EXISTS {results_table_name} CASCADE;"))
            
            create_sql = text(f"""
                CREATE TABLE {results_table_name} (
                    {', '.join(column_definitions)}
                );
            """)
            db.execute(create_sql)
            db.commit()
            logger.info(f"结果表 {results_table_name} 已成功初始化。")
        except SQLAlchemyError as e:
            logger.error(f"初始化结果表 {results_table_name} 时发生数据库错误: {e}", exc_info=True)
            db.rollback()
            raise

    def add_tasks(self, db: Session, project_id: int, tasks_data: Dict[str, List[Any]]) -> int:
        """
        向指定项目的任务表中批量添加新任务。
        """
        if not tasks_data:
            return 0
        
        columns = list(tasks_data.keys())
        if not columns:
            return 0
        
        try:
            num_rows = len(tasks_data[columns[0]])
            if not all(len(v) == num_rows for v in tasks_data.values()):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="数据格式错误：所有列的值列表长度必须相同。"
                )
        except (KeyError, IndexError):
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="数据格式错误：任务数据不能为空。"
            )
        
        if num_rows == 0:
            return 0
            
        tasks_to_insert = [
            {col: tasks_data[col][i] for col in columns}
            for i in range(num_rows)
        ]
        
        tasks_table_name = f'project_{project_id}_tasks'
        self._validate_column_names(columns)
        
        column_names = ", ".join([f'"{col}"' for col in columns])
        value_placeholders = ", ".join([f":{col}" for col in columns])
        
        insert_statement = text(f"""
            INSERT INTO {tasks_table_name} ({column_names}) 
            VALUES ({value_placeholders})
        """)

        try:
            logger.info(f"正在向项目 {project_id} 的任务表 {tasks_table_name} 中批量插入 {len(tasks_to_insert)} 个任务...")
            db.execute(insert_statement, tasks_to_insert)
            db.commit()
            logger.info(f"成功为项目 {project_id} 插入 {len(tasks_to_insert)} 个任务。")
            return len(tasks_to_insert)
        except SQLAlchemyError as e:
            logger.error(f"为项目 {project_id} 批量插入任务时发生数据库错误: {e}", exc_info=True)
            db.rollback()
            raise
            
    def get_next_task(self, db: Session, project_id: int, worker_id: str) -> Optional[TaskResponse]:
        """
        原子性地获取下一个可用任务。
        """
        tasks_table_name = f'project_{project_id}_tasks'
        logger.info(f"工作节点 '{worker_id}' 正在从项目 {project_id} 的表 '{tasks_table_name}' 中请求下一个任务。")

        query = text(f"""
            WITH existing_task AS (
                SELECT *
                FROM {tasks_table_name}
                WHERE worker_id = :worker_id AND status = 'in_progress'
                ORDER BY id
                LIMIT 1
            ),
            locked_task AS (
                SELECT id
                FROM {tasks_table_name}
                WHERE 
                    status = 'pending' 
                    AND NOT EXISTS (SELECT 1 FROM existing_task)
                ORDER BY id
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            ),
            updated_task AS (
                UPDATE {tasks_table_name}
                SET 
                    status = 'in_progress', 
                    worker_id = :worker_id, 
                    claimed_at = NOW()
                WHERE id = (SELECT id FROM locked_task)
                RETURNING *
            )
            SELECT * FROM existing_task
            UNION ALL
            SELECT * FROM updated_task;
        """)

        try:
            result = db.execute(
                query,
                {"worker_id": worker_id}
            ).fetchone()
            
            db.commit()

            if result:
                task_data = dict(result._mapping)
                return TaskResponse(id=task_data.pop('id'), data=task_data)
            else:
                logger.info(f"项目 {project_id} 中没有待处理或进行中的任务可分配给工作节点 '{worker_id}'。")
                return None

        except SQLAlchemyError as e:
            logger.error(f"为项目 {project_id} 获取下一个任务时发生数据库错误: {e}", exc_info=True)
            db.rollback()
            raise

    def submit_task_result(self, db: Session, project_id: int, task_id: int, results_data: Dict[str, Any]):
        """
        在一个事务中为单个任务批量提交结果并更新任务状态为 'completed'。
        """
        tasks_table_name = f'project_{project_id}_tasks'
        update_statement = text(f"UPDATE {tasks_table_name} SET status = 'completed' WHERE id = :task_id")

        if not results_data or not any(results_data.values()):
            logger.warning(f"任务 {task_id} 提交了空结果集，将仅更新任务状态为 'completed'。")
            try:
                with db.begin():
                    db.execute(update_statement, {"task_id": task_id})
                logger.info(f"任务 {task_id} 状态已成功更新为 'completed'，没有插入任何结果数据。")
            except SQLAlchemyError as e:
                logger.error(f"为任务 {task_id} 更新状态时发生数据库错误: {e}", exc_info=True)
                raise
            return

        columns = list(results_data.keys())
        self._validate_column_names(columns)
        
        try:
            first_val = next(iter(results_data.values()))
            is_columnar = isinstance(first_val, list)

            if is_columnar:
                num_rows = len(first_val)
                if not all(isinstance(v, list) and len(v) == num_rows for v in results_data.values()):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="数据格式错误：所有列的值列表长度必须相同。"
                    )
                results_to_insert = [
                    {col: results_data[col][i] for col in columns}
                    for i in range(num_rows)
                ]
            else:
                num_rows = 1
                results_to_insert = [results_data]
        
        except (KeyError, IndexError, StopIteration):
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="数据格式错误：结果数据不能为空或格式不正确。"
            )

        if num_rows == 0:
            logger.warning(f"任务 {task_id} 提交了0行结果，将仅更新任务状态为 'completed'。")
            try:
                with db.begin():
                    db.execute(update_statement, {"task_id": task_id})
                logger.info(f"任务 {task_id} 状态已成功更新为 'completed'。")
            except SQLAlchemyError as e:
                logger.error(f"为任务 {task_id} 更新状态时发生数据库错误: {e}", exc_info=True)
                raise
            return

        for row in results_to_insert:
            row['task_id'] = task_id
        
        insert_columns = columns + ['task_id']
        column_names = ", ".join([f'"{col}"' for col in insert_columns])
        value_placeholders = ", ".join([f":{col}" for col in insert_columns])
        
        results_table_name = f'project_{project_id}_results'
        insert_statement = text(f"""
            INSERT INTO {results_table_name} ({column_names})
            VALUES ({value_placeholders})
        """)

        try:
            logger.info(f"正在为项目 {project_id} 的任务 {task_id} 提交 {len(results_to_insert)} 条结果。")
            with db.begin():
                db.execute(insert_statement, results_to_insert)
                db.execute(update_statement, {"task_id": task_id})
            logger.info(f"项目 {project_id} 的任务 {task_id} 的 {len(results_to_insert)} 条结果提交成功，事务已提交。")
        except SQLAlchemyError as e:
            logger.error(f"为项目 {project_id} 任务 {task_id} 提交结果时发生数据库错误，事务已回滚: {e}", exc_info=True)
            raise

    def report_task_failure(self, db: Session, project_id: int, task_id: int, error_message: Optional[str] = None):
        """
        报告任务执行失败。
        """
        tasks_table_name = f'project_{project_id}_tasks'
        MAX_RETRIES = 3

        update_statement = text(f"""
            UPDATE {tasks_table_name}
            SET 
                status = CASE 
                    WHEN retry_count >= :max_retries THEN 'failed' 
                    ELSE 'pending' 
                END,
                retry_count = retry_count + 1,
                worker_id = NULL,
                claimed_at = NULL
            WHERE id = :task_id AND status = 'in_progress'
            RETURNING status, retry_count;
        """)

        try:
            log_message = f"报告项目 {project_id} 的任务 {task_id} 失败。"
            if error_message:
                log_message += f" 错误信息: {error_message}"
            logger.warning(log_message)
            
            result = db.execute(update_statement, {"task_id": task_id, "max_retries": MAX_RETRIES - 1}).fetchone()
            db.commit()

            if result:
                new_status, retry_count = result
                logger.info(f"任务 {task_id} 状态已更新为 '{new_status}'，当前重试次数: {retry_count}。")
            else:
                logger.warning(f"尝试报告任务 {task_id} 失败，但该任务不存在或状态不是 'in_progress'。操作被跳过。")
                pass

        except SQLAlchemyError as e:
            logger.error(f"为项目 {project_id} 任务 {task_id} 报告失败时发生数据库错误: {e}", exc_info=True)
            db.rollback()
            raise

    def get_task_columns(self, db: Session, project_id: int) -> List[str]:
        """
        获取指定项目任务表的用户自定义列名。
        如果任务表不存在，则返回一个空列表。
        """
        project_exists = db.query(Project).filter(Project.id == project_id).first()
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID为 {project_id} 的项目未找到。")

        tasks_table_name = f'project_{project_id}_tasks'
        
        table_exists_query = text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :table_name);")
        if not db.execute(table_exists_query, {'table_name': tasks_table_name}).scalar():
            logger.warning(f"尝试获取一个不存在的任务表 '{tasks_table_name}' 的列名。")
            return []

        try:
            all_task_columns_query = text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table_name ORDER BY ordinal_position;
            """)
            all_task_columns = [row[0] for row in db.execute(all_task_columns_query, {'table_name': tasks_table_name}).fetchall()]
            
            task_excluded_columns = {'id', 'status', 'worker_id', 'claimed_at', 'retry_count'}
            return [col for col in all_task_columns if col not in task_excluded_columns]

        except SQLAlchemyError as e:
            logger.error(f"查询项目 {project_id} 任务表列名时发生数据库错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="查询任务表列名时发生数据库错误。"
            )

    def get_result_columns(self, db: Session, project_id: int) -> List[str]:
        """
        获取指定项目结果表的用户自定义列名。
        如果结果表不存在，则返回一个空列表。
        """
        project_exists = db.query(Project).filter(Project.id == project_id).first()
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID为 {project_id} 的项目未找到。")
        
        results_table_name = f'project_{project_id}_results'

        table_exists_query = text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :table_name);")
        if not db.execute(table_exists_query, {'table_name': results_table_name}).scalar():
            logger.warning(f"尝试获取一个不存在的结果表 '{results_table_name}' 的列名。")
            return []

        try:
            all_result_columns_query = text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table_name ORDER BY ordinal_position;
            """)
            all_result_columns = [row[0] for row in db.execute(all_result_columns_query, {'table_name': results_table_name}).fetchall()]
            
            result_excluded_columns = {'id', 'task_id', 'note'}
            return [col for col in all_result_columns if col not in result_excluded_columns]

        except SQLAlchemyError as e:
            logger.error(f"查询项目 {project_id} 结果表列名时发生数据库错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="查询结果表列名时发生数据库错误。"
            )

    def get_task_progress(self, db: Session, project_id: int) -> float:
        """
        计算并返回项目的任务完成进度，以浮点数表示（保留四位小数）。
        如果任务表不存在或没有任务，则返回 0.0。
        """
        project_exists = db.query(Project).filter(Project.id == project_id).first()
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID为 {project_id} 的项目未找到。")

        tasks_table_name = f'project_{project_id}_tasks'
        
        table_exists_query = text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :table_name);")
        if not db.execute(table_exists_query, {'table_name': tasks_table_name}).scalar():
             logger.warning(f"任务表 '{tasks_table_name}' 不存在，无法计算进度，返回 0.0。")
             return 0.0

        query = text(f"""
            SELECT
                COUNT(*) AS total_tasks,
                COUNT(*) FILTER (WHERE status = 'completed') AS completed_tasks
            FROM {tasks_table_name}
        """)
        try:
            result = db.execute(query).fetchone()
            if not result or result.total_tasks == 0:
                logger.info(f"项目 {project_id} 任务表中没有任务，完成度为 0.0。")
                return 0.0
            
            progress = result.completed_tasks / result.total_tasks
            return round(progress, 4)
        except SQLAlchemyError as e:
            logger.error(f"查询项目 {project_id} 任务进度时发生数据库错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="查询任务进度时发生数据库错误。"
            )

    def get_results_count(self, db: Session, project_id: int) -> int:
        """
        获取项目结果表的总行数。
        如果结果表不存在，返回 0。
        """
        project_exists = db.query(Project).filter(Project.id == project_id).first()
        if not project_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ID为 {project_id} 的项目未找到。")

        results_table_name = f'project_{project_id}_results'

        table_exists_query = text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :table_name);")
        if not db.execute(table_exists_query, {'table_name': results_table_name}).scalar():
            logger.warning(f"结果表 '{results_table_name}' 不存在，返回数量为 0。")
            return 0

        query = text(f"SELECT COUNT(*) FROM {results_table_name}")
        try:
            count = db.execute(query).scalar_one()
            return count
        except SQLAlchemyError as e:
            logger.error(f"查询项目 {project_id} 结果数量时发生数据库错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="查询结果数量时发生数据库错误。"
            )

# 创建一个服务实例，以便在其他地方重用
task_service = TaskService()
