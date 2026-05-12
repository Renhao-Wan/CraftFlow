# CraftFlow 环境变量配置完整指南

> 本文档详细说明 CraftFlow 后端的环境变量配置体系，包括文件组织、加载逻辑、配置项说明和打包流程。

## 一、配置文件组织

### 1.1 文件清单

```
craftflow-backend/
├── .env.example      # 配置说明文档（列出所有配置项及详细说明）
├── .env.standalone   # 桌面端默认配置（可直接使用）
└── .env.server       # 服务端默认配置（可直接使用）
```

| 文件 | 用途 | 提交 Git |
|------|------|----------|
| `.env.example` | 配置说明文档，供开发者参考 | ✅ 是 |
| `.env.standalone` | 桌面端默认配置，包含合理默认值 | ✅ 是 |
| `.env.server` | 服务端默认配置，包含合理默认值 | ✅ 是 |

**注意**：以下文件不提交 Git，由用户本地创建：
- `.env.dev` — 本地开发配置（包含真实 API Key）
- `.env` — 用户自定义配置

### 1.2 文件定位

| 场景 | 使用的配置文件 |
|------|---------------|
| 桌面端开发 | `.env.standalone` 或 `.env.dev` |
| 服务端开发 | `.env.server` 或 `.env.dev` |
| 桌面端打包后 | `%APPDATA%/CraftFlow/.env`（首次运行从 `.env.standalone` 复制） |
| 生产环境部署 | `.env.server` 或自定义 `.env` |

---

## 二、配置加载逻辑

### 2.1 加载流程图

```
应用启动时，决定加载哪个 .env 文件？

                    ┌─────────────────────┐
                    │ 读取环境变量         │
                    │ CRAFTFLOW_ENV_FILE  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ 有值且文件存在？      │
                    └──────────┬──────────┘
                          是 / \ 否
                         /     \
                        ▼       ▼
              ┌──────────┐  ┌─────────────────────┐
              │ 使用该文件 │  │ 是否 PyInstaller 打包？│
              └──────────┘  └──────────┬──────────┘
                                  是 / \ 否
                                 /     \
                                ▼       ▼
                  ┌──────────────┐  ┌─────────────────────┐
                  │ %APPDATA%/   │  │ 读取环境变量          │
                  │ CraftFlow/   │  │ APP_MODE             │
                  │ .env         │  └──────────┬──────────┘
                  └──────────────┘             │
                                  ┌────────────▼────────────┐
                                  │ APP_MODE 的值是什么？      │
                                  └────────────┬────────────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          │                    │                    │
                          ▼                    ▼                    ▼
                   "standalone"           "server"               其他/无
                          │                    │                    │
                          ▼                    ▼                    ▼
                ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
                │.env.standalone│    │ .env.server  │    │   .env.dev   │
                │  存在？       │    │  存在？       │    │  (回退)      │
                └──────┬───────┘    └──────┬───────┘    └──────────────┘
                  是 / \ 否           是 / \ 否
                 /     \             /     \
                ▼       ▼           ▼       ▼
          使用该文件  .env.dev   使用该文件  .env.dev
```

### 2.2 加载优先级

| 优先级 | 方式 | 说明 |
|--------|------|------|
| 1 | `CRAFTFLOW_ENV_FILE` 环境变量 | 显式指定配置文件路径，最高优先级 |
| 2 | PyInstaller 打包环境 | 自动使用 `%APPDATA%/CraftFlow/.env` |
| 3 | `.env.{APP_MODE}` | 根据 APP_MODE 选择（standalone/server） |
| 4 | `.env.dev` | 最终回退 |

### 2.3 相关代码

**配置文件路径获取**：`app/core/config.py`

```python
def _get_env_file() -> str:
    """获取 .env 文件路径"""
    import os

    # 1. 显式指定（最高优先级）
    env_file = os.environ.get("CRAFTFLOW_ENV_FILE")
    if env_file and Path(env_file).is_file():
        return env_file

    # 2. 桌面版环境
    if _is_frozen():
        from desktop_config import get_env_file
        return str(get_env_file())

    # 3. 开发环境：根据 APP_MODE 选择
    base_dir = _get_base_dir()
    app_mode = os.environ.get("APP_MODE", "standalone")

    mode_env_file = base_dir / f".env.{app_mode}"
    if mode_env_file.is_file():
        return str(mode_env_file)

    # 回退
    return str(base_dir / ".env.dev")
```

