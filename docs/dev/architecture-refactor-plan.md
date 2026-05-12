# CraftFlow 架构改造计划：一套代码配置驱动

> 本文档规划了 CraftFlow 从当前"双端硬编码"演进为"一套代码、配置驱动"架构的详细实施方案。

## 一、改造背景与目标

### 1.1 当前问题

当前 CraftFlow 同时维护桌面端和网页端，但存在以下架构问题：

| 问题 | 影响 |
|------|------|
| 数据库硬编码 | TaskStore 仅支持 SQLite，无法切换 PostgreSQL |
| 无运行模式区分 | 桌面端和服务端共用同一配置，无法差异化启动 |
| 鉴权机制缺失 | 所有 API 端点完全开放，无安全防护 |
| 配置分散 | 数据库路径、连接串等散落在各模块中 |
| 依赖注入固化 | 服务初始化逻辑硬编码，无法根据模式动态组装 |

### 1.2 改造目标

遵循 **12-Factor App** 架构规范，实现：

```
┌─────────────────────────────────────────────────────────────┐
│                    一套 Python 后端代码                        │
├─────────────────────────────────────────────────────────────┤
│  通过 .env 环境变量驱动：                                      │
│  - APP_MODE: standalone / server                             │
│  - ENABLE_AUTH: true / false                                 │
│  - API_KEY: xxx (验证 Java 后端调用)                          │
│  - CHECKPOINTER_BACKEND: memory / sqlite / postgres          │
│  - TASKSTORE_BACKEND: sqlite / postgres                      │
│  - DATABASE_URL: postgresql+asyncpg://... 或 sqlite:///...   │
└─────────────────────────────────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                              ▼
    ┌───────────────┐              ┌───────────────┐
    │   桌面端模式    │              │   服务端模式    │
    │  (standalone)  │              │   (server)     │
    ├───────────────┤              ├───────────────┤
    │ SQLite        │              │ PostgreSQL    │
    │ 无鉴权        │              │ API Key 鉴权  │
    │ localhost     │              │ 云端部署      │
    │ 零配置启动    │              │ 高可用        │
    └───────────────┘              └───────────────┘
```

### 1.3 核心原则

1. **单一代码库**：绝对不开两个分支，业务逻辑只有一份
2. **配置驱动**：所有差异化行为通过环境变量控制
3. **工厂模式**：存储组件通过工厂方法创建，运行时动态绑定
4. **渐进式改造**：分阶段实施，每阶段可独立验证

---

## 二、当前架构分析

### 2.1 配置系统现状 (`app/core/config.py`)

**已有配置项**：

| 分组 | 配置项 | 状态 |
|------|--------|------|
| 应用基础 | `app_name`, `environment`(dev/prod), `debug` | ✅ 已有 |
| LLM | `llm_api_key`, `llm_api_base`, `llm_model` | ✅ 已有 |
| Checkpointer | `checkpointer_backend`(memory/sqlite/postgres), `database_url` | ✅ 已有 |
| 向量数据库 | `enable_rag`, `vector_db_backend` | ✅ 已有 |
| FastAPI | `host`, `port`, `cors_origins` | ✅ 已有 |
| Redis | `redis_host/port/password` | ⚠️ 已定义未使用 |

**缺失配置项**：

| 配置项 | 用途 | 优先级 |
|--------|------|--------|
| `APP_MODE` | 区分 standalone/server 模式 | P0 |
| `ENABLE_AUTH` | 鉴权开关（API Key 验证） | P0 |
| `API_KEY` | 服务端 API Key，用于验证 Java 后端调用 | P0 |
| `TASKSTORE_BACKEND` | TaskStore 存储后端选择 | P0 |
| `TASKSTORE_DB_PATH` | SQLite TaskStore 路径 | P1 |
| `CHECKPOINT_DB_PATH` | SQLite Checkpointer 路径 | P1 |

### 2.2 Checkpointer 现状 (`app/services/checkpointer.py`)

**设计良好**，已采用抽象工厂模式：

```python
# 已实现的工厂类
CheckpointerFactory (基类)
├── MemoryCheckpointerFactory    → MemorySaver
├── SqliteCheckpointerFactory    → AsyncSqliteSaver
└── PostgresCheckpointerFactory  → AsyncPostgresSaver
```

**改造成本**：低。主要改进点：
- SQLite 路径应从配置读取
- PostgresCloser 的健壮性需要增强

