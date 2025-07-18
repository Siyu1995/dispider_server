# **后端 API 文档 **

本文档旨在为前端开发人员提供后端 API 的详细参考。所有端点路径均已根据 `main.py` 中的全局前缀进行了修正。

## **通用响应格式**

所有成功的响应都遵循标准格式，但为了简洁，下面的文档将只展示 `data` 字段的内容。对于错误响应，请参考具体的 HTTP 状态码和返回的 `detail` 信息。

标准响应体结构:
```json
{
  "code": 200,
  "msg": "success",
  "data": { ... } // 实际业务数据
}
```

---

## **1. 认证模块 (Auth)**

- **全局前缀**: `/api/auth`
- **功能**: 负责用户注册、登录和身份验证。

### 1.1 用户登录获取 Token
- **功能**: 用户使用用户名和密码登录，获取用于后续请求的 `access_token`。
- **Endpoint**: `POST /api/auth/token`
- **请求格式**: `application/x-www-form-urlencoded` (表单数据: `username`, `password`)
- **返回结构**:
    ```json
    {
      "access_token": "string",
      "token_type": "bearer"
    }
    ```

### 1.2 注册新用户
- **功能**: 创建一个新用户账户。
- **Endpoint**: `POST /api/auth/users/register`
- **请求体**: `{"username", "password", "email", "pushme_key" | null, "is_super_admin"}`
- **返回结构**: `{"id", "username", "email", "pushme_key", "is_super_admin"}`

### 1.3 获取当前用户信息
- **功能**: 获取当前已登录用户的基础信息。
- **Endpoint**: `GET /api/auth/users/me`
- **认证**: Bearer Token
- **返回结构**: `{"id", "username", "email", "pushme_key", "is_super_admin"}`

### 1.4 检查超级管理员权限
- **功能**: 一个受保护的端点，用于验证当前用户是否为超级管理员。
- **Endpoint**: `GET /api/auth/users/me/admin`
- **调用方式**:
    - **认证**: 仅限超级管理员的 Bearer Token。
- **返回结构** (`data` 字段):
    ```json
    {
      "message": "Welcome super admin aaaaa"
    }
    ```

### 1.5 获取所有用户列表
- **功能**: 获取系统中的所有用户列表（仅限超级管理员）。
- **Endpoint**: `GET /api/auth/users`
- **认证**: 仅限超级管理员的 Bearer Token。
- **返回结构**: (列表)
    ```json
    [
      {
        "id": "integer",
        "username": "string",
        "email": "string",
        "pushme_key": "string" | null,
        "is_super_admin": "boolean"
      }
    ]
    ```

---

## **2. 项目模块 (Projects)**

- **全局前缀**: `/api/projects`
- **功能**: 管理项目本身的核心信息、代码和成员。

### 2.1 获取项目列表
- **功能**: 获取用户参与的所有项目列表，超级管理员可获取全部项目。
- **Endpoint**: `GET /api/projects/`
- **认证**: Bearer Token
- **返回结构**: (列表)
    ```json
    [
      {
        "id": integer,
        "name": "string",
        "status": "active" | "archived",
        "settings": {} | null,
        "role": "project_owner" | "project_admin" | "project_member" | null
      }
    ]
    ```

### 2.2 获取单个项目详情
- **功能**: 获取指定项目的详细信息。
- **Endpoint**: `GET /api/projects/{project_id}`
- **认证**: 项目成员及以上
- **路径参数**: `project_id` (integer)
- **返回结构**:
    ```json
    {
      "id": integer,
      "name": "string",
      "status": "active" | "archived",
      "settings": {} | null,
      "role": "project_owner" | "project_admin" | "project_member" | null
    }
    ```

### 2.3 创建新项目
- **功能**: 创建一个新项目 (仅限超级管理员)。
- **Endpoint**: `POST /api/projects/`
- **认证**: 超级管理员
- **请求体**: `{"name": "string", "settings": {} | null}`
- **返回结构**: `{"id", "name", "status", "settings"}`

