"""
数据传输对象 (DTO) 模块

本模块导出所有 API 请求和响应模型，供路由层使用。
"""

from app.schemas.chat import (
    ChatChunk,
    ChatMessage,
    ChatRequest,
    TestProfileResponse,
)
from app.schemas.request import (
    CreationRequest,
    PolishingRequest,
    ResumeRequest,
)
from app.schemas.response import (
    ErrorResponse,
    TaskResponse,
    TaskStatusResponse,
)

__all__ = [
    # 对话模型
    "ChatMessage",
    "ChatRequest",
    "ChatChunk",
    "TestProfileResponse",
    # 请求模型
    "CreationRequest",
    "PolishingRequest",
    "ResumeRequest",
    # 响应模型
    "TaskResponse",
    "TaskStatusResponse",
    "ErrorResponse",
]
