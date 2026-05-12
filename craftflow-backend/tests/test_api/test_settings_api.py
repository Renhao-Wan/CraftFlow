"""Settings API 测试

测试 LLM Profile CRUD 和写作参数 API 端点。
使用 mock 隔离 BusinessAdapter。
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.base import BusinessAdapter
from app.api.dependencies import get_adapter
from app.main import create_app


@pytest.fixture
def mock_adapter():
    """mock BusinessAdapter"""
    adapter = AsyncMock(spec=BusinessAdapter)

    # LLM Profile mock 数据
    adapter.get_all_llm_profiles.return_value = [
        {
            "id": "profile-001",
            "name": "GPT-4",
            "api_key": "sk-test1234abcd",
            "api_base": "https://api.openai.com/v1",
            "model": "gpt-4",
            "temperature": 0.7,
            "is_default": True,
            "created_at": "2026-05-12T10:00:00",
            "updated_at": "2026-05-12T10:00:00",
        }
    ]

    adapter.get_llm_profile.return_value = {
        "id": "profile-001",
        "name": "GPT-4",
        "api_key": "sk-test1234abcd",
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-4",
        "temperature": 0.7,
        "is_default": True,
        "created_at": "2026-05-12T10:00:00",
        "updated_at": "2026-05-12T10:00:00",
    }

    adapter.save_llm_profile.return_value = {
        "id": "profile-new",
        "name": "DeepSeek",
        "api_key": "sk-new-key",
        "api_base": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "temperature": 0.5,
        "is_default": False,
        "created_at": "2026-05-12T11:00:00",
        "updated_at": "2026-05-12T11:00:00",
    }

    adapter.delete_llm_profile.return_value = True
    adapter.set_default_profile.return_value = True

    # 写作参数 mock 数据
    adapter.get_writing_params.return_value = {
        "max_outline_sections": "5",
        "max_concurrent_writers": "3",
    }
    adapter.update_writing_params.return_value = {
        "max_outline_sections": "8",
        "max_concurrent_writers": "5",
    }

    return adapter


@pytest.fixture
def settings_app(mock_adapter):
    """创建包含 Settings 路由的 FastAPI 应用"""
    app = create_app()
    app.dependency_overrides[get_adapter] = lambda: mock_adapter
    return app


@pytest.fixture
async def client(settings_app):
    """创建测试用 HTTP 客户端"""
    transport = ASGITransport(app=settings_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================
# LLM Profile CRUD
# ============================================


class TestLlmProfilesApi:
    """测试 LLM Profile API"""

    @pytest.mark.asyncio
    async def test_list_profiles(self, client, mock_adapter):
        """测试获取所有 Profile"""
        response = await client.get("/api/v1/settings/llm-profiles")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "profile-001"
        # API Key 应被脱敏
        assert "****" in data[0]["api_key"]

    @pytest.mark.asyncio
    async def test_create_profile(self, client, mock_adapter):
        """测试创建新 Profile"""
        response = await client.post(
            "/api/v1/settings/llm-profiles",
            json={
                "name": "DeepSeek",
                "api_key": "sk-new-key",
                "api_base": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "temperature": 0.5,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "DeepSeek"
        assert "****" in data["api_key"]
        mock_adapter.save_llm_profile.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_profile_with_default(self, client, mock_adapter):
        """测试创建 Profile 并设为默认"""
        response = await client.post(
            "/api/v1/settings/llm-profiles",
            json={
                "name": "Default Model",
                "api_key": "sk-key",
                "model": "gpt-4o",
                "is_default": True,
            },
        )

        assert response.status_code == 201
        mock_adapter.set_default_profile.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_profile(self, client, mock_adapter):
        """测试更新 Profile"""
        response = await client.put(
            "/api/v1/settings/llm-profiles/profile-001",
            json={
                "name": "GPT-4 Updated",
                "api_key": "sk-updated-key",
                "model": "gpt-4-turbo",
            },
        )

        assert response.status_code == 200
        mock_adapter.save_llm_profile.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_nonexistent_profile(self, client, mock_adapter):
        """测试更新不存在的 Profile 返回 404"""
        mock_adapter.get_llm_profile.return_value = None

        response = await client.put(
            "/api/v1/settings/llm-profiles/nonexistent",
            json={"name": "Test", "api_key": "sk-key", "model": "gpt-4"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_profile(self, client, mock_adapter):
        """测试删除 Profile"""
        response = await client.delete("/api/v1/settings/llm-profiles/profile-001")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        mock_adapter.delete_llm_profile.assert_called_once_with("profile-001")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_profile(self, client, mock_adapter):
        """测试删除不存在的 Profile 返回 404"""
        mock_adapter.delete_llm_profile.return_value = False

        response = await client.delete("/api/v1/settings/llm-profiles/nonexistent")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_set_default_profile(self, client, mock_adapter):
        """测试设为默认"""
        response = await client.post("/api/v1/settings/llm-profiles/profile-001/set-default")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_adapter.set_default_profile.assert_called_once_with("profile-001")

    @pytest.mark.asyncio
    async def test_set_default_nonexistent(self, client, mock_adapter):
        """测试设为默认时 Profile 不存在返回 404"""
        mock_adapter.set_default_profile.return_value = False

        response = await client.post("/api/v1/settings/llm-profiles/nonexistent/set-default")

        assert response.status_code == 404


# ============================================
# 写作参数
# ============================================


class TestWritingParamsApi:
    """测试写作参数 API"""

    @pytest.mark.asyncio
    async def test_get_writing_params(self, client, mock_adapter):
        """测试获取写作参数"""
        response = await client.get("/api/v1/settings/writing-params")

        assert response.status_code == 200
        data = response.json()
        assert data["max_outline_sections"] == 5
        assert data["max_concurrent_writers"] == 3

    @pytest.mark.asyncio
    async def test_update_writing_params(self, client, mock_adapter):
        """测试更新写作参数"""
        response = await client.patch(
            "/api/v1/settings/writing-params",
            json={"max_outline_sections": 8, "max_concurrent_writers": 5},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["max_outline_sections"] == 8
        assert data["max_concurrent_writers"] == 5
        mock_adapter.update_writing_params.assert_called_once_with(
            {"max_outline_sections": 8, "max_concurrent_writers": 5}
        )

    @pytest.mark.asyncio
    async def test_update_partial_writing_params(self, client, mock_adapter):
        """测试部分更新写作参数"""
        response = await client.patch(
            "/api/v1/settings/writing-params",
            json={"max_outline_sections": 10},
        )

        assert response.status_code == 200
        mock_adapter.update_writing_params.assert_called_once_with(
            {"max_outline_sections": 10}
        )

    @pytest.mark.asyncio
    async def test_update_empty_writing_params(self, client, mock_adapter):
        """测试空更新返回当前值"""
        response = await client.patch(
            "/api/v1/settings/writing-params",
            json={},
        )

        assert response.status_code == 200
        mock_adapter.update_writing_params.assert_not_called()