### 2.4 更新项目状态
- **功能**: 更新项目状态 (激活/归档)，仅限超级管理员。
- **Endpoint**: `PATCH /api/projects/{project_id}/status`
- **认证**: 超级管理员
- **请求体**: `{"status": "active" | "archived"}`
- **返回结构**: `{"id", "name", "status", "settings"}`

### 2.5 上传项目代码包
- **功能**: 上传 ZIP 格式的代码包 (项目所有者及以上)。
- **Endpoint**: `POST /api/projects/{project_id}/code`
- **认证**: 项目所有者及以上
- **请求格式**: `multipart/form-data` (表单字段: `file`)
- **返回结构**: `{"message": "string", "file_path": "string"}`

### 2.6 获取项目代码文件列表
- **功能**: 获取指定项目代码目录下的所有文件名 (项目成员及以上)。
- **Endpoint**: `GET /api/projects/{project_id}/files`
- **认证**: 项目成员及以上
- **返回结构**:
    ```json
    {
      "files": ["string"]
    }
    ```

### 2.7 获取项目成员列表
- **功能**: 获取项目的所有成员及其角色 (项目成员及以上)。
- **Endpoint**: `GET /api/projects/{project_id}/members`
- **认证**: 项目成员及以上
- **返回结构**: `[{"user_id", "role", "id", "project_id"}]`

### 2.8 邀请新成员
- **功能**: 邀请用户加入项目并分配角色 (项目管理员及以上)。
- **Endpoint**: `POST /api/projects/{project_id}/members`
- **认证**: 项目管理员及以上
- **请求体**: `{"user_id": integer, "role": "project_admin" | "project_member"}`
- **返回结构**: `{"user_id", "role", "id", "project_id"}`

### 2.9 更新成员角色
- **功能**: 更新项目成员的角色 (项目管理员及以上)。
- **Endpoint**: `PUT /api/projects/{project_id}/members/{user_id}`
- **认证**: 项目管理员及以上
- **返回结构**: `{"user_id", "role", "id", "project_id"}`

### 2.10 移除项目成员
- **功能**: 从项目中移除一个成员 (项目管理员及以上)。
- **Endpoint**: `DELETE /api/projects/{project_id}/members/{user_id}`
- **认证**: 项目管理员及以上
- **返回**: `204 No Content`

---

## **3. 任务模块 (Tasks)**

- **全局前缀**: `/api/projects/{project_id}`
- **功能**: 管理特定项目下的任务、结果、表结构等。

### 3.1 获取表结构
- **功能**: 获取任务表和结果表的用户自定义列名。
- **Endpoint**: `GET /api/projects/{project_id}/tasks/schema`
- **认证**: 项目成员及以上
- **返回结构**:
    ```json
    {
      "task_columns": ["string"],
      "result_columns": ["string"]
    }
    ```

### 3.2 初始化任务表
- **功能**: 为项目创建或重建任务表 (项目所有者及以上)。
- **Endpoint**: `POST /api/projects/{project_id}/tasks/table`
- **认证**: 项目所有者及以上
- **请求体**: `{"columns": ["string"]}`
- **返回结构**: `{"message": "任务表已成功初始化。"}`

### 3.3 初始化结果表
- **功能**: 为项目创建或重建结果表 (项目所有者及以上)。
- **Endpoint**: `POST /api/projects/{project_id}/tasks/results/table`
- **认证**: 项目所有者及以上
- **请求体**: `{"columns": ["string"]}`
- **返回结构**: `{"message": "结果表已成功初始化。"}`

### 3.4 批量添加任务
- **功能**: 向项目的任务表中批量添加数据 (项目成员及以上)。
- **Endpoint**: `POST /api/projects/{project_id}/tasks`
- **认证**: 项目成员及以上
- **请求体**: (列式数据)
    ```json
    { "url": ["http://a.com"], "user_id": [101] }
    ```
- **返回结构**: `{"message": "任务批量添加成功", "inserted_count": integer}`

### 3.5 获取任务表列名
- **功能**: 获取任务表的用户自定义列名列表。
- **Endpoint**: `GET /api/projects/{project_id}/tasks/columns`
- **认证**: 项目成员及以上
- **返回结构**: `["string"]`