**桌面版路径适配**：`desktop_config.py`

```python
def get_env_file() -> Path:
    """获取桌面版 .env 文件路径"""
    env_path = get_data_dir() / ".env"  # %APPDATA%/CraftFlow/.env

    if not env_path.exists():
        # 首次运行：从 .env.standalone 复制
        template_path = bundle_dir / ".env.standalone"
        shutil.copy2(template_path, env_path)

    return env_path
```

---

## 三、配置项说明

### 3.1 应用基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `APP_NAME` | str | CraftFlow Backend | 应用名称 |
| `APP_VERSION` | str | 0.1.0 | 应用版本 |
| `APP_MODE` | standalone/server | standalone | 运行模式 |
| `ENVIRONMENT` | development/production | development | 运行环境 |
| `DEBUG` | bool | true | 调试模式 |
| `LOG_LEVEL` | DEBUG/INFO/WARNING/ERROR | INFO | 日志级别 |

**APP_MODE 说明**：
- `standalone`：桌面端模式，SQLite 存储，无鉴权，零配置
- `server`：服务端模式，PostgreSQL 存储，API Key 鉴权

### 3.2 鉴权配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `ENABLE_AUTH` | bool | false | 是否启用 API Key 鉴权 |
| `API_KEY` | str | craftflow-dev-key | API Key，用于验证 Java 后端调用 |

**说明**：
- `standalone` 模式下 `ENABLE_AUTH` 自动禁用
- `server` 模式下建议启用，并修改 `API_KEY` 为强密钥
- 请求头 `X-API-Key` 传递 API Key

### 3.3 LLM 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `LLM_API_KEY` | str | - | LLM API 密钥（必填） |
| `LLM_API_BASE` | str | - | LLM API 基础 URL（可选） |
| `LLM_MODEL` | str | gpt-4-turbo | 默认 LLM 模型 |
| `MAX_TOKENS` | int | 4096 | 最大 Token 数（1-128000） |
| `DEFAULT_TEMPERATURE` | float | 0.7 | 默认温度参数（0.0-2.0） |

### 3.4 状态持久化配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `CHECKPOINTER_BACKEND` | memory/sqlite/postgres | sqlite | Checkpointer 后端 |
| `CHECKPOINT_DB_PATH` | str | data/checkpoints/checkpoints.db | SQLite Checkpointer 路径 |
| `TASKSTORE_BACKEND` | sqlite/postgres | sqlite | TaskStore 后端 |
| `TASKSTORE_DB_PATH` | str | data/sqlite/craftflow.db | SQLite TaskStore 路径 |
| `DATABASE_URL` | str | - | PostgreSQL 连接串 |
| `DB_POOL_SIZE` | int | 10 | 数据库连接池大小 |
| `DB_MAX_OVERFLOW` | int | 20 | 连接池最大溢出数 |

**后端选择**：
| 后端 | 适用场景 | 说明 |
|------|----------|------|
| `memory` | 快速调试 | 内存存储，进程退出即丢失 |
| `sqlite` | 桌面端/开发 | SQLite 持久化，零配置 |
| `postgres` | 服务端/生产 | PostgreSQL 持久化，高可用 |

**DATABASE_URL 格式**：
```
postgresql+asyncpg://user:password@host:port/dbname
```

### 3.5 外部工具配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `TAVILY_API_KEY` | str | - | Tavily Search API 密钥（互联网搜索） |
| `E2B_API_KEY` | str | - | E2B Code Interpreter API 密钥（代码沙箱） |

