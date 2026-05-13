"""核心基础设施模块

提供全局配置、日志系统、鉴权和异常处理功能。
"""

from app.core.auth import verify_api_key, verify_ws_api_key
from app.core.config import Settings, get_settings, settings
from app.core import tool_configs
from app.core.exceptions import (
    CheckpointerError,
    CraftFlowException,
    GraphExecutionError,
    LLMProviderError,
    TaskNotFoundError,
    TaskTimeoutError,
    ToolExecutionError,
    ValidationError,
    register_exception_handlers,
)
from app.core.logger import get_logger, logger, setup_logger

__all__ = [
    # 配置
    "Settings",
    "get_settings",
    "settings",
    "tool_configs",
    # 鉴权
    "verify_api_key",
    "verify_ws_api_key",
    # 日志
    "logger",
    "setup_logger",
    "get_logger",
    # 异常
    "CraftFlowException",
    "GraphExecutionError",
    "CheckpointerError",
    "TaskNotFoundError",
    "TaskTimeoutError",
    "LLMProviderError",
    "ToolExecutionError",
    "ValidationError",
    "register_exception_handlers",
]
