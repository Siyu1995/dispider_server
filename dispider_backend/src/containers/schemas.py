from pydantic import BaseModel, Field
from typing import List, Optional, Dict

# 定义启动容器批处理时的请求模型
class BatchStartRequest(BaseModel):
    container_count: int = 1 # 要启动的容器数量，默认为1
    image: str = Field(..., description="用于启动容器的 Docker 镜像标签，例如 'my-crawler:latest'。")
    # 新增 volumes 参数，并为其设置一个默认值方便 Windows 测试
    # 格式为 {"宿主机路径": "容器内路径"}
    volumes: Optional[Dict[str, str]] = Field(None, description="数据卷挂载配置，格式为 {'host_path': 'container_path'}")
    # 新增代理配置参数，它将作为环境变量传递给容器
    proxy_config: Optional[Dict[str, str]] = Field(None, description="代理配置，例如 {'HTTP_PROXY': 'http://user:pass@host:port'}")

# 定义成功启动容器后的响应模型
class ContainerResponse(BaseModel):
    id: int
    container_id: str
    container_name: str
    worker_id: str
    host_port: str
    status: str
    project_id: int

    class Config:
        from_attributes = True

# 定义批量启动的响应模型
class BatchStartResponse(BaseModel):
    message: str
    started_containers: List[ContainerResponse]

# --- 新增的模型 ---

class ContainerStatusRequest(BaseModel):
    """
    容器上报状态的请求体模型。
    """
    status: str = Field(..., description="容器的当前状态，例如 'needs_manual_intervention' 或 'running'。")
    message: Optional[str] = Field(None, description="当状态需要关注时，附带的详细信息。")

class AlertResponse(BaseModel):
    """
    向前端返回警报信息的响应模型。
    """
    worker_id: str
    project_id: int
    status: str
    message: Optional[str] = None 