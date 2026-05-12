# CraftFlow 数据存储架构设计

> 本文档详细描述 CraftFlow 的四层数据存储架构，包括各层职责、存储选型、数据流和抽象接口设计。

## 一、存储架构总览

CraftFlow 采用**四层分离**的存储架构，业务数据与 AI 状态各自独立：

```
┌─────────────────────────────────────────────────────────────────┐
│                       数据存储架构                                │
├─────────────┬───────────────┬──────────────┬───────────────────┤
│  _tasks dict│   TaskStore   │ Checkpointer │    Vector DB      │
│   （内存）   │  （业务持久化） │ （AI 状态）  │   （RAG 向量）    │
├─────────────┼───────────────┼──────────────┼───────────────────┤
│ 运行中任务   │ 终态任务记录   │ 图执行状态   │ 知识库 Embedding  │
│ 中断任务     │ 中断任务记录   │ ThreadState  │ 检索结果          │
│ 快速查询     │ 历史查询       │ 断点续传     │ 语义搜索          │
├─────────────┼───────────────┼──────────────┼───────────────────┤
│ Python dict │ SQLite / PG   │ SQLite / PG  │ Chroma / PGVector │
│ 进程内存     │ 业务层         │ AI 层        │ AI 层             │
└─────────────┴───────────────┴──────────────┴───────────────────┘
```

### 各层职责对比

| 存储层 | 位置 | 职责 | 层级 | 持久化 | 模式差异 |
|--------|------|------|------|--------|----------|
| `_tasks` dict | 内存 | 运行中/中断任务快速查询 | 业务层 | 否（进程退出丢失） | 无 |
| TaskStore | SQLite / PG | 任务数据持久化 | 业务层 | 是 | standalone: SQLite, server: SQLite/PG |
| Checkpointer | SQLite / PG | LangGraph 图状态持久化 | AI 层 | 是 | standalone: SQLite, server: memory/sqlite/PG |
| Vector DB | Chroma / PGVector | RAG 向量检索 | AI 层 | 是 | standalone: Chroma, server: PGVector |

## 二、_tasks dict（内存层）

### 2.1 设计目的

`_tasks` dict 是 `CreationService` 和 `PolishingService` 内部的内存缓存，用于快速查询**运行中**和**中断**状态的任务。

### 2.2 数据结构

```python
# CreationService._tasks
{
    "c-uuid-xxx": {
        "task_id": "c-uuid-xxx",
        "thread_id": "thread-uuid-xxx",
        "graph_type": "creation",
        "status": "running",           # running / interrupted / completed / failed
        "request": {"topic": "...", "description": "..."},
        "created_at": datetime(...),
        "updated_at": datetime(...),
        # interrupted 时额外包含：
        "interrupt_data": {...},
    }
}

# PolishingService._tasks
{
    "p-uuid-xxx": {
        "task_id": "p-uuid-xxx",
        "thread_id": "thread-uuid-xxx",
        "graph_type": "polishing",
        "status": "completed",
        "request": {"content": "...", "mode": 3},
        "result": "...",
        "created_at": datetime(...),
        "updated_at": datetime(...),
    }
}
```

### 2.3 生命周期

```
任务创建  → 写入 _tasks dict（status=running）
中断      → 更新 _tasks dict（status=interrupted）
完成      → 从 _tasks dict 移除（已持久化到 TaskStore）
失败      → 从 _tasks dict 移除（已持久化到 TaskStore）
服务重启  → 从 TaskStore 加载 interrupted 任务到 _tasks dict
```

### 2.4 为什么不用 Redis？

当前阶段 `_tasks` dict 足够满足需求：
- 单进程部署，无分布式需求
- 内存访问速度远超 Redis
- 无额外依赖，降低运维复杂度
- 未来多实例部署时可替换为 Redis

## 三、TaskStore（业务持久化层）

### 3.1 抽象接口

`AbstractTaskStore` 定义了任务持久化的标准接口：

```python
class AbstractTaskStore(ABC):
    async def init_db(self) -> None
    async def save_task(self, task: dict[str, Any]) -> None
    async def get_task(self, task_id: str, graph_type: str = None) -> Optional[dict]
    async def get_interrupted_tasks(self) -> list[dict]
    async def get_task_list(self, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]
    async def delete_task(self, task_id: str) -> bool
    async def close(self) -> None
```

