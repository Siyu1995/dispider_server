# 使用官方 Python 镜像作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装依赖
# 单独复制 requirements.txt 可以利用 Docker 的层缓存机制，
# 仅当 requirements.txt 更改时才重新安装依赖。
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 暴露应用运行的端口
EXPOSE 8000

# 运行应用的命令
# 使用 uvicorn 启动 FastAPI 应用
# --host 0.0.0.0 使服务可以从容器外部访问
# --reload-dir src 让 uvicorn 只监控 src 目录下的文件变更，避免上传文件触发重载
# 假设主应用实例在 main.py 的 app 对象中
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload-dir", "src"] 