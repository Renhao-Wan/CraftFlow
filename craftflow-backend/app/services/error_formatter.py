"""错误消息格式化工具

将后端异常转换为用户友好的错误消息，避免暴露内部实现细节。
"""


def format_error_message(error: Exception) -> str:
    """将异常转换为用户友好的错误消息

    Args:
        error: 捕获的异常

    Returns:
        str: 用户友好的错误消息
    """
    raw = str(error)
    error_type = type(error).__name__

    # API Key 无效
    if "invalid_api_key" in raw or "Incorrect API key" in raw:
        return "API Key 无效，请在设置页面检查 LLM 配置"

    # 401 认证失败
    if "401" in raw and ("authentication" in raw.lower() or "unauthorized" in raw.lower()):
        return "API 认证失败，请在设置页面检查 LLM 配置"

    # 429 速率限制 / 余额不足
    if "429" in raw or "rate_limit" in raw:
        if "quota" in raw.lower() or "billing" in raw.lower() or "insufficient" in raw.lower():
            return "API 账户余额不足，请充值或更换 API Key"
        return "API 请求频率过高，请稍后重试"

    # 404 模型不存在
    if "404" in raw or "model_not_found" in raw or "does not exist" in raw:
        return "指定的模型不存在，请在设置页面检查模型名称"

    # 网络连接错误
    if any(
        kw in raw.lower() for kw in ["connectionerror", "connection refused", "connect timeout"]
    ):
        return "无法连接到 LLM 服务，请检查网络连接或 API 地址配置"

    # 请求超时
    if "timeout" in raw.lower() or "timed out" in raw.lower():
        return "LLM 请求超时，请稍后重试"

    # 500/502/503 服务端错误
    if any(code in raw for code in ["500", "502", "503"]):
        return "LLM 服务暂时不可用，请稍后重试"

    # 已格式化的 CraftFlowException（ValidationError 等），直接使用原消息
    if error_type in ("ValidationError", "CraftFlowException"):
        return raw

    # 兜底：返回通用消息
    return f"任务执行失败: {raw[:200]}" if len(raw) > 200 else f"任务执行失败: {raw}"