### 3.6 获取结果表列名
- **功能**: 获取结果表的用户自定义列名列表。
- **Endpoint**: `GET /api/projects/{project_id}/tasks/results/columns`
- **认证**: 项目成员及以上
- **返回结构**: `["string"]`

### 3.7 获取任务完成度
- **功能**: 获取项目当前任务的完成比例 (0.0 到 1.0 之间)，保留四位小数。
- **Endpoint**: `GET /api/projects/{project_id}/tasks/progress`
- **认证**: 项目成员及以上
- **返回结构**: `0.7556` (示例)

### 3.8 获取结果总数
- **功能**: 获取项目结果表的总行数。
- **Endpoint**: `GET /api/projects/{project_id}/tasks/results/count`
- **认证**: 项目成员及以上
- **返回结构**: `12345` (示例)

### 3.9 获取下一个待处理任务
- **功能**: 原子化地获取一个待处理任务。
- **Endpoint**: `GET /api/projects/{project_id}/tasks/next?worker_id={worker_id}`
- **查询参数**: `worker_id` (string, required)
- **返回**:
    - `200 OK`: `{"id": integer, "data": {}}`
    - `204 No Content`: 无可用任务

### 3.10 提交任务结果
- **功能**: 工作节点提交已完成任务的结果。
- **Endpoint**: `POST /api/projects/{project_id}/tasks/{task_id}/result`
- **请求体**: `{"url": "http://a.com", "title": "Title"}`
- **返回结构**: `{"message": "任务 {task_id} 的结果已成功提交。"}`

### 3.11 报告任务失败
- **功能**: 工作节点报告任务执行失败。
- **Endpoint**: `POST /api/projects/{project_id}/tasks/{task_id}/fail`
- **请求体** (可选): `{"error": "string"}`
- **返回结构**: `{"message": "已收到任务 {task_id} 的失败报告。"}`

---

## **4. 容器模块 (Containers)**

- **功能**: 管理与项目关联或独立的工作容器。

### **项目关联的容器**
- **全局前缀**: `/api/projects/{project_id}/containers`

#### 4.1.1 批量启动容器
- **功能**: 为指定项目批量创建并启动工作容器。
- **Endpoint**: `POST /api/projects/{project_id}/containers/batch/start`
- **认证**: Bearer Token
- **请求体**:
    ```json
    {
      "container_count": integer,
      "image": "my-crawler:latest",
      "volumes": { "host_path": "container_path" } | null,
      "proxy_config": { "HTTP_PROXY": "http://user:pass@host:port" } | null
    }
    ```
- **返回结构**: `{"message", "started_containers": [...]}`

#### 4.1.2 报告容器状态
- **功能**: 容器上报其当前状态。
- **Endpoint**: `POST /api/projects/{project_id}/containers/{worker_id}/status`
- **请求体**: `{"status": "string", "message": "string" | null}`
- **返回结构**: `{"message": "状态已成功记录。"}`

#### 4.1.3 获取容器警报
- **功能**: 获取所有需要人工干预的容器警报。
- **Endpoint**: `GET /api/projects/{project_id}/containers/alerts`
- **认证**: Bearer Token
- **返回结构**: `[{"worker_id", "project_id", "status", "message"}]`

### **独立容器管理**
- **全局前缀**: `/api/containers`

#### 4.2.1 停止容器
- **功能**: 停止一个正在运行的容器。
- **Endpoint**: `POST /api/containers/{container_db_id}/stop`
- **认证**: Bearer Token
- **返回结构**: `{"id", "container_id", "container_name", "status", "project_id"}`

#### 4.2.2 重启容器
- **功能**: 重启一个已存在的容器。
- **Endpoint**: `POST /api/containers/{container_db_id}/restart`
- **认证**: Bearer Token
- **返回结构**: (同上)

#### 4.2.3 移除容器
- **功能**: 停止并删除一个容器及其在数据库中的记录。
- **Endpoint**: `DELETE /api/containers/{container_db_id}`
- **认证**: Bearer Token
- **返回**: `204 No Content`