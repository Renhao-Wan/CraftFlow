# CraftFlow 设置系统架构设计

> 本文档描述 CraftFlow 的设置系统设计，包括 LLM 多配置管理、桌面端与网页端的差异化设置、以及 `.env` 配置的职责简化。

## 一、设计背景

### 1.1 现状问题

当前 LLM 配置通过 `.env` 文件的 5 个扁平字段管理：

```bash
LLM_API_KEY=xxx
LLM_API_BASE=xxx
LLM_MODEL=gpt-4-turbo
MAX_TOKENS=4096
DEFAULT_TEMPERATURE=0.7
```

存在以下问题：
- **单模型限制**：只能配置一个 LLM，无法按场景选择不同模型
- **职责混乱**：`.env` 同时承载基础设施配置和业务配置
- **不适应多端架构**：Java 层（业务层）管理 LLM 配置更合理，但 `.env` 是 Python 层直接读取的

### 1.2 设计目标

- 支持多个 LLM 配置（Profile），用户可按需切换
- LLM 配置作为**业务数据**存入数据库，与 Java 层共享
- `.env` 退化为纯基础设施配置，不包含业务参数
- 桌面端和网页端共享同一套设置系统，通过 `APP_MODE` 控制差异

## 二、设置分层模型

```
┌─────────────────────────────────────────────────────────┐
│ 第一层：用户偏好（前端 localStorage）                      │
│ - 主题（浅色/深色/跟随系统）                               │
│ - 未来：语言、UI 布局偏好                                  │
│ 特点：即时生效，不涉及后端，用户个人                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ 第二层：运行时参数（数据库 llm_profiles 表）                │
│ - LLM 配置（API Key、模型、温度等）                        │
│ - 写作参数（章节数、并发数等）                               │
│ 特点：热更新，无需重启，所有用户共享（server 模式）           │
└─────────────────────────────────────────────────────────┘
```

## 三、LLM 多配置管理

### 3.1 核心概念：LLM Profile

每个 LLM Profile 是一组完整的 LLM 连接配置：

| 字段 | 说明 | 示例 |
|------|------|------|
| `id` | UUID 主键 | `a1b2c3d4-...` |
| `name` | 用户自定义名称 | `GPT-4o`、`DeepSeek`、`本地 Ollama` |
| `api_key` | API 密钥 | `sk-xxx` |
| `api_base` | API 基础 URL | `https://api.openai.com/v1`、留空使用默认 |
| `model` | 模型名称 | `gpt-4o`、`deepseek-chat` |
| `temperature` | 温度参数 | `0.7` |
| `is_default` | 是否默认 | `1` = 创建任务时默认使用 |
| `created_at` | 创建时间 | ISO 格式 |
| `updated_at` | 更新时间 | ISO 格式 |

**约束**：`is_default=1` 的记录最多只能有一条（应用层保证）。

### 3.2 数据库表设计

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

### 3.3 存储位置

LLM Profile 存储在 **tasks 表同一个数据库**中（`craftflow.db` / PostgreSQL），不新建独立数据库。

| 模式 | 数据库 | 说明 |
|------|--------|------|
| standalone（桌面端） | `data/sqlite/craftflow.db` | 与 tasks 表共存 |
| server（网页端） | PostgreSQL | 与 tasks 表共存，Java 层和 Python 层共享 |

### 3.4 与现有 `.env` 配置的关系

`.env` 中的 LLM 字段（`LLM_API_KEY`、`LLM_API_BASE`、`LLM_MODEL`、`MAX_TOKENS`、`DEFAULT_TEMPERATURE`）**完全删除**。

启动引导逻辑：

```
应用启动
  │
  ├─ 读取 llm_profiles 表
  │
  ├─ 有数据 → 正常启动，使用 is_default=1 的 Profile
  │
  └─ 空表 → 提示用户去设置页添加 LLM 配置
              （创作/润色页面显示"请先配置 LLM"引导）
```

> **设计决策**：不保留 `.env` 中的 LLM 字段作为 fallback。原因是：
> 1. 保留会导致两个配置来源（`.env` 和数据库），增加维护复杂度
> 2. Server 端由 Java 层管理 LLM 配置，`.env` 中的字段没有意义
> 3. 强制走数据库保证了架构一致性

## 四、对现有代码的影响

### 4.1 LLMFactory 改造

当前 `LLMFactory` 从 `settings` 单例读取配置：

```python
# 当前实现
def create_llm(cls, temperature=None, model=None, max_tokens=None, ...):
    temperature = temperature or settings.default_temperature
    model = model or settings.llm_model
    # ...
    llm = cls._create_openai_compatible_llm(model, temperature, max_tokens, ...)
```

改造后从数据库读取 Profile：

