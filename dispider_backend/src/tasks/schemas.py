from pydantic import BaseModel, Field
from typing import List, Dict, Any

# 定义爬虫获取任务时的响应模型
class TaskResponse(BaseModel):
    id: int
    data: Dict[str, Any]

# 定义初始化表结构时的请求体模型
class TableInitializationRequest(BaseModel):
    columns: List[str] = Field(..., min_items=1, description="用于初始化表的列名列表，至少需要一列。")

# 定义批量操作成功后的通用响应模型
class BulkInsertResponse(BaseModel):
    message: str
    inserted_count: int

class ProjectTablesStructureResponse(BaseModel):
    """响应项目任务表和结果表结构的模型。"""
    task_columns: List[str] = Field(..., description="任务表的用户自定义列名列表。")
    result_columns: List[str] = Field(..., description="结果表的用户自定义列名列表。")
