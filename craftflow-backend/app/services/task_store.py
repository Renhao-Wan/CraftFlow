"""TaskStore 抽象接口与工厂

定义 TaskStore 的抽象接口，通过工厂函数根据配置创建具体的存储实现：
- SqliteTaskStore：桌面端/开发环境，使用 aiosqlite
- PostgresTaskStore：服务端/生产环境，使用 asyncpg
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class AbstractTaskStore(ABC):
    """TaskStore 抽象接口

    定义任务持久化存储的标准接口，所有具体实现必须继承此类。
    """

    @abstractmethod
    async def init_db(self) -> None:
        """初始化数据库连接和表结构"""

    @abstractmethod
    async def save_task(self, task: dict[str, Any]) -> None:
        """保存或更新任务记录

        Args:
            task: 任务数据字典，必须包含 task_id, graph_type, status, created_at, updated_at
        """

    @abstractmethod
    async def get_task(
        self,
        task_id: str,
        graph_type: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """根据 task_id 查询单个任务

        Args:
            task_id: 任务 ID
            graph_type: 可选，限定任务类型（'creation' | 'polishing'）

        Returns:
            任务数据字典，不存在时返回 None
        """

    @abstractmethod
    async def get_interrupted_tasks(self) -> list[dict[str, Any]]:
        """查询所有中断状态的任务（用于服务重启后恢复到内存）

        Returns:
            中断状态的任务数据字典列表，按创建时间降序
        """

    @abstractmethod
    async def get_task_list(
        self,
        limit: int = 50,
        offset: int = 0,
        statuses: tuple[str, ...] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """查询任务列表（按创建时间降序），可选按状态过滤

        Args:
            limit: 最大返回数量
            offset: 偏移量（分页用）
            statuses: 可选的状态过滤，如 ("completed", "failed")

        Returns:
            (任务数据字典列表, 总数)
        """

    @abstractmethod
    async def delete_task(self, task_id: str) -> bool:
        """删除任务记录

        Returns:
            是否成功删除（True=有记录被删除，False=记录不存在）
        """

    @abstractmethod
    async def delete_tasks_by_status(self, statuses: tuple[str, ...]) -> int:
        """按状态删除任务记录

        Returns:
            被删除的记录数
        """

    @abstractmethod
    async def close(self) -> None:
        """关闭数据库连接"""


def create_task_store() -> AbstractTaskStore:
    """根据配置创建 TaskStore 实例

    读取 settings.taskstore_backend 决定使用哪种存储后端：
    - sqlite：使用 SqliteTaskStore（默认，适用于桌面端和开发环境）
    - postgres：使用 PostgresTaskStore（适用于服务端生产环境）

    SQLite 路径使用 _get_default_db_path() 基于文件位置推导绝对路径，
    不依赖当前工作目录。

    Returns:
        AbstractTaskStore 的具体实现实例
    """
    from app.core.config import settings

    backend = settings.taskstore_backend

    if backend == "sqlite":
        from app.services.task_store_sqlite import SqliteTaskStore

        return SqliteTaskStore()  # 使用 _get_default_db_path()，绝对路径

    elif backend == "postgres":
        from app.services.task_store_postgres import PostgresTaskStore

        if not settings.database_url:
            raise ValueError("PostgreSQL 模式下必须配置 DATABASE_URL")
        return PostgresTaskStore(database_url=settings.database_url)

    else:
        raise ValueError(f"不支持的 TaskStore 后端: {backend}")


__all__ = [
    "AbstractTaskStore",
    "create_task_store",
]
