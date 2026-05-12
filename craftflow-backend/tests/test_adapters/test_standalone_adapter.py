"""StandaloneAdapter LLM Profile CRUD 测试

测试 LLM Profile 的增删改查、默认切换等逻辑。
使用临时 SQLite 文件，测试结束后自动清理。
"""

from pathlib import Path

import pytest

from app.adapters.standalone import StandaloneAdapter


@pytest.fixture
async def adapter(tmp_path: Path):
    """创建使用临时 SQLite 的 StandaloneAdapter"""
    db_path = tmp_path / "test_craftflow.db"
    svc = StandaloneAdapter(db_path=db_path)
    await svc.init()
    yield svc
    await svc.close()


def _sample_profile(name: str = "default", is_default: int = 0) -> dict:
    """生成测试用 Profile 数据"""
    return {
        "name": name,
        "api_key": "sk-test-key",
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-4",
        "temperature": 0.7,
        "is_default": is_default,
    }


# ============================================
# save_llm_profile 测试
# ============================================


class TestSaveLlmProfile:
    """测试保存 LLM Profile"""

    @pytest.mark.asyncio
    async def test_save_new_profile(self, adapter):
        """测试新建 Profile"""
        result = await adapter.save_llm_profile(_sample_profile())

        assert result["id"] is not None
        assert result["name"] == "default"
        assert result["api_key"] == "sk-test-key"
        assert result["model"] == "gpt-4"
        assert result["temperature"] == 0.7
        assert result["is_default"] is False
        assert result["created_at"] is not None
        assert result["updated_at"] is not None

    @pytest.mark.asyncio
    async def test_save_profile_with_custom_id(self, adapter):
        """测试指定 ID 新建 Profile"""
        profile = _sample_profile(name="custom")
        profile["id"] = "custom-id-001"

        result = await adapter.save_llm_profile(profile)

        assert result["id"] == "custom-id-001"
        assert result["name"] == "custom"

    @pytest.mark.asyncio
    async def test_save_updates_existing_profile(self, adapter):
        """测试更新已存在的 Profile"""
        profile = _sample_profile(name="to-update")
        saved = await adapter.save_llm_profile(profile)

        # 修改 model 字段
        update_data = {**saved, "model": "gpt-4o"}
        updated = await adapter.save_llm_profile(update_data)

        assert updated["id"] == saved["id"]
        assert updated["model"] == "gpt-4o"
        assert updated["created_at"] == saved["created_at"]
        assert updated["updated_at"] >= saved["updated_at"]

    @pytest.mark.asyncio
    async def test_save_default_profile(self, adapter):
        """测试保存默认 Profile"""
        result = await adapter.save_llm_profile(_sample_profile(is_default=1))

        assert result["is_default"] is True

    @pytest.mark.asyncio
    async def test_save_profile_default_values(self, adapter):
        """测试默认值填充"""
        minimal = {"name": "minimal", "api_key": "sk-xxx", "model": "gpt-3.5-turbo"}
        result = await adapter.save_llm_profile(minimal)

        assert result["api_base"] == ""
        assert result["temperature"] == 0.7
        assert result["is_default"] is False


# ============================================
# get_llm_profile 测试
# ============================================


