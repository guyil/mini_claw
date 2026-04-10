"""Sandbox tools 测试

验证 sandbox_tools 通过 SandboxPoolManager 执行命令，
并在 Docker 不可用时正确降级。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.sandbox_pool import SandboxPoolManager
from app.tools.sandbox_tools import create_sandbox_tools


@pytest.fixture
def mock_pool():
    pool = MagicMock(spec=SandboxPoolManager)
    pool.execute = AsyncMock(return_value="mock output")
    pool.is_docker_mode = True
    return pool


@pytest.fixture
def tools_with_pool(mock_pool):
    return create_sandbox_tools("test-session", "test-user", sandbox_pool=mock_pool)


class TestToolCreation:
    def test_creates_three_tools(self, tools_with_pool):
        names = [t.name for t in tools_with_pool]
        assert "exec_command" in names
        assert "read_file" in names
        assert "write_file" in names

    def test_creates_tools_without_pool(self):
        """无 pool 时也能正常创建工具（降级模式）"""
        tools = create_sandbox_tools("test-session", "test-user", sandbox_pool=None)
        assert len(tools) == 3


class TestExecCommand:
    @pytest.mark.asyncio
    async def test_delegates_to_pool(self, tools_with_pool, mock_pool):
        exec_tool = next(t for t in tools_with_pool if t.name == "exec_command")
        result = await exec_tool.ainvoke({"command": "echo hi"})
        mock_pool.execute.assert_awaited_once_with(
            "test-session", "test-user", "echo hi", timeout=60
        )
        assert result == "mock output"

    @pytest.mark.asyncio
    async def test_custom_timeout(self, tools_with_pool, mock_pool):
        exec_tool = next(t for t in tools_with_pool if t.name == "exec_command")
        await exec_tool.ainvoke({"command": "sleep 10", "timeout": 120})
        mock_pool.execute.assert_awaited_once_with(
            "test-session", "test-user", "sleep 10", timeout=120
        )

    @pytest.mark.asyncio
    async def test_blocked_command(self, tools_with_pool, mock_pool):
        mock_pool.execute = AsyncMock(return_value="ERROR: 命令被安全策略阻止。")
        exec_tool = next(t for t in tools_with_pool if t.name == "exec_command")
        result = await exec_tool.ainvoke({"command": "rm -rf /"})
        assert "安全策略阻止" in result


class TestReadFile:
    @pytest.mark.asyncio
    async def test_read_delegates_cat(self, tools_with_pool, mock_pool):
        mock_pool.execute = AsyncMock(return_value="file content here")
        read_tool = next(t for t in tools_with_pool if t.name == "read_file")
        result = await read_tool.ainvoke({"path": "/workspace/test.txt"})
        mock_pool.execute.assert_awaited_once()
        call_args = mock_pool.execute.call_args
        assert "cat" in call_args[0][2]
        assert "file content here" in result


class TestWriteFile:
    @pytest.mark.asyncio
    async def test_write_delegates_heredoc(self, tools_with_pool, mock_pool):
        mock_pool.execute = AsyncMock(return_value="")
        write_tool = next(t for t in tools_with_pool if t.name == "write_file")
        await write_tool.ainvoke({"path": "/workspace/out.txt", "content": "hello"})
        mock_pool.execute.assert_awaited_once()
        call_args = mock_pool.execute.call_args
        assert "out.txt" in call_args[0][2]
        assert "hello" in call_args[0][2]


class TestFallbackWithoutPool:
    @pytest.mark.asyncio
    async def test_exec_echo_without_pool(self):
        """无 pool 时应降级到本地 subprocess"""
        tools = create_sandbox_tools("s1", "u1", sandbox_pool=None)
        exec_tool = next(t for t in tools if t.name == "exec_command")
        result = await exec_tool.ainvoke({"command": "echo fallback_ok"})
        assert "fallback_ok" in result

    @pytest.mark.asyncio
    async def test_blocked_without_pool(self):
        tools = create_sandbox_tools("s1", "u1", sandbox_pool=None)
        exec_tool = next(t for t in tools if t.name == "exec_command")
        result = await exec_tool.ainvoke({"command": "rm -rf /"})
        assert "安全策略阻止" in result
