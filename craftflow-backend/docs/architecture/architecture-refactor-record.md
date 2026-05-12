# CraftFlow 架构改造实施记录

> 本文档记录 CraftFlow 从"双端硬编码"演进为"一套代码、配置驱动"架构的实施过程。

## 改造目标

遵循 **12-Factor App** 架构规范，实现：
- 单一代码库，配置驱动
- 工厂模式，存储组件运行时动态绑定
- 渐进式改造，每阶段可独立验证

## 实施阶段

### Phase 1：配置层改造 ✅

| 步骤 | 任务 | 涉及文件 |
|------|------|----------|
| 1.1 | 新增 `APP_MODE`, `ENABLE_AUTH`, `TASKSTORE_BACKEND` 等配置项 | `app/core/config.py` |
| 1.2 | 添加 `model_validator` 实现模式自动调整 | `app/core/config.py` |
| 1.3 | 创建 `.env.standalone` 和 `.env.server` 模板 | 项目根目录 |
| 1.4 | 统一 `_get_env_file()` 逻辑，消除硬编码 | `app/core/config.py` |

### Phase 2：TaskStore 抽象化 ✅

| 步骤 | 任务 | 涉及文件 |
|------|------|----------|
| 2.1 | 定义 `AbstractTaskStore` 接口 | `app/services/task_store.py` |
| 2.2 | 抽取 `SqliteTaskStore` 实现 | `app/services/task_store_sqlite.py` |
| 2.3 | 实现 `PostgresTaskStore` | `app/services/task_store_postgres.py` |
| 2.4 | 实现 `create_task_store()` 工厂函数 | `app/services/task_store.py` |
| 2.5 | 修改 `dependencies.py` 使用工厂函数 | `app/api/dependencies.py` |

**完成内容**：
- `task_store.py` 重构为抽象接口 + 工厂函数，保留 `TaskStore` 别名向后兼容
- `task_store_sqlite.py`：从原 `task_store.py` 提取，支持桌面端 `%APPDATA%` 路径
- `task_store_postgres.py`：基于 asyncpg 连接池的 PostgreSQL 实现
- `dependencies.py`：使用 `create_task_store()` 工厂替代直接实例化
- 所有类型引用更新为 `AbstractTaskStore`

### Phase 3：鉴权模块 ✅

| 步骤 | 任务 | 涉及文件 |
|------|------|----------|
| 3.1 | 实现 `auth.py` API Key 验证模块 | `app/core/auth.py` |
| 3.2 | 添加 `verify_api_key` 依赖 | `app/core/auth.py` |
| 3.3 | 改造 REST 路由注入鉴权 | `app/api/v1/*.py` |
| 3.4 | 改造 WebSocket 鉴权 | `app/api/v1/ws.py` |
| 3.5 | 生产环境异常信息脱敏 | `app/core/exceptions.py` |

**完成内容**：
- `auth.py`：实现 `verify_api_key`（REST 鉴权）和 `verify_ws_api_key`（WebSocket 鉴权）
- standalone 模式自动放行，server 模式验证 `X-API-Key` 请求头
- `exceptions.py`：生产环境下隐藏内部实现细节
- `tests/test_auth.py`：13 个测试覆盖 standalone/server 模式

### Phase 4：依赖注入改造 ✅

| 步骤 | 任务 | 涉及文件 |
|------|------|----------|
| 4.1 | 重构 `init_services()` 支持模式感知 | `app/api/dependencies.py` |
| 4.2 | 将 `_load_interrupted_tasks()` 内聚到 Service | `app/services/creation_svc.py`, `polishing_svc.py` |
| 4.3 | 条件化 WebSocket 服务初始化 | `app/main.py` |

**完成内容**：
- `dependencies.py`：移除独立的 `_load_interrupted_tasks()` 函数，委托给各 Service
- `creation_svc.py` / `polishing_svc.py`：新增 `load_interrupted_tasks()` 方法
- `main.py`：WebSocket 服务仅在 server 模式下初始化

### Phase 5：集成测试与文档 ✅

| 步骤 | 任务 | 涉及文件 |
|------|------|----------|
| 5.1 | 编写 standalone 模式端到端测试 | `tests/test_standalone.py` |
| 5.2 | 编写 server 模式端到端测试 | `tests/test_server.py` |
| 5.3 | 更新 README 和架构文档 | `README.md`, `docs/` |
| 5.4 | 更新 `.env.example` | 项目根目录 |

**完成内容**：
- `test_standalone.py`：11 个测试覆盖 standalone 模式全流程
- `test_server.py`：18 个测试覆盖 server 模式鉴权场景
- 全量测试 219 个全部通过

## 文件变更清单

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

## 验收标准

### 功能验收 ✅

- [x] standalone 模式：SQLite 存储，无鉴权，所有功能正常
- [x] server 模式：PostgreSQL 存储，API Key 鉴权，所有功能正常
- [x] 模式切换：仅修改 `APP_MODE` 和相关数据库配置，代码无需改动

### 安全验收 ✅

- [x] server 模式下，无 API Key 请求返回 401
- [x] server 模式下，无效 API Key 返回 403
- [x] standalone 模式下，无鉴权直接放行
- [x] 生产环境异常响应不包含内部实现细节

### 代码质量验收 ✅

- [x] 所有现有测试通过（219 个测试全部通过）
- [x] 新增代码测试覆盖率 > 80%
- [x] 代码格式化（black/ruff）通过

---

**文档版本**: v1.0  
**创建日期**: 2026-05-12  
**维护者**: Renhao-Wan
