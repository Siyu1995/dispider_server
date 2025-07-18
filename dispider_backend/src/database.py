from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import settings

# 数据库连接URL
# 从 settings 对象中读取数据库URL
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# 创建 SQLAlchemy 引擎
# connect_args 是特定于 aiosqlite 的，对于 PostgreSQL 不需要
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 创建一个 SessionLocal 类
# sessionmaker 是一个会话工厂，我们将用它来创建独立的数据库会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 创建所有模型类的基类
# declarative_base() 返回一个类，我们的模型将继承这个类。
# 这样，SQLAlchemy 就可以将 Python 类映射到数据库表。
Base = declarative_base()


# 数据库会话依赖项
def get_db():
    """
    FastAPI 依赖项：为每个请求创建一个新的 SQLAlchemy Session。

    这个函数是一个生成器，它会：
    1. 创建一个新的数据库会话 (db = SessionLocal())。
    2. 使用 `yield` 将这个会话提供给路径操作函数。
    3. 在请求处理完毕后（无论成功或失败），`finally` 块中的代码会执行，确保会话被关闭 (db.close())。
       这对于释放数据库连接、防止连接池耗尽至关重要。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 