# CraftFlow 数据归属权架构设计

> 本文档定义 CraftFlow 在 standalone 和 server 两种模式下，各类数据的归属权、读写职责和通信方式。这是从"Python 全栈"演进到"Java 业务层 + Python AI 层"分离架构的指导文档。

## 一、设计背景

### 1.1 现状问题

当前 Python 后端直接拥有所有数据表（`tasks`、未来的 `llm_profiles`），通过 `TaskStore` 直接读写 SQLite/PostgreSQL。这在 standalone 模式下合理，但与 server 模式的架构目标冲突：

- **Server 模式目标**：Java 后端是业务层，负责用户管理、任务调度、数据持久化；Python 后端是 AI 层，只负责 LangGraph 执行和 LLM 调用。
- **当前问题**：Python 后端同时承担了业务层和 AI 层的职责，与 Java 后端的职责边界模糊。

### 1.2 核心原则

**数据归属权由 APP_MODE 决定**：

| 模式 | 业务数据 owner | AI 状态 owner | 说明 |
|------|---------------|--------------|------|
| standalone | Python | Python | Python 全栈，无 Java |
| server | Java | Python | 职责分离，各管各的 |

## 二、数据分类与归属

### 2.1 完整数据分类

```
┌─────────────────────────────────────────────────────────────────┐
│                        CraftFlow 数据全景                        │
├──────────────┬────────────────┬─────────────┬──────────────────┤
│   数据类型    │    归属层       │  standalone │     server       │
├──────────────┼────────────────┼─────────────┼──────────────────┤
│ tasks 表     │ 业务数据        │ Python 直写  │ Java 管理        │
│ llm_profiles │ 业务数据        │ Python 直写  │ Java 管理        │
│ 用户/权限    │ 业务数据        │ 不适用       │ Java 管理        │
│ _tasks dict  │ 运行时内存      │ Python      │ Python           │
│ Checkpointer │ AI 图状态       │ Python      │ Python           │
│ Vector DB    │ AI 知识库       │ Python      │ Python           │
└──────────────┴────────────────┴─────────────┴──────────────────┘
```

### 2.2 逐项说明

#### tasks 表（任务元数据）

| 属性 | standalone | server |
|------|-----------|--------|
| 存储 | SQLite (`craftflow.db`) | PostgreSQL |
| 写入方 | Python（CreationService / PolishingService） | Java |
| 读取方 | Python + 前端直读 | Java → 前端 |
| 删除方 | Python（用户通过 API 触发） | Java |

**为什么 server 模式归 Java**：
- 任务是核心业务实体，与用户、配额、权限强关联
- Java 需要基于任务做业务逻辑（计费、审计、分页查询）
- Python 不应感知用户身份和业务规则

#### llm_profiles 表（LLM 配置）

| 属性 | standalone | server |
|------|-----------|--------|
| 存储 | SQLite (`craftflow.db`) | PostgreSQL |
| 写入方 | Python（设置页 API） | Java（管理后台） |
| 读取方 | Python（LLMFactory） | Python（LLMFactory） |

**server 模式的特殊性**：LLM 配置由 Java 管理，但 Python 需要读取来创建 ChatOpenAI 实例。读取方式见第三节。

#### _tasks dict（运行时内存）

| 属性 | 说明 |
|------|------|
| 位置 | `CreationService._tasks`、`PolishingService._tasks` |
| 用途 | 缓存 running / interrupted 状态的任务，支持快速查询和任务恢复 |
| 生命周期 | 任务创建时写入，终态时移除，服务重启时从持久化层恢复 |

**两种模式都保留**：`_tasks` dict 是 Python 执行引擎的内部状态，与业务层无关。

#### Checkpointer（LangGraph 图状态）

| 属性 | standalone | server |
|------|-----------|--------|
| 存储 | SQLite (`checkpoints.db`) | PostgreSQL |
| 管理方 | Python（LangGraph AsyncSqliteSaver） | Python（LangGraph AsyncPostgresSaver） |
| 用途 | 图执行断点续传、HITL 恢复 | 同左 |

**两种模式都归 Python**：Checkpointer 是 LangGraph 的内部机制，Java 不感知。

