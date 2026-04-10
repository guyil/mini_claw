"""SandboxPoolManager 测试

测试 Docker 沙箱容器池的完整生命周期：
- 容器创建与复用
- 命令执行
- 会话释放
- 空闲清理
- Docker 不可用时的降级行为
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sandbox_pool import SandboxPoolManager


@pytest.fixture
def mock_docker_client():
    """模拟 docker.DockerClient"""
    client = MagicMock()
    client.ping = MagicMock(return_value=True)

    container = MagicMock()
    container.id = "abc123"
    container.status = "running"
    container.exec_run = MagicMock(return_value=(0, b"hello world"))
    container.stop = MagicMock()
    container.remove = MagicMock()

    client.containers = MagicMock()
    client.containers.run = MagicMock(return_value=container)

    return client, container


@pytest.fixture
def pool_with_docker(mock_docker_client):
    """使用模拟 Docker client 的 pool"""
    client, container = mock_docker_client
    with patch("app.services.sandbox_pool.docker") as mock_docker_mod:
        mock_docker_mod.from_env.return_value = client
        pool = SandboxPoolManager(image="mclaw-sandbox:latest")
        pool._client = client
        pool._available = True
        yield pool, client, container


class TestSandboxPoolInit:
    def test_docker_unavailable_sets_available_false(self):
        """Docker 不可用时应标记为不可用而非抛异常"""
        with patch("app.services.sandbox_pool.docker") as mock_docker_mod:
            mock_docker_mod.from_env.side_effect = Exception("Docker not running")
            pool = SandboxPoolManager()
            assert pool._available is False

    def test_docker_available_sets_available_true(self, mock_docker_client):
        client, _ = mock_docker_client
        with patch("app.services.sandbox_pool.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = client
            pool = SandboxPoolManager()
            assert pool._available is True


class TestContainerLifecycle:
    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_container(self, pool_with_docker):
        pool, client, container = pool_with_docker
        result = await pool._get_or_create_container("session-1", "user-1")
        assert result == container
        client.containers.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_reuses_existing(self, pool_with_docker):
        pool, client, container = pool_with_docker
        await pool._get_or_create_container("session-1", "user-1")
        await pool._get_or_create_container("session-1", "user-1")
        # 只应创建一次
        assert client.containers.run.call_count == 1

    @pytest.mark.asyncio
    async def test_release_session_stops_container(self, pool_with_docker):
        pool, client, container = pool_with_docker
        await pool._get_or_create_container("session-1", "user-1")
        await pool.release_session("session-1")
        container.stop.assert_called_once()
        container.remove.assert_called_once()
        assert "session-1" not in pool._sessions

    @pytest.mark.asyncio
    async def test_release_nonexistent_session_is_noop(self, pool_with_docker):
        pool, _, _ = pool_with_docker
        await pool.release_session("nonexistent")

    @pytest.mark.asyncio
    async def test_max_active_limit(self, pool_with_docker):
        pool, client, container = pool_with_docker
        pool.max_active = 2
        await pool._get_or_create_container("s1", "u1")
        await pool._get_or_create_container("s2", "u1")
        result = await pool.execute("s3", "u1", "echo test")
        assert "容器数已达上限" in result


class TestCommandExecution:
    @pytest.mark.asyncio
    async def test_execute_returns_stdout(self, pool_with_docker):
        pool, client, container = pool_with_docker
        container.exec_run.return_value = (0, b"output data")
        result = await pool.execute("session-1", "user-1", "echo hi")
        assert "output data" in result

    @pytest.mark.asyncio
    async def test_execute_returns_stderr_on_nonzero_exit(self, pool_with_docker):
        pool, client, container = pool_with_docker
        container.exec_run.return_value = (1, b"error msg")
        result = await pool.execute("session-1", "user-1", "bad_cmd")
        assert "error msg" in result
        assert "EXIT_CODE: 1" in result

    @pytest.mark.asyncio
    async def test_execute_truncates_long_output(self, pool_with_docker):
        pool, client, container = pool_with_docker
        long_output = b"x" * 20000
        container.exec_run.return_value = (0, long_output)
        result = await pool.execute("session-1", "user-1", "big_output")
        assert "输出已截断" in result
        assert len(result) < 20000

    @pytest.mark.asyncio
    async def test_blocked_command_rejected(self, pool_with_docker):
        pool, _, _ = pool_with_docker
        result = await pool.execute("s1", "u1", "rm -rf /")
        assert "安全策略阻止" in result

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, pool_with_docker):
        pool, client, container = pool_with_docker
        container.exec_run.return_value = (0, b"done")
        await pool.execute("s1", "u1", "sleep 1", timeout=30)
        call_kwargs = container.exec_run.call_args
        assert call_kwargs is not None


class TestFallbackMode:
    @pytest.mark.asyncio
    async def test_fallback_executes_locally(self):
        """Docker 不可用时应降级到本地 subprocess"""
        with patch("app.services.sandbox_pool.docker") as mock_docker_mod:
            mock_docker_mod.from_env.side_effect = Exception("Docker not running")
            pool = SandboxPoolManager()
            result = await pool.execute("s1", "u1", "echo fallback_test")
            assert "fallback_test" in result

    @pytest.mark.asyncio
    async def test_fallback_blocked_command(self):
        """降级模式下也应拦截危险命令"""
        with patch("app.services.sandbox_pool.docker") as mock_docker_mod:
            mock_docker_mod.from_env.side_effect = Exception("Docker not running")
            pool = SandboxPoolManager()
            result = await pool.execute("s1", "u1", "rm -rf /")
            assert "安全策略阻止" in result


class TestIdleCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_removes_idle_sessions(self, pool_with_docker):
        pool, client, container = pool_with_docker
        await pool._get_or_create_container("s1", "u1")
        # 手动将 last_used 设为很久以前
        pool._sessions["s1"].last_used = pool._sessions["s1"].last_used.replace(year=2020)
        await pool.cleanup_idle()
        assert "s1" not in pool._sessions
        container.stop.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_keeps_active_sessions(self, pool_with_docker):
        pool, client, container = pool_with_docker
        await pool._get_or_create_container("s1", "u1")
        await pool.cleanup_idle()
        assert "s1" in pool._sessions
