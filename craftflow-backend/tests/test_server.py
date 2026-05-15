"""server 模式端到端测试

验证 server 模式下的完整行为：
- API Key 鉴权：无 key → 401，无效 key → 403，有效 key → 200
- 健康检查无需鉴权
- 所有 REST 端点均受鉴权保护
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.base import BusinessAdapter
from app.api.dependencies import get_adapter, get_creation_service, get_polishing_service
from app.main import create_app
from app.schemas.response import TaskResponse, TaskStatusResponse
from app.services.creation_svc import CreationService
from app.services.polishing_svc import PolishingService

TEST_API_KEY = "test-server-api-key-12345"


@pytest.fixture
def mock_creation_svc():
    """mock CreationService"""
    svc = AsyncMock(spec=CreationService)
    svc._tasks = {}
    svc.start_task.return_value = TaskResponse(
        task_id="c-server-001",
        status="interrupted",
        message="大纲已生成",
        created_at=datetime(2026, 5, 12, 10, 0, 0),
    )
    svc.get_task_status.return_value = TaskStatusResponse(
        task_id="c-server-001",
        status="interrupted",
        current_node="outline_confirmation",
        awaiting="outline_confirmation",
        progress=30.0,
        created_at=datetime(2026, 5, 12, 10, 0, 0),
        updated_at=datetime(2026, 5, 12, 10, 1, 0),
    )
    svc.resume_task.return_value = TaskResponse(
        task_id="c-server-001",
        status="completed",
        message="创作任务已完成",
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
def server_app(mock_creation_svc, mock_polishing_svc, mock_adapter):
    """创建 server 模式的 FastAPI 应用"""
    app = create_app()
    app.dependency_overrides[get_creation_service] = lambda: mock_creation_svc
    app.dependency_overrides[get_polishing_service] = lambda: mock_polishing_svc
    app.dependency_overrides[get_adapter] = lambda: mock_adapter
    return app


@pytest.fixture
async def client(server_app):
    """创建测试用 HTTP 客户端"""
    transport = ASGITransport(app=server_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _auth_headers(api_key: str = TEST_API_KEY) -> dict[str, str]:
    """生成鉴权请求头"""
    return {"X-API-Key": api_key}


# ============================================
# 健康检查（无需鉴权）
# ============================================


class TestServerHealthCheck:
    """server 模式健康检查（无需 API Key）"""

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client):
        """健康检查端点无需 API Key"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_includes_mode(self, client):
        """健康检查包含 mode 字段"""
        response = await client.get("/health")

        data = response.json()
        assert "mode" in data


# ============================================
# 401 未提供 API Key
# ============================================


class TestServerMissingApiKey:
    """server 模式下未提供 API Key 返回 401"""

    @pytest.mark.asyncio
    async def test_tasks_list_401(self, client):
        """任务列表未提供 key 返回 401"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.get("/api/v1/tasks")

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_task_status_401(self, client):
        """任务状态查询未提供 key 返回 401"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.get("/api/v1/tasks/c-server-001")

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_task_401(self, client):
        """创建任务未提供 key 返回 401"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.post(
                "/api/v1/creation",
                json={"topic": "测试主题"},
            )

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_resume_task_401(self, client):
        """恢复任务未提供 key 返回 401"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.post(
                "/api/v1/tasks/c-server-001/resume",
                json={"action": "confirm_outline"},
            )

            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_task_401(self, client):
        """删除任务未提供 key 返回 401"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.delete("/api/v1/tasks/c-server-001")

            assert response.status_code == 401


# ============================================
# 403 无效 API Key
# ============================================


class TestServerInvalidApiKey:
    """server 模式下无效 API Key 返回 403"""

    @pytest.mark.asyncio
    async def test_tasks_list_403(self, client):
        """任务列表无效 key 返回 403"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.get(
                "/api/v1/tasks",
                headers=_auth_headers("wrong-key"),
            )

            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_task_403(self, client):
        """创建任务无效 key 返回 403"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.post(
                "/api/v1/creation",
                json={"topic": "测试"},
                headers=_auth_headers("wrong-key"),
            )

            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_resume_task_403(self, client):
        """恢复任务无效 key 返回 403"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.post(
                "/api/v1/tasks/c-server-001/resume",
                json={"action": "confirm_outline"},
                headers=_auth_headers("wrong-key"),
            )

            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_task_403(self, client):
        """删除任务无效 key 返回 403"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.delete(
                "/api/v1/tasks/c-server-001",
                headers=_auth_headers("wrong-key"),
            )

            assert response.status_code == 403


# ============================================
# 200 有效 API Key
# ============================================


class TestServerValidApiKey:
    """server 模式下有效 API Key 正常访问"""

    @pytest.mark.asyncio
    async def test_tasks_list_200(self, client):
        """任务列表有效 key 返回 200"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.get(
                "/api/v1/tasks",
                headers=_auth_headers(),
            )

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data

    @pytest.mark.asyncio
    async def test_task_status_200(self, client, mock_creation_svc):
        """任务状态查询有效 key 返回 200"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.get(
                "/api/v1/tasks/c-server-001",
                headers=_auth_headers(),
            )

            assert response.status_code == 200
            assert response.json()["task_id"] == "c-server-001"

    @pytest.mark.asyncio
    async def test_create_task_201(self, client, mock_creation_svc):
        """创建任务有效 key 返回 201"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.post(
                "/api/v1/creation",
                json={"topic": "服务端创作"},
                headers=_auth_headers(),
            )

            assert response.status_code == 201
            assert response.json()["task_id"] == "c-server-001"

    @pytest.mark.asyncio
    async def test_resume_task_200(self, client, mock_creation_svc):
        """恢复任务有效 key 返回 200"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.post(
                "/api/v1/tasks/c-server-001/resume",
                json={"action": "confirm_outline"},
                headers=_auth_headers(),
            )

            assert response.status_code == 200
            assert response.json()["status"] == "completed"

    @pytest.mark.asyncio
    async def test_delete_task_200(self, client, mock_creation_svc):
        """删除任务有效 key 返回 200（内存任务）"""
        mock_creation_svc._tasks["c-server-001"] = {"task_id": "c-server-001"}

        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.delete(
                "/api/v1/tasks/c-server-001",
                headers=_auth_headers(),
            )

            assert response.status_code == 200
            assert response.json()["deleted"] is True


# ============================================
# 错误响应不泄露内部信息（生产环境）
# ============================================


class TestServerErrorSanitization:
    """server 模式（production）下错误响应脱敏"""

    @pytest.mark.asyncio
    async def test_401_response_format(self, client):
        """401 响应包含标准错误格式"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.get("/api/v1/tasks")

            assert response.status_code == 401
            data = response.json()
            assert "error" in data or "detail" in data

    @pytest.mark.asyncio
    async def test_403_response_format(self, client):
        """403 响应包含标准错误格式"""
        with patch("app.core.auth.settings") as mock_auth:
            mock_auth.enable_auth = True
            mock_auth.api_key = TEST_API_KEY

            response = await client.get(
                "/api/v1/tasks",
                headers=_auth_headers("wrong"),
            )

            assert response.status_code == 403
            data = response.json()
            assert "error" in data or "detail" in data
