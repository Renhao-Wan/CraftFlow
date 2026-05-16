"""任务 REST API

提供通用的任务查询和删除功能。
- GET    /tasks           任务列表（SQLite 终态 + 内存运行态）
- GET    /tasks/{task_id} 单任务状态查询
- DELETE /tasks/{task_id} 删除任务记录
"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.adapters.base import BusinessAdapter
from app.api.dependencies import (
    get_adapter,
    get_creation_service,
    get_polishing_service,
)
from app.core.auth import verify_api_key
from app.core.exceptions import TaskNotFoundError
from app.core.logger import get_logger
from app.schemas.response import TaskStatusResponse
from app.services.creation_svc import CreationService
from app.services.polishing_svc import PolishingService

router = APIRouter()
logger = get_logger(__name__)


@router.get("/tasks")
async def list_tasks(
    limit: int = Query(5, ge=1, le=200, description="历史任务每页数量"),
    offset: int = Query(0, ge=0, description="历史任务偏移量"),
    running_limit: int = Query(5, ge=1, le=50, description="运行中任务每页数量"),
    running_offset: int = Query(0, ge=0, description="运行中任务偏移量"),
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
    creation_svc: CreationService = Depends(get_creation_service),
    polishing_svc: PolishingService = Depends(get_polishing_service),
) -> dict[str, Any]:
    """获取任务列表（双列表：运行中 + 历史）

    返回两个独立列表，各自分页：
    - running_items：内存中 running/interrupted 任务
    - items：SQLite 中 completed/failed 任务

    Returns:
        { running_items: [...], running_total: int, items: [...], total: int }
    """
    # 1. 从内存获取所有 running/interrupted 任务
    all_running: list[dict[str, Any]] = []
    for task in creation_svc._tasks.values():
        if task["status"] in ("running", "interrupted"):
            all_running.append(_format_running_task(task))
    for task in polishing_svc._tasks.values():
        if task["status"] in ("running", "interrupted"):
            all_running.append(_format_running_task(task))

    all_running.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    running_total = len(all_running)
    running_items = all_running[running_offset : running_offset + running_limit]

    # 2. 从 SQLite 查询终态任务（completed/failed）
    items, total = await adapter.get_task_list(
        limit=limit, offset=offset, statuses=("completed", "failed")
    )

    return {
        "running_items": running_items,
        "running_total": running_total,
        "items": items,
        "total": total,
    }


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    caller: dict[str, Any] = Depends(verify_api_key),
    creation_svc: CreationService = Depends(get_creation_service),
    polishing_svc: PolishingService = Depends(get_polishing_service),
) -> TaskStatusResponse:
    """查询单个任务状态

    自动识别任务类型（创作/润色），查询顺序：
    1. CreationService（内存 → TaskStore）
    2. PolishingService（内存 → TaskStore）
    """
    try:
        return await creation_svc.get_task_status(task_id)
    except TaskNotFoundError:
        pass

    try:
        return await polishing_svc.get_task_status(task_id)
    except TaskNotFoundError:
        pass

    raise TaskNotFoundError(task_id=task_id)


@router.delete("/tasks")
async def delete_tasks_by_status(
    statuses: str = Query(..., description="按状态过滤删除，逗号分隔，如 completed,failed"),
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
) -> dict[str, Any]:
    """按状态清空 SQLite 中的任务记录

    仅清空匹配状态的任务，不影响内存中的运行态任务。
    """
    status_list = tuple(s.strip() for s in statuses.split(","))
    db_count = await adapter.delete_tasks_by_status(status_list)
    logger.info(f"已按状态删除任务 {status_list} - 数据库: {db_count}")
    return {"deleted": db_count}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    caller: dict[str, Any] = Depends(verify_api_key),
    adapter: BusinessAdapter = Depends(get_adapter),
    creation_svc: CreationService = Depends(get_creation_service),
    polishing_svc: PolishingService = Depends(get_polishing_service),
) -> dict[str, Any]:
    """删除任务记录

    优先从内存中删除运行中的任务，如果内存中没有则从 SQLite 删除。
    """
    # 1. 先检查内存中是否有该任务（running/interrupted）
    if task_id in creation_svc._tasks:
        creation_svc._tasks.pop(task_id, None)
        return {"task_id": task_id, "deleted": True}

    if task_id in polishing_svc._tasks:
        polishing_svc._tasks.pop(task_id, None)
        return {"task_id": task_id, "deleted": True}

    # 2. 内存中没有，从 SQLite 删除
    deleted = await adapter.delete_task(task_id)
    if not deleted:
        raise TaskNotFoundError(task_id=task_id)
    return {"task_id": task_id, "deleted": True}


def _format_running_task(task: dict[str, Any]) -> dict[str, Any]:
    """将内存中的运行态任务格式化为 API 响应格式"""
    request = task.get("request", {})
    graph_type = task.get("graph_type", "creation")

    result: dict[str, Any] = {
        "task_id": task["task_id"],
        "graph_type": graph_type,
        "status": task["status"],
        "created_at": str(task["created_at"]),
        "updated_at": str(task["updated_at"]),
    }

    # 包含进度和当前节点信息（如果有的话）
    if "progress" in task:
        result["progress"] = task["progress"]
    if "current_node" in task:
        result["current_node"] = task["current_node"]
    if "current_node_label" in task:
        result["current_node_label"] = task["current_node_label"]

    if graph_type == "creation":
        result["topic"] = request.get("topic")
        result["description"] = request.get("description")
    elif graph_type == "polishing":
        result["content"] = request.get("content")
        result["mode"] = request.get("mode")

    return result
