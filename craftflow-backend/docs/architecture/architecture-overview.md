# CraftFlow 后端架构总览

> 本文档描述 CraftFlow Python 后端的整体架构设计，包括系统分层、双模式运行机制、适配器架构、设置系统和核心模块职责。

## 一、系统定位

CraftFlow Python 后端是整个平台的 **AI 能力层**，专注于 LangGraph 驱动的智能长文创作与多阶审校。它不处理用户管理、登录注册等业务逻辑——这些由 Java 后端负责。

```
┌─────────────────────────────────────────────────────────────────┐
│  客户端（桌面端 Electron / 网页端 SPA）                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Java 后端（业务层）—— 网页端部署时存在                            │
│  - 用户注册/登录、JWT 签发                                       │
│  - 权限校验、配额管理                                            │
│  - 调用 Python 后端时携带 X-API-Key                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST / WebSocket
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Python 后端（AI 层）← 本文档描述的系统                           │
│  - API Key 验证（验证调用方是否合法）                              │
│  - LangGraph 执行创作/润色图                                     │
│  - LLM 调用、工具链                                              │
│  - 任务状态管理                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 二、双模式运行架构

一套代码通过 `APP_MODE` 环境变量驱动两种运行模式：

```
┌─────────────────────────────────────────────────────────────┐
│                    一套 Python 后端代码                        │
├─────────────────────────────────────────────────────────────┤
│  通过 .env 环境变量驱动：                                      │
│  - APP_MODE: standalone / server                             │
│  - ENABLE_AUTH: true / false                                 │
│  - TASKSTORE_BACKEND: sqlite / postgres                      │
│  - CHECKPOINTER_BACKEND: memory / sqlite / postgres          │
└─────────────────────────────────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                              ▼
    ┌───────────────┐              ┌───────────────┐
    │   桌面端模式    │              │   服务端模式    │
    │  (standalone)  │              │   (server)     │
    ├───────────────┤              ├───────────────┤
    │ SQLite        │              │ SQLite / PG   │
    │ 无鉴权        │              │ API Key 鉴权  │
    │ localhost     │              │ 云端部署      │
    │ WebSocket     │              │ WebSocket     │
    │ 零配置启动    │              │ 高可用        │
    └───────────────┘              └───────────────┘
```

### 模式对比

| 维度 | standalone（桌面端） | server（服务端） |
|------|---------------------|-----------------|
| 存储后端 | 强制 SQLite | SQLite 或 PostgreSQL（可选） |
| 鉴权 | 强制关闭 | 可选（建议开启） |
| WebSocket | 启用（无鉴权） | 启用（可选鉴权） |
| 网络 | 127.0.0.1 | 0.0.0.0 |
| 调用方 | 前端直连 | Java 后端代理 |
| 数据目录 | %APPDATA%/CraftFlow/ | 项目目录或自定义 |
| 业务数据 owner | Python 直读写 | Java 管理 |
| LLM 配置 | Python 直读写 | Java 管理，Python 只读 |

### 模式验证器

`config.py` 中的 `model_validator` 在配置加载后自动调整：

```python
@model_validator(mode="after")
def validate_mode_config(self) -> "Settings":
    if self.app_mode == "standalone":
        self.enable_auth = False                    # 强制禁用鉴权
        if self.checkpointer_backend == "postgres":
            self.checkpointer_backend = "sqlite"    # 强制降级为 sqlite
        if self.taskstore_backend == "postgres":
            self.taskstore_backend = "sqlite"       # 强制降级为 sqlite
    elif self.app_mode == "server":
        # postgres 时必须配置 DATABASE_URL
        if (self.checkpointer_backend == "postgres" or
            self.taskstore_backend == "postgres") and not self.database_url:
            raise ValueError("server 模式下使用 postgres 后端时必须配置 DATABASE_URL")
    return self
```

**关键约束**：
- standalone 模式下 postgres 会被**自动降级**为 sqlite，不可逆转
- server 模式下 sqlite 和 postgres **均可使用**，无强制要求

## 三、后端分层结构

```
Controller (app/api/v1/)           ← FastAPI 路由，请求解析和响应封装
    │  依赖注入 (Depends)
    ▼