### 3.6 向量数据库配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `ENABLE_RAG` | bool | false | 是否启用 RAG 功能 |
| `VECTOR_DB_BACKEND` | pgvector/chroma | pgvector | 向量数据库后端 |
| `VECTOR_COLLECTION_NAME` | str | craftflow_docs | 向量数据库集合名称 |
| `EMBEDDING_MODEL` | str | text-embedding-3-small | Embedding 模型名称 |
| `EMBEDDING_API_KEY` | str | - | Embedding API 密钥（留空使用 LLM_API_KEY） |
| `EMBEDDING_API_BASE` | str | - | Embedding API 基础 URL（留空使用 LLM_API_BASE） |
| `EMBEDDING_DIMENSIONS` | int | 1536 | Embedding 向量维度 |

### 3.7 FastAPI 服务配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `HOST` | str | 0.0.0.0 | 服务监听地址 |
| `PORT` | int | 8000 | 服务监听端口 |
| `RELOAD` | bool | true | 热重载（仅开发环境） |
| `WORKERS` | int | 1 | 工作进程数 |
| `CORS_ORIGINS` | str | http://localhost:3000,http://localhost:5173 | 允许的跨域来源（逗号分隔） |
| `CORS_ALLOW_CREDENTIALS` | bool | true | 是否允许携带凭证 |

**HOST 说明**：
- `127.0.0.1`：仅本地访问（推荐桌面端）
- `0.0.0.0`：允许外部访问（推荐服务端）

### 3.8 Redis 配置（可选）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `REDIS_HOST` | str | localhost | Redis 主机地址 |
| `REDIS_PORT` | int | 6379 | Redis 端口 |
| `REDIS_PASSWORD` | str | - | Redis 密码 |
| `REDIS_DB` | int | 0 | Redis 数据库索引 |
| `REDIS_MAX_CONNECTIONS` | int | 20 | Redis 最大连接数 |

### 3.9 业务逻辑配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `MAX_OUTLINE_SECTIONS` | int | 10 | 大纲最大章节数（1-50） |
| `MAX_CONCURRENT_WRITERS` | int | 5 | 并发写作节点数量上限（1-20） |
| `MAX_DEBATE_ITERATIONS` | int | 3 | 对抗循环最大迭代次数（1-10） |
| `EDITOR_PASS_SCORE` | int | 90 | 主编通过分数阈值（0-100） |
| `TASK_TIMEOUT` | int | 3600 | 任务超时时间（秒，60-86400） |
| `TOOL_CALL_TIMEOUT` | int | 30 | 工具调用超时时间（秒，5-300） |

---

## 四、模式验证器

### 4.1 自动调整规则

配置加载后，`model_validator` 会根据 `APP_MODE` 自动调整配置：

```python
@model_validator(mode="after")
def validate_mode_config(self) -> "Settings":
    if self.app_mode == "standalone":
        # 桌面端模式：强制禁用鉴权
        self.enable_auth = False
        # 桌面端模式：强制使用 SQLite
        if self.checkpointer_backend == "postgres":
            self.checkpointer_backend = "sqlite"
        if self.taskstore_backend == "postgres":
            self.taskstore_backend = "sqlite"
    elif self.app_mode == "server":
        # 服务端模式：postgres 模式要求配置 database_url
        if (self.checkpointer_backend == "postgres" or
            self.taskstore_backend == "postgres") and not self.database_url:
            raise ValueError("server 模式下使用 postgres 后端时必须配置 DATABASE_URL")
    return self
```

### 4.2 调整规则汇总

| 模式 | 自动调整 |
|------|----------|
| `standalone` | `ENABLE_AUTH` 强制为 `false` |
| `standalone` | `CHECKPOINTER_BACKEND` 强制为 `sqlite`（如为 postgres） |
| `standalone` | `TASKSTORE_BACKEND` 强制为 `sqlite`（如为 postgres） |
| `server` | 使用 postgres 时，`DATABASE_URL` 必填（否则报错） |

---

## 五、打包流程

### 5.1 PyInstaller 打包

**配置文件**：`craftflow-desktop/backend/craftflow.spec`

```python
# 数据文件：复制 app/ 和 .env.standalone 到打包目录
datas=[
    (str(src_root / 'app'), 'app'),
    (str(src_root / '.env.standalone'), '.'),  # 桌面端默认配置
    (str(src_root / 'desktop_config.py'), '.'),
],
```