### 2.3 TaskStore 现状 (`app/services/task_store.py`)

**设计缺陷**：纯 SQLite 实现，无抽象接口。

```python
# 当前实现：硬编码 SQLite
class TaskStore:
    def __init__(self, db_path: Path = _DB_PATH):
        self._db_path = db_path
        # ... 直接使用 aiosqlite
```

**改造成本**：高。需要：
1. 抽取 `AbstractTaskStore` 接口
2. 实现 `SqliteTaskStore` 和 `PostgresTaskStore`
3. 配置驱动选择

### 2.4 依赖注入现状 (`app/api/dependencies.py`)

**当前模式**：手动单例 + FastAPI Depends

```python
# 模块级单例变量
_creation_service: CreationService | None = None
_polishing_service: PolishingService | None = None
_task_store: TaskStore | None = None
```

**改造需求**：
- 根据 `APP_MODE` 动态决定初始化哪些服务
- 将 `_load_interrupted_tasks()` 内聚到 Service 内部
- 引入显式的初始化编排机制

### 2.5 鉴权现状

**完全缺失**：
- 无 User 模型
- 无 JWT/Token 验证
- 无 API Key 校验
- 无速率限制
- WebSocket 无认证

---

## 三、改造方案设计

### 3.1 配置层改造

#### 3.1.1 新增配置项

```python
# app/core/config.py 新增配置项

class Settings(BaseSettings):
    # ===== 应用模式 =====
    app_mode: Literal["standalone", "server"] = "standalone"
    """运行模式：
    - standalone: 桌面端模式，SQLite，无鉴权，localhost
    - server: 服务端模式，PostgreSQL，JWT 鉴权，云端部署
    """

    # ===== 鉴权配置 =====
    enable_auth: bool = False
    """是否启用 API Key 鉴权。standalone 模式下自动禁用"""

    api_key: str = "craftflow-dev-key"
    """API Key，用于验证 Java 后端调用。server 模式下必须修改"""

    # ===== TaskStore 配置 =====
    taskstore_backend: Literal["sqlite", "postgres"] = "sqlite"
    """TaskStore 存储后端"""

    taskstore_db_path: str = "data/sqlite/craftflow.db"
    """SQLite TaskStore 数据库路径，仅 taskstore_backend=sqlite 时生效"""

    # ===== Checkpointer 配置增强 =====
    checkpoint_db_path: str = "data/checkpoints/checkpoints.db"
    """SQLite Checkpointer 数据库路径，仅 checkpointer_backend=sqlite 时生效"""

    # ===== 数据库连接（PostgreSQL） =====
    database_url: str = ""
    """PostgreSQL 连接串，taskstore_backend=postgres 或 checkpointer_backend=postgres 时必填"""

    @model_validator(mode="after")
    def validate_mode_config(self) -> "Settings":
        """根据 APP_MODE 自动调整配置"""
        if self.app_mode == "standalone":
            # 桌面端模式强制使用 SQLite 和无鉴权
            self.enable_auth = False
            if not self.taskstore_backend:
                self.taskstore_backend = "sqlite"
            if not self.checkpointer_backend:
                self.checkpointer_backend = "sqlite"
        elif self.app_mode == "server":
            # 服务端模式要求数据库配置
            if not self.database_url:
                raise ValueError("server 模式下必须配置 DATABASE_URL")
        return self
```

#### 3.1.2 环境文件模板

**桌面端 `.env.standalone`**：
```bash
# CraftFlow 桌面端配置
APP_MODE=standalone
ENABLE_AUTH=false

# 存储配置（SQLite）
CHECKPOINTER_BACKEND=sqlite
CHECKPOINT_DB_PATH=data/checkpoints/checkpoints.db
TASKSTORE_BACKEND=sqlite
TASKSTORE_DB_PATH=data/sqlite/craftflow.db

# LLM 配置
LLM_API_KEY=your_api_key
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4

# 禁用 RAG（可选）
ENABLE_RAG=false
```

**服务端 `.env.server`**：
```bash
# CraftFlow 服务端配置
APP_MODE=server
ENABLE_AUTH=true
API_KEY=your-strong-api-key-here

# 存储配置（PostgreSQL）
CHECKPOINTER_BACKEND=postgres
TASKSTORE_BACKEND=postgres
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/craftflow

# LLM 配置
LLM_API_KEY=your_api_key
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4

# RAG 配置（可选）
ENABLE_RAG=true
VECTOR_DB_BACKEND=pgvector
```

