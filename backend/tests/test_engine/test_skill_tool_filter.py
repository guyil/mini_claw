"""Skill Tool Filter 单元测试

P1: 技能执行时按 required_tools 过滤注入的 tools
"""

from __future__ import annotations

import pytest
from langchain_core.tools import StructuredTool

from app.engine.tool_filter import filter_tools_for_skill


def _make_tool(name: str) -> StructuredTool:
    async def dummy() -> str:
        return "ok"
    return StructuredTool.from_function(
        coroutine=dummy,
        name=name,
        description=f"Tool {name}",
    )


class TestFilterToolsForSkill:
    def test_filter_returns_only_required_tools(self):
        tools = [_make_tool("memory_write"), _make_tool("exec_command"), _make_tool("feishu_send")]
        required = ["exec_command"]

        result = filter_tools_for_skill(tools, required)
        names = [t.name for t in result]
        assert "exec_command" in names
        assert "memory_write" not in names
        assert "feishu_send" not in names

    def test_filter_always_includes_skill_complete(self):
        tools = [_make_tool("exec_command"), _make_tool("skill_complete")]
        required = ["exec_command"]

        result = filter_tools_for_skill(tools, required)
        names = [t.name for t in result]
        assert "skill_complete" in names
        assert "exec_command" in names

    def test_filter_returns_all_when_no_required_tools(self):
        tools = [_make_tool("a"), _make_tool("b"), _make_tool("c")]
        result = filter_tools_for_skill(tools, None)
        assert len(result) == 3

        result = filter_tools_for_skill(tools, [])
        assert len(result) == 3

    def test_filter_handles_missing_tools_gracefully(self):
        tools = [_make_tool("a")]
        required = ["a", "nonexistent"]
        result = filter_tools_for_skill(tools, required)
        names = [t.name for t in result]
        assert "a" in names
        assert len(result) == 1  # nonexistent is silently skipped
