"""鉴权模块测试

测试 API Key 验证逻辑，覆盖 standalone/server 两种模式。
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.core.auth import verify_api_key, verify_ws_api_key

# ============================================
# verify_api_key 测试
# ============================================


class TestVerifyApiKey:
    """测试 REST API Key 验证"""

    @pytest.mark.asyncio
    async def test_standalone_mode_bypass(self):
        """standalone 模式下跳过验证，返回默认调用方"""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.enable_auth = False

            result = await verify_api_key(api_key=None)

            assert result == {"caller": "local", "authenticated": True}

    @pytest.mark.asyncio
    async def test_standalone_mode_ignores_key(self):
        """standalone 模式下即使提供了 key 也忽略"""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.enable_auth = False

            result = await verify_api_key(api_key="any-key")

            assert result == {"caller": "local", "authenticated": True}

    @pytest.mark.asyncio
    async def test_server_mode_valid_key(self):
        """server 模式下有效 key 通过验证"""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.enable_auth = True
            mock_settings.api_key = "test-api-key"

            result = await verify_api_key(api_key="test-api-key")

            assert result == {"caller": "java-backend", "authenticated": True}

    @pytest.mark.asyncio
    async def test_server_mode_missing_key(self):
        """server 模式下未提供 key 返回 401"""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.enable_auth = True
            mock_settings.api_key = "test-api-key"

            with pytest.raises(Exception) as exc_info:
                await verify_api_key(api_key=None)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_server_mode_invalid_key(self):
        """server 模式下无效 key 返回 403"""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.enable_auth = True
            mock_settings.api_key = "test-api-key"

            with pytest.raises(Exception) as exc_info:
                await verify_api_key(api_key="wrong-key")

            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


# ============================================
# verify_ws_api_key 测试
# ============================================


class TestVerifyWsApiKey:
    """测试 WebSocket API Key 验证"""

    @pytest.mark.asyncio
    async def test_standalone_mode_bypass(self):
        """standalone 模式下跳过 WebSocket 验证"""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.enable_auth = False

            mock_ws = AsyncMock()
            mock_ws.query_params = {}

            result = await verify_ws_api_key(mock_ws)

            assert result is True
            mock_ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_server_mode_valid_key(self):
        """server 模式下有效 key 通过 WebSocket 验证"""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.enable_auth = True
            mock_settings.api_key = "test-api-key"

            mock_ws = AsyncMock()
            mock_ws.query_params = {"api_key": "test-api-key"}

            result = await verify_ws_api_key(mock_ws)

            assert result is True
            mock_ws.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_server_mode_missing_key(self):
        """server 模式下未提供 key 关闭连接"""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.enable_auth = True
            mock_settings.api_key = "test-api-key"

            mock_ws = AsyncMock()
            mock_ws.query_params = {}

            result = await verify_ws_api_key(mock_ws)

            assert result is False
            mock_ws.close.assert_called_once_with(code=4001, reason="未提供 API Key")

    @pytest.mark.asyncio
    async def test_server_mode_invalid_key(self):
        """server 模式下无效 key 关闭连接"""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.enable_auth = True
            mock_settings.api_key = "test-api-key"

            mock_ws = AsyncMock()
            mock_ws.query_params = {"api_key": "wrong-key"}

            result = await verify_ws_api_key(mock_ws)

            assert result is False
            mock_ws.close.assert_called_once_with(code=4001, reason="无效的 API Key")


# ============================================
# REST 路由鉴权集成测试
# ============================================


class TestRestAuthIntegration:
    """测试 REST 路由鉴权集成"""

    @pytest.fixture
    def app(self):
        """创建测试用 FastAPI 应用"""
        from unittest.mock import AsyncMock

        from app.adapters.base import BusinessAdapter
        from app.api.dependencies import get_adapter, get_creation_service, get_polishing_service
        from app.api.v1.creation import router as creation_router
        from app.api.v1.tasks import router as tasks_router
        from app.core.exceptions import register_exception_handlers
        from app.services.creation_svc import CreationService
        from app.services.polishing_svc import PolishingService

        application = FastAPI()
        register_exception_handlers(application)
        application.include_router(creation_router, prefix="/api/v1")
        application.include_router(tasks_router, prefix="/api/v1")

        # Mock 服务依赖
        mock_creation = AsyncMock(spec=CreationService)
        mock_creation._tasks = {}
        mock_polishing = AsyncMock(spec=PolishingService)
        mock_polishing._tasks = {}
        mock_adapter = AsyncMock(spec=BusinessAdapter)
        mock_adapter.get_task.return_value = None
        mock_adapter.get_task_list.return_value = ([], 0)

        application.dependency_overrides[get_creation_service] = lambda: mock_creation
        application.dependency_overrides[get_polishing_service] = lambda: mock_polishing
        application.dependency_overrides[get_adapter] = lambda: mock_adapter

        return application

    @pytest.mark.asyncio
    async def test_standalone_no_auth_required(self, app):
        """standalone 模式下无需 API Key 即可访问"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.core.auth.settings") as mock_settings:
                mock_settings.enable_auth = False

                response = await client.get("/api/v1/tasks")

                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_server_mode_missing_key_returns_401(self, app):
        """server 模式下未提供 API Key 返回 401"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.core.auth.settings") as mock_settings:
                mock_settings.enable_auth = True
                mock_settings.api_key = "test-key"

                response = await client.get("/api/v1/tasks")

                assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_server_mode_invalid_key_returns_403(self, app):
        """server 模式下无效 API Key 返回 403"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.core.auth.settings") as mock_settings:
                mock_settings.enable_auth = True
                mock_settings.api_key = "test-key"

                response = await client.get(
                    "/api/v1/tasks",
                    headers={"X-API-Key": "wrong-key"},
                )

                assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_server_mode_valid_key_passes(self, app):
        """server 模式下有效 API Key 正常访问"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.core.auth.settings") as mock_settings:
                mock_settings.enable_auth = True
                mock_settings.api_key = "test-key"

                response = await client.get(
                    "/api/v1/tasks",
                    headers={"X-API-Key": "test-key"},
                )

                assert response.status_code == 200
