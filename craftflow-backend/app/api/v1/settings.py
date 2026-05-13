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
from app.core.auth import verify_api_key
from app.schemas.request import LlmProfileRequest, WritingParamsRequest
from app.schemas.response import LlmProfileResponse, WritingParamsResponse

router = APIRouter(prefix="/settings")


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
    profile_data = request.model_dump()
    try:
        saved = await adapter.save_llm_profile(profile_data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

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
    try:
        saved = await adapter.save_llm_profile(profile_data)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

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
