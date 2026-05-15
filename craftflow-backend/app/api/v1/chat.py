"""Chat API 路由

提供 SSE 流式对话端点：
- POST /chat  SSE 流式对话（standalone 前端直连，server Java 代理）
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_chat_service
from app.schemas.chat import ChatRequest
from app.services.chat_svc import ChatService

router = APIRouter(prefix="/chat")


@router.post("")
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """SSE 流式对话端点。

    前端通过 fetch + ReadableStream 消费 SSE 流。
    响应格式：data: {"content": "...", "done": false}\\n\\n
    结束标记：data: [DONE]\\n\\n
    """
    return StreamingResponse(
        service.stream_chat(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
