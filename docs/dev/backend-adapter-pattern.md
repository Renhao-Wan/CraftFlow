# CraftFlow 后端适配器架构设计

> 本文档定义 CraftFlow Python 后端如何通过适配器模式支持 standalone 和 server 两种运行模式，实现"一套核心代码，两种业务行为"。

## 一、设计目标

CraftFlow 需要支持两种截然不同的运行模式：

| 模式 | 业务层 | AI 层 | 说明 |
|------|--------|-------|------|
| standalone | Python | Python | 桌面端，Python 全栈 |
| server | Java | Python | 网页端，职责分离 |

两种模式**共享 AI 层**（Graph、Nodes、Tools、LLMFactory），但**业务层行为不同**（任务管理、LLM 配置读取、数据持久化）。

**目标**：核心代码不感知模式差异，通过适配器层隔离。

## 二、架构总览

```
craftflow-backend/
├── app/
│   ├── core/                  # 共享基础设施
│   │   ├── config.py          # Settings（含 APP_MODE）
│   │   ├── logger.py
│   │   └── exceptions.py
│   │
│   ├── graph/                 # 共享 AI 层（不感知模式）
│   │   ├── common/            # LLMFactory, prompts
│   │   ├── creation/          # Creation Graph
│   │   ├── polishing/         # Polishing Graph
│   │   └── tools/             # 搜索、沙箱、RAG
│   │
│   ├── schemas/               # 共享 Pydantic 模型
│   │
│   ├── services/              # 共享业务逻辑
│   │   ├── creation_svc.py    # 核心逻辑不变
│   │   ├── polishing_svc.py   # 核心逻辑不变
│   │   └── checkpointer.py    # AI 层，两种模式都用
│   │
│   ├── adapters/              # ★ 模式适配层（新增）
│   │   ├── base.py            # 抽象接口
│   │   ├── standalone.py      # standalone 适配器
│   │   └── server.py          # server 适配器
│   │
│   ├── api/                   # 路由层
│   │   ├── v1/                # 面向前端的业务 API（standalone 使用）
│   │   └── internal/          # 面向 Java 的内部 API（server 使用）
│   │
│   ├── main.py                # standalone 入口
│   └── main_server.py         # server 入口
│
├── data/                      # 本地数据（standalone）
│   ├── sqlite/
│   └── checkpoints/
│
└── .env                       # 基础设施配置（无业务参数）
```

## 三、适配器设计

### 3.1 抽象接口

```python
# adapters/base.py
from abc import ABC, abstractmethod
from typing import Any, Optional


class BusinessAdapter(ABC):
    """业务层适配器接口

    隔离 standalone 和 server 模式的差异。
    Service 层通过此接口与业务数据交互，不感知底层实现。
    """

    # ========== 任务管理 ==========

    @abstractmethod
    async def save_task(self, task: dict[str, Any]) -> None:
        """保存或更新任务记录"""

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        """查询单个任务"""

    @abstractmethod
    async def get_task_list(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """查询任务列表"""

    @abstractmethod
    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""

    @abstractmethod
    async def get_interrupted_tasks(self) -> list[dict[str, Any]]:
        """查询所有中断任务（用于服务重启恢复）"""

    # ========== LLM 配置 ==========

    @abstractmethod
    async def get_llm_profile(self, profile_id: str | None = None) -> Optional[dict[str, Any]]:
        """获取 LLM Profile（None = 默认 Profile）"""

    @abstractmethod
    async def get_all_llm_profiles(self) -> list[dict[str, Any]]:
        """获取所有 LLM Profile"""

    # ========== 生命周期 ==========

    @abstractmethod
    async def init(self) -> None:
        """初始化适配器（建表、连接池等）"""

    @abstractmethod
    async def close(self) -> None:
        """关闭适配器"""
```

### 3.2 standalone 适配器

standalone 模式下，Python 直接读写 SQLite，同时承担业务层和 AI 层。