```python
# 改造后
def create_llm(cls, profile_id: str | None = None, temperature=None, model=None, ...):
    if profile_id:
        profile = await llm_profile_store.get_profile(profile_id)
    else:
        profile = await llm_profile_store.get_default_profile()

    if not profile:
        raise ValueError("未找到 LLM 配置，请先在设置页添加")

    # Profile 值为默认，调用方显式传入的值覆盖
    api_key = profile["api_key"]
    api_base = profile["api_base"]
    model = model or profile["model"]
    temperature = temperature if temperature is not None else profile["temperature"]
    # ...
```

**关键变化**：
- `create_llm()` 变为 `async`（需要查询数据库）
- 缓存 key 从 `"{model}_{temperature}_{max_tokens}_..."` 变为 `"{profile_id}_{temperature}_{max_tokens}_..."`
- 节点专用 getter（`get_editor_llm()` 等）仍可覆盖 temperature 和 max_tokens

### 4.2 Settings 类简化

删除以下字段（从 `.env` 移除）：

```python
# 删除
llm_api_key: str
llm_api_base: str
llm_model: str
max_tokens: int
default_temperature: float
```

保留基础设施字段不变。

### 4.3 .env 文件简化

**改造前**（`.env.dev` 示例）：
```bash
APP_MODE=standalone
LLM_API_KEY=sk-xxx                # ← 删除（迁移至 llm_profiles 表）
LLM_API_BASE=xxx                   # ← 删除
LLM_MODEL=gpt-4-turbo              # ← 删除
MAX_TOKENS=4096                     # ← 删除
DEFAULT_TEMPERATURE=0.7             # ← 删除
MAX_OUTLINE_SECTIONS=10             # ← 删除（迁移至 settings 表）
MAX_CONCURRENT_WRITERS=5            # ← 删除
MAX_DEBATE_ITERATIONS=3             # ← 删除
EDITOR_PASS_SCORE=90                # ← 删除
TASK_TIMEOUT=3600                   # ← 删除
TOOL_CALL_TIMEOUT=30                # ← 删除
TASKSTORE_BACKEND=sqlite
CHECKPOINTER_BACKEND=sqlite
```

**改造后**：
```bash
APP_MODE=standalone
TASKSTORE_BACKEND=sqlite
CHECKPOINTER_BACKEND=sqlite
```

`.env` 只保留基础设施配置（APP_MODE、数据库后端、向量数据库等），LLM 配置、写作参数和外部工具 API Key 全部从数据库读取。

## 五、后端 API 设计

### 5.1 LLM Profile 管理接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/settings/llm-profiles` | GET | 获取所有 LLM Profile 列表 |
| `/api/v1/settings/llm-profiles` | POST | 创建新 Profile |
| `/api/v1/settings/llm-profiles/{id}` | PUT | 更新 Profile |
| `/api/v1/settings/llm-profiles/{id}` | DELETE | 删除 Profile |
| `/api/v1/settings/llm-profiles/{id}/set-default` | POST | 设为默认 |

### 5.2 写作参数接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/settings/writing-params` | GET | 获取当前写作参数 |
| `/api/v1/settings/writing-params` | PATCH | 更新写作参数 |

写作参数存储在 `llm_profiles` 表之外，可以新建一张小表或使用 JSON 字段：

```sql
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

存储：
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

### 5.3 运行时参数热更新

`PATCH /api/v1/settings/writing-params` 修改后：
1. 写入数据库 `settings` 表
2. 更新内存中的配置缓存
3. 下次创建任务时使用新参数
4. **不需要重启服务**

## 六、桌面端与网页端差异

### 6.1 设置页功能对比

| 设置项 | 桌面端（standalone） | 网页端（server） |
|--------|---------------------|-----------------|
| 主题切换 | ✅ | ✅ |
| LLM Profile 管理 | ✅ 用户自行管理 | ❌ 已在数据库配好 |
| 写作参数 | ✅ | ✅ |
| 外部工具 API Key | ✅ 用户自己填 | ❌ 已在数据库配好 |
| 数据目录展示 | ✅ 显示本地路径 | ❌ 不适用 |
| 清除本地数据 | ✅ 清空 SQLite | ❌ 不适用 |

### 6.2 配置来源差异

```
桌面端（standalone）：
┌─────────────────────────────────────────┐
│ Electron 设置页                          │
│  → 写入 SQLite (craftflow.db)            │
│  → Python 后端从 SQLite 读取              │
└─────────────────────────────────────────┘

网页端（server）：
┌─────────────────────────────────────────┐
│ Java 管理后台                             │
│  → 写入 PostgreSQL                       │
│  → Python 后端从 PostgreSQL 读取          │
│  → 用户前端只修改偏好类设置                │
└─────────────────────────────────────────┘
```

**Python 后端代码完全相同**：它只从数据库读取 `llm_profiles`，不关心是谁写入的。

---

**文档版本**: v1.1
**创建日期**: 2026-05-12
**最后更新**: 2026-05-13
**维护者**: Renhao-Wan
