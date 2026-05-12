# CraftFlow 设置系统实施计划

> 本文档定义设置系统和适配器架构的实施顺序。当前优先开发 desktop 端（standalone 模式），同时预留 server 端架构。

## 一、实施背景

- **当前目标**：完成桌面端设置功能（LLM 多配置管理、写作参数配置）
- **架构目标**：通过适配器模式预留 server 端扩展能力
- **不处理**：老用户迁移（假设当前处于早期开发阶段，无历史数据需要迁移）

## 二、依赖关系

```
Step 1: BusinessAdapter 接口 + StandaloneAdapter
  └─→ Step 2: Service 层切换到 Adapter
        └─→ Step 3: LLM Profile 表 + CRUD
              └─→ Step 4: LLMFactory 改造
                    └─→ Step 5: 后端 Settings API
                          └─→ Step 6: 前端设置页
                                └─→ Step 7: 清理旧配置
```

Step 1-2 是纯重构（不改行为），Step 3-5 是后端核心改造，Step 6-7 是功能交付和收尾。

## 三、详细步骤

### Step 1：BusinessAdapter 接口 + StandaloneAdapter

**目标**：定义适配器抽象接口，将现有 TaskStore 包装为 StandaloneAdapter。

**新增文件**：
```
app/adapters/
├── __init__.py
├── base.py              # BusinessAdapter 抽象接口
└── standalone.py         # StandaloneAdapter 实现
```

**`base.py` 内容**：
- 定义 `BusinessAdapter` 抽象类
- 方法与当前 `AbstractTaskStore` 对齐：`save_task()`、`get_task()`、`get_task_list()`、`delete_task()`、`get_interrupted_tasks()`
- 新增 LLM Profile 方法占位（Step 3 实现）：`get_llm_profile()`、`get_all_llm_profiles()`
- 生命周期方法：`init()`、`close()`

**`standalone.py` 内容**：
- `StandaloneAdapter` 实现 `BusinessAdapter`
- 内部持有 `SqliteTaskStore` 实例，tasks 相关方法委托给它
- LLM Profile 方法暂时 `raise NotImplementedError`（Step 3 实现）

**验证**：现有测试全部通过，行为无变化。

**为 server 端预留**：
- 接口设计已包含 server 模式需要的方法签名
- `ServerAdapter` 在此步骤不实现，但接口已为其留好位置

---

### Step 2：Service 层切换到 Adapter

**目标**：Service 层从直接依赖 `AbstractTaskStore` 改为依赖 `BusinessAdapter`。

**修改文件**：
- `app/services/creation_svc.py` — 构造参数 `task_store` → `adapter`
- `app/services/polishing_svc.py` — 同上
- `app/api/dependencies.py` — 注入 `StandaloneAdapter` 替代 `SqliteTaskStore`
- `app/main.py` — 启动时创建 `StandaloneAdapter`

**改动模式**：
```python
# 改造前
class CreationService:
    def __init__(self, task_store: AbstractTaskStore, ...):
        self.task_store = task_store

    async def _persist_and_cleanup(self, ...):
        await self.task_store.save_task(...)

# 改造后
class CreationService:
    def __init__(self, adapter: BusinessAdapter, ...):
        self.adapter = adapter

    async def _persist_and_cleanup(self, ...):
        await self.adapter.save_task(...)
```

**不改的部分**：
- `_tasks` dict 逻辑不变
- Graph 调用逻辑不变
- API 路由不变
- 功能行为完全不变，纯重构

**验证**：现有测试全部通过，API 行为无变化。

---

### Step 3：LLM Profile 表 + CRUD

**目标**：在 SQLite 中创建 `llm_profiles` 表，实现 LLM Profile 的增删改查。

**修改文件**：
- `app/services/task_store_sqlite.py` — `init_db()` 中新增 `llm_profiles` 建表
- `app/adapters/base.py` — 补全 LLM Profile 抽象方法
- `app/adapters/standalone.py` — 实现 LLM Profile CRUD

