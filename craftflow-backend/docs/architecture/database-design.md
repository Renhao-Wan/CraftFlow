# CraftFlow 数据存储架构设计

> 本文档详细描述 CraftFlow 的数据存储架构，包括各层职责、存储选型、数据流、数据归属权和抽象接口设计。

## 一、存储架构总览

CraftFlow 采用**分层分离**的存储架构，业务数据与 AI 状态各自独立：

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
| TaskStore | SQLite / PG | 任务数据持久化 | 业务层 | 是 | standalone: SQLite, server: Java 管理 |
| LLM Profiles | SQLite / PG | LLM 配置管理 | 业务层 | 是 | standalone: SQLite, server: Java 管理 |
| Checkpointer | SQLite / PG | LangGraph 图状态持久化 | AI 层 | 是 | standalone: SQLite, server: PG |
| Vector DB | Chroma / PGVector | RAG 向量检索 | AI 层 | 是 | standalone: Chroma, server: PGVector |

## 二、数据归属权

### 2.1 核心原则

**数据归属权由 APP_MODE 决定**：

| 模式 | 业务数据 owner | AI 状态 owner | 说明 |
|------|---------------|--------------|------|
| standalone | Python | Python | Python 全栈，无 Java |
| server | Java | Python | 职责分离，各管各的 |

### 2.2 数据分类与归属

| 数据类型 | 归属层 | standalone | server |
|----------|--------|-----------|--------|
| tasks 表 | 业务数据 | Python 直写 | Java 管理 |
| llm_profiles 表 | 业务数据 | Python 直写 | Java 管理 |
| 用户/权限 | 业务数据 | 不适用 | Java 管理 |
| _tasks dict | 运行时内存 | Python | Python |
| Checkpointer | AI 图状态 | Python | Python |
| Vector DB | AI 知识库 | Python | Python |

### 2.3 standalone 模式数据流

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

### 2.4 server 模式数据流

Java 管业务，Python 管执行：

```
前端 (Vue SPA)
    │
    │ REST / WebSocket
    ▼
Java 后端（业务层）
    ├── tasks 表（PostgreSQL）
    ├── llm_profiles 表（PostgreSQL）
    └── 用户/权限管理
         │
         │ REST（内部 API）
         ▼
Python 后端（AI 层）
    ├── _tasks dict（内存缓存）
    ├── Checkpointer → PostgreSQL
    ├── LLMFactory → 读 llm_profiles（只读）
    └── Vector DB → PGVector
```

## 三、_tasks dict（内存层）

### 3.1 设计目的

`_tasks` dict 是 `CreationService` 和 `PolishingService` 内部的内存缓存，用于快速查询**运行中**和**中断**状态的任务。

