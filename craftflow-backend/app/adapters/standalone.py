"""StandaloneAdapter 实现

standalone 模式下，Python 直接读写 SQLite，同时承担业务层和 AI 层。
适用于桌面端和本地开发。
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.adapters.base import BusinessAdapter
from app.core.logger import get_logger
from app.services.task_store_sqlite import SqliteTaskStore

logger = get_logger(__name__)


class StandaloneAdapter(BusinessAdapter):
    """standalone 模式适配器

    Python 全栈：直接读写 SQLite（tasks 表 + llm_profiles 表）。
    适用于桌面端和本地开发。
    """

    def __init__(self, db_path: Path | None = None):
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

    # ========== LLM 配置 ==========

    @property
    def _db(self):
        """复用 SqliteTaskStore 的数据库连接"""
        return self.task_store._db

    async def get_llm_profile(self, profile_id: str | None = None) -> Optional[dict[str, Any]]:
        """获取单个 LLM Profile

        Args:
            profile_id: Profile ID，None 时返回默认 Profile
        """
        if self._db is None:
            raise RuntimeError("StandaloneAdapter 未初始化")

        if profile_id is not None:
            cursor = await self._db.execute(
                "SELECT * FROM llm_profiles WHERE id = ?", (profile_id,)
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM llm_profiles WHERE is_default = 1"
            )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _profile_row_to_dict(cursor, row)

    async def get_all_llm_profiles(self) -> list[dict[str, Any]]:
        """获取所有 LLM Profile（按创建时间降序）"""
        if self._db is None:
            raise RuntimeError("StandaloneAdapter 未初始化")

        cursor = await self._db.execute(
            "SELECT * FROM llm_profiles ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [_profile_row_to_dict(cursor, row) for row in rows]

    async def save_llm_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        """保存或更新 LLM Profile

        新建时自动生成 id、created_at、updated_at。
        更新时自动更新 updated_at。
        """
        if self._db is None:
            raise RuntimeError("StandaloneAdapter 未初始化")

        now = datetime.now(timezone.utc).isoformat()
        profile_id = profile.get("id") or str(uuid.uuid4())

        # 检查是否已存在
        existing = await self.get_llm_profile(profile_id)
        created_at = existing["created_at"] if existing else now

        await self._db.execute(
            """INSERT OR REPLACE INTO llm_profiles
            (id, name, api_key, api_base, model, temperature, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile_id,
                profile["name"],
                profile["api_key"],
                profile.get("api_base", ""),
                profile["model"],
                profile.get("temperature", 0.7),
                profile.get("is_default", 0),
                created_at,
                now,
            ),
        )
        await self._db.commit()
        logger.debug(f"LLM Profile 已保存 - id: {profile_id}, name: {profile['name']}")

        return await self.get_llm_profile(profile_id)

    async def delete_llm_profile(self, profile_id: str) -> bool:
        """删除 LLM Profile"""
        if self._db is None:
            raise RuntimeError("StandaloneAdapter 未初始化")

        cursor = await self._db.execute(
            "DELETE FROM llm_profiles WHERE id = ?", (profile_id,)
        )
        await self._db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(f"LLM Profile 已删除 - id: {profile_id}")
        return deleted

    async def set_default_profile(self, profile_id: str) -> bool:
        """将指定 Profile 设为默认（事务内先清零再设 1）"""
        if self._db is None:
            raise RuntimeError("StandaloneAdapter 未初始化")

        # 检查目标 Profile 是否存在
        existing = await self.get_llm_profile(profile_id)
        if existing is None:
            return False

        async with self._db.execute("BEGIN"):
            await self._db.execute(
                "UPDATE llm_profiles SET is_default = 0, updated_at = ? WHERE is_default = 1",
                (datetime.now(timezone.utc).isoformat(),),
            )
            await self._db.execute(
                "UPDATE llm_profiles SET is_default = 1, updated_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), profile_id),
            )
        await self._db.commit()
        logger.debug(f"默认 LLM Profile 已切换 - id: {profile_id}")
        return True

    # ========== 写作参数 ==========

    async def get_writing_params(self) -> dict[str, Any]:
        """获取所有写作参数（key-value 表）"""
        if self._db is None:
            raise RuntimeError("StandaloneAdapter 未初始化")

        cursor = await self._db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

    async def update_writing_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """更新写作参数（INSERT OR REPLACE），返回更新后的完整参数"""
        if self._db is None:
            raise RuntimeError("StandaloneAdapter 未初始化")

        for key, value in params.items():
            await self._db.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
        await self._db.commit()
        logger.debug(f"写作参数已更新: {list(params.keys())}")
        return await self.get_writing_params()


def _profile_row_to_dict(cursor, row) -> dict[str, Any]:
    """将 llm_profiles 行转换为字典，is_default 转为 bool"""
    columns = [desc[0] for desc in cursor.description]
    d = dict(zip(columns, row, strict=False))
    d["is_default"] = bool(d["is_default"])
    return d
