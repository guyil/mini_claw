"""Sandbox tools 测试"""

import pytest

from app.tools.sandbox_tools import create_sandbox_tools


@pytest.fixture
def sandbox_tools():
    return create_sandbox_tools("test-session", "test-user")


def test_creates_three_tools(sandbox_tools):
    names = [t.name for t in sandbox_tools]
    assert "exec_command" in names
    assert "read_file" in names
    assert "write_file" in names


@pytest.mark.asyncio
async def test_exec_command_blocked(sandbox_tools):
    exec_tool = next(t for t in sandbox_tools if t.name == "exec_command")
    result = await exec_tool.ainvoke({"command": "rm -rf /"})
    assert "安全策略阻止" in result


@pytest.mark.asyncio
async def test_exec_command_echo(sandbox_tools):
    exec_tool = next(t for t in sandbox_tools if t.name == "exec_command")
    result = await exec_tool.ainvoke({"command": "echo hello"})
    assert "hello" in result
