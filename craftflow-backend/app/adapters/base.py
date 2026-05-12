"""BusinessAdapter 抽象接口

定义 standalone 和 server 模式的统一业务接口。
Service 层依赖此接口，不感知底层实现差异。
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BusinessAdapter(ABC):
    """业务层适配器接口

    隔离 standalone 和 server 模式的差异。
    Service 层通过此接口与业务数据交互，不感知底层实现。
    """

    # ========== 任务管理 ==========

    @abstractmethod
    async def save_task(self, task: dict[str, Any]) -> None:
        """保存或更新任务记录"""

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        """查询单个任务"""

    @abstractmethod
    async def get_task_list(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        """查询任务列表（分页）"""

    @abstractmethod
    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""

    @abstractmethod
    async def get_interrupted_tasks(self) -> list[dict[str, Any]]:
        """查询所有中断任务（用于服务重启恢复）"""

    # ========== LLM 配置 ==========

    @abstractmethod
    async def get_llm_profile(self, profile_id: str | None = None) -> Optional[dict[str, Any]]:
        """获取 LLM Profile（None = 默认 Profile）"""

    @abstractmethod
    async def get_all_llm_profiles(self) -> list[dict[str, Any]]:
        """获取所有 LLM Profile"""

    # ========== 生命周期 ==========

    @abstractmethod
    async def init(self) -> None:
        """初始化适配器（建表、连接池等）"""

    @abstractmethod
    async def close(self) -> None:
        """关闭适配器"""
