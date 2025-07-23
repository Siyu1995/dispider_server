from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from src.auth import router as auth_router
from src.projects import router as projects_router
from src.containers import router as containers_router
from src.tasks import router as tasks_router
from src.proxy_manager import router as proxy_manager_router
from src.proxy_manager.service import initialize_proxy_manager
from src.config import settings
from fastapi.middleware.cors import CORSMiddleware
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 在应用启动时创建数据库表
# 注意：在一个使用 Alembic 进行数据库迁移的成熟项目中，下面这行代码通常应该被移除或注释掉。
# 数据库的创建和变更应完全由迁移脚本来管理，以确保版本控制和一致性。
# Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """
    应用启动事件处理器。
    
    在应用启动时执行必要的初始化操作：
    1. 恢复容器代理映射数据（从配置文件到Redis）
    2. 检查并更新代理组数据
    3. 初始化代理健康监控服务
    4. 启动后台健康检查线程
    5. 启动容器自动重新分配线程
    """
    try:
        logger.info("正在启动应用...")
        
        # 完整初始化代理管理器（包含数据恢复）
        logger.info("初始化代理管理器（包含数据恢复）...")
        initialize_proxy_manager()
        
        logger.info("应用启动完成，所有服务已就绪")
    except Exception as e:
        logger.error(f"应用启动过程中发生错误: {e}", exc_info=True)
        # 不要阻止应用启动，但记录错误
        logger.warning("代理管理器初始化失败，但应用仍将继续启动")

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    全局 HTTP 异常处理器。
    捕获所有 HTTPException，并将其格式化为标准的 API 响应结构。

    Args:
        request (Request): FastAPI 的请求对象。
        exc (HTTPException): 捕获到的 HTTP 异常。

    Returns:
        JSONResponse: 包含标准错误信息的 JSON 响应。
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "msg": exc.detail,
            "data": None
        },
    )

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 允许访问的源
    allow_credentials=True,       # 支持 cookie
    allow_methods=["*"],          # 允许所有方法 (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],          # 允许所有请求头
)

# 包含来自 auth 模块的路由
# 这样，所有在 auth.router 中定义的路由都会被添加到主应用中
app.include_router(auth_router.router, prefix="/api/auth")

# 包含来自 projects 模块的路由
app.include_router(projects_router.router, prefix="/api/projects")

# 包含来自 tasks 模块的路由
app.include_router(tasks_router.router, prefix="/api/tasks")

# 包含与项目关联的容器路由
# 请注意，这个路由器的前缀与 projects_router 相同，这是因为它的 API 路径
# (例如 /api/projects/{project_id}/containers/batch/start) 是 projects 资源的子集
app.include_router(containers_router.router, prefix="/api/projects")

# 包含独立的容器管理路由
app.include_router(containers_router.container_router, prefix="/api/containers")

# 包含代理管理器路由
app.include_router(proxy_manager_router.router, prefix="/api/proxy_manager")


@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/health")
def health_check():
    """
    应用健康检查接口。
    
    Returns:
        应用基本状态信息
    """
    return {
        "status": "healthy",
        "message": "Dispider Backend API is running",
        "version": "1.0.0"
    } 