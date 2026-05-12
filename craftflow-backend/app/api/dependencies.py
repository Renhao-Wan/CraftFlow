"""FastAPI 依赖注入模块

提供全局共享的服务实例，通过 FastAPI 的 Depends() 机制注入到路由中。

依赖链：
    checkpointer + task_store → CreationService / PolishingService
    （checkpointer 和 task_store 在应用启动时初始化）

模式感知：
    - standalone 模式：SQLite 存储，无鉴权
    - server 模式：PostgreSQL 存储，API Key 鉴权，可选 Redis/监控

使用方式：
    @router.post("/creation")
    async def create_task(
        request: CreationRequest,
        service: CreationService = Depends(get_creation_service),
    ):
        ...
"""

from app.core.config import settings
from app.core.exceptions import CheckpointerError
from app.core.logger import get_logger
from app.services.checkpointer import get_checkpointer
from app.services.creation_svc import CreationService
from app.services.polishing_svc import PolishingService
from app.services.task_store import AbstractTaskStore, create_task_store

logger = get_logger(__name__)

# ============================================
# 模块级单例（应用启动后初始化）
# ============================================

_creation_service: CreationService | None = None
_polishing_service: PolishingService | None = None
_task_store: AbstractTaskStore | None = None


async def init_services() -> None:
    """根据 APP_MODE 初始化所有业务服务

    初始化流程：
    1. 创建 TaskStore（配置驱动：SQLite / PostgreSQL）
    2. 初始化 Checkpointer
    3. 创建业务服务（CreationService, PolishingService）
    4. 从 TaskStore 加载中断任务到内存（服务重启恢复）
    5. server 模式下额外初始化扩展组件

    在应用启动时调用，必须在 init_checkpointer() 之后执行。

    Raises:
        CheckpointerError: Checkpointer 尚未初始化
    """
    global _creation_service, _polishing_service, _task_store

    logger.info(
        f"初始化业务服务 | 模式: {settings.app_mode} | TaskStore: {settings.taskstore_backend}"
    )

    checkpointer = get_checkpointer()

    # 1. 初始化 TaskStore（配置驱动）
    _task_store = create_task_store()
    await _task_store.init_db()

    # 2. 创建业务服务
    _creation_service = CreationService(checkpointer=checkpointer, task_store=_task_store)
    _polishing_service = PolishingService(checkpointer=checkpointer, task_store=_task_store)

    # 3. 从 TaskStore 加载中断任务到内存（委托给各 Service 自行处理）
    creation_loaded = await _creation_service.load_interrupted_tasks()
    polishing_loaded = await _polishing_service.load_interrupted_tasks()

    if creation_loaded + polishing_loaded > 0:
        logger.info(f"已恢复中断任务 | 创作: {creation_loaded} | 润色: {polishing_loaded}")

    # 4. server 模式下额外初始化扩展组件
    if settings.is_server:
        await _init_server_components()

    logger.info("业务服务初始化完成（CreationService, PolishingService, TaskStore）")


async def _init_server_components() -> None:
    """服务端模式额外组件初始化

    server 模式下可扩展：Redis 连接池、监控指标收集等。
    当前为空实现，预留扩展点。
    """
    logger.info("server 模式扩展组件初始化（当前无额外组件）")


async def close_services() -> None:
    """关闭所有业务服务，释放资源"""
    global _creation_service, _polishing_service, _task_store

    if _task_store:
        await _task_store.close()
    _creation_service = None
    _polishing_service = None
    _task_store = None

    logger.info("业务服务已关闭")


# ============================================
# FastAPI 依赖注入函数
# ============================================


def get_creation_service() -> CreationService:
    """获取 CreationService 实例（FastAPI 依赖注入）

    Returns:
        CreationService: 创作业务服务实例

    Raises:
        CheckpointerError: 服务尚未初始化时抛出
    """
    if _creation_service is None:
        raise CheckpointerError(
            message="CreationService 尚未初始化，请确保应用已启动",
        )
    return _creation_service


def get_polishing_service() -> PolishingService:
    """获取 PolishingService 实例（FastAPI 依赖注入）

    Returns:
        PolishingService: 润色业务服务实例

    Raises:
        CheckpointerError: 服务尚未初始化时抛出
    """
    if _polishing_service is None:
        raise CheckpointerError(
            message="PolishingService 尚未初始化，请确保应用已启动",
        )
    return _polishing_service


def get_task_store() -> AbstractTaskStore:
    """获取 TaskStore 实例（FastAPI 依赖注入）

    Returns:
        AbstractTaskStore: 任务持久化存储实例（SQLite 或 PostgreSQL）

    Raises:
        CheckpointerError: 服务尚未初始化时抛出
    """
    if _task_store is None:
        raise CheckpointerError(
            message="TaskStore 尚未初始化，请确保应用已启动",
        )
    return _task_store
