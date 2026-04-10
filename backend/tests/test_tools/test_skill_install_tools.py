"""Tests for skill_install_tools — install_skill LangChain tool."""

from __future__ import annotations

import pytest

from app.tools.skill_install_tools import create_skill_install_tools


class TestCreateSkillInstallTools:
    def test_returns_install_tool(self):
        tools = create_skill_install_tools(db=None, bot_id="bot-1", user_id="user-1")
        assert len(tools) == 1
        assert tools[0].name == "install_skill"
        assert "URL" in tools[0].description

    @pytest.mark.asyncio
    async def test_install_without_db_returns_error(self):
        tools = create_skill_install_tools(db=None, bot_id="bot-1", user_id="user-1")
        result = await tools[0].ainvoke({"url": "https://example.com/skill.zip"})
        assert "ERROR" in result
        assert "数据库" in result
