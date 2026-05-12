"""鉴权模块

提供轻量级 API Key 验证，保护 Python 后端的 REST 和 WebSocket 端点。

职责划分：
- standalone 模式：无鉴权，自动放行
- server 模式：验证请求头中的 X-API-Key，确认调用方是合法的 Java 后端
- JWT 签发/验证属于 Java 后端职责，Python 后端不做用户鉴权
"""

from typing import Any

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# API Key 从请求头 X-API-Key 读取
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Depends(api_key_header),
) -> dict[str, Any]:
    """验证 API Key，返回调用方信息

    作为 FastAPI 依赖注入到需要鉴权的路由中。

    - standalone 模式：跳过验证，返回默认调用方
    - server 模式：验证 X-API-Key 请求头

    Args:
        api_key: 从 X-API-Key 请求头提取的值

    Returns:
        调用方信息字典，如 {"caller": "local", "authenticated": True}

    Raises:
        HTTPException 401: 未提供 API Key
        HTTPException 403: API Key 无效
    """
    if not settings.enable_auth:
        return {"caller": "local", "authenticated": True}

    if api_key is None:
        logger.warning("API Key 验证失败：未提供 API Key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供 API Key",
        )

    if api_key != settings.api_key:
        logger.warning("API Key 验证失败：无效的 API Key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无效的 API Key",
        )

    return {"caller": "java-backend", "authenticated": True}


async def verify_ws_api_key(websocket: WebSocket) -> bool:
    """验证 WebSocket 连接的 API Key

    WebSocket 无法使用标准 HTTP 请求头鉴权，因此从查询参数读取 API Key。

    - standalone 模式：跳过验证，直接返回 True
    - server 模式：验证 api_key 查询参数

    Args:
        websocket: WebSocket 连接对象

    Returns:
        验证是否通过

    Side Effects:
        验证失败时关闭 WebSocket 连接（code 4001）
    """
    if not settings.enable_auth:
        return True

    api_key = websocket.query_params.get("api_key")

    if api_key is None:
        logger.warning("WebSocket API Key 验证失败：未提供 api_key 参数")
        await websocket.close(code=4001, reason="未提供 API Key")
        return False

    if api_key != settings.api_key:
        logger.warning("WebSocket API Key 验证失败：无效的 api_key")
        await websocket.close(code=4001, reason="无效的 API Key")
        return False

    return True
