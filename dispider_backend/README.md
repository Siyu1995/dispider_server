# Dispider Backend

本项目是 Dispider 分布式爬虫管理与调度系统的后端服务。

## ✨ 功能特性

- 动态项目管理
- 任务分发与调度
- 结果收集与存储
- 容器生命周期管理

## 🚀 技术栈

- **框架:** FastAPI
- **数据库:** PostgreSQL
- **缓存:** Redis
- **容器化:** Docker, Docker Compose

## 🛠️ 开发环境设置

请按照以下步骤来设置和启动本地开发环境。

### 1. 先决条件

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

### 2. 环境配置

项目使用 `.env` 文件来管理环境变量。

首先，复制环境变量模板文件：

```bash
cp .env.example .env
```

然后，打开 `.env` 文件并根据您的需要修改其中的值（例如数据库密码）。

> **注意:** 如果您没有 `.env.example` 文件，请手动创建 `.env` 文件，并参考 `docker-compose.yml` 添加必要的环境变量，如 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` 等。

### 3. 启动服务

完成配置后，在项目根目录运行以下命令来构建并启动所有服务：

```bash
docker-compose up --build
```

该命令会：
- 基于 `Dockerfile` 构建后端服务的镜像。
- 拉取并启动 PostgreSQL 和 Redis 服务的镜像。
- 创建并挂载用于数据持久化的卷。
- 启动所有容器。

服务启动后，您可以访问 `http://localhost:8000/docs` 来查看 FastAPI 自动生成的 API 文档。

### 4. 停止服务

要停止所有正在运行的服务，请运行：

```bash
docker-compose down
``` 