### 3.2 实现类

```
AbstractTaskStore（抽象接口）
├── SqliteTaskStore   ← task_store_sqlite.py（aiosqlite）
└── PostgresTaskStore ← task_store_postgres.py（asyncpg）
```

工厂函数 `create_task_store()` 根据 `settings.taskstore_backend` 创建对应实例。

### 3.3 数据表结构

```sql
CREATE TABLE tasks (
    task_id      TEXT PRIMARY KEY,        -- 任务唯一 ID（如 c-uuid-xxx）
    graph_type   TEXT NOT NULL,           -- 任务类型：creation / polishing
    status       TEXT NOT NULL,           -- 状态：running / interrupted / completed / failed
    topic        TEXT,                    -- 创作主题（creation 类型）
    description  TEXT,                    -- 创作描述（creation 类型）
    content      TEXT,                    -- 润色内容（polishing 类型）
    mode         INTEGER,                -- 润色模式 1/2/3（polishing 类型）
    result       TEXT,                    -- 任务结果（completed 时）
    error        TEXT,                    -- 错误信息（failed 时）
    progress     REAL DEFAULT 100.0,      -- 进度百分比
    created_at   TEXT/TIMESTAMP NOT NULL, -- 创建时间
    updated_at   TEXT/TIMESTAMP NOT NULL  -- 更新时间
);

CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);
```

### 3.4 SQLite vs PostgreSQL 实现差异

| 特性 | SqliteTaskStore | PostgresTaskStore |
|------|----------------|-------------------|
| 连接方式 | `aiosqlite.connect()` 单连接 | `asyncpg.create_pool()` 连接池 |
| 参数占位符 | `?` | `$1, $2, ...` |
| UPSERT 语法 | `INSERT OR REPLACE` | `INSERT ... ON CONFLICT DO UPDATE` |
| 时间类型 | TEXT（ISO 格式） | TIMESTAMP |
| 删除确认 | `cursor.rowcount > 0` | `result == "DELETE 1"` |
| 连接池配置 | 无（单连接） | `min_size=2, max_size=10` |
| 桌面版路径 | `%APPDATA%/CraftFlow/sqlite/` | 不适用 |

### 3.5 数据流

```
任务创建 → _tasks dict (status=running)
         → TaskStore.save_task() (status=running)

任务中断 → _tasks dict 更新 (status=interrupted)
         → TaskStore.save_task() (status=interrupted)

任务完成 → TaskStore.save_task() (status=completed, result=...)
         → _tasks dict 移除
         → Checkpointer 清理

任务失败 → TaskStore.save_task() (status=failed, error=...)
         → _tasks dict 移除

查询任务 → 先查 _tasks dict（内存），再查 TaskStore（持久化）

服务重启 → TaskStore.get_interrupted_tasks() → 恢复到 _tasks dict
```

## 四、Checkpointer（AI 状态层）

### 4.1 职责

Checkpointer 是 LangGraph 的状态持久化机制，用于保存图执行过程中的中间状态，支持：
- **断点续传**：任务中断后恢复执行
- **时间旅行**：回溯到任意 checkpoint
- **HITL**：在 interrupt 点暂停等待用户输入

### 4.2 工厂模式

```python
# 已实现的工厂类
CheckpointerFactory（基类）
├── MemoryCheckpointerFactory    → MemorySaver        # 内存，调试用
├── SqliteCheckpointerFactory    → AsyncSqliteSaver   # SQLite，桌面端
└── PostgresCheckpointerFactory  → AsyncPostgresSaver # PostgreSQL，服务端
```

### 4.3 与 TaskStore 的关系

```
┌─────────────────────────────────────────────────┐
│                  TaskStore                       │
│  存储：任务元数据（谁创建、什么状态、结果是什么）    │
│  关心：业务语义                                    │
└─────────────────────┬───────────────────────────┘
                      │ task_id ↔ thread_id 映射
                      ▼
┌─────────────────────────────────────────────────┐
│               Checkpointer                       │
│  存储：图执行状态（执行到哪个节点、中间变量）        │
│  关心：执行语义                                    │
└─────────────────────────────────────────────────┘
```