#### Vector DB（RAG 知识库）

| 属性 | standalone | server |
|------|-----------|--------|
| 存储 | Chroma (`data/chroma_db/`) | PGVector (PostgreSQL) |
| 管理方 | Python | Python |

**两种模式都归 Python**：RAG 是 AI 层能力，与业务逻辑无关。

## 三、两种模式的数据流

### 3.1 standalone 模式

Python 全栈，直接拥有所有数据：

```
前端 (Vue/Electron)
    │
    │ REST / WebSocket
    ▼
Python 后端（全栈）
    ├── _tasks dict（内存缓存）
    ├── TaskStore → SQLite (tasks 表)
    ├── LLMFactory → SQLite (llm_profiles 表)
    ├── Checkpointer → SQLite (checkpoints.db)
    └── Vector DB → Chroma
```

**任务生命周期**：
```
前端请求 → Python 创建任务 → 写 _tasks dict + tasks 表
         → 执行 LangGraph → 更新 tasks 表 → 移出 _tasks dict
         → 前端查询 → 先查 _tasks dict，再查 tasks 表
```

**LLM 配置读取**：
```
LLMFactory.create_llm()
    → 读 SQLite llm_profiles 表
    → 获取 is_default=1 的 Profile
    → 创建 ChatOpenAI 实例
```

### 3.2 server 模式

Java 管业务，Python 管执行：

```
前端 (Vue SPA)
    │
    │ REST / WebSocket
    ▼
Java 后端（业务层）
    ├── tasks 表（PostgreSQL）
    ├── llm_profiles 表（PostgreSQL）
    ├── 用户/权限管理
    └── 任务调度
         │
         │ REST（内部 API）
         ▼
Python 后端（AI 层）
    ├── _tasks dict（内存缓存）
    ├── Checkpointer → PostgreSQL
    ├── LLMFactory → 读 llm_profiles（见下文）
    └── Vector DB → PGVector
```

**任务生命周期**：
```
前端请求 → Java 创建任务记录（tasks 表, status=running）
         → Java 调用 Python POST /internal/tasks/execute
         → Python 执行 LangGraph（_tasks dict 缓存运行状态）
         → Python 完成 → 回调 Java PATCH /internal/tasks/{id}/status
         → Java 更新 tasks 表（status=completed, result=...）
         → 前端查询 → 直接问 Java
```

**LLM 配置读取**（server 模式）：
```
Python 需要读取 llm_profiles 表，有两种方案：

方案 A：Python 直读 PostgreSQL（推荐）
    LLMFactory → 直接读 PostgreSQL llm_profiles 表
    优点：简单，无额外 API
    前提：Python 有 PostgreSQL 只读权限

方案 B：通过 Java API 获取
    LLMFactory → GET /internal/llm-profiles/{id} → Java
    优点：完全解耦，Java 可做权限控制
    缺点：多一次网络调用，需要缓存
```

**推荐方案 A**：Python 直读 PostgreSQL 的 `llm_profiles` 表。理由：
- LLM 配置读取频率高（每次创建 LLM 实例），网络调用开销大
- Java 和 Python 共享同一个 PostgreSQL，直读是最简单的
- Python 只需要**只读**权限，不会修改 `llm_profiles` 表

## 四、通信协议（server 模式）

### 4.1 Java → Python（任务执行）

```
POST /internal/tasks/execute
Content-Type: application/json
X-API-Key: {internal-api-key}

{
    "task_id": "c-uuid-xxx",
    "thread_id": "thread-uuid-xxx",
    "graph_type": "creation",
    "params": {
        "topic": "...",
        "description": "...",
        "outline": [...]
    },
    "profile_id": "a1b2c3d4-..."   // 使用哪个 LLM Profile
}
```

Python 响应：
```json
{
    "status": "accepted",
    "task_id": "c-uuid-xxx"
}
```

### 4.2 Python → Java（状态回调）

任务状态变更时，Python 回调 Java：

```
PATCH /internal/tasks/{task_id}/status
Content-Type: application/json
X-API-Key: {internal-api-key}

{
    "status": "completed",
    "result": "...",
    "progress": 100.0,
    "updated_at": "2026-05-12T10:30:00Z"
}
```

