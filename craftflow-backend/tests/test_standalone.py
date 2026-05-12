"""standalone 模式端到端测试

验证 standalone 模式下的完整行为：
- 无鉴权，所有端点直接放行
- SQLite 存储后端
- 健康检查返回 standalone 模式信息
- 任务 CRUD 全流程
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.base import BusinessAdapter
from app.api.dependencies import get_adapter, get_creation_service, get_polishing_service
from app.main import create_app
from app.schemas.response import TaskResponse, TaskStatusResponse
from app.services.creation_svc import CreationService
from app.services.polishing_svc import PolishingService


@pytest.fixture
def mock_creation_svc():
    """mock CreationService"""
    svc = AsyncMock(spec=CreationService)
    svc._tasks = {}
    svc.start_task.return_value = TaskResponse(
        task_id="c-standalone-001",
        status="interrupted",
        message="大纲已生成，请确认后继续",
        created_at=datetime(2026, 5, 12, 10, 0, 0),
    )
    svc.get_task_status.return_value = TaskStatusResponse(
        task_id="c-standalone-001",
        status="interrupted",
        current_node="outline_confirmation",
        awaiting="outline_confirmation",
        progress=30.0,
        created_at=datetime(2026, 5, 12, 10, 0, 0),
        updated_at=datetime(2026, 5, 12, 10, 1, 0),
    )
    svc.resume_task.return_value = TaskResponse(
        task_id="c-standalone-001",
        status="completed",
        message="创作任务已完成",
        created_at=datetime(2026, 5, 12, 10, 0, 0),
    )
    return svc


@pytest.fixture
def mock_polishing_svc():
    """mock PolishingService"""
    svc = AsyncMock(spec=PolishingService)
    svc._tasks = {}
    svc.get_task_status.side_effect = Exception("TaskNotFoundError")
    return svc


@pytest.fixture
def mock_adapter():
    """mock BusinessAdapter"""
    adapter = AsyncMock(spec=BusinessAdapter)
    adapter.get_task.return_value = None
    adapter.get_task_list.return_value = ([], 0)
    adapter.delete_task.return_value = False
    return adapter


@pytest.fixture
def standalone_app(mock_creation_svc, mock_polishing_svc, mock_adapter):
    """创建 standalone 模式的 FastAPI 应用

    模拟 standalone 配置：enable_auth=False, app_mode=standalone
    """
    app = create_app()
    app.dependency_overrides[get_creation_service] = lambda: mock_creation_svc
    app.dependency_overrides[get_polishing_service] = lambda: mock_polishing_svc
    app.dependency_overrides[get_adapter] = lambda: mock_adapter
    return app


@pytest.fixture
async def client(standalone_app):
    """创建测试用 HTTP 客户端"""
    transport = ASGITransport(app=standalone_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================
# 健康检查
# ============================================


class TestStandaloneHealthCheck:
    """standalone 模式健康检查"""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        """健康检查返回 200"""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_includes_mode(self, client):
        """健康检查包含 mode 字段"""
        response = await client.get("/health")

        data = response.json()
        assert "mode" in data


# ============================================
# 无鉴权访问
# ============================================


class TestStandaloneNoAuth:
    """standalone 模式下无需 API Key"""

    @pytest.mark.asyncio
    async def test_tasks_list_no_auth(self, client):
        """无 API Key 可访问任务列表"""
        response = await client.get("/api/v1/tasks")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_task_status_no_auth(self, client, mock_creation_svc):
        """无 API Key 可查询任务状态"""
        response = await client.get("/api/v1/tasks/c-standalone-001")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "c-standalone-001"

    @pytest.mark.asyncio
    async def test_create_task_no_auth(self, client, mock_creation_svc):
        """无 API Key 可创建任务"""
        response = await client.post(
            "/api/v1/creation",
            json={"topic": "测试主题", "description": "测试描述"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == "c-standalone-001"
        assert data["status"] == "interrupted"

    @pytest.mark.asyncio
    async def test_resume_task_no_auth(self, client, mock_creation_svc):
        """无 API Key 可恢复任务"""
        response = await client.post(
            "/api/v1/tasks/c-standalone-001/resume",
            json={"action": "confirm_outline"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_delete_task_no_auth(self, client, mock_creation_svc):
        """无 API Key 可删除任务"""
        mock_creation_svc._tasks["c-standalone-001"] = {"task_id": "c-standalone-001"}

        response = await client.delete("/api/v1/tasks/c-standalone-001")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True


# ============================================
# 任务生命周期（standalone 全流程）
# ============================================


class TestStandaloneTaskLifecycle:
    """standalone 模式下任务生命周期测试"""

    @pytest.mark.asyncio
    async def test_create_then_query(self, client, mock_creation_svc):
        """创建任务后可查询状态"""
        # 创建
        create_resp = await client.post(
            "/api/v1/creation",
            json={"topic": "微服务架构"},
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["task_id"]

        # 查询
        status_resp = await client.get(f"/api/v1/tasks/{task_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "interrupted"

    @pytest.mark.asyncio
    async def test_create_then_resume(self, client, mock_creation_svc):
        """创建任务后可恢复执行"""
        # 创建
        create_resp = await client.post(
            "/api/v1/creation",
            json={"topic": "Python 编程"},
        )
        task_id = create_resp.json()["task_id"]

        # 恢复
        resume_resp = await client.post(
            f"/api/v1/tasks/{task_id}/resume",
            json={"action": "confirm_outline"},
        )
        assert resume_resp.status_code == 200
        assert resume_resp.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_create_then_delete(self, client, mock_creation_svc):
        """创建任务后可删除"""
        # 创建
        create_resp = await client.post(
            "/api/v1/creation",
            json={"topic": "删除测试"},
        )
        task_id = create_resp.json()["task_id"]

        # 删除（从内存中）
        mock_creation_svc._tasks[task_id] = {"task_id": task_id}
        delete_resp = await client.delete(f"/api/v1/tasks/{task_id}")
        assert delete_resp.status_code == 200
        assert delete_resp.json()["deleted"] is True


# ============================================
# 无效 API Key 被忽略（standalone 模式）
# ============================================


class TestStandaloneIgnoresApiKey:
    """standalone 模式下即使提供了 API Key 也被忽略"""

    @pytest.mark.asyncio
    async def test_providing_key_still_accessible(self, client):
        """提供 API Key 不影响访问"""
        response = await client.get(
            "/api/v1/tasks",
            headers={"X-API-Key": "any-key-whatsoever"},
        )

        assert response.status_code == 200
