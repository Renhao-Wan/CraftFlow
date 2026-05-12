# CraftFlow 后端架构总览

> 本文档描述 CraftFlow Python 后端的整体架构设计，包括系统分层、双模式运行机制、数据流和核心模块职责。

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
Graph (app/graph/creation/, polishing/)  ← LangGraph StateGraph 定义
    │
    ▼
Nodes & Tools (app/graph/tools/)   ← 纯逻辑，无 FastAPI 依赖
```

**关键约束**：Nodes 和 Tools 不得导入 `fastapi` 或 `request` 对象。

### 各层职责

| 层级 | 目录 | 职责 | 依赖 |
|------|------|------|------|
| Controller | `app/api/v1/` | HTTP 请求解析、响应封装、鉴权注入 | FastAPI, Service |
| Dependencies | `app/api/dependencies.py` | 服务单例管理、模式感知初始化 | Service, Config |
| Service | `app/services/` | 任务 CRUD、Graph 调用、状态管理 | Graph, TaskStore, Checkpointer |
| Graph | `app/graph/` | LangGraph StateGraph 编排 | Nodes, Tools |
| Nodes | `app/graph/*/nodes.py` | 图节点执行逻辑 | LLM, Tools |
| Tools | `app/graph/tools/` | 外部工具封装（搜索、沙箱等） | 外部 API |
| Core | `app/core/` | 配置、日志、鉴权、异常处理 | 无业务依赖 |
| Schemas | `app/schemas/` | Pydantic V2 数据模型 | 无业务依赖 |

## 四、核心模块清单

| 模块 | 文件 | 说明 |
|------|------|------|
| 配置 | `app/core/config.py` | `Settings` 单例（`lru_cache`），环境变量驱动 |
| 鉴权 | `app/core/auth.py` | API Key 验证（REST + WebSocket） |
| 异常 | `app/core/exceptions.py` | `CraftFlowException` 层级 + 全局 handler |
| 日志 | `app/core/logger.py` | Loguru 日志，`setup_logger()` 初始化 |
| 依赖注入 | `app/api/dependencies.py` | 服务单例 + 模式感知初始化编排 |
| LLM 工厂 | `app/graph/common/llm_factory.py` | `LLMFactory` 单例缓存 |
| 创作图 | `app/graph/creation/` | PlannerNode → HITL → WriterNode(Map-Reduce) → ReducerNode |
| 润色图 | `app/graph/polishing/` | RouterNode → 三档模式（格式化/Debate/事实核查） |
| 任务存储 | `app/services/task_store.py` | `AbstractTaskStore` 抽象 + 工厂 |
| 状态存储 | `app/services/checkpointer.py` | `CheckpointerFactory` 抽象工厂 |

## 五、数据流

### 5.1 任务创建流程

```
客户端请求 → Controller → Service.start_task()
    │
    ├→ _tasks dict（内存）     ← status=running
    ├→ TaskStore（SQLite/PG）  ← status=running
    └→ Checkpointer            ← thread_id → 图状态
    │
    ▼
Graph 执行 → PlannerNode 生成大纲
    │
    ▼
interrupt（HITL）→ status=interrupted
    │
    ├→ _tasks dict 更新
    ├→ TaskStore 更新
    └→ WebSocket 推送
```

### 5.2 任务恢复流程

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
    ├→ TaskStore 更新（result=...）
    ├→ Checkpointer 清理
    └→ _tasks dict 移除
```

### 5.3 任务查询流程

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
查 TaskStore（SQLite/PG，已完成/失败任务）
```

## 六、LangGraph 双图架构

### 6.1 Creation Graph

```
planner_node → interrupt(HITL 大纲确认) → fan-out writer_nodes(Map-Reduce) → reducer_node
```

- **PlannerNode**：根据主题生成大纲
- **interrupt**：HITL 中断点，等待用户确认/修改大纲
- **WriterNode**：并发撰写各章节（Map-Reduce 模式）
- **ReducerNode**：合并章节，生成最终文章

### 6.2 Polishing Graph

```
router_node → mode 1: formatter_node
            → mode 2: debate 子图 (Author-Editor 博弈)
            → mode 3: fact_checker_node → debate 子图
```

- **mode 1**：极速格式化（单次 LLM 调用）
- **mode 2**：专家对抗审查（Author-Editor 多轮博弈）
- **mode 3**：事实核查 + 对抗循环（最高质量）

### 6.3 Debate 子图

```
author_node → editor_node → should_continue_debate?
            → 是: increment_iteration_node → author_node（循环）
            → 否: finalize_debate_node（输出最终结果）
```

## 七、启动流程

```python
# app/main.py lifespan

async def lifespan(app: FastAPI):
    # ── startup ──
    setup_logger()                    # 1. 初始化日志
    await init_checkpointer()         # 2. 初始化 Checkpointer
    await init_services()             # 3. 初始化业务服务
        ├→ create_task_store()        #    3a. 创建 TaskStore（配置驱动）
        ├→ CreationService(...)       #    3b. 创建创作服务
        ├→ PolishingService(...)      #    3c. 创建润色服务
        ├→ load_interrupted_tasks()   #    3d. 恢复中断任务
        └→ _init_server_components()  #    3e. server 模式扩展（预留）

    init_ws_services()                # 4. 初始化 WebSocket 服务

    yield

    # ── shutdown ──
    await close_services()            # 关闭业务服务
    await close_checkpointer()        # 关闭 Checkpointer
```

## 八、全局资源生命周期

| 对象 | 单例？ | 说明 |
|------|--------|------|
| LLM (ChatModel) | 是 | 通过 `LLMFactory` 缓存，禁止在请求/节点内重新实例化 |
| Checkpointer | 是 | 全局一个实例，通过 `CheckpointerFactory` 创建 |
| TaskStore | 是 | 全局一个实例，通过 `create_task_store()` 工厂创建 |
| Graph (编译后) | 是 | `StateGraph.compile()` 结果在启动时创建并全局共享 |
| State / ThreadState | 否 | 每个 `thread_id` 独立，通过 `config` 隔离 |

---

**文档版本**: v1.0  
**创建日期**: 2026-05-12  
**维护者**: Renhao-Wan
