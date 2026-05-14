"""LLM 对话服务

提供 SSE 流式对话和 LLM Profile 连接测试功能。
与 CreationService/PolishingService 不同，本服务不管理任务生命周期，
对话数据仅在内存中临时存在，不持久化。
"""

import json
import time
from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
)

from app.adapters.base import BusinessAdapter
from app.core.logger import get_logger
from app.graph.common.llm_factory import LLMFactory
from app.schemas.chat import ChatMessage, ChatRequest, TestProfileResponse


def _map_stream_error(error: Exception) -> str:
    """将异常映射为用户友好的错误信息。

    与 test_profile 方法保持一致的错误映射策略。
    """
    if isinstance(error, AuthenticationError):
        return "API Key 无效，请检查配置"
    if isinstance(error, NotFoundError):
        return "模型不存在，请检查模型名称"
    if isinstance(error, RateLimitError):
        return "请求频率超限，请稍后重试"
    if isinstance(error, APITimeoutError):
        return "请求超时，请检查网络连接"
    if isinstance(error, APIConnectionError):
        return "无法连接到 API 服务器，请检查网络或 API Base 地址"
    if isinstance(error, APIStatusError):
        return f"API 返回错误 (HTTP {error.status_code})"
    if isinstance(error, ValueError):
        return str(error)
    return "对话请求失败，请稍后重试"

logger = get_logger(__name__)


class ChatService:
    """对话服务，负责 LLM 流式对话和连接测试。

    Attributes:
        adapter: 业务适配器，用于获取 LLM Profile 信息
    """

    TEST_MESSAGE = "请回复OK，确认连接正常。"

    def __init__(self, adapter: BusinessAdapter) -> None:
        self.adapter = adapter

    async def stream_chat(
        self,
        request: ChatRequest,
    ) -> AsyncGenerator[str, None]:
        """SSE 流式对话生成器。

        调用 LLMFactory.create_llm 获取 LLM 实例，使用 astream() 流式输出。
        将 LLM 返回的 chunk 拆分为单字符逐个输出，实现平滑的打字机效果。

        Args:
            request: 对话请求，包含消息历史和可选的 profile_id

        Yields:
            SSE 格式的 chunk 字符串（data: {...}\\n\\n）
        """
        try:
            llm = await LLMFactory.create_llm(profile_id=request.profile_id, streaming=True)
            messages = self._convert_messages(request.messages)

            async for chunk in llm.astream(messages):
                content = chunk.content if isinstance(chunk.content, str) else ""
                yield f"data: {json.dumps({'content': content, 'done': False}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'content': '', 'done': True}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"流式对话异常: {e}")
            error_msg = _map_stream_error(e)
            yield f"data: {json.dumps({'content': '', 'done': True, 'error': error_msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    async def test_profile(self, profile_id: str) -> TestProfileResponse:
        """测试 LLM Profile 连接。

        发送固定测试消息，返回完整响应和延迟。

        Args:
            profile_id: LLM Profile ID

        Returns:
            TestProfileResponse，包含成功/失败状态和响应内容
        """
        try:
            llm = await LLMFactory.create_llm(profile_id=profile_id, streaming=False)
            start_time = time.monotonic()

            response = await llm.ainvoke([HumanMessage(content=self.TEST_MESSAGE)])

            latency_ms = int((time.monotonic() - start_time) * 1000)
            content = (
                response.content if isinstance(response.content, str) else str(response.content)
            )

            logger.info(f"LLM Profile 测试成功: profile_id={profile_id}, latency={latency_ms}ms")
            return TestProfileResponse(success=True, reply=content, latency_ms=latency_ms)

        except Exception as e:
            logger.error(f"LLM Profile 测试失败: profile_id={profile_id}, error={e}")
            return TestProfileResponse(success=False, error=_map_stream_error(e))

    @staticmethod
    def _convert_messages(messages: list[ChatMessage]) -> list[BaseMessage]:
        """将 ChatMessage 列表转换为 LangChain BaseMessage 列表。

        Args:
            messages: 前端传来的对话消息列表

        Returns:
            LangChain BaseMessage 列表
        """
        result: list[BaseMessage] = []
        for msg in messages:
            if msg.role == "user":
                result.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                result.append(AIMessage(content=msg.content))
        return result
