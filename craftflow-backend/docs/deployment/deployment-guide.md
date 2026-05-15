# CraftFlow 部署指南

> 本文档提供 CraftFlow Python 后端在不同场景下的部署方案，包括桌面端、开发环境和服务端生产环境。

## 一、部署场景总览

| 场景 | APP_MODE | 存储 | 鉴权 | 网络 | 说明 |
|------|----------|------|------|------|------|
| 桌面端 | standalone | SQLite | 无 | localhost | Electron 打包，零配置 |
| 本地开发 | standalone | SQLite | 无 | localhost | 开发调试 |
| 测试环境 | server | SQLite | 可选 | 0.0.0.0 | 有鉴权但本地存储 |
| 生产环境 | server | PostgreSQL | 开启 | 0.0.0.0 | 完整云端部署 |

## 二、环境要求

### 2.1 基础要求

- Python 3.11+
- uv（推荐）或 pip

### 2.2 按场景

| 依赖 | 桌面端 | 开发环境 | 生产环境 |
|------|--------|----------|----------|
| Python 3.11+ | ✅ | ✅ | ✅ |
| uv | ✅ | ✅ | ✅ |
| PostgreSQL 14+ | ❌ | ❌ | ✅（可选） |
| Redis | ❌ | ❌ | ❌（可选） |

## 三、桌面端部署（standalone 模式）

### 3.1 配置

使用 `.env.standalone` 模板，零配置启动：

```bash
APP_MODE=standalone
ENVIRONMENT=development
ENABLE_AUTH=false

CHECKPOINTER_BACKEND=sqlite
TASKSTORE_BACKEND=sqlite

LLM_API_KEY=sk-your-api-key
LLM_API_BASE=
LLM_MODEL=gpt-4-turbo
```

### 3.2 启动

```bash
cd craftflow-backend
uv sync
uv run uvicorn app.main:app --env-file .env.standalone --host 127.0.0.1 --port 8000
```

### 3.3 Electron 打包

桌面端通过 PyInstaller 打包为独立可执行文件：

```
craftflow-desktop/
├── backend/                    # Python 后端打包
│   ├── craftflow.spec          # PyInstaller 配置
│   └── dist/craftflow/         # 打包产物
├── frontend/                   # Vue 前端构建
└── electron/                   # Electron 主进程
```

**打包后数据目录**：
- Windows: `%APPDATA%/CraftFlow/`
- macOS/Linux: `~/.craftflow/`

**首次运行**：自动从打包的 `.env.standalone` 复制配置到数据目录。

## 四、本地开发部署

### 4.1 配置

复制模板为开发配置：

```bash
# 桌面端模式开发
cp .env.standalone .env.dev

# 或服务端模式开发
cp .env.server .env.dev
```

编辑 `.env.dev`，填写 `LLM_API_KEY`。

### 4.2 启动

```bash
cd craftflow-backend
uv sync
uv sync --extra dev

# 使用 uvicorn 热重载
uv run uvicorn app.main:app --reload --env-file .env.dev --host 127.0.0.1 --port 8000
```

### 4.3 前端联调

```bash
# 终端 1：启动后端
cd craftflow-backend
uv run uvicorn app.main:app --reload --env-file .env.dev --host 127.0.0.1 --port 8000

# 终端 2：启动前端
cd craftflow-web
npm run dev
```

前端开发服务器（Vite）会自动代理 `/api` 请求到后端 `localhost:8000`。

### 4.4 指定配置文件

```bash
# 方式 1：显式指定（推荐）
CRAFTFLOW_ENV_FILE=.env.server uv run uvicorn app.main:app

# 方式 2：uvicorn 参数（仅注入进程环境，不影响 Settings 的 env_file）
uv run uvicorn app.main:app --env-file .env.server
```

## 五、服务端部署（server 模式 + SQLite）

适用：小规模部署、测试环境、单机 server 模式。

### 5.1 配置

```bash
# 复制模板
cp .env.server .env

# 编辑配置
vi .env
```

关键配置：

```bash
APP_MODE=server
ENVIRONMENT=production
ENABLE_AUTH=true
API_KEY=your-strong-32char-random-key

CHECKPOINTER_BACKEND=sqlite
TASKSTORE_BACKEND=sqlite

LLM_API_KEY=sk-your-api-key
LLM_MODEL=gpt-4-turbo

HOST=0.0.0.0
PORT=8000
WORKERS=1
```

### 5.2 启动

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env
```

### 5.3 特点

- 有 API Key 鉴权保护
- 数据存本地 SQLite 文件
- 单进程，适合中小规模
- 无需外部数据库服务

## 六、服务端部署（server 模式 + PostgreSQL）

适用：生产环境、多实例部署、需要数据共享和高可用。

### 6.1 PostgreSQL 准备

```sql
-- 创建数据库
CREATE DATABASE craftflow;