### 3.2 数据结构

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
```

### 3.3 生命周期

```
任务创建  → 写入 _tasks dict（status=running）
中断      → 更新 _tasks dict（status=interrupted）
完成      → 从 _tasks dict 移除（已持久化到 TaskStore）
失败      → 从 _tasks dict 移除（已持久化到 TaskStore）
服务重启  → 从 TaskStore 加载 interrupted 任务到 _tasks dict
```

### 3.4 为什么不用 Redis？

当前阶段 `_tasks` dict 足够满足需求：
- 单进程部署，无分布式需求
- 内存访问速度远超 Redis
- 无额外依赖，降低运维复杂度
- 未来多实例部署时可替换为 Redis

## 四、TaskStore（业务持久化层）

### 4.1 抽象接口

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

### 4.2 实现类

```
AbstractTaskStore（抽象接口）
├── SqliteTaskStore   ← task_store_sqlite.py（aiosqlite）
└── PostgresTaskStore ← task_store_postgres.py（asyncpg）
```

工厂函数 `create_task_store()` 根据 `settings.taskstore_backend` 创建对应实例。

### 4.3 tasks 表结构

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

### 4.4 SQLite vs PostgreSQL 实现差异

| 特性 | SqliteTaskStore | PostgresTaskStore |
|------|----------------|-------------------|
| 连接方式 | `aiosqlite.connect()` 单连接 | `asyncpg.create_pool()` 连接池 |
| 参数占位符 | `?` | `$1, $2, ...` |
| UPSERT 语法 | `INSERT OR REPLACE` | `INSERT ... ON CONFLICT DO UPDATE` |
| 时间类型 | TEXT（ISO 格式） | TIMESTAMP |
| 删除确认 | `cursor.rowcount > 0` | `result == "DELETE 1"` |
| 连接池配置 | 无（单连接） | `min_size=2, max_size=10` |
| 桌面版路径 | `%APPDATA%/CraftFlow/sqlite/` | 不适用 |

## 五、LLM Profiles（LLM 配置层）

### 5.1 设计目的

LLM Profile 存储 LLM 连接配置，支持多配置管理。用户可创建多个 Profile，按需切换。

### 5.2 llm_profiles 表结构

#### SQLite（桌面端 / 开发环境）

```sql
CREATE TABLE IF NOT EXISTS llm_profiles (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    api_key     TEXT NOT NULL,
    api_base    TEXT NOT NULL DEFAULT '',
    model       TEXT NOT NULL,
    temperature REAL NOT NULL DEFAULT 0.7,
    is_default  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

#### PostgreSQL（服务端生产环境）

```sql
CREATE TABLE IF NOT EXISTS llm_profiles (
    id          VARCHAR(64) PRIMARY KEY,
    name        VARCHAR(128) NOT NULL UNIQUE,
    api_key     TEXT NOT NULL,
    api_base    VARCHAR(512) NOT NULL DEFAULT '',
    model       VARCHAR(128) NOT NULL,
    temperature REAL NOT NULL DEFAULT 0.7,
    is_default  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP NOT NULL,
    updated_at  TIMESTAMP NOT NULL
);
```

### 5.3 约束

- `is_default=1` 的记录最多只能有一条（应用层保证）
- `name` 字段唯一

### 5.4 与 .env 配置的关系

`.env` 中的 LLM 字段（`LLM_API_KEY`、`LLM_API_BASE`、`LLM_MODEL`、`MAX_TOKENS`、`DEFAULT_TEMPERATURE`）**将被删除**，全部从数据库读取。

启动引导逻辑：
```
应用启动
  │
  ├─ 读取 llm_profiles 表
  │
  ├─ 有数据 → 正常启动，使用 is_default=1 的 Profile
  │
  └─ 空表 → 提示用户去设置页添加 LLM 配置
```

## 六、settings 表（运行时参数）

### 6.1 设计目的

存储运行时可调参数，支持热更新（修改后无需重启服务）。

### 6.2 表结构

```sql
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

### 6.3 存储内容

```json
{
    "max_outline_sections": "5",
    "max_concurrent_writers": "3",
    "max_debate_iterations": "3",
    "editor_pass_score": "90",
    "task_timeout": "3600",
    "tool_call_timeout": "30",
    "default_profile_id": "a1b2c3d4-..."
}
```

## 七、Checkpointer（AI 状态层）

### 7.1 职责

Checkpointer 是 LangGraph 的状态持久化机制，用于保存图执行过程中的中间状态，支持：
- **断点续传**：任务中断后恢复执行
- **时间旅行**：回溯到任意 checkpoint
- **HITL**：在 interrupt 点暂停等待用户输入

### 7.2 工厂模式

```
CheckpointerFactory（基类）
├── MemoryCheckpointerFactory    → MemorySaver        # 内存，调试用
├── SqliteCheckpointerFactory    → AsyncSqliteSaver   # SQLite，桌面端
└── PostgresCheckpointerFactory  → AsyncPostgresSaver # PostgreSQL，服务端
```

### 7.3 与 TaskStore/Adapter 的关系

```
┌─────────────────────────────────────────────────┐
│              Adapter / TaskStore                 │
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
- 查询任务状态：先从 Adapter 获取元数据，再从 Checkpointer 获取图状态
- 清理任务：同时清理 TaskStore 记录和 Checkpointer checkpoint

### 7.4 配置选择

| 后端 | 适用场景 | 配置 |
|------|----------|------|
| `memory` | 快速调试、单元测试 | `CHECKPOINTER_BACKEND=memory` |
| `sqlite` | 桌面端、开发环境 | `CHECKPOINTER_BACKEND=sqlite` |
| `postgres` | 服务端生产环境 | `CHECKPOINTER_BACKEND=postgres` + `DATABASE_URL` |

### 7.5 server 模式隔离

PostgreSQL 中 Checkpointer 的表应与业务表隔离：

```sql
-- 方案 A：独立 schema
CREATE SCHEMA IF NOT EXISTS checkpoint;
-- LangGraph 的表自动创建在 checkpoint schema 下
```

## 八、Vector DB（RAG 向量层）

### 8.1 职责

向量数据库用于 RAG（检索增强生成）功能，存储文档的 Embedding 向量，支持语义搜索。

### 8.2 后端选择

| 后端 | 适用场景 | 配置 | 数据目录 |
|------|----------|------|----------|
| Chroma | 开发环境、桌面端 | `VECTOR_DB_BACKEND=chroma` | `data/chroma_db/` |
| PGVector | 生产环境 | `VECTOR_DB_BACKEND=pgvector` | PostgreSQL 内 |

### 8.3 自动回退

`KnowledgeRetriever` 会根据配置自动选择后端，如果 PGVector 不可用则回退到 Chroma。

### 8.4 开关控制

RAG 功能通过 `ENABLE_RAG` 配置项控制：
- `false`（默认）：禁用 RAG，不初始化向量数据库
- `true`：启用 RAG，根据 `VECTOR_DB_BACKEND` 初始化对应后端

## 九、数据库选型指南

### 9.1 standalone 模式推荐配置

```
CHECKPOINTER_BACKEND=sqlite
TASKSTORE_BACKEND=sqlite
ENABLE_RAG=false
```

特点：零配置，SQLite 路径基于代码位置自动推导，无需手动配置。

### 9.2 server 模式推荐配置（SQLite）

```
CHECKPOINTER_BACKEND=sqlite
TASKSTORE_BACKEND=sqlite
ENABLE_AUTH=true
API_KEY=your-strong-api-key
```

适用：小规模部署、测试环境、单机 server 模式。

### 9.3 server 模式推荐配置（PostgreSQL）

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

## 十、数据目录结构

### 10.1 开发环境

```
craftflow-backend/
└── data/
    ├── sqlite/
    │   └── craftflow.db          # TaskStore + LLM Profiles
    ├── checkpoints/
    │   └── checkpoints.db        # Checkpointer
    └── chroma_db/                # Vector DB（Chroma）
```

### 10.2 桌面端打包后

```
%APPDATA%/CraftFlow/（Windows）
├── .env                          # 用户配置
├── sqlite/
│   └── craftflow.db              # TaskStore + LLM Profiles
├── checkpoints/
│   └── checkpoints.db            # Checkpointer
└── logs/
```

### 10.3 服务端部署

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

**文档版本**: v2.1
**创建日期**: 2026-05-12
**最后更新**: 2026-05-13
**维护者**: Renhao-Wan