```python
# adapters/standalone.py
from app.adapters.base import BusinessAdapter
from app.services.task_store_sqlite import SqliteTaskStore


class StandaloneAdapter(BusinessAdapter):
    """standalone 模式适配器

    Python 全栈：直接读写 SQLite（tasks 表 + llm_profiles 表）。
    适用于桌面端和本地开发。
    """

    def __init__(self, db_path: str | None = None):
        self.task_store = SqliteTaskStore(db_path)
        self._db_path = db_path

    async def init(self):
        await self.task_store.init_db()
        await self._init_llm_profiles_table()

    async def _init_llm_profiles_table(self):
        """创建 llm_profiles 表（如果不存在）"""
        # 复用 task_store 的连接
        ...

    async def save_task(self, task):
        await self.task_store.save_task(task)

    async def get_task(self, task_id):
        return await self.task_store.get_task(task_id)

    async def get_task_list(self, limit=50, offset=0):
        return await self.task_store.get_task_list(limit, offset)

    async def delete_task(self, task_id):
        return await self.task_store.delete_task(task_id)

    async def get_interrupted_tasks(self):
        return await self.task_store.get_interrupted_tasks()

    async def get_llm_profile(self, profile_id=None):
        if profile_id:
            # SELECT * FROM llm_profiles WHERE id = ?
            ...
        else:
            # SELECT * FROM llm_profiles WHERE is_default = 1
            ...

    async def get_all_llm_profiles(self):
        # SELECT * FROM llm_profiles ORDER BY created_at DESC
        ...

    async def close(self):
        await self.task_store.close()
```

### 3.3 server 适配器

server 模式下，Python 只管 AI 层，业务数据通过 Java 内部 API 或直读 PostgreSQL。

```python
# adapters/server.py
from app.adapters.base import BusinessAdapter


class ServerAdapter(BusinessAdapter):
    """server 模式适配器

    Python 只做 AI 层：
    - 任务管理：通过 Java 内部 API 回调
    - LLM 配置：直读 PostgreSQL llm_profiles 表（只读）
    """

    def __init__(self, java_client: "JavaInternalClient", db_url: str):
        self.java = java_client
        self._db_url = db_url
        self._pg_pool = None

    async def init(self):
        # 建立 PostgreSQL 连接池（用于直读 llm_profiles）
        import asyncpg
        self._pg_pool = await asyncpg.create_pool(self._db_url, min_size=2, max_size=5)

    # ========== 任务管理：委托 Java ==========

    async def save_task(self, task):
        # server 模式下 Python 不写 tasks 表
        # 状态变更通过 update_task_status 回调 Java
        pass

    async def get_task(self, task_id):
        # 从 Java 获取
        return await self.java.get_task(task_id)

    async def get_task_list(self, limit=50, offset=0):
        # 从 Java 获取
        return await self.java.get_task_list(limit, offset)

    async def delete_task(self, task_id):
        # 委托 Java 删除
        return await self.java.delete_task(task_id)

    async def get_interrupted_tasks(self):
        # 从 Java 获取
        return await self.java.get_interrupted_tasks()

    # ========== LLM 配置：直读 PostgreSQL ==========

    async def get_llm_profile(self, profile_id=None):
        async with self._pg_pool.acquire() as conn:
            if profile_id:
                row = await conn.fetchrow(
                    "SELECT * FROM llm_profiles WHERE id = $1", profile_id
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM llm_profiles WHERE is_default = TRUE"
                )
            return dict(row) if row else None

    async def get_all_llm_profiles(self):
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM llm_profiles ORDER BY created_at DESC"
            )
            return [dict(r) for r in rows]

    # ========== 额外方法：状态回调 ==========

    async def notify_task_status(self, task_id: str, status: str, **kwargs):
        """通知 Java 任务状态变更（server 模式独有）"""
        await self.java.patch_task_status(task_id, status, **kwargs)

    async def close(self):
        if self._pg_pool:
            await self._pg_pool.close()
```

