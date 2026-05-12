"""LLM 工厂模块

提供单例模式的 LLM 实例管理，统一使用 OpenAI 兼容格式。
支持所有兼容 OpenAI API 格式的 LLM Provider（OpenAI、DeepSeek、Azure OpenAI、本地模型等）。

配置来源：BusinessAdapter 的 llm_profiles 表（通过 LLMFactory.set_adapter() 注入）。
"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.logger import logger

# ============================================
# LLM 工厂常量
# ============================================

# 网络配置常量
DEFAULT_REQUEST_TIMEOUT: int = 60  # 请求超时时间（秒），LangChain 默认 600s
DEFAULT_MAX_RETRIES: int = 3  # 最大重试次数，LangChain 默认 2
DEFAULT_STREAMING: bool = True  # 启用流式输出，支持 astream_events

# 节点专用温度常量
EDITOR_NODE_TEMPERATURE: float = 0.2  # 编辑节点：低温度，输出更保守确定

# 节点专用 max_tokens 常量
PLANNER_MAX_TOKENS: int = 8192  # PlannerNode: 大纲生成需要较大输出空间
WRITER_MAX_TOKENS: int = 2048  # WriterNode: 目标 800-1500 字，2048 留出余量
EDITOR_MAX_TOKENS: int = 2048  # EditorNode: JSON 评分 ~300-500 token，2048 留出充足余量
FACTCHECKER_MAX_TOKENS: int = (
    4096  # FactCheckerNode: 核查报告 JSON ~300-650 token，4096 留出充足余量
)


class LLMFactory:
    """LLM 工厂类

    统一使用 OpenAI 兼容格式，支持多种温度参数配置。
    使用单例模式确保相同参数配置全局只有一个 LLM 实例。

    支持的 Provider:
    - OpenAI 官方 API
    - DeepSeek
    - Azure OpenAI
    - 本地模型（如 Ollama、vLLM）
    - 其他兼容 OpenAI API 格式的服务

    配置来源：
    - 优先从 BusinessAdapter 的 LLM Profile 读取
    - 未设置 Adapter 时回退到 settings（向后兼容）
    """

    _instances: dict[str, BaseChatModel] = {}
    _adapter: Any = None  # BusinessAdapter 实例

    @classmethod
    def set_adapter(cls, adapter: Any) -> None:
        """设置 BusinessAdapter 实例（在 init_services 中调用）"""
        cls._adapter = adapter
        logger.info("LLMFactory 已绑定 BusinessAdapter")

    @classmethod
    async def create_llm(
        cls,
        temperature: float | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        streaming: bool = DEFAULT_STREAMING,
        profile_id: str | None = None,
    ) -> BaseChatModel:
        """创建 LLM 实例（OpenAI 兼容格式）

        Args:
            temperature: 温度参数，控制输出随机性（0.0-2.0）。None 时使用配置默认值
            model: 模型名称。None 时使用配置默认值
            max_tokens: 最大 Token 数。None 时使用配置默认值
            request_timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            streaming: 是否启用流式输出
            profile_id: LLM Profile ID，None 时使用默认 Profile

        Returns:
            BaseChatModel: LLM 实例

        Raises:
            ValueError: 当配置缺失或 Profile 不存在时抛出
        """
        # 解析配置（从 Adapter Profile 或 settings 回退）
        profile_config = await cls._resolve_config(profile_id)

        # 使用 Profile 配置或参数覆盖
        temperature = temperature if temperature is not None else profile_config["temperature"]
        model = model or profile_config["model"]
        max_tokens = max_tokens or profile_config.get("max_tokens", 4096)

        # 生成缓存 key（包含所有可区分参数）
        cache_key = (
            f"{profile_id}_{model}_{temperature}_{max_tokens}"
            f"_{request_timeout}_{max_retries}_{streaming}"
        )

        # 检查缓存
        if cache_key in cls._instances:
            logger.debug(f"复用已缓存的 LLM 实例: {cache_key}")
            return cls._instances[cache_key]

        # 创建新实例
        logger.info(
            f"创建新的 LLM 实例 - Model: {model}, "
            f"Temperature: {temperature}, MaxTokens: {max_tokens}, "
            f"Timeout: {request_timeout}s, Retries: {max_retries}, Streaming: {streaming}"
        )

        from typing import cast

        llm = cls._create_openai_compatible_llm(
            cast(str, model),
            cast(float, temperature),
            cast(int, max_tokens),
            profile_config,
            request_timeout,
            max_retries,
            streaming,
        )

        # 缓存实例
        cls._instances[cache_key] = llm
        return llm

    @classmethod
    async def _resolve_config(cls, profile_id: str | None = None) -> dict[str, Any]:
        """解析 LLM 配置（从 Adapter Profile 读取）

        Args:
            profile_id: Profile ID，None 时使用默认 Profile

        Returns:
            配置字典，包含 api_key, api_base, model, temperature 等

        Raises:
            ValueError: Adapter 未设置或 Profile 不存在时抛出
        """
        if cls._adapter is None:
            raise ValueError(
                "LLMFactory 未绑定 BusinessAdapter，请确保应用已正确启动。"
            )

        profile = await cls._adapter.get_llm_profile(profile_id)
        if profile is None:
            raise ValueError(
                "未找到 LLM Profile，请在设置页面配置 LLM。"
                f"(profile_id={profile_id or '默认'})"
            )
        return {
            "api_key": profile["api_key"],
            "api_base": profile.get("api_base", ""),
            "model": profile["model"],
            "temperature": profile.get("temperature", 0.7),
            "max_tokens": None,  # Profile 不含 max_tokens，由调用方指定
        }

    @staticmethod
    def _create_openai_compatible_llm(
        model: str,
        temperature: float,
        max_tokens: int,
        profile_config: dict[str, Any],
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        streaming: bool = DEFAULT_STREAMING,
    ) -> ChatOpenAI:
        """创建 OpenAI 兼容的 LLM 实例

        Args:
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 Token 数
            profile_config: Profile 配置字典
            request_timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            streaming: 是否启用流式输出

        Returns:
            ChatOpenAI: LLM 实例

        Raises:
            ValueError: API Key 未配置时抛出
        """
        api_key = profile_config.get("api_key")
        if not api_key:
            raise ValueError("LLM API Key 未配置，无法创建 LLM 实例")

        kwargs = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": api_key,
            "request_timeout": request_timeout,
            "max_retries": max_retries,
            "streaming": streaming,
        }

        # 如果配置了自定义 API Base（如 DeepSeek、Azure OpenAI、本地模型）
        api_base = profile_config.get("api_base", "")
        if api_base:
            kwargs["base_url"] = api_base
            logger.info(f"使用自定义 API Base: {api_base}")

        return ChatOpenAI(**kwargs)

    @classmethod
    def clear_cache(cls) -> None:
        """清空 LLM 实例缓存

        用于测试或需要重新加载配置的场景。
        """
        logger.info("清空 LLM 实例缓存")
        cls._instances.clear()


# ============================================
# 节点专用 LLM Getter（均为 async）
# ============================================


async def get_default_llm(profile_id: str | None = None) -> BaseChatModel:
    """获取默认 LLM 实例（使用配置文件的默认参数）

    Returns:
        BaseChatModel: 默认 LLM 实例
    """
    return await LLMFactory.create_llm(profile_id=profile_id)


async def get_editor_llm(profile_id: str | None = None) -> BaseChatModel:
    """获取编辑节点专用 LLM 实例（低温度）

    编辑节点输出结构化 JSON 评分（~300-500 token），
    低温度确保输出更保守确定，max_tokens=2048 留出充足余量避免截断。

    Returns:
        BaseChatModel: 编辑节点 LLM 实例
    """
    return await LLMFactory.create_llm(
        temperature=EDITOR_NODE_TEMPERATURE,
        max_tokens=EDITOR_MAX_TOKENS,
        profile_id=profile_id,
    )


async def get_planner_llm(profile_id: str | None = None) -> BaseChatModel:
    """获取 PlannerNode 专用 LLM 实例（大纲生成需要较大输出空间）

    Returns:
        BaseChatModel: Planner 专用 LLM 实例
    """
    return await LLMFactory.create_llm(max_tokens=PLANNER_MAX_TOKENS, profile_id=profile_id)


async def get_writer_llm(profile_id: str | None = None) -> BaseChatModel:
    """获取 WriterNode 专用 LLM 实例

    Writer 目标输出 800-1500 字（约 500-1500 token），
    max_tokens=2048 留出合理余量，避免过度生成。

    Returns:
        BaseChatModel: Writer 专用 LLM 实例
    """
    return await LLMFactory.create_llm(max_tokens=WRITER_MAX_TOKENS, profile_id=profile_id)


async def get_factchecker_llm(profile_id: str | None = None) -> BaseChatModel:
    """获取 FactCheckerNode 专用 LLM 实例

    FactChecker 输出核查报告 JSON（~300-650 token），
    max_tokens=4096 给予充足余量，避免 JSON 被截断。

    Returns:
        BaseChatModel: FactChecker 专用 LLM 实例
    """
    return await LLMFactory.create_llm(max_tokens=FACTCHECKER_MAX_TOKENS, profile_id=profile_id)


async def get_custom_llm(
    temperature: float | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    profile_id: str | None = None,
) -> BaseChatModel:
    """获取自定义参数的 LLM 实例（用于临时/实验性场景）

    注意：正式节点应使用专用 getter（get_planner_llm 等），
    本函数仅用于调试或未来扩展场景。

    Args:
        temperature: 温度参数
        model: 模型名称
        max_tokens: 最大 Token 数
        profile_id: LLM Profile ID

    Returns:
        BaseChatModel: 自定义 LLM 实例
    """
    return await LLMFactory.create_llm(
        temperature=temperature, model=model, max_tokens=max_tokens, profile_id=profile_id
    )
