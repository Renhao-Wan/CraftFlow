"""LLM 对话相关 Schema 定义

定义 SSE 流式对话和 LLM Profile 连接测试的请求/响应模型。
"""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """对话消息模型"""

    role: Literal["user", "assistant"] = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, description="消息内容")


class ChatRequest(BaseModel):
    """SSE 流式对话请求"""

    messages: list[ChatMessage] = Field(..., min_length=1, description="对话历史")
    profile_id: str | None = Field(default=None, description="指定 LLM Profile ID，不传则使用默认")

    class Config:
        json_schema_extra = {
            "example": {
                "messages": [{"role": "user", "content": "你好，请介绍一下自己"}],
                "profile_id": None,
            }
        }


class ChatChunk(BaseModel):
    """SSE 流式响应 chunk"""

    content: str = Field(default="", description="本次 chunk 的文本内容")
    done: bool = Field(default=False, description="是否生成完毕")
    error: str | None = Field(default=None, description="错误信息（流中途出错时）")


class TestProfileResponse(BaseModel):
    """LLM Profile 连接测试响应"""

    success: bool = Field(..., description="测试是否成功")
    reply: str | None = Field(default=None, description="LLM 回复内容（成功时）")
    error: str | None = Field(default=None, description="错误信息（失败时）")
    latency_ms: int | None = Field(default=None, description="响应延迟（毫秒）")