### 3.4 两种适配器对比

| 能力 | StandaloneAdapter | ServerAdapter |
|------|-------------------|---------------|
| 任务读写 | SQLite 直读写 | 委托 Java API |
| LLM 配置读取 | SQLite 直读 | PostgreSQL 直读（只读） |
| LLM 配置写入 | SQLite 直写 | Java 管理，Python 不写 |
| 状态回调 | 不需要（直接写 DB） | 回调 Java 内部 API |
| Checkpointer | SQLite（Python 管） | PostgreSQL（Python 管） |
| 额外依赖 | 无 | JavaInternalClient |

## 四、Service 层适配

### 4.1 依赖注入

Service 层通过构造函数接收适配器，不关心具体实现：

```python
# services/creation_svc.py
class CreationService:
    def __init__(
        self,
        adapter: BusinessAdapter,    # ★ 注入适配器
        checkpointer: CheckpointerService,
    ):
        self.adapter = adapter
        self.checkpointer = checkpointer
        self._tasks: dict[str, dict] = {}  # 内存缓存（两种模式都有）

    async def _persist_and_cleanup(self, task_id: str, ...):
        """任务到达终态时：持久化 + 清理"""
        # 通过适配器保存（standalone 写 SQLite，server 回调 Java）
        await self.adapter.save_task({...})
        # 清理 checkpoint（AI 层，两种模式一样）
        await self.checkpointer.cleanup(thread_id)
        # 移出内存缓存
        self._tasks.pop(task_id, None)
```

### 4.2 启动时注入

```python
# main.py（standalone 入口）
from app.adapters.standalone import StandaloneAdapter

adapter = StandaloneAdapter()
await adapter.init()

creation_svc = CreationService(adapter=adapter, checkpointer=checkpointer_svc)
polishing_svc = PolishingService(adapter=adapter, checkpointer=checkpointer_svc)
```

```python
# main_server.py（server 入口）
from app.adapters.server import ServerAdapter

adapter = ServerAdapter(java_client=java_client, db_url=settings.database_url)
await adapter.init()

creation_svc = CreationService(adapter=adapter, checkpointer=checkpointer_svc)
polishing_svc = PolishingService(adapter=adapter, checkpointer=checkpointer_svc)
```

### 4.3 _tasks dict 的处理

`_tasks` dict 是 Python 的运行时内存缓存，两种模式都保留：

| 场景 | standalone | server |
|------|-----------|--------|
| 任务创建 | 写入 `_tasks` dict | 写入 `_tasks` dict |
| 任务查询 | 先查 `_tasks`，再查 SQLite | 先查 `_tasks`，再问 Java |
| 任务恢复 | 从 `_tasks` 读取 | 从 `_tasks` 读取 |
| 服务重启恢复 | 从 SQLite 加载 interrupted 任务 | 从 Java 获取 interrupted 任务 |

server 模式下的查询顺序：
```
1. _tasks dict（内存）→ 找到则返回
2. adapter.get_task() → 问 Java → 找到则返回
3. TaskNotFoundError
```

## 五、路由层差异

### 5.1 standalone 路由（`main.py`）

```
/api/v1/creation          POST   ← 用户直接调用
/api/v1/polishing         POST   ← 用户直接调用
/api/v1/tasks             GET    ← 用户查询
/api/v1/tasks/{id}        GET    ← 用户查询
/api/v1/tasks/{id}        DELETE ← 用户删除
/api/v1/tasks/{id}/resume POST   ← HITL 恢复
/ws                       WS     ← 实时通信
/health                   GET
```

### 5.2 server 路由（`main_server.py`）

```
/internal/tasks/execute        POST   ← Java 调用：执行任务
/internal/tasks/{id}/resume    POST   ← Java 调用：恢复任务
/internal/tasks/{id}/status    PATCH  ← Python 回调：通知状态（反向）
/ws                            WS     ← 前端直连或经 Java 代理
/health                        GET
```