### 3.2 TaskStore 抽象层改造

#### 3.2.1 抽象接口定义

```python
# app/services/task_store.py

from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.response import TaskStatusResponse

class AbstractTaskStore(ABC):
    """TaskStore 抽象接口"""

    @abstractmethod
    async def init_db(self) -> None:
        """初始化数据库连接和表结构"""
        pass

    @abstractmethod
    async def save_task(self, task_id: str, task_data: dict) -> None:
        """保存或更新任务"""
        pass

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[dict]:
        """获取任务详情"""
        pass

    @abstractmethod
    async def get_interrupted_tasks(self) -> list[dict]:
        """获取所有中断的任务"""
        pass

    @abstractmethod
    async def get_task_list(
        self,
        graph_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """获取任务列表"""
        pass

    @abstractmethod
    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭数据库连接"""
        pass
```

#### 3.2.2 SQLite 实现

```python
# app/services/task_store_sqlite.py

import aiosqlite
from pathlib import Path
from app.services.task_store import AbstractTaskStore

class SqliteTaskStore(AbstractTaskStore):
    """SQLite TaskStore 实现"""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db: Optional[aiosqlite.Connection] = None

    async def init_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                graph_type TEXT NOT NULL,
                status TEXT NOT NULL,
                topic TEXT,
                description TEXT,
                content TEXT,
                mode INTEGER,
                result TEXT,
                error TEXT,
                progress REAL DEFAULT 100.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await self._db.commit()

    # ... 其他方法实现（从现有代码迁移）
```

#### 3.2.3 PostgreSQL 实现

```python
# app/services/task_store_postgres.py

import asyncpg
from app.services.task_store import AbstractTaskStore

class PostgresTaskStore(AbstractTaskStore):
    """PostgreSQL TaskStore 实现"""

    def __init__(self, database_url: str):
        self._database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None

    async def init_db(self) -> None:
        self._pool = await asyncpg.create_pool(self._database_url)
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id VARCHAR(64) PRIMARY KEY,
                    graph_type VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    topic TEXT,
                    description TEXT,
                    content TEXT,
                    mode INTEGER,
                    result TEXT,
                    error TEXT,
                    progress REAL DEFAULT 100.0,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)

    # ... 其他方法实现（SQL 语法适配 PostgreSQL）
```

#### 3.2.4 工厂函数

```python
# app/services/task_store.py (追加)

def create_task_store() -> AbstractTaskStore:
    """根据配置创建 TaskStore 实例"""
    from app.core.config import settings

    if settings.taskstore_backend == "sqlite":
        from app.services.task_store_sqlite import SqliteTaskStore
        return SqliteTaskStore(db_path=settings.taskstore_db_path)
    elif settings.taskstore_backend == "postgres":
        from app.services.task_store_postgres import PostgresTaskStore
        if not settings.database_url:
            raise ValueError("PostgreSQL 模式下必须配置 DATABASE_URL")
        return PostgresTaskStore(database_url=settings.database_url)
    else:
        raise ValueError(f"不支持的 TaskStore 后端: {settings.taskstore_backend}")
```

### 3.3 鉴权模块设计

#### 3.3.1 职责划分

**核心原则**：Python 后端只做 AI 能力，不处理用户管理。鉴权由 CraftFlow Java 后端负责。

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端（桌面端/网页端）                      │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Java 后端（CraftFlow 业务层）                   │
│  - 用户注册/登录                                                  │
│  - JWT 签发/验证                                                 │
│  - 权限校验、配额管理                                              │
│  - 任务路由、结果缓存                                              │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Python 后端（CraftFlow AI 层）                  │
│  - API Key 验证（验证调用方是否合法）                               │
│  - LangGraph 执行                                               │
│  - LLM 调用、工具链                                               │
│  - 任务状态管理                                                   │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.3.2 Python 后端鉴权方案

Python 后端采用**轻量级 API Key 验证**，而非 JWT：

| 模式 | 鉴权方式 | 说明 |
|------|----------|------|
| `standalone` | 无鉴权 | 桌面端单机使用，直接放行 |
| `server` | API Key 验证 | 验证请求头中的 API Key，确认调用方是合法的 Java 后端 |

**为什么不用 JWT？**
1. JWT 签发/验证是业务层职责，Python 后端不应该有用户信息
2. Python 后端只关心"谁在调用我"（Java 后端），不关心"用户是谁"
3. 简化 Python 后端的依赖和复杂度
4. API Key 足以保护内网服务，JWT 留给 Java 后端处理客户端鉴权