class TestGetLlmProfile:
    """测试查询 LLM Profile"""

    @pytest.mark.asyncio
    async def test_get_by_id(self, adapter):
        """测试按 ID 查询"""
        saved = await adapter.save_llm_profile(_sample_profile(name="by-id"))

        result = await adapter.get_llm_profile(saved["id"])

        assert result is not None
        assert result["id"] == saved["id"]
        assert result["name"] == "by-id"

    @pytest.mark.asyncio
    async def test_get_default_profile(self, adapter):
        """测试查询默认 Profile"""
        await adapter.save_llm_profile(_sample_profile(name="non-default", is_default=0))
        await adapter.save_llm_profile(_sample_profile(name="the-default", is_default=1))

        result = await adapter.get_llm_profile()

        assert result is not None
        assert result["name"] == "the-default"
        assert result["is_default"] is True

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, adapter):
        """测试查询不存在的 Profile 返回 None"""
        result = await adapter.get_llm_profile("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_default_when_none_set(self, adapter):
        """测试无默认 Profile 时返回 None"""
        await adapter.save_llm_profile(_sample_profile(is_default=0))

        result = await adapter.get_llm_profile()

        assert result is None


# ============================================
# get_all_llm_profiles 测试
# ============================================


class TestGetAllLlmProfiles:
    """测试查询所有 LLM Profile"""

    @pytest.mark.asyncio
    async def test_get_all_empty(self, adapter):
        """测试空列表"""
        result = await adapter.get_all_llm_profiles()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_all_returns_sorted(self, adapter):
        """测试返回所有 Profile 且包含全部记录"""
        await adapter.save_llm_profile(_sample_profile(name="alpha"))
        await adapter.save_llm_profile(_sample_profile(name="beta"))
        await adapter.save_llm_profile(_sample_profile(name="gamma"))

        result = await adapter.get_all_llm_profiles()

        assert len(result) == 3
        names = {p["name"] for p in result}
        assert names == {"alpha", "beta", "gamma"}

    @pytest.mark.asyncio
    async def test_get_all_contains_all_fields(self, adapter):
        """测试返回的字段完整性"""
        await adapter.save_llm_profile(_sample_profile())

        result = await adapter.get_all_llm_profiles()

        assert len(result) == 1
        profile = result[0]
        assert "id" in profile
        assert "name" in profile
        assert "api_key" in profile
        assert "api_base" in profile
        assert "model" in profile
        assert "temperature" in profile
        assert "is_default" in profile
        assert "created_at" in profile
        assert "updated_at" in profile


# ============================================
# delete_llm_profile 测试
# ============================================


class TestDeleteLlmProfile:
    """测试删除 LLM Profile"""

    @pytest.mark.asyncio
    async def test_delete_existing(self, adapter):
        """测试删除已存在的 Profile"""
        saved = await adapter.save_llm_profile(_sample_profile())

        result = await adapter.delete_llm_profile(saved["id"])

        assert result is True
        assert await adapter.get_llm_profile(saved["id"]) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, adapter):
        """测试删除不存在的 Profile 返回 False"""
        result = await adapter.delete_llm_profile("nonexistent-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_does_not_affect_others(self, adapter):
        """测试删除不影响其他 Profile"""
        p1 = await adapter.save_llm_profile(_sample_profile(name="keep"))
        p2 = await adapter.save_llm_profile(_sample_profile(name="remove"))

        await adapter.delete_llm_profile(p2["id"])

        assert await adapter.get_llm_profile(p1["id"]) is not None
        assert await adapter.get_llm_profile(p2["id"]) is None


# ============================================
# set_default_profile 测试
# ============================================


class TestSetDefaultProfile:
    """测试设置默认 Profile"""

    @pytest.mark.asyncio
    async def test_set_default(self, adapter):
        """测试将 Profile 设为默认"""
        saved = await adapter.save_llm_profile(_sample_profile(is_default=0))

        result = await adapter.set_default_profile(saved["id"])

        assert result is True
        profile = await adapter.get_llm_profile(saved["id"])
        assert profile["is_default"] is True

    @pytest.mark.asyncio
    async def test_set_default_clears_previous(self, adapter):
        """测试切换默认时清除旧默认"""
        p1 = await adapter.save_llm_profile(_sample_profile(name="old-default", is_default=1))
        p2 = await adapter.save_llm_profile(_sample_profile(name="new-default", is_default=0))

        await adapter.set_default_profile(p2["id"])

        old = await adapter.get_llm_profile(p1["id"])
        new = await adapter.get_llm_profile(p2["id"])
        assert old["is_default"] is False
        assert new["is_default"] is True

    @pytest.mark.asyncio
    async def test_set_default_nonexistent_returns_false(self, adapter):
        """测试设置不存在的 Profile 返回 False"""
        result = await adapter.set_default_profile("nonexistent-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_only_one_default_exists(self, adapter):
        """测试同一时刻最多一个默认 Profile"""
        p1 = await adapter.save_llm_profile(_sample_profile(name="p1", is_default=1))
        p2 = await adapter.save_llm_profile(_sample_profile(name="p2"))
        p3 = await adapter.save_llm_profile(_sample_profile(name="p3"))

        await adapter.set_default_profile(p2["id"])
        await adapter.set_default_profile(p3["id"])

        profiles = await adapter.get_all_llm_profiles()
        defaults = [p for p in profiles if p["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["id"] == p3["id"]


# ============================================
# 写作参数测试
# ============================================


class TestWritingParams:
    """测试写作参数 CRUD"""

    @pytest.mark.asyncio
    async def test_get_default_writing_params(self, adapter):
        """测试获取默认写作参数"""
        params = await adapter.get_writing_params()

        assert params["max_outline_sections"] == "5"
        assert params["max_concurrent_writers"] == "3"

    @pytest.mark.asyncio
    async def test_update_writing_params(self, adapter):
        """测试更新写作参数"""
        params = await adapter.update_writing_params(
            {"max_outline_sections": "8", "max_concurrent_writers": "5"}
        )

        assert params["max_outline_sections"] == "8"
        assert params["max_concurrent_writers"] == "5"

    @pytest.mark.asyncio
    async def test_update_partial_writing_params(self, adapter):
        """测试部分更新写作参数"""
        await adapter.update_writing_params({"max_outline_sections": "10"})

        params = await adapter.get_writing_params()
        assert params["max_outline_sections"] == "10"
        # 未更新的应保持默认值
        assert params["max_concurrent_writers"] == "3"

    @pytest.mark.asyncio
    async def test_writing_params_persisted(self, adapter):
        """测试写作参数持久化"""
        await adapter.update_writing_params({"max_outline_sections": "7"})

        # 关闭并重新打开
        await adapter.close()
        adapter.task_store = adapter.task_store.__class__(adapter.task_store._db_path)
        await adapter.init()

        params = await adapter.get_writing_params()
        assert params["max_outline_sections"] == "7"
