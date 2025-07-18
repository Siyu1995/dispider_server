from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from src.auth.router import router as auth_router
from src.projects.router import router as projects_router
from src.tasks.router import router as tasks_router
from src.containers.router import router as project_containers_router, container_router as standalone_container_router
from src.database import engine, Base
from src.auth import models as auth_models
from fastapi.middleware.cors import CORSMiddleware


# 在应用启动时创建数据库表
# 注意：在一个使用 Alembic 进行数据库迁移的成熟项目中，下面这行代码通常应该被移除或注释掉。
# 数据库的创建和变更应完全由迁移脚本来管理，以确保版本控制和一致性。
# Base.metadata.create_all(bind=engine)

app = FastAPI()

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
app.include_router(auth_router, prefix="/api/auth")

# 包含来自 projects 模块的路由
app.include_router(projects_router, prefix="/api/projects")

# 包含来自 tasks 模块的路由
app.include_router(tasks_router, prefix="/api/projects")

# 包含与项目关联的容器路由
# 请注意，这个路由器的前缀与 projects_router 相同，这是因为它的 API 路径
# (例如 /api/projects/{project_id}/containers/batch/start) 是 projects 资源的子集
app.include_router(project_containers_router, prefix="/api/projects")

# 包含独立的容器管理路由
app.include_router(standalone_container_router, prefix="/api/containers")

@app.get("/")
def read_root():
    return {"Hello": "World"} 