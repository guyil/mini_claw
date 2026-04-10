"""Tests for enhanced skill_service — get_skill_with_assets."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.skill_service import get_skill_with_assets


def _make_skill(name="test_skill", instructions="do stuff", assets=None):
    skill = MagicMock()
    skill.name = name
    skill.instructions = instructions
    skill.assets = assets or []
    return skill


def _make_asset(filename="scripts/run.py", content="print(1)", is_binary=False):
    asset = MagicMock()
    asset.filename = filename
    asset.content = content
    asset.is_binary = is_binary
    return asset


class TestGetSkillWithAssets:
    @pytest.mark.asyncio
    async def test_returns_instructions_and_assets(self):
        assets = [
            _make_asset("scripts/fill.py", "fill()"),
            _make_asset("reference.md", "# Ref"),
        ]
        skill = _make_skill(assets=assets)

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = skill
        db.execute.return_value = result_mock

        result = await get_skill_with_assets(db, "test_skill")
        assert result is not None
        assert result["instructions"] == "do stuff"
        assert len(result["assets"]) == 2
        assert result["assets"][0]["filename"] == "scripts/fill.py"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_skill(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        result = await get_skill_with_assets(db, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_excludes_binary_assets(self):
        assets = [
            _make_asset("scripts/run.py", "code"),
            _make_asset("image.png", "binary", is_binary=True),
        ]
        skill = _make_skill(assets=assets)

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = skill
        db.execute.return_value = result_mock

        result = await get_skill_with_assets(db, "test_skill")
        text_assets = [a for a in result["assets"] if not a["is_binary"]]
        assert len(text_assets) == 1