**数据库表**：
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

**约束**：`is_default=1` 最多一条，应用层保证。

**Adapter 方法**：
```python
# base.py 新增
async def get_llm_profile(self, profile_id: str | None = None) -> Optional[dict]
async def get_all_llm_profiles(self) -> list[dict]
async def save_llm_profile(self, profile: dict) -> None
async def delete_llm_profile(self, profile_id: str) -> bool
async def set_default_profile(self, profile_id: str) -> None
```

**验证**：
- 写单元测试验证 CRUD 操作
- 验证 `is_default` 唯一性约束
- 现有功能不受影响

**为 server 端预留**：
- 相同的接口，`ServerAdapter` 未来实现为直读 PostgreSQL
- 写入操作在 server 模式下由 Java 负责，`ServerAdapter` 的写入方法可以为空实现

---

### Step 4：LLMFactory 改造

**目标**：LLMFactory 从读 `settings` 改为读 `adapter.get_llm_profile()`。

**修改文件**：
- `app/graph/common/llm_factory.py` — 核心改造
- 所有调用 `get_default_llm()` 等的 Graph 节点 — 改为 `await`

**核心变化**：
```python
# 改造前（同步）
def get_default_llm() -> BaseChatModel:
    return LLMFactory.create_llm()

# 改造后（异步）
async def get_default_llm() -> BaseChatModel:
    return await LLMFactory.create_llm()
```

**`LLMFactory.create_llm()` 改造**：
- 新增 `profile_id` 参数
- 通过 adapter 获取 Profile 配置
- 处理"无 Profile"场景（抛出 `ValueError`，前端引导用户去设置页）
- 缓存 key 加入 `profile_id`

**需要同步修改的调用方**：
- `app/graph/creation/planner_node.py`
- `app/graph/creation/writer_node.py`
- `app/graph/creation/reducer_node.py`
- `app/graph/polishing/author_node.py`
- `app/graph/polishing/editor_node.py`
- `app/graph/polishing/fact_checker_node.py`
- `app/graph/polishing/formatter_node.py`
- 其他调用 `get_*_llm()` 的地方

**验证**：
- 所有 Graph 节点正常获取 LLM 实例
- 无 Profile 时抛出明确错误
- 现有测试通过

**为 server 端预留**：
- LLMFactory 通过 adapter 读取，不关心数据来自 SQLite 还是 PostgreSQL
- server 模式下 `ServerAdapter.get_llm_profile()` 直读 PG，逻辑相同

---

### Step 5：后端 Settings API

**目标**：新增设置相关的 REST API，供前端设置页调用。

**新增文件**：
- `app/api/v1/settings.py` — 设置路由