#### 3.3.3 API Key 验证实现

```python
# app/core/auth.py

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from app.core.config import settings

# API Key 从请求头 X-API-Key 读取
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(
    api_key: str | None = Depends(api_key_header),
) -> dict:
    """验证 API Key，返回调用方信息"""
    if not settings.enable_auth:
        # standalone 模式：无鉴权，返回默认调用方
        return {"caller": "local", "authenticated": True}

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供 API Key",
        )

    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无效的 API Key",
        )

    return {"caller": "java-backend", "authenticated": True}
```

#### 3.3.4 路由鉴权注入

```python
# app/api/v1/creation.py (改造后)

from fastapi import APIRouter, Depends
from app.core.auth import verify_api_key

router = APIRouter()

@router.post("/creation")
async def create_creation_task(
    request: CreationRequest,
    caller: dict = Depends(verify_api_key),  # 注入鉴权
    svc: CreationService = Depends(get_creation_service),
):
    # caller 在 standalone 模式下为 {"caller": "local"}
    # server 模式下为 {"caller": "java-backend"}
    ...
```

#### 3.3.5 WebSocket 鉴权

```python
# app/api/v1/ws.py (改造后)

async def ws_endpoint(websocket: WebSocket):
    # 从查询参数获取 API Key
    api_key = websocket.query_params.get("api_key")

    if settings.enable_auth:
        if api_key != settings.api_key:
            await websocket.close(code=4001, reason="无效的 API Key")
            return

    await websocket.accept()
    # ... 后续逻辑
```

#### 3.3.6 Java 后端鉴权职责（参考）

Java 后端负责完整的用户鉴权流程：

```java
// Java 后端鉴权流程（参考）
@RestController
public class TaskController {

    @PostMapping("/api/tasks")
    public ResponseEntity<?> createTask(
        @RequestHeader("Authorization") String jwtToken,  // 客户端 JWT
        @RequestBody TaskRequest request
    ) {
        // 1. 验证客户端 JWT
        User user = jwtService.validateToken(jwtToken);

        // 2. 检查用户配额
        quotaService.checkQuota(user);

        // 3. 调用 Python 后端（携带 API Key）
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-API-Key", pythonBackendApiKey);

        ResponseEntity<TaskResponse> response = restTemplate.exchange(
            pythonBackendUrl + "/api/v1/creation",
            HttpMethod.POST,
            new HttpEntity<>(request, headers),
            TaskResponse.class
        );

        return response;
    }
}
```

### 3.4 依赖注入改造

#### 3.4.1 模式感知的初始化编排

```python
# app/api/dependencies.py (改造后)

from app.core.config import settings

# 服务实例容器
_services: dict = {}

async def init_services() -> None:
    """根据 APP_MODE 初始化服务"""
    from app.services.checkpointer import init_checkpointer
    from app.services.task_store import create_task_store

    # 初始化 Checkpointer
    await init_checkpointer()

    # 初始化 TaskStore（配置驱动）
    task_store = create_task_store()
    await task_store.init_db()
    _services["task_store"] = task_store

    # 初始化业务服务
    from app.services.creation_svc import CreationService
    from app.services.polishing_svc import PolishingService

    checkpointer = get_checkpointer()
    _services["creation_service"] = CreationService(checkpointer, task_store)
    _services["polishing_service"] = PolishingService(checkpointer, task_store)

    # 恢复中断任务
    await _load_interrupted_tasks()

    # server 模式下可额外初始化 Redis、监控等
    if settings.app_mode == "server":
        await _init_server_components()

async def _init_server_components() -> None:
    """服务端模式额外组件初始化"""
    # Redis 连接池
    # 监控指标收集
    # ...
```

#### 3.4.2 条件化服务注册

```python
# app/main.py (改造后)

from contextlib import asynccontextmanager
from app.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logger()
    await init_services()

    if settings.app_mode == "server":
        await init_ws_services()  # WebSocket 仅服务端需要

    yield

    # Shutdown
    await close_services()
    await close_checkpointer()
```

### 3.5 数据库连接统一管理（可选）

如果未来需要统一管理 PostgreSQL 连接池：

