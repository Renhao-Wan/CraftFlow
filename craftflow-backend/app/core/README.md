# CraftFlow 核心基础设施模块

本模块提供 CraftFlow 后端的基础设施功能，包括配置管理、日志系统和异常处理。

---

## 📦 模块结构

```
app/core/
├── __init__.py          # 模块导出
├── config.py            # 全局配置管理
├── logger.py            # 结构化日志系统
├── exceptions.py        # 自定义异常与处理器
└── README.md            # 本文档
```

---

## 🚀 快速开始

### 1. 配置管理

```python
from app.core import settings

# 访问配置
print(f"运行环境: {settings.environment}")
print(f"是否生产环境: {settings.is_production}")
print(f"运行模式: {settings.app_mode}")
```

**配置来源**: `.env.dev` 文件（开发环境）或环境变量。`config.py` 仅保留基础设施配置（APP_MODE、鉴权、持久化后端、外部工具等）。LLM 配置已迁移至数据库 `llm_profiles` 表，写作参数已迁移至数据库 `settings` 表，均通过前端设置页面管理。

### 2. 日志系统

```python
from app.core import logger, setup_logger

# 在应用启动时初始化（只需调用一次）
setup_logger()

# 使用日志
logger.info("应用启动成功")
logger.debug("调试信息", extra={"user_id": 123})
logger.warning("警告信息")
logger.error("错误信息")

# 带上下文的日志
from app.core import get_logger
module_logger = get_logger(__name__)
module_logger.info("模块日志")
```

**日志输出**:
- 终端：彩色输出（开发环境）
- 文件：`logs/app_{date}.log`（所有级别）
- 文件：`logs/error_{date}.log`（仅错误）

### 3. 异常处理

```python
from app.core import (
    TaskNotFoundError,
    GraphExecutionError,
    ValidationError,
)

# 抛出业务异常
def get_task(task_id: str):
    if not task_exists(task_id):
        raise TaskNotFoundError(task_id=task_id)
    return task

# 抛出带详情的异常
def execute_graph():
    try:
        # ... graph 执行逻辑
        pass
    except Exception as e:
        raise GraphExecutionError(
            message="节点执行失败",
            details={"node": "PlannerNode", "error": str(e)}
        )
```

**FastAPI 集成**:

```python
from fastapi import FastAPI
from app.core import register_exception_handlers

app = FastAPI()

# 注册全局异常处理器
register_exception_handlers(app)

# 现在所有异常都会被自动处理并返回统一格式
```

---

## 📋 配置项说明

### 应用配置
- `app_name`: 应用名称
- `app_version`: 应用版本
- `environment`: 运行环境（development/production）
- `debug`: 调试模式
- `log_level`: 日志级别（DEBUG/INFO/WARNING/ERROR）

### 持久化配置
- `use_persistent_checkpointer`: 是否使用持久化 Checkpointer
- `database_url`: PostgreSQL 数据库连接 URL
- `db_pool_size`: 数据库连接池大小
- `db_max_overflow`: 连接池最大溢出数

### 外部工具配置
- `tavily_api_key`: Tavily Search API 密钥
- `e2b_api_key`: E2B Code Interpreter API 密钥

### 服务配置
- `host`: 服务监听地址
- `port`: 服务监听端口
- `cors_origins`: 允许的跨域来源（逗号分隔）

### 已迁移至数据库的配置

以下配置已从 `config.py` / `.env` 迁移至数据库，通过前端设置页面或 Settings API 管理：

**LLM 配置**（`llm_profiles` 表）：
- `api_key`、`api_base`、`model`、`temperature` 等，支持多 Profile 管理

**写作参数**（`settings` 表）：
- `max_outline_sections`：大纲最大章节数
- `max_concurrent_writers`：并发写作节点数量上限
- `max_debate_iterations`：对抗循环最大迭代次数
- `editor_pass_score`：主编通过分数阈值
- `task_timeout`：任务超时时间（秒）
- `tool_call_timeout`：工具调用超时时间（秒）

---

## 🎯 异常类型

### CraftFlowException (基类)
所有业务异常的基类，包含：
- `error_code`: 错误码（用于前端识别）
- `message`: 错误消息
- `status_code`: HTTP 状态码
- `details`: 额外的错误详情

### 具体异常类型

| 异常类                    | 错误码                     | 状态码 | 使用场景              |
|------------------------|-------------------------|-----|-------------------|
| GraphExecutionError    | GRAPH_EXECUTION_ERROR   | 500 | Graph 执行失败       |
| CheckpointerError      | CHECKPOINTER_ERROR      | 500 | 状态持久化失败          |
| TaskNotFoundError      | TASK_NOT_FOUND          | 404 | 任务不存在            |
| TaskTimeoutError       | TASK_TIMEOUT            | 408 | 任务执行超时           |
| LLMProviderError       | LLM_PROVIDER_ERROR      | 502 | LLM API 调用失败     |
| ToolExecutionError     | TOOL_EXECUTION_ERROR    | 502 | 外部工具调用失败         |
| ValidationError        | VALIDATION_ERROR        | 422 | 业务逻辑验证失败         |

### 错误响应格式

```json
{
  "error_code": "TASK_NOT_FOUND",
  "message": "任务不存在: abc123",
  "details": {
    "task_id": "abc123"
  }
}
```

---

## 🔧 高级用法

### 1. 自定义日志格式

```python
from app.core.logger import logger

# 结构化日志
logger.bind(
    user_id=123,
    request_id="abc-123"
).info("用户操作", action="create_task")
```

### 2. 环境特定配置

```python
from app.core import settings

if settings.is_production:
    # 生产环境特定逻辑
    enable_monitoring()
else:
    # 开发环境特定逻辑
    enable_debug_mode()
```

### 3. 配置验证

```python
from app.core.config import Settings

# 手动创建配置实例（用于测试）
test_settings = Settings(
    environment="development"
)
```

---

## 📝 最佳实践

### 1. 日志记录
- ✅ 使用结构化日志（bind 方法）
- ✅ 记录关键业务操作
- ✅ 错误日志包含上下文信息
- ❌ 避免在循环中记录大量日志
- ❌ 避免记录敏感信息（密码、Token）

### 2. 异常处理
- ✅ 使用具体的异常类型
- ✅ 提供详细的错误信息
- ✅ 在异常中包含上下文（details）
- ❌ 避免捕获后不处理
- ❌ 避免使用通用 Exception

### 3. 配置管理
- ✅ 使用环境变量管理敏感信息
- ✅ 提供合理的默认值
- ✅ 使用类型注解
- ❌ 避免硬编码配置
- ❌ 避免在代码中修改配置

---

## 🧪 测试

运行配置验证测试：
```bash
python scripts/check_config.py
```

运行异常处理测试：
```bash
python tests/test_exceptions.py
```

---

## 📚 依赖

- `pydantic >= 2.10.0`: 配置管理和数据验证
- `pydantic-settings >= 2.7.0`: 环境变量读取
- `loguru >= 0.7.3`: 结构化日志
- `fastapi >= 0.115.0`: Web 框架（异常处理器）

---

## 🔗 相关文档

- [开发计划](../../../docs/plan/dev-plan.md)
- [系统架构设计](../../../../docs/architecture.md)

---

**维护者**: Renhao-Wan
**最后更新**: 2026-05-13