**接口定义**：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/settings/llm-profiles` | GET | 获取所有 LLM Profile |
| `/api/v1/settings/llm-profiles` | POST | 创建新 Profile |
| `/api/v1/settings/llm-profiles/{id}` | PUT | 更新 Profile |
| `/api/v1/settings/llm-profiles/{id}` | DELETE | 删除 Profile |
| `/api/v1/settings/llm-profiles/{id}/set-default` | POST | 设为默认 |
| `/api/v1/settings/writing-params` | GET | 获取写作参数 |
| `/api/v1/settings/writing-params` | PATCH | 更新写作参数 |

**写入参数存储**：新增 `settings` 表（key-value），存储 `max_outline_sections`、`max_concurrent_writers` 等。

**修改文件**：
- `app/api/v1/router.py` — 注册 settings 路由

**验证**：
- 用 curl/httpie 测试所有接口
- 验证 Profile 的 CRUD 和默认切换

**为 server 端预留**：
- standalone 模式：这些路由由 Python 直接处理
- server 模式：这些路由不暴露（由 Java 提供等价接口），Python 只暴露 `/internal/` 路由

---

### Step 6：前端设置页

**目标**：完整的设置页面 UI。

**新增文件**：
```
craftflow-web/src/
├── views/Settings.vue                    # 设置页主视图
├── components/settings/
│   ├── LlmProfileList.vue               # LLM 配置列表
│   ├── LlmProfileForm.vue               # 新增/编辑表单
│   ├── WritingParams.vue                # 写作参数设置
│   └── AppearanceSettings.vue           # 外观设置（主题）
├── stores/settings.ts                    # Pinia settings store
└── api/settings.ts                       # Settings API 调用
```

**修改文件**：
- `src/router/index.ts` — 新增 `/settings` 路由
- `src/components/layout/AppSidebar.vue` — footer 区域新增设置按钮

**设置页功能**：

| 区域 | 内容 | 说明 |
|------|------|------|
| 外观 | 主题切换（浅色/深色/跟随系统） | 从侧边栏迁入 |
| LLM 配置 | Profile 列表 + 新增/编辑/删除/设为默认 | 核心功能 |
| 写作参数 | 大纲章节数、并发写作者数 | 滑块/数字输入 |

**验证**：
- 设置页可正常访问
- LLM Profile 的 CRUD 完整可用
- 写作参数修改后生效
- 主题切换正常

**为 server 端预留**：
- 前端设置页在 server 模式下可以复用（通过 API 区分）
- 或 server 模式由 Java 管理后台提供设置功能，前端设置页隐藏管理类选项

---

### Step 7：清理旧配置

**目标**：删除 `.env` 中的 LLM 字段，简化 Settings 类。

**修改文件**：
- `craftflow-backend/.env.dev` — 删除 `LLM_API_KEY`、`LLM_API_BASE`、`LLM_MODEL`、`MAX_TOKENS`、`DEFAULT_TEMPERATURE`
- `craftflow-backend/.env.example` — 同上
- `craftflow-backend/.env.standalone` — 同上
- `craftflow-backend/.env.server` — 同上
- `craftflow-backend/app/core/config.py` — 删除对应的 Settings 字段
- `craftflow-backend/docs/deployment/env-configuration-guide.md` — 更新文档
- `craftflow-backend/CLAUDE.md` — 更新 LLM 配置说明

**保留的 `.env` 字段**（纯基础设施）：
```
APP_MODE=standalone
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
ENABLE_AUTH=false
API_KEY=...
TASKSTORE_BACKEND=sqlite
CHECKPOINTER_BACKEND=sqlite
TAVILY_API_KEY=...
E2B_API_KEY=...
ENABLE_RAG=false
HOST=127.0.0.1
PORT=8000
...
```

**验证**：
- 服务正常启动
- LLM 配置完全从数据库读取
- 无残留的旧 LLM 环境变量引用

---

## 四、server 端预留总结

当前只实现 standalone 模式，但以下设计已为 server 端预留：

| 预留点 | 当前实现 | server 端扩展 |
|--------|---------|--------------|
| `BusinessAdapter` 接口 | ✅ 已定义 | 实现 `ServerAdapter` |
| Service 层依赖 Adapter | ✅ 已切换 | 注入 `ServerAdapter` |
| `llm_profiles` 表 | SQLite | PostgreSQL（相同表结构） |
| LLMFactory 通过 Adapter 读取 | ✅ 已改造 | `ServerAdapter` 直读 PG |
| Settings API 路由 | `/api/v1/settings/*` | server 模式下不暴露，由 Java 提供 |
| `/internal/` 路由 | 未实现 | Java ↔ Python 内部通信 |

**将来接入 Java 后端时需要做的事**：
1. 实现 `ServerAdapter`（`adapters/server.py`）
2. 新增 `main_server.py`（只注册 `/internal/` 路由）
3. 实现 `JavaInternalClient`（调用 Java API）
4. 不动 Service 层、Graph 层、前端设置页

---

**文档版本**: v1.0
**创建日期**: 2026-05-12
**维护者**: Renhao-Wan