Service (app/services/)            ← 业务编排，任务生命周期管理
    │
    ▼
Adapter (app/adapters/)            ← 模式适配层，隔离 standalone/server 差异
    │
    ▼
Graph (app/graph/creation/, polishing/)  ← LangGraph StateGraph 定义
    │
    ▼
Nodes & Tools (app/graph/tools/)   ← 纯逻辑，无 FastAPI 依赖
```

**关键约束**：
- Nodes 和 Tools 不得导入 `fastapi` 或 `request` 对象
- Service 层通过 `BusinessAdapter` 接口与数据交互，不感知底层实现

### 各层职责

| 层级 | 目录 | 职责 | 依赖 |
|------|------|------|------|
| Controller | `app/api/v1/` | HTTP 请求解析、响应封装、鉴权注入 | FastAPI, Service |
| Dependencies | `app/api/dependencies.py` | 服务单例管理、模式感知初始化 | Service, Adapter, Config |
| Service | `app/services/` | 业务编排、Graph 调用、任务生命周期管理 | Adapter, Graph, Checkpointer |
| Adapter | `app/adapters/` | 模式适配，隔离 standalone/server 数据访问差异 | TaskStore, LLMProfileStore |
| Graph | `app/graph/` | LangGraph StateGraph 编排 | Nodes, Tools |
| Nodes | `app/graph/*/nodes.py` | 图节点执行逻辑 | LLM, Tools |
| Tools | `app/graph/tools/` | 外部工具封装（搜索、沙箱等） | 外部 API |
| Core | `app/core/` | 配置、日志、鉴权、异常处理 | 无业务依赖 |
| Schemas | `app/schemas/` | Pydantic V2 数据模型 | 无业务依赖 |

## 四、适配器架构

### 4.1 设计目标

通过适配器模式隔离 standalone 和 server 两种模式的数据访问差异，实现"一套核心代码，两种业务行为"：

| 模式 | 业务层 | AI 层 | 说明 |
|------|--------|-------|------|
| standalone | Python | Python | 桌面端，Python 全栈 |
| server | Java | Python | 网页端，职责分离 |

### 4.2 适配器接口

```python
# app/adapters/base.py
class BusinessAdapter(ABC):
    """业务层适配器接口"""

    # 任务管理
    async def save_task(self, task: dict) -> None
    async def get_task(self, task_id: str) -> Optional[dict]
    async def get_task_list(self, limit=50, offset=0) -> tuple[list[dict], int]
    async def delete_task(self, task_id: str) -> bool
    async def get_interrupted_tasks(self) -> list[dict]

    # LLM 配置
    async def get_llm_profile(self, profile_id: str | None = None) -> Optional[dict]
    async def get_all_llm_profiles(self) -> list[dict]

    # 生命周期
    async def init(self) -> None
    async def close(self) -> None
```

### 4.3 两种适配器实现

| 能力 | StandaloneAdapter | ServerAdapter |
|------|-------------------|---------------|
| 任务读写 | SQLite 直读写 | 委托 Java API |
| LLM 配置读取 | SQLite 直读 | PostgreSQL 直读（只读） |
| LLM 配置写入 | SQLite 直写 | Java 管理，Python 不写 |
| 状态回调 | 不需要（直接写 DB） | 回调 Java 内部 API |
| Checkpointer | SQLite（Python 管） | PostgreSQL（Python 管） |

### 4.4 文件组织

```
app/adapters/
├── __init__.py
├── base.py              # BusinessAdapter 抽象接口
├── standalone.py         # StandaloneAdapter（SQLite 直读写）
└── server.py             # ServerAdapter（Java API + PG 直读）
```

## 五、设置系统架构

### 5.1 设置分层模型

```
┌─────────────────────────────────────────────────────────────────┐
│ 第一层：用户偏好（前端 localStorage）                              │
│ - 主题（浅色/深色/跟随系统）                                       │
│ 特点：即时生效，不涉及后端                                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 第二层：运行时参数（数据库 llm_profiles 表）                        │
│ - LLM 配置（API Key、模型、温度等）                                │
│ - 写作参数（章节数、并发数等）                                      │
│ 特点：热更新，无需重启                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 LLM Profile 多配置管理

每个 LLM Profile 是一组完整的 LLM 连接配置：

| 字段 | 说明 | 示例 |
|------|------|------|
| `id` | UUID 主键 | `a1b2c3d4-...` |
| `name` | 用户自定义名称 | `GPT-4o`、`DeepSeek` |
| `api_key` | API 密钥 | `sk-xxx` |
| `api_base` | API 基础 URL | `https://api.openai.com/v1` |
| `model` | 模型名称 | `gpt-4o`、`deepseek-chat` |
| `temperature` | 温度参数 | `0.7` |
| `is_default` | 是否默认 | `1` = 创建任务时默认使用 |

**存储位置**：与 tasks 表共存于同一个数据库（`craftflow.db` / PostgreSQL）。

### 5.3 LLMFactory 改造

LLMFactory 从读 `.env` 配置改为读数据库：

```python
# 改造后
async def create_llm(cls, profile_id: str | None = None, ...):
    if profile_id:
        profile = await adapter.get_llm_profile(profile_id)
    else:
        profile = await adapter.get_llm_profile()  # 获取默认 Profile

    if not profile:
        raise ValueError("未找到 LLM 配置，请先在设置页添加")

    # 使用 Profile 中的配置创建 ChatOpenAI
    ...
```

**关键变化**：
- `create_llm()` 变为 `async`（需要查询数据库）
- `.env` 中的 LLM 字段（`LLM_API_KEY` 等）将被删除
- 启动时如果无 LLM Profile，提示用户去设置页添加

### 5.4 Settings API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/settings/llm-profiles` | GET | 获取所有 LLM Profile |
| `/api/v1/settings/llm-profiles` | POST | 创建新 Profile |
| `/api/v1/settings/llm-profiles/{id}` | PUT | 更新 Profile |
| `/api/v1/settings/llm-profiles/{id}` | DELETE | 删除 Profile |
| `/api/v1/settings/llm-profiles/{id}/set-default` | POST | 设为默认 |
| `/api/v1/settings/writing-params` | GET | 获取写作参数 |
| `/api/v1/settings/writing-params` | PATCH | 更新写作参数 |

## 六、核心模块清单

| 模块 | 文件 | 说明 |
|------|------|------|
| 配置 | `app/core/config.py` | `Settings` 单例（`lru_cache`），环境变量驱动 |
| 鉴权 | `app/core/auth.py` | API Key 验证（REST + WebSocket） |
| 异常 | `app/core/exceptions.py` | `CraftFlowException` 层级 + 全局 handler |
| 日志 | `app/core/logger.py` | Loguru 日志，`setup_logger()` 初始化 |
| 依赖注入 | `app/api/dependencies.py` | 服务单例 + 模式感知初始化编排 |
| 适配器 | `app/adapters/` | `BusinessAdapter` 抽象 + Standalone/Server 实现 |
| LLM 工厂 | `app/graph/common/llm_factory.py` | `LLMFactory` 单例缓存，从数据库读取配置 |
| 创作图 | `app/graph/creation/` | PlannerNode → HITL → WriterNode(Map-Reduce) → ReducerNode |
| 润色图 | `app/graph/polishing/` | RouterNode → 三档模式（格式化/Debate/事实核查） |
| 任务存储 | `app/services/task_store.py` | `AbstractTaskStore` 抽象 + 工厂 |
| 状态存储 | `app/services/checkpointer.py` | `CheckpointerFactory` 抽象工厂 |

## 七、数据流

### 7.1 任务创建流程

```
客户端请求 → Controller → Service.start_task()
    │
    ├→ _tasks dict（内存）     ← status=running
    ├→ Adapter.save_task()     ← status=running（standalone: SQLite, server: 回调 Java）
    └→ Checkpointer            ← thread_id → 图状态
    │
    ▼
Graph 执行 → PlannerNode 生成大纲
    │
    ▼
interrupt（HITL）→ status=interrupted
    │
    ├→ _tasks dict 更新
    ├→ Adapter.save_task() 更新
    └→ WebSocket 推送
```

### 7.2 任务恢复流程

```
客户端请求 → Controller → Service.resume_task()
    │
    ▼
Command(resume=user_input) → Graph 继续执行
    │
    ▼
WriterNode(Map-Reduce) → ReducerNode
    │
    ▼
完成 → status=completed
    │
    ├→ Adapter.save_task() 更新（result=...）
    ├→ Checkpointer 清理
    └→ _tasks dict 移除
```

### 7.3 任务查询流程

```
GET /tasks/{task_id}
    │
    ▼
先查 CreationService._tasks dict（内存，运行中/中断任务）
    │ 未找到
    ▼
再查 PolishingService._tasks dict（内存）
    │ 未找到
    ▼
查 Adapter.get_task()（standalone: SQLite, server: Java API）
```

## 八、LangGraph 双图架构

### 8.1 Creation Graph

```
planner_node → interrupt(HITL 大纲确认) → fan-out writer_nodes(Map-Reduce) → reducer_node
```

- **PlannerNode**：根据主题生成大纲
- **interrupt**：HITL 中断点，等待用户确认/修改大纲
- **WriterNode**：并发撰写各章节（Map-Reduce 模式）
- **ReducerNode**：合并章节，生成最终文章

### 8.2 Polishing Graph

```
router_node → mode 1: formatter_node
            → mode 2: debate 子图 (Author-Editor 博弈)
            → mode 3: fact_checker_node → debate 子图
```

- **mode 1**：极速格式化（单次 LLM 调用）
- **mode 2**：专家对抗审查（Author-Editor 多轮博弈）
- **mode 3**：事实核查 + 对抗循环（最高质量）

### 8.3 Debate 子图

```
author_node → editor_node → should_continue_debate?
            → 是: increment_iteration_node → author_node（循环）
            → 否: finalize_debate_node（输出最终结果）
```

## 九、启动流程

```python
# app/main.py lifespan

async def lifespan(app: FastAPI):
    # ── startup ──
    setup_logger()                    # 1. 初始化日志
    await init_checkpointer()         # 2. 初始化 Checkpointer
    await init_services()             # 3. 初始化业务服务
        ├→ create_adapter()           #    3a. 创建适配器（配置驱动）
        ├→ adapter.init()             #    3b. 初始化适配器（建表等）
        ├→ CreationService(...)       #    3c. 创建创作服务
        ├→ PolishingService(...)      #    3d. 创建润色服务
        ├→ load_interrupted_tasks()   #    3e. 恢复中断任务
        └→ _init_server_components()  #    3f. server 模式扩展（预留）

    init_ws_services()                # 4. 初始化 WebSocket 服务

    yield

    # ── shutdown ──
    await close_services()            # 关闭业务服务
    await adapter.close()             # 关闭适配器
    await close_checkpointer()        # 关闭 Checkpointer
```

## 十、全局资源生命周期

| 对象 | 单例？ | 说明 |
|------|--------|------|
| LLM (ChatModel) | 是 | 通过 `LLMFactory` 缓存，从数据库读取 Profile 配置 |
| Checkpointer | 是 | 全局一个实例，通过 `CheckpointerFactory` 创建 |
| Adapter | 是 | 全局一个实例，通过 `create_adapter()` 工厂创建 |
| TaskStore | 是 | 全局一个实例，Adapter 内部持有 |
| Graph (编译后) | 是 | `StateGraph.compile()` 结果在启动时创建并全局共享 |
| State / ThreadState | 否 | 每个 `thread_id` 独立，通过 `config` 隔离 |

---

**文档版本**: v2.0
**创建日期**: 2026-05-12
**最后更新**: 2026-05-12
**维护者**: Renhao-Wan