-- 创建用户（可选）
CREATE USER craftflow WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE craftflow TO craftflow;
```

### 6.2 配置

```bash
cp .env.server .env
vi .env
```

关键配置：

```bash
APP_MODE=server
ENVIRONMENT=production
ENABLE_AUTH=true
API_KEY=your-strong-32char-random-key

CHECKPOINTER_BACKEND=postgres
TASKSTORE_BACKEND=postgres
DATABASE_URL=postgresql+asyncpg://craftflow:your-password@localhost:5432/craftflow
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

LLM_API_KEY=sk-your-api-key
LLM_MODEL=gpt-4-turbo

ENABLE_RAG=true
VECTOR_DB_BACKEND=pgvector

HOST=0.0.0.0
PORT=8000
WORKERS=4

CORS_ORIGINS=https://your-domain.com
```

### 6.3 启动

```bash
# 开发模式
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env

# 生产模式（Gunicorn + Uvicorn workers）
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --env-file .env
```

### 6.4 特点

- 完整的 API Key 鉴权
- PostgreSQL 持久化，支持多实例共享
- WebSocket 实时推送
- 支持 RAG（PGVector）
- 生产环境异常脱敏

## 七、反向代理配置

### 7.1 Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 超时设置（长任务）
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

### 7.2 CORS 配置

反向代理部署时，需要更新 CORS 配置：

```bash
CORS_ORIGINS=https://your-domain.com
CORS_ALLOW_CREDENTIALS=true
```

## 八、健康检查

所有部署模式下，`/health` 端点无需鉴权：

```bash
curl http://localhost:8000/health
```

响应：
```json
{
    "status": "ok",
    "version": "0.1.0",
    "mode": "server",
    "environment": "production"
}
```

可用于：
- 负载均衡器健康检查
- 容器编排探针（Kubernetes liveness/readiness probe）
- 监控系统探测

## 九、日志配置

```bash
# 日志级别
LOG_LEVEL=INFO    # DEBUG/INFO/WARNING/ERROR

# 调试模式（显示详细错误信息）
DEBUG=false       # 生产环境设为 false
```

日志输出到：
- 控制台（stdout）
- 文件（`logs/` 目录，Loguru 自动管理）

## 十、环境变量配置文件对照

| 文件 | 用途 | 代码加载 | 提交 Git |
|------|------|----------|----------|
| `.env.example` | 配置说明文档 | ❌ | ✅ |
| `.env.standalone` | 桌面端配置模板（供复制参考） | ❌ | ✅ |
| `.env.server` | 服务端配置模板（供复制参考） | ❌ | ✅ |
| `.env.dev` | 本地开发配置 | ✅ | ❌ |
| `.env` | 生产环境配置 | ✅ | ❌ |

代码加载优先级：`CRAFTFLOW_ENV_FILE` → PyInstaller → `.env.dev` → `.env`。

详细配置说明见 [环境变量配置指南](env-configuration-guide.md)。

## 十一、常见问题

### Q1: server 模式必须用 PostgreSQL 吗？

不是。server 模式支持 SQLite 和 PostgreSQL。只有选择 postgres 后端时才需要配置 `DATABASE_URL`。详见 [数据库设计文档](database-design.md)。

### Q2: 如何在 server 模式下禁用鉴权？

```bash
ENABLE_AUTH=false
```

但**不推荐**在生产环境禁用鉴权。

### Q3: 如何切换 standalone/server 模式？

`APP_MODE` 控制运行时行为（鉴权、存储后端校验），不影响配置文件选择。修改方式：

- **本地开发**：编辑 `.env.dev` 中的 `APP_MODE`
- **生产部署**：编辑 `.env` 中的 `APP_MODE`
- **切换配置文件**：使用 `CRAFTFLOW_ENV_FILE=.env.server`

需注意：
- standalone 模式下 postgres 会被自动降级为 sqlite
- standalone 模式下鉴权自动禁用

### Q4: WebSocket 在 standalone 模式下可用吗？

是的，所有模式（standalone 和 server）都支持 WebSocket。standalone 模式下无需 API Key 鉴权，直接连接即可。

### Q5: 多实例部署需要注意什么？

- 使用 PostgreSQL 作为 TaskStore 和 Checkpointer 后端
- 所有实例共享同一个 `DATABASE_URL` 和 `API_KEY`
- `_tasks` dict 是进程内存，多实例间不共享——任务查询会从 TaskStore 获取

---

**文档版本**: v1.0  
**创建日期**: 2026-05-12  
**维护者**: Renhao-Wan
