"""Settings API 路由

提供设置相关的 RESTful 接口：
- GET    /settings/llm-profiles           获取所有 LLM Profile
- POST   /settings/llm-profiles           创建新 Profile
- PUT    /settings/llm-profiles/{id}       更新 Profile
- DELETE /settings/llm-profiles/{id}       删除 Profile
- POST   /settings/llm-profiles/{id}/set-default  设为默认
- GET    /settings/writing-params          获取写作参数
- PATCH  /settings/writing-params          更新写作参数
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.base import BusinessAdapter
from app.api.dependencies import get_adapter
from app.core import tool_configs
from app.core.auth import verify_api_key
from app.schemas.request import LlmProfileRequest, ToolConfigsRequest, WritingParamsRequest
from app.schemas.response import LlmProfileResponse, ToolConfigsResponse, WritingParamsResponse

router = APIRouter(prefix="/settings")

MAX_LLM_PROFILES = 20


def _mask_api_key(api_key: str) -> str:
    """脱敏 API Key，只显示前 4 位和后 4 位"""
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}****{api_key[-4:]}"


# ============================================
# LLM Profile CRUD
# ============================================


@router.get("/llm-profiles", response_model=list[LlmProfileResponse])
async def list_llm_profiles(
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
) -> list[dict[str, Any]]:
    """获取所有 LLM Profile"""
    profiles = await adapter.get_all_llm_profiles()
    for p in profiles:
        p["api_key"] = _mask_api_key(p["api_key"])
    return profiles


@router.post("/llm-profiles", response_model=LlmProfileResponse, status_code=201)
async def create_llm_profile(
    request: LlmProfileRequest,
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
) -> dict[str, Any]:
    """创建新的 LLM Profile"""
    if not request.api_key:
        raise HTTPException(status_code=422, detail="创建配置时 API Key 为必填项")

    existing = await adapter.get_all_llm_profiles()
    if len(existing) >= MAX_LLM_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"LLM 配置数量已达上限（{MAX_LLM_PROFILES} 个），请先删除不需要的配置",
        )

    profile_data = request.model_dump()
    try:
        saved = await adapter.save_llm_profile(profile_data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    # 如果设为默认，执行切换
    if request.is_default:
        await adapter.set_default_profile(saved["id"])
        saved = await adapter.get_llm_profile(saved["id"])

    saved["api_key"] = _mask_api_key(saved["api_key"])
    return saved


@router.put("/llm-profiles/{profile_id}", response_model=LlmProfileResponse)
async def update_llm_profile(
    profile_id: str,
    request: LlmProfileRequest,
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
) -> dict[str, Any]:
    """更新 LLM Profile"""
    existing = await adapter.get_llm_profile(profile_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} 不存在")

    profile_data = request.model_dump()
    profile_data["id"] = profile_id
    # 留空则保留原 API Key
    if not profile_data.get("api_key"):
        profile_data["api_key"] = existing["api_key"]
    try:
        saved = await adapter.save_llm_profile(profile_data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    if request.is_default:
        await adapter.set_default_profile(profile_id)
        saved = await adapter.get_llm_profile(profile_id)

    saved["api_key"] = _mask_api_key(saved["api_key"])
    return saved


@router.delete("/llm-profiles/{profile_id}")
async def delete_llm_profile(
    profile_id: str,
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
) -> dict[str, Any]:
    """删除 LLM Profile"""
    deleted = await adapter.delete_llm_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} 不存在")
    return {"deleted": True, "profile_id": profile_id}


@router.post("/llm-profiles/{profile_id}/set-default")
async def set_default_profile(
    profile_id: str,
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
) -> dict[str, Any]:
    """将指定 Profile 设为默认"""
    success = await adapter.set_default_profile(profile_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} 不存在")
    return {"success": True, "profile_id": profile_id}


# ============================================
# 外部工具配置
# ============================================


def _mask_tool_key(key: str) -> str:
    """脱敏工具 API Key"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


@router.get("/tool-configs", response_model=ToolConfigsResponse)
async def get_tool_configs(
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
) -> dict[str, str]:
    """获取外部工具配置（脱敏）"""
    configs = await adapter.get_tool_configs()
    return {k: _mask_tool_key(v) for k, v in configs.items()}


@router.patch("/tool-configs", response_model=ToolConfigsResponse)
async def update_tool_configs(
    request: ToolConfigsRequest,
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
) -> dict[str, str]:
    """更新外部工具配置（部分更新）"""
    update_data: dict[str, Any] = {}
    for field_name in ("tavily_api_key", "e2b_api_key"):
        value = getattr(request, field_name, None)
        if value is not None:
            update_data[field_name] = value

    if not update_data:
        configs = await adapter.get_tool_configs()
        return {k: _mask_tool_key(v) for k, v in configs.items()}

    result = await adapter.update_tool_configs(update_data)

    # 刷新缓存
    for key, value in update_data.items():
        tool_configs.refresh(key, value)

    return {k: _mask_tool_key(v) for k, v in result.items()}


# ============================================
# 写作参数
# ============================================


_PARAM_DEFAULTS: dict[str, int] = {
    "max_outline_sections": 5,
    "max_concurrent_writers": 3,
    "max_debate_iterations": 3,
    "editor_pass_score": 90,
    "task_timeout": 3600,
    "tool_call_timeout": 30,
}


def _build_params_response(params: dict[str, Any]) -> dict[str, int]:
    """从原始 key-value 构建响应字典"""
    return {key: int(params.get(key, default)) for key, default in _PARAM_DEFAULTS.items()}


@router.get("/writing-params", response_model=WritingParamsResponse)
async def get_writing_params(
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
) -> dict[str, int]:
    """获取写作参数"""
    params = await adapter.get_writing_params()
    return _build_params_response(params)


@router.patch("/writing-params", response_model=WritingParamsResponse)
async def update_writing_params(
    request: WritingParamsRequest,
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
) -> dict[str, int]:
    """更新写作参数"""
    update_data: dict[str, Any] = {}
    for field in _PARAM_DEFAULTS:
        value = getattr(request, field, None)
        if value is not None:
            update_data[field] = value

    if not update_data:
        params = await adapter.get_writing_params()
        return _build_params_response(params)

    params = await adapter.update_writing_params(update_data)
    return _build_params_response(params)
