"""StandaloneAdapter 实现

standalone 模式下，Python 直接读写 SQLite，同时承担业务层和 AI 层。
适用于桌面端和本地开发。
"""

from typing import Any, Optional

from app.adapters.base import BusinessAdapter
from app.services.task_store_sqlite import SqliteTaskStore


class StandaloneAdapter(BusinessAdapter):
    """standalone 模式适配器

    Python 全栈：直接读写 SQLite（tasks 表 + llm_profiles 表）。
    适用于桌面端和本地开发。
    """

    def __init__(self, db_path: str | None = None):
        self.task_store = SqliteTaskStore(db_path)

    # ========== 生命周期 ==========

    async def init(self) -> None:
        await self.task_store.init_db()

    async def close(self) -> None:
        await self.task_store.close()

    # ========== 任务管理（委托 SqliteTaskStore） ==========

    async def save_task(self, task: dict[str, Any]) -> None:
        await self.task_store.save_task(task)

    async def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        return await self.task_store.get_task(task_id)

    async def get_task_list(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        return await self.task_store.get_task_list(limit, offset)

    async def delete_task(self, task_id: str) -> bool:
        return await self.task_store.delete_task(task_id)

    async def get_interrupted_tasks(self) -> list[dict[str, Any]]:
        return await self.task_store.get_interrupted_tasks()

    # ========== LLM 配置（Step 3 实现） ==========

    async def get_llm_profile(self, profile_id: str | None = None) -> Optional[dict[str, Any]]:
        raise NotImplementedError("LLM Profile 功能将在 Step 3 实现")

    async def get_all_llm_profiles(self) -> list[dict[str, Any]]:
        raise NotImplementedError("LLM Profile 功能将在 Step 3 实现")