状态值：`running` | `interrupted` | `completed` | `failed`

### 4.3 Python → Java（HITL 中断通知）

当 LangGraph 触发 `GraphInterrupt` 时：

```
PATCH /internal/tasks/{task_id}/status
{
    "status": "interrupted",
    "interrupt_data": {
        "type": "outline_approval",
        "outline": [...],
        "awaiting": "user_input"
    },
    "progress": 30.0
}
```

Java 收到后存储中断数据，前端通过 Java API 获取并展示 HITL 表单。

### 4.4 Java → Python（任务恢复）

用户提交 HITL 表单后：

```
POST /internal/tasks/{task_id}/resume
Content-Type: application/json

{
    "resume_data": {
        "approved_outline": [...]
    }
}
```

## 五、TaskStore 改造方案

### 5.1 当前 AbstractTaskStore 接口

```python
class AbstractTaskStore(ABC):
    async def init_db(self) -> None
    async def save_task(self, task: dict) -> None
    async def get_task(self, task_id, graph_type) -> Optional[dict]
    async def get_interrupted_tasks(self) -> list[dict]
    async def get_task_list(self, limit, offset) -> tuple[list[dict], int]
    async def delete_task(self, task_id) -> bool
    async def close(self) -> None
```

### 5.2 改造后的职责划分

**standalone 模式**：`SqliteTaskStore` 不变，Python 继续直接读写。

**server 模式**：Python 不需要 TaskStore。Java 通过内部 API 驱动 Python 执行，Python 通过回调通知 Java 结果。

```
standalone:
    Python → SqliteTaskStore → SQLite

server:
    Java → JPA/MyBatis → PostgreSQL（tasks 表）
    Python → 无 TaskStore（_tasks dict + 回调 Java 即可）
```

### 5.3 服务层改造

当前 `CreationService` / `PolishingService` 同时操作 `_tasks` dict 和 TaskStore。改造后：

```python
# standalone 模式（不变）
class CreationService:
    _tasks: dict          # 内存缓存
    task_store: SqliteTaskStore  # 持久化

    async def _persist_and_cleanup(self, task_id, ...):
        await self.task_store.save_task(...)   # 写 SQLite
        self._tasks.pop(task_id, None)

# server 模式（简化）
class CreationService:
    _tasks: dict          # 内存缓存
    # 无 task_store

    async def _notify_java(self, task_id, status, ...):
        await self.java_client.update_task_status(task_id, status, ...)
        self._tasks.pop(task_id, None)
```

通过**依赖注入**在启动时根据 `APP_MODE` 注入不同的行为：

```python
# app/api/dependencies.py
if settings.is_standalone:
    creation_svc = CreationService(task_store=sqlite_store, java_client=None)
else:
    creation_svc = CreationService(task_store=None, java_client=java_client)
```

### 5.4 保留和删除的部分

| 组件 | standalone | server | 说明 |
|------|-----------|--------|------|
| `AbstractTaskStore` | ✅ 保留 | ❌ 不需要 | server 模式下 Java 管 tasks |
| `SqliteTaskStore` | ✅ 保留 | ❌ 不需要 | 同上 |
| `PostgresTaskStore` | ❌ 不用于 tasks | ❌ 不需要 | tasks 表归 Java，Python 不直接写 PG 的 tasks 表 |
| `_tasks` dict | ✅ 保留 | ✅ 保留 | Python 运行时内存，两种模式都需要 |
| `create_task_store()` | ✅ 保留 | ⚠️ 简化 | server 模式下返回 None 或跳过 |
| `CheckpointerService` | ✅ 保留 | ✅ 保留 | AI 层，两种模式都归 Python |

> **注意**：`PostgresTaskStore` 在 server 模式下**不用于 tasks 表**，但可能用于其他 Python 自有的表（如 checkpointer 的元数据）。如果未来有纯 Python 的 PostgreSQL 需求，可以保留。

## 六、LLM 配置读取方案

### 6.1 standalone 模式

Python 直接读 SQLite `llm_profiles` 表：

