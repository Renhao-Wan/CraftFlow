"""外部工具 API 配置缓存

启动时从 adapter 加载到内存，运行时同步读取（供同步 @tool 函数使用）。
API 更新时通过 refresh() 刷新缓存，无需重启服务。

使用方式：
    # 启动时
    await tool_configs.load_from_adapter(adapter)

    # 运行时（同步读取）
    key = tool_configs.get("tavily_api_key")

    # API 更新后
    tool_configs.refresh("tavily_api_key", "new-key")
"""

from typing import Any

_configs: dict[str, str] = {}


async def load_from_adapter(adapter: Any) -> None:
    """从 adapter 加载配置到缓存（启动时调用）"""
    global _configs
    _configs = await adapter.get_tool_configs()


def get(key: str) -> str:
    """同步读取配置值，未配置时返回空字符串"""
    return _configs.get(key, "")


def refresh(key: str, value: str) -> None:
    """API 更新后刷新缓存"""
    _configs[key] = value