```python
# app/core/database.py

from typing import Optional
import asyncpg

class DatabaseManager:
    """统一数据库连接管理"""

    _instance: Optional["DatabaseManager"] = None
    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    def get_instance(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def init_pool(self, database_url: str, **kwargs) -> None:
        self._pool = await asyncpg.create_pool(database_url, **kwargs)

    async def get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("数据库连接池未初始化")
        return self._pool

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
```

---

## 四、详细实施步骤

### Phase 1：配置层改造 ✅ 已完成

| 步骤 | 任务 | 涉及文件 | 验证方式 | 状态 |
|------|------|----------|----------|------|
| 1.1 | 新增 `APP_MODE`, `ENABLE_AUTH`, `TASKSTORE_BACKEND` 等配置项 | `app/core/config.py` | 运行 `check_config.py` 验证 | ✅ |
| 1.2 | 添加 `model_validator` 实现模式自动调整 | `app/core/config.py` | 单元测试 | ✅ |
| 1.3 | 创建 `.env.standalone` 和 `.env.server` 模板 | 项目根目录 | 手动验证 | ✅ |
| 1.4 | 统一 `_get_env_file()` 逻辑，消除硬编码 | `app/core/config.py` | 桌面端/服务端启动验证 | ✅ |

### Phase 2：TaskStore 抽象化 ✅ 已完成

| 步骤 | 任务 | 涉及文件 | 验证方式 | 状态 |
|------|------|----------|----------|------|
| 2.1 | 定义 `AbstractTaskStore` 接口 | `app/services/task_store.py` | 类型检查通过 | ✅ |
| 2.2 | 抽取 `SqliteTaskStore` 实现 | `app/services/task_store_sqlite.py` | 现有测试通过 | ✅ |
| 2.3 | 实现 `PostgresTaskStore` | `app/services/task_store_postgres.py` | 新增 PG 测试 | ✅ |
| 2.4 | 实现 `create_task_store()` 工厂函数 | `app/services/task_store.py` | 配置切换验证 | ✅ |
| 2.5 | 修改 `dependencies.py` 使用工厂函数 | `app/api/dependencies.py` | 启动验证 | ✅ |

**完成内容**：
- `task_store.py` 重构为抽象接口 + 工厂函数，保留 `TaskStore` 别名向后兼容
- `task_store_sqlite.py`：从原 `task_store.py` 提取，支持桌面端 `%APPDATA%` 路径
- `task_store_postgres.py`：基于 asyncpg 连接池的 PostgreSQL 实现
- `dependencies.py`：使用 `create_task_store()` 工厂替代直接实例化
- 所有类型引用更新为 `AbstractTaskStore`（creation_svc, polishing_svc, tasks.py, 测试）

### Phase 3：鉴权模块 ✅ 已完成

| 步骤 | 任务 | 涉及文件 | 验证方式 | 状态 |
|------|------|----------|----------|------|
| 3.1 | 实现 `auth.py` API Key 验证模块 | `app/core/auth.py` | 单元测试 | ✅ |
| 3.2 | 添加 `verify_api_key` 依赖 | `app/core/auth.py` | 集成测试 | ✅ |
| 3.3 | 改造 REST 路由注入鉴权 | `app/api/v1/*.py` | 有/无 API Key 测试 | ✅ |
| 3.4 | 改造 WebSocket 鉴权 | `app/api/v1/ws.py` | 连接测试 | ✅ |
| 3.5 | 生产环境异常信息脱敏 | `app/core/exceptions.py` | 安全审查 | ✅ |

**完成内容**：
- `auth.py`：实现 `verify_api_key`（REST 鉴权依赖）和 `verify_ws_api_key`（WebSocket 鉴权），standalone 模式自动放行，server 模式验证 `X-API-Key` 请求头
- `creation.py`、`polishing.py`、`tasks.py`：所有 REST 端点注入 `verify_api_key` 依赖
- `ws.py`：WebSocket 连接建立前通过查询参数 `api_key` 验证
- `exceptions.py`：生产环境下 `craftflow_exception_handler` 和 `generic_exception_handler` 隐藏内部实现细节（`details` 和 `exception_type`）
- `app/core/__init__.py`：导出 `verify_api_key` 和 `verify_ws_api_key`
- `tests/test_auth.py`：13 个测试覆盖 standalone/server 模式、REST/WebSocket 鉴权、集成测试（401/403/200）

### Phase 4：依赖注入改造（预计 1-2 天）