```python
class LLMProfileStore:
    """LLM Profile 读取（standalone 模式，直读 SQLite）"""

    async def get_default_profile(self) -> Optional[dict]:
        # SELECT * FROM llm_profiles WHERE is_default = 1

    async def get_profile(self, profile_id: str) -> Optional[dict]:
        # SELECT * FROM llm_profiles WHERE id = ?
```

### 6.2 server 模式

**推荐：Python 直读 PostgreSQL `llm_profiles` 表（只读）**

```python
class LLMProfileStore:
    """LLM Profile 读取（server 模式，直读 PostgreSQL，只读）"""

    async def get_default_profile(self) -> Optional[dict]:
        # SELECT * FROM llm_profiles WHERE is_default = TRUE

    async def get_profile(self, profile_id: str) -> Optional[dict]:
        # SELECT * FROM llm_profiles WHERE id = $1
```

**连接配置**：复用 `DATABASE_URL`（已有的 PostgreSQL 连接串）。

**权限控制**：Python 的 PostgreSQL 用户只有 `llm_profiles` 表的 `SELECT` 权限，无 `INSERT/UPDATE/DELETE`。

```sql
-- PostgreSQL 权限设置
GRANT SELECT ON llm_profiles TO craftflow_python;
-- 不授予写权限
```

### 6.3 LLMFactory 改造

```python
class LLMFactory:
    _instances: dict[str, BaseChatModel] = {}
    _profile_store: LLMProfileStore  # 依赖注入

    @classmethod
    async def create_llm(cls, profile_id: str | None = None, ...) -> BaseChatModel:
        if profile_id:
            profile = await cls._profile_store.get_profile(profile_id)
        else:
            profile = await cls._profile_store.get_default_profile()

        if not profile:
            raise ValueError("未找到 LLM 配置，请先在设置页添加")

        # 使用 Profile 中的配置创建 ChatOpenAI
        ...
```

## 七、Checkpointer 归属

Checkpointer 在两种模式下都归 Python 管理：

| 属性 | standalone | server |
|------|-----------|--------|
| 后端 | AsyncSqliteSaver | AsyncPostgresSaver |
| 存储 | `data/checkpoints/checkpoints.db` | PostgreSQL（独立 schema 或表前缀） |
| 用途 | 图执行断点续传、HITL 恢复 | 同左 |
| Java 是否感知 | 否 | 否 |

**为什么 Java 不管 Checkpointer**：
- Checkpointer 是 LangGraph 的内部状态机制，存储的是图执行的中间节点状态
- Java 只关心"任务完成了没有"，不关心"图执行到哪个节点了"
- Python 通过回调通知 Java 最终状态即可

**server 模式的 Checkpointer 隔离**：

PostgreSQL 中 Checkpointer 的表应与业务表隔离：

```sql
-- 方案 A：独立 schema
CREATE SCHEMA IF NOT EXISTS checkpoint;
-- LangGraph 的表自动创建在 checkpoint schema 下

-- 方案 B：表前缀
-- LangGraph 创建的表自动加前缀（需 LangGraph 支持）
```

## 八、架构演进路线

### Phase 1：当前状态（Python 全栈）

```
Python 直接拥有 tasks 表 + llm_profiles 表 + checkpointer
适用于：standalone 模式，单机开发
```

### Phase 2：内部 API 定义

```
定义 Java ↔ Python 内部通信协议
Python 新增 /internal/ 路由
Java 新增对应的调用客户端
此时仍可 Python 直写 tasks 表（渐进式迁移）
```

### Phase 3：职责分离

```
Java 接管 tasks 表 + llm_profiles 表的写入
Python 移除 TaskStore 的写入逻辑
Python 通过内部 API 回调 Java
standalone 模式保持不变
```

### Phase 4：多实例支持（远期）

```
Java 负责任务分发（哪个 Python 实例执行哪个任务）
Python 实例无状态化（_tasks dict 通过 Redis 共享）
Checkpointer 通过 PostgreSQL 共享
```

---

**文档版本**: v1.0
**创建日期**: 2026-05-12
**维护者**: Renhao-Wan
