"""PostgreSQL TaskStore 实现

使用 asyncpg 连接池将任务数据持久化到 PostgreSQL。
适用于服务端部署场景（APP_MODE=server）。
"""

from datetime import datetime
from typing import Any, Optional

import asyncpg

from app.core.logger import get_logger
from app.services.task_store import AbstractTaskStore

logger = get_logger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id VARCHAR(64) PRIMARY KEY,
    graph_type VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    topic TEXT,
    description TEXT,
    content TEXT,
    mode INTEGER,
    result TEXT,
    error TEXT,
    progress REAL DEFAULT 100.0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
"""


class PostgresTaskStore(AbstractTaskStore):
    """PostgreSQL 任务持久化存储

    使用 asyncpg 连接池，适用于服务端高并发场景。
    """

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None

    async def init_db(self) -> None:
        """初始化连接池和表结构"""
        self._pool = await asyncpg.create_pool(self._database_url, min_size=2, max_size=10)
        async with self._pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)
            await conn.execute(_CREATE_INDEX_SQL)
        logger.info("PostgreSQL TaskStore 初始化完成")

    async def save_task(self, task: dict[str, Any]) -> None:
        """保存或更新任务记录（INSERT ... ON CONFLICT UPDATE）"""
        if self._pool is None:
            raise RuntimeError("TaskStore 未初始化，请先调用 init_db()")

        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO tasks
                (task_id, graph_type, status, topic, description, content, mode,
                 result, error, progress, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (task_id) DO UPDATE SET
                    graph_type = EXCLUDED.graph_type,
                    status = EXCLUDED.status,
                    topic = EXCLUDED.topic,
                    description = EXCLUDED.description,
                    content = EXCLUDED.content,
                    mode = EXCLUDED.mode,
                    result = EXCLUDED.result,
                    error = EXCLUDED.error,
                    progress = EXCLUDED.progress,
                    updated_at = EXCLUDED.updated_at""",
                task["task_id"],
                task["graph_type"],
                task["status"],
                task.get("topic"),
                task.get("description"),
                task.get("content"),
                task.get("mode"),
                task.get("result"),
                task.get("error"),
                task.get("progress", 100.0),
                _to_timestamp(task["created_at"]),
                _to_timestamp(task["updated_at"]),
            )
        logger.debug(f"任务已保存到 PostgreSQL - task_id: {task['task_id']}")

    async def get_task(
        self,
        task_id: str,
        graph_type: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """根据 task_id 查询单个任务"""
        if self._pool is None:
            raise RuntimeError("TaskStore 未初始化")

        async with self._pool.acquire() as conn:
            if graph_type:
                row = await conn.fetchrow(
                    "SELECT * FROM tasks WHERE task_id = $1 AND graph_type = $2",
                    task_id,
                    graph_type,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM tasks WHERE task_id = $1",
                    task_id,
                )
        if row is None:
            return None
        return _record_to_dict(row)

    async def get_interrupted_tasks(self) -> list[dict[str, Any]]:
        """查询所有中断状态的任务"""
        if self._pool is None:
            raise RuntimeError("TaskStore 未初始化")

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM tasks WHERE status = $1 ORDER BY created_at DESC",
                "interrupted",
            )
        return [_record_to_dict(row) for row in rows]

    async def get_task_list(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """查询任务列表（按创建时间降序）"""
        if self._pool is None:
            raise RuntimeError("TaskStore 未初始化")

        async with self._pool.acquire() as conn:
            total_row = await conn.fetchrow("SELECT COUNT(*) FROM tasks")
            total = total_row[0] if total_row else 0

            rows = await conn.fetch(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit,
                offset,
            )
        return [_record_to_dict(row) for row in rows], total

    async def delete_task(self, task_id: str) -> bool:
        """删除任务记录"""
        if self._pool is None:
            raise RuntimeError("TaskStore 未初始化")

        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM tasks WHERE task_id = $1",
                task_id,
            )
        deleted = result == "DELETE 1"
        if deleted:
            logger.debug(f"任务已从 PostgreSQL 删除 - task_id: {task_id}")
        return deleted

    async def close(self) -> None:
        """关闭连接池"""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL TaskStore 连接池已关闭")


def _record_to_dict(record: asyncpg.Record) -> dict[str, Any]:
    """将 asyncpg Record 转换为字典，统一 datetime 为 str 类型"""
    d = dict(record)
    for key in ("created_at", "updated_at"):
        if isinstance(d.get(key), datetime):
            d[key] = d[key].isoformat()
    return d


def _to_timestamp(value: Any) -> Any:
    """将字符串时间戳转为 datetime（asyncpg 需要 datetime 参数）"""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.now()
    return datetime.now()