| 步骤 | 任务 | 涉及文件 | 验证方式 |
|------|------|----------|----------|
| 4.1 | 重构 `init_services()` 支持模式感知 | `app/api/dependencies.py` | 两种模式启动验证 |
| 4.2 | 将 `_load_interrupted_tasks()` 内聚到 Service | `app/services/creation_svc.py` | 中断恢复测试 |
| 4.3 | 条件化 WebSocket 服务初始化 | `app/main.py` | 桌面端启动验证 |

### Phase 5：集成测试与文档（预计 1-2 天）

| 步骤 | 任务 | 涉及文件 | 验证方式 |
|------|------|----------|----------|
| 5.1 | 编写 standalone 模式端到端测试 | `tests/test_standalone.py` | pytest 通过 |
| 5.2 | 编写 server 模式端到端测试 | `tests/test_server.py` | pytest 通过 |
| 5.3 | 更新 README 和架构文档 | `README.md`, `docs/` | 文档审查 |
| 5.4 | 更新 `.env.example` | 项目根目录 | 配置验证 |

---

## 五、文件变更清单

### 新增文件

| 文件路径 | 说明 |
|----------|------|
| `app/core/auth.py` | 鉴权模块（API Key 验证） |
| `app/services/task_store_sqlite.py` | SQLite TaskStore 实现 |
| `app/services/task_store_postgres.py` | PostgreSQL TaskStore 实现 |
| `.env.standalone` | 桌面端配置模板 |
| `.env.server` | 服务端配置模板 |
| `tests/test_standalone.py` | standalone 模式测试 |
| `tests/test_server.py` | server 模式测试 |

### 修改文件

| 文件路径 | 改动说明 |
|----------|----------|
| `app/core/config.py` | 新增配置项、模式验证器 |
| `app/services/task_store.py` | 抽取接口、工厂函数 |
| `app/api/dependencies.py` | 模式感知初始化 |
| `app/api/v1/creation.py` | 注入鉴权依赖 |
| `app/api/v1/polishing.py` | 注入鉴权依赖 |
| `app/api/v1/tasks.py` | 注入鉴权依赖 |
| `app/api/v1/ws.py` | WebSocket 鉴权 |
| `app/main.py` | 条件化服务初始化 |
| `app/core/exceptions.py` | 生产环境异常脱敏 |

---

## 六、风险与缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| PostgreSQL TaskStore 实现复杂 | 进度延迟 | 优先实现接口，PG 实现可延后 |
| 鉴权改造影响现有功能 | 桌面端体验下降 | `enable_auth=False` 时完全跳过 API Key 验证 |
| 配置项过多导致混乱 | 使用门槛提高 | 提供合理的默认值，standalone 模式零配置 |
| 现有测试需要适配 | 测试工作量增加 | 保持向后兼容，现有测试默认 standalone 模式 |

---

## 七、验收标准

### 7.1 功能验收

- [ ] standalone 模式：使用 `.env.standalone` 启动，SQLite 存储，无鉴权，所有功能正常
- [ ] server 模式：使用 `.env.server` 启动，PostgreSQL 存储，JWT 鉴权，所有功能正常
- [ ] 模式切换：仅修改 `APP_MODE` 和相关数据库配置，代码无需改动

### 7.2 性能验收

- [ ] standalone 模式启动时间 < 3 秒
- [ ] server 模式启动时间 < 5 秒
- [ ] 鉴权中间件延迟 < 5ms

### 7.3 安全验收

- [ ] server 模式下，无 API Key 请求返回 401
- [ ] server 模式下，无效 API Key 返回 403
- [ ] standalone 模式下，无鉴权直接放行
- [ ] 生产环境异常响应不包含内部实现细节
- [ ] WebSocket 连接需要有效 API Key（server 模式）

### 7.4 代码质量验收

- [ ] 所有现有测试通过
- [ ] 新增代码测试覆盖率 > 80%
- [ ] 类型检查（mypy/pyright）通过
- [ ] 代码格式化（black/ruff）通过

---

## 八、后续扩展

完成本阶段改造后，可继续以下优化：

1. **Redis 集成**：利用已有的 Redis 配置，实现任务队列、分布式锁
2. **多租户隔离**：在 Checkpointer 和 TaskStore 中增加 `namespace` 维度
3. **可观测性**：添加 Prometheus 指标、OpenTelemetry 链路追踪
4. **API 版本管理**：支持 v1/v2 并行，平滑升级
5. **速率限制**：基于 Redis 的滑动窗口限流

---

**文档版本**: v1.0
**创建日期**: 2026-05-12
**维护者**: Renhao-Wan