- TaskStore 中的 `task_id` 与 Checkpointer 中的 `thread_id` 一一对应
- 查询任务状态：先从 TaskStore 获取元数据，再从 Checkpointer 获取图状态
- 清理任务：同时清理 TaskStore 记录和 Checkpointer checkpoint

### 4.4 配置选择

| 后端 | 适用场景 | 配置 |
|------|----------|------|
| `memory` | 快速调试、单元测试 | `CHECKPOINTER_BACKEND=memory` |
| `sqlite` | 桌面端、开发环境 | `CHECKPOINTER_BACKEND=sqlite` |
| `postgres` | 服务端生产环境 | `CHECKPOINTER_BACKEND=postgres` + `DATABASE_URL` |

## 五、Vector DB（RAG 向量层）

### 5.1 职责

向量数据库用于 RAG（检索增强生成）功能，存储文档的 Embedding 向量，支持语义搜索。

### 5.2 后端选择

| 后端 | 适用场景 | 配置 | 数据目录 |
|------|----------|------|----------|
| Chroma | 开发环境、桌面端 | `VECTOR_DB_BACKEND=chroma` | `data/chroma_db/` |
| PGVector | 生产环境 | `VECTOR_DB_BACKEND=pgvector` | PostgreSQL 内 |

### 5.3 自动回退

`KnowledgeRetriever` 会根据配置自动选择后端，如果 PGVector 不可用则回退到 Chroma。

### 5.4 开关控制

RAG 功能通过 `ENABLE_RAG` 配置项控制：
- `false`（默认）：禁用 RAG，不初始化向量数据库
- `true`：启用 RAG，根据 `VECTOR_DB_BACKEND` 初始化对应后端

## 六、数据库选型指南

### 6.1 standalone 模式推荐配置

```
CHECKPOINTER_BACKEND=sqlite
TASKSTORE_BACKEND=sqlite
ENABLE_RAG=false
```

特点：零配置，SQLite 路径基于代码位置自动推导，无需手动配置。

> **桌面端说明**：桌面端（PyInstaller 打包）自动使用 `%APPDATA%/CraftFlow/` 目录存储数据。

### 6.2 server 模式推荐配置（SQLite）

```
CHECKPOINTER_BACKEND=sqlite
TASKSTORE_BACKEND=sqlite
ENABLE_AUTH=true
API_KEY=your-strong-api-key
```

适用：小规模部署、测试环境、单机 server 模式。有鉴权保护但数据存本地文件。

### 6.3 server 模式推荐配置（PostgreSQL）

```
CHECKPOINTER_BACKEND=postgres
TASKSTORE_BACKEND=postgres
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/craftflow
ENABLE_AUTH=true
API_KEY=your-strong-api-key
ENABLE_RAG=true
VECTOR_DB_BACKEND=pgvector
```

适用：生产环境、多实例部署、需要数据共享和高可用。

### 6.4 混合配置

各存储层可以独立选择后端：

```
CHECKPOINTER_BACKEND=postgres     # 图状态用 PG（多实例共享）
TASKSTORE_BACKEND=sqlite          # 任务数据用 SQLite（本地）
ENABLE_RAG=true
VECTOR_DB_BACKEND=chroma          # 向量用 Chroma（本地）
```

## 七、数据目录结构

### 7.1 开发环境

```
craftflow-backend/
└── data/
    ├── sqlite/
    │   └── craftflow.db          # TaskStore
    ├── checkpoints/
    │   └── checkpoints.db        # Checkpointer
    └── chroma_db/                # Vector DB（Chroma）
```

### 7.2 桌面端打包后

```
%APPDATA%/CraftFlow/（Windows）
├── .env                          # 用户配置
├── sqlite/
│   └── craftflow.db              # TaskStore
├── checkpoints/
│   └── checkpoints.db            # Checkpointer
└── logs/
```

### 7.3 服务端部署

```
/opt/craftflow/
├── .env                          # 服务配置
├── data/
│   ├── sqlite/                   # SQLite 模式时
│   └── checkpoints/              # SQLite 模式时
└── logs/
```

PostgreSQL 数据由数据库服务管理，不在文件系统中。

---

**文档版本**: v1.0  
**创建日期**: 2026-05-12  
**维护者**: Renhao-Wan
