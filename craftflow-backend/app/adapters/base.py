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
        self, limit: int = 50, offset: int = 0, statuses: tuple[str, ...] | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """查询任务列表（分页），可选按状态过滤"""

    @abstractmethod
    async def delete_task(self, task_id: str) -> bool:
        """删除任务"""

    @abstractmethod
    async def delete_tasks_by_status(self, statuses: tuple[str, ...]) -> int:
        """按状态删除任务，返回被删除的记录数"""

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

    @abstractmethod
    async def save_llm_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """保存或更新 LLM Profile（新建用 INSERT，更新用 UPDATE）"""

    @abstractmethod
    async def delete_llm_profile(self, profile_id: str) -> bool:
        """删除 LLM Profile，返回是否成功"""

    @abstractmethod
    async def set_default_profile(self, profile_id: str) -> bool:
        """将指定 Profile 设为默认，返回是否成功"""

    # ========== 写作参数 ==========

    @abstractmethod
    async def get_writing_params(self) -> dict[str, Any]:
        """获取写作参数"""

    @abstractmethod
    async def update_writing_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """更新写作参数，返回更新后的完整参数"""

    # ========== 外部工具配置 ==========

    @abstractmethod
    async def get_tool_configs(self) -> dict[str, str]:
        """获取所有外部工具配置（tavily_api_key, e2b_api_key 等）"""

    @abstractmethod
    async def update_tool_configs(self, configs: dict[str, Any]) -> dict[str, str]:
        """更新外部工具配置，返回更新后的完整配置"""

    # ========== 生命周期 ==========

    @abstractmethod
    async def init(self) -> None:
        """初始化适配器（建表、连接池等）"""

    @abstractmethod
    async def close(self) -> None:
        """关闭适配器"""