**打包产物**：
```
craftflow-desktop/backend/dist/craftflow/
├── _internal/
│   ├── .env.standalone    # 模板配置文件
│   ├── desktop_config.py  # 路径适配模块
│   └── ...
└── craftflow.exe          # 可执行文件
```

### 5.2 首次运行流程

```
用户首次运行 craftflow.exe
    │
    ▼
desktop_config.get_env_file()
    │
    ├─ 检查 %APPDATA%/CraftFlow/.env 是否存在
    │
    ├─ 不存在 → 从打包的 .env.standalone 复制
    │
    └─ 返回 %APPDATA%/CraftFlow/.env
```

### 5.3 用户配置目录

| 平台 | 数据目录 |
|------|----------|
| Windows | `%APPDATA%/CraftFlow/` |
| macOS | `~/.craftflow/` |
| Linux | `~/.craftflow/` |

目录内容：
```
%APPDATA%/CraftFlow/
├── .env                  # 用户配置（首次运行自动创建）
├── sqlite/
│   └── craftflow.db      # TaskStore 数据库
├── checkpoints/
│   └── checkpoints.db    # Checkpointer 数据库
└── logs/
    └── ...
```

---

## 六、使用示例

### 6.1 开发环境

```bash
# 方式 1：使用桌面端配置（推荐）
cp .env.standalone .env.dev
# 编辑 .env.dev，填写 LLM_API_KEY

# 方式 2：使用服务端配置
cp .env.server .env.dev
# 编辑 .env.dev，填写 DATABASE_URL 等

# 方式 3：使用启动脚本（自动创建 .env.dev）
scripts/dev.ps1    # Windows
scripts/dev.sh     # Linux/macOS
```

### 6.2 指定配置文件

```bash
# 方式 1：通过环境变量指定 APP_MODE
APP_MODE=server python -m app.main

# 方式 2：显式指定配置文件
CRAFTFLOW_ENV_FILE=/path/to/custom.env python -m app.main

# 方式 3：通过 uvicorn 参数
uv run uvicorn app.main:app --env-file .env.server
```

### 6.3 生产环境部署

```bash
# 1. 复制服务端配置
cp .env.server .env

# 2. 编辑配置
vi .env
# - 修改 API_KEY 为强密钥
# - 配置 DATABASE_URL
# - 配置 LLM_API_KEY

# 3. 启动服务
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 七、配置验证

### 7.1 验证脚本

```bash
# 运行配置验证脚本
uv run python scripts/check_config.py
```

### 7.2 验证内容

脚本会输出以下配置信息：
- 应用基础配置（APP_MODE、ENVIRONMENT 等）
- 鉴权配置（ENABLE_AUTH、API_KEY）
- LLM 配置
- 状态持久化配置（CHECKPOINTER_BACKEND、TASKSTORE_BACKEND）
- 外部工具配置
- 向量数据库配置
- FastAPI 服务配置
- 业务逻辑配置

---

## 八、常见问题

### Q1: 如何切换桌面端/服务端模式？

**开发环境**：
```bash
# 桌面端模式
APP_MODE=standalone python -m app.main

# 服务端模式
APP_MODE=server python -m app.main
```

**打包后**：编辑 `%APPDATA%/CraftFlow/.env`，修改 `APP_MODE`。

### Q2: 如何使用 PostgreSQL？

1. 设置 `APP_MODE=server`
2. 配置 `DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db`
3. 设置 `CHECKPOINTER_BACKEND=postgres`
4. 设置 `TASKSTORE_BACKEND=postgres`

### Q3: 如何禁用鉴权？

`standalone` 模式下鉴权自动禁用。如需在 `server` 模式下禁用：
```bash
ENABLE_AUTH=false
```

### Q4: 配置文件的优先级？

1. `CRAFTFLOW_ENV_FILE` 环境变量（最高）
2. PyInstaller 打包环境自动检测
3. `.env.{APP_MODE}` 文件
4. `.env.dev`（最低）

---

**文档版本**: v1.0  
**创建日期**: 2026-05-12  
**维护者**: Renhao-Wan