server 模式下**不暴露** `/api/v1/` 业务路由，这些由 Java 提供。

### 5.3 WebSocket 差异

| 场景 | standalone | server |
|------|-----------|--------|
| 前端连接 | 直连 Python WS | 经 Java 代理或直连 Python WS |
| 任务创建消息 | Python 处理 | Python 处理（Java 已授权） |
| 状态推送 | Python 直推 | Python 直推（或通过 Java 中转） |

WebSocket 在两种模式下都由 Python 处理，差异在于连接建立时的鉴权方式。

## 六、文件组织

### 6.1 新增文件

```
app/adapters/
├── __init__.py
├── base.py              # BusinessAdapter 抽象接口
├── standalone.py         # StandaloneAdapter（SQLite 直读写）
└── server.py             # ServerAdapter（Java API + PG 直读）
```

### 6.2 需要修改的文件

| 文件 | 修改内容 |
|------|----------|
| `app/services/creation_svc.py` | `task_store` → `adapter`，调用方式不变 |
| `app/services/polishing_svc.py` | 同上 |
| `app/graph/common/llm_factory.py` | 从 `adapter.get_llm_profile()` 读取配置 |
| `app/api/dependencies.py` | 根据 `APP_MODE` 注入不同适配器 |
| `app/main.py` | standalone 入口，创建 StandaloneAdapter |
| `app/main_server.py` | server 入口，创建 ServerAdapter（新增文件） |

### 6.3 不需要修改的文件

| 文件 | 原因 |
|------|------|
| `app/graph/creation/*` | Graph 定义与模式无关 |
| `app/graph/polishing/*` | 同上 |
| `app/graph/tools/*` | 工具链与模式无关 |
| `app/schemas/*` | Pydantic 模型与模式无关 |
| `app/core/config.py` | Settings 仍保留 `APP_MODE` 字段 |

## 七、内部通信协议（server 模式）

### 7.1 Java → Python：任务执行

```
POST /internal/tasks/execute
X-API-Key: {internal-key}

{
    "task_id": "c-uuid-xxx",
    "thread_id": "thread-uuid-xxx",
    "graph_type": "creation",
    "params": { "topic": "...", "description": "..." },
    "profile_id": "a1b2c3d4-..."
}
```

### 7.2 Python → Java：状态回调

```
PATCH /internal/tasks/{task_id}/status
X-API-Key: {internal-key}

{
    "status": "completed",
    "result": "...",
    "progress": 100.0
}
```

### 7.3 Java → Python：任务恢复

```
POST /internal/tasks/{task_id}/resume
X-API-Key: {internal-key}

{
    "resume_data": { "approved_outline": [...] }
}
```

## 八、演进路线

### Phase 1：提取适配器接口（当前可做）

- 定义 `BusinessAdapter` 抽象接口
- 将 `SqliteTaskStore` 包装为 `StandaloneAdapter`
- Service 层改为依赖 `BusinessAdapter`
- **不影响现有功能**

### Phase 2：实现 ServerAdapter

- 实现 `ServerAdapter`（Java API 客户端 + PG 直读）
- 新增 `/internal/` 路由
- 新增 `main_server.py` 入口
- **Java 后端同步开发内部 API**

### Phase 3：Java 接管业务数据

- Java 实现 tasks 表和 llm_profiles 表的 CRUD
- Python 移除 `PostgresTaskStore`（不再直接写 PG 的 tasks 表）
- Python 的 `ServerAdapter` 只保留读取 + 回调

### Phase 4：多实例支持（远期）

- Java 负责任务分发
- Python 实例无状态化
- `_tasks` dict 通过 Redis 共享
- Checkpointer 通过 PostgreSQL 共享

---

**文档版本**: v1.0
**创建日期**: 2026-05-12
**维护者**: Renhao-Wan
