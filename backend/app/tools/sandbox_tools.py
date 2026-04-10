"""Sandbox CLI Tools — Docker 沙箱执行

通过 SandboxPoolManager 在隔离的 Docker 容器中执行命令。
SandboxPoolManager 未提供或 Docker 不可用时，降级为本地 subprocess。
"""

from __future__ import annotations

import asyncio
import logging
import re

from langchain_core.tools import StructuredTool

from app.services.sandbox_pool import BLOCKED_PATTERNS, SandboxPoolManager

logger = logging.getLogger(__name__)


def create_sandbox_tools(
    session_key: str,
    user_id: str,
    *,
    sandbox_pool: SandboxPoolManager | None = None,
) -> list[StructuredTool]:
    """创建 CLI 沙箱执行工具

    Args:
        session_key: 会话标识，同会话复用同一容器
        user_id: 用户标识
        sandbox_pool: 沙箱容器池管理器，为 None 时降级到本地 subprocess
    """

    pool = sandbox_pool

    async def _exec_via_pool(command: str, timeout: int = 60) -> str:
        return await pool.execute(session_key, user_id, command, timeout=timeout)

    async def _exec_local(command: str, timeout: int = 60) -> str:
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, command):
                return "ERROR: 命令被安全策略阻止。"
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
            if len(result) > 10000:
                result = result[:5000] + "\n\n... [输出已截断] ...\n\n" + result[-2000:]
            return result
        except asyncio.TimeoutError:
            return f"ERROR: 命令执行超时 ({timeout}s)"
        except Exception as e:
            return f"ERROR: {e}"

    _exec_command = _exec_via_pool if pool is not None else _exec_local

    async def _read_file(path: str) -> str:
        return await _exec_command(f"cat {path}")

    async def _write_file(path: str, content: str) -> str:
        return await _exec_command(
            f"cat << 'HEREDOC_EOF' > {path}\n{content}\nHEREDOC_EOF"
        )

    mode_hint = "Docker 沙箱" if (pool and pool.is_docker_mode) else "本地"
    logger.info("沙箱工具已创建: session=%s, mode=%s", session_key, mode_hint)

    return [
        StructuredTool.from_function(
            coroutine=_exec_command,
            name="exec_command",
            description=(
                "在隔离的沙箱环境中执行 Shell 命令并返回输出。"
                "同一会话内的多次调用共享工作区。"
            ),
        ),
        StructuredTool.from_function(
            coroutine=_read_file,
            name="read_file",
            description="读取工作区中的文件内容。",
        ),
        StructuredTool.from_function(
            coroutine=_write_file,
            name="write_file",
            description="将内容写入工作区中的文件。",
        ),
    ]
