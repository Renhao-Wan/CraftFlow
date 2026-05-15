"""FastAPI 依赖注入模块

提供全局共享的服务实例，通过 FastAPI 的 Depends() 机制注入到路由中。

依赖链：
    checkpointer + adapter → CreationService / PolishingService
    （checkpointer 和 adapter 在应用启动时初始化）

模式感知：
    - standalone 模式：StandaloneAdapter（SQLite 存储），无鉴权
    - server 模式：ServerAdapter（Java API + PG），API Key 鉴权

使用方式：
    @router.post("/creation")
    async def create_task(
        request: CreationRequest,
        service: CreationService = Depends(get_creation_service),
    ):
        ...
"""

from app.adapters.base import BusinessAdapter
from app.adapters.standalone import StandaloneAdapter
from app.core import tool_configs
from app.core.config import settings
from app.core.exceptions import CheckpointerError
from app.core.logger import get_logger
from app.graph.common.llm_factory import LLMFactory
from app.services.chat_svc import ChatService
from app.services.checkpointer import get_checkpointer
from app.services.creation_svc import CreationService
from app.services.polishing_svc import PolishingService

logger = get_logger(__name__)

# ============================================
# 模块级单例（应用启动后初始化）
# ============================================

_creation_service: CreationService | None = None
_polishing_service: PolishingService | None = None
_chat_service: ChatService | None = None
_adapter: BusinessAdapter | None = None


async def init_services() -> None:
    """根据 APP_MODE 初始化所有业务服务

    初始化流程：
    1. 创建 Adapter（配置驱动：StandaloneAdapter / ServerAdapter）
    2. 初始化 Checkpointer
    3. 创建业务服务（CreationService, PolishingService）
    4. 从 Adapter 加载中断任务到内存（服务重启恢复）
    5. server 模式下额外初始化扩展组件

    在应用启动时调用，必须在 init_checkpointer() 之后执行。

    Raises:
        CheckpointerError: Checkpointer 尚未初始化
    """
    global _creation_service, _polishing_service, _chat_service, _adapter

    logger.info(f"初始化业务服务 | 模式: {settings.app_mode}")

    checkpointer = get_checkpointer()

    # 1. 初始化 Adapter（配置驱动）
    _adapter = StandaloneAdapter()
    await _adapter.init()

    # 2. 加载外部工具配置到缓存
    await tool_configs.load_from_adapter(_adapter)

    # 3. 绑定 Adapter 到 LLMFactory
    LLMFactory.set_adapter(_adapter)

    # 3. 创建业务服务
    _creation_service = CreationService(checkpointer=checkpointer, adapter=_adapter)
    _polishing_service = PolishingService(checkpointer=checkpointer, adapter=_adapter)
    _chat_service = ChatService(adapter=_adapter)

    # 3. 从 Adapter 加载中断任务到内存（委托给各 Service 自行处理）
    creation_loaded = await _creation_service.load_interrupted_tasks()
    polishing_loaded = await _polishing_service.load_interrupted_tasks()

    if creation_loaded + polishing_loaded > 0:
        logger.info(f"已恢复中断任务 | 创作: {creation_loaded} | 润色: {polishing_loaded}")

    # 4. server 模式下额外初始化扩展组件
    if settings.is_server:
        await _init_server_components()

    logger.info("业务服务初始化完成（CreationService, PolishingService, ChatService, Adapter）")


async def _init_server_components() -> None:
    """服务端模式额外组件初始化

    server 模式下可扩展：Redis 连接池、监控指标收集等。
    当前为空实现，预留扩展点。
    """
    logger.info("server 模式扩展组件初始化（当前无额外组件）")


async def close_services() -> None:
    """关闭所有业务服务，释放资源"""
    global _creation_service, _polishing_service, _chat_service, _adapter

    LLMFactory.clear_cache()
    if _adapter:
        await _adapter.close()
    _creation_service = None
    _polishing_service = None
    _chat_service = None
    _adapter = None

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


def get_adapter() -> BusinessAdapter:
    """获取 BusinessAdapter 实例（FastAPI 依赖注入）

    Returns:
        BusinessAdapter: 业务适配器实例

    Raises:
        CheckpointerError: 服务尚未初始化时抛出
    """
    if _adapter is None:
        raise CheckpointerError(
            message="BusinessAdapter 尚未初始化，请确保应用已启动",
        )
    return _adapter


def get_chat_service() -> ChatService:
    """获取 ChatService 实例（FastAPI 依赖注入）

    Returns:
        ChatService: 对话服务实例

    Raises:
        CheckpointerError: 服务尚未初始化时抛出
    """
    if _chat_service is None:
        raise CheckpointerError(
            message="ChatService 尚未初始化，请确保应用已启动",
        )
    return _chat_service
