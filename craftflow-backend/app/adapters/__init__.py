"""适配器层

隔离 standalone 和 server 模式的业务差异。
Service 层通过 BusinessAdapter 接口与业务数据交互，不感知底层实现。
"""

from app.adapters.base import BusinessAdapter
from app.adapters.standalone import StandaloneAdapter

__all__ = [
    "BusinessAdapter",
    "StandaloneAdapter",
]
