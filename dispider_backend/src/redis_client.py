import redis
import os
from dotenv import load_dotenv
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 加载 .env 文件中的环境变量
load_dotenv()

# 从环境变量获取 Redis 配置，并提供默认值
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# 创建一个全局的 Redis 连接池
# 连接池允许多个 Redis 连接共享，避免了为每个请求创建和销毁连接的开销，
# 这对于高性能应用至关重要。
# decode_responses=True 确保从 Redis 获取的值是字符串而不是字节。
try:
    redis_pool = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )
    logger.info(f"成功创建到 Redis ({REDIS_HOST}:{REDIS_PORT}) 的连接池。")
except Exception as e:
    logger.error(f"创建 Redis 连接池失败: {e}", exc_info=True)
    redis_pool = None

def get_redis_client():
    """
    提供一个依赖注入函数，用于从连接池中获取一个 Redis 客户端实例。
    如果连接池未成功初始化，则会引发异常。

    Returns:
        A Redis client instance.

    Raises:
        ConnectionError: If the Redis connection pool is not available.
    """
    if not redis_pool:
        raise ConnectionError("Redis 连接池不可用，请检查服务是否已启动以及配置是否正确。")
    try:
        # 从连接池获取一个连接
        client = redis.Redis(connection_pool=redis_pool)
        # 测试连接是否正常
        client.ping()
        return client
    except redis.exceptions.ConnectionError as e:
        logger.error(f"无法连接到 Redis: {e}", exc_info=True)
        raise ConnectionError("无法连接到 Redis，请确认服务正在运行。")

# 这是一个可以直接使用的 Redis 客户端实例，主要用于非 FastAPI 应用部分或简单脚本
# 在 FastAPI 的依赖注入中，推荐使用 get_redis_client()
redis_client = get_redis_client() if redis_pool else None 