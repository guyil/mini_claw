"""Sandbox Pool Manager — Docker 沙箱容器池

管理 session-scoped 的 Docker 容器，为每个会话提供隔离的执行环境。
Docker 不可用时自动降级为本地 subprocess 执行（开发模式）。
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

try:
    import docker
    import docker.errors
except ImportError:
    docker = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

BLOCKED_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\b(shutdown|reboot)\b",
    r"\bdd\s+.*of=/",
    r">\s*/dev/",
    r"\bcurl\s+.*\|\s*bash",
    r"\bchmod\s+777",
]

MAX_OUTPUT_LEN = 10000
TRUNCATE_HEAD = 5000
TRUNCATE_TAIL = 2000


def _is_blocked(command: str) -> bool:
    return any(re.search(p, command) for p in BLOCKED_PATTERNS)


@dataclass
class SandboxSession:
    container: object  # docker Container object
    session_key: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        self.last_used = datetime.utcnow()


class SandboxPoolManager:
    """Session-scoped Docker 容器池管理器

    每个 session_key 对应一个独立容器，同会话内共享 /workspace。
    Docker 不可用时降级为本地 subprocess（仅限开发环境）。
    """

    def __init__(
        self,
        image: str = "mclaw-sandbox:latest",
        max_active: int = 10,
        idle_timeout_minutes: int = 10,
    ):
        self.image = image
        self.max_active = max_active
        self.idle_timeout = timedelta(minutes=idle_timeout_minutes)
        self._sessions: dict[str, SandboxSession] = {}
        self._available = False
        self._client = None

        self._init_docker()

    def _init_docker(self) -> None:
        if docker is None:
            logger.warning("docker 包未安装，沙箱将使用本地 subprocess 降级模式")
            return
        try:
            self._client = docker.from_env()
            self._client.ping()
            self._available = True
            logger.info("Docker 沙箱已连接，镜像: %s", self.image)
        except Exception as e:
            logger.warning("Docker 不可用 (%s)，沙箱将使用本地 subprocess 降级模式", e)
            self._available = False

    @property
    def is_docker_mode(self) -> bool:
        return self._available

    async def _get_or_create_container(self, session_key: str, user_id: str):
        """获取已有容器或创建新容器"""
        if session_key in self._sessions:
            session = self._sessions[session_key]
            session.touch()
            return session.container

        container = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._client.containers.run(
                self.image,
                command="sleep infinity",
                detach=True,
                mem_limit="512m",
                cpu_period=100000,
                cpu_quota=50000,  # 0.5 CPU
                network_mode="none",
                read_only=False,
                security_opt=["no-new-privileges"],
                labels={
                    "mclaw.session": session_key,
                    "mclaw.user": user_id,
                    "mclaw.managed": "true",
                },
            ),
        )

        self._sessions[session_key] = SandboxSession(
            container=container,
            session_key=session_key,
            user_id=user_id,
        )
        logger.info(
            "创建沙箱容器: session=%s, container=%s",
            session_key,
            container.id[:12],
        )
        return container

    async def execute(
        self,
        session_key: str,
        user_id: str,
        command: str,
        timeout: int = 60,
    ) -> str:
        """在沙箱中执行命令

        Docker 模式：在隔离容器中执行
        降级模式：在本地 subprocess 中执行
        """
        if _is_blocked(command):
            return "ERROR: 命令被安全策略阻止。"

        if not self._available:
            return await self._fallback_execute(command, timeout)

        active_count = len(self._sessions)
        if session_key not in self._sessions and active_count >= self.max_active:
            return f"ERROR: 活跃容器数已达上限 ({self.max_active})，请稍后重试。"

        try:
            container = await self._get_or_create_container(session_key, user_id)
            exit_code, output = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: container.exec_run(
                    ["bash", "-c", command],
                    workdir="/workspace",
                    user="agent",
                    demux=False,
                ),
            )

            result = output.decode(errors="replace") if output else ""

            if exit_code != 0:
                result += f"\nEXIT_CODE: {exit_code}"

            if len(result) > MAX_OUTPUT_LEN:
                result = (
                    result[:TRUNCATE_HEAD]
                    + "\n\n... [输出已截断] ...\n\n"
                    + result[-TRUNCATE_TAIL:]
                )

            self._sessions[session_key].touch()
            return result

        except Exception as e:
            logger.error("沙箱执行失败: %s", e)
            return f"ERROR: 沙箱执行失败: {e}"

    async def _fallback_execute(self, command: str, timeout: int) -> str:
        """降级模式：本地 subprocess 执行"""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            result = stdout.decode(errors="replace")
            if proc.returncode != 0:
                result += f"\nSTDERR: {stderr.decode(errors='replace')}"

            if len(result) > MAX_OUTPUT_LEN:
                result = (
                    result[:TRUNCATE_HEAD]
                    + "\n\n... [输出已截断] ...\n\n"
                    + result[-TRUNCATE_TAIL:]
                )
            return result

        except asyncio.TimeoutError:
            return f"ERROR: 命令执行超时 ({timeout}s)"
        except Exception as e:
            return f"ERROR: {e}"

    async def release_session(self, session_key: str) -> None:
        """释放会话，停止并移除容器"""
        session = self._sessions.pop(session_key, None)
        if session is None:
            return

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: (session.container.stop(timeout=5), session.container.remove(force=True)),
            )
            logger.info("已释放沙箱容器: session=%s", session_key)
        except Exception as e:
            logger.warning("释放容器失败 (session=%s): %s", session_key, e)

    async def cleanup_idle(self) -> None:
        """清理超过 idle_timeout 的空闲容器"""
        now = datetime.utcnow()
        expired = [
            key
            for key, session in self._sessions.items()
            if (now - session.last_used) > self.idle_timeout
        ]
        for key in expired:
            await self.release_session(key)
        if expired:
            logger.info("清理了 %d 个空闲沙箱容器", len(expired))

    async def shutdown(self) -> None:
        """关闭所有容器（应用退出时调用）"""
        keys = list(self._sessions.keys())
        for key in keys:
            await self.release_session(key)
        logger.info("沙箱容器池已关闭")
