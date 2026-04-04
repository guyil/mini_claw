"""Sandbox CLI Tools — Docker 沙箱执行

MVP 阶段使用 stub 实现（直接在本地 subprocess 执行或返回模拟结果），
后续接入 SandboxPoolManager 实现真正的容器隔离。
"""

from __future__ import annotations

import asyncio
import logging
import re

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

BLOCKED_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\b(shutdown|reboot)\b",
    r"\bdd\s+.*of=/",
    r">\s*/dev/",
    r"\bcurl\s+.*\|\s*bash",
    r"\bchmod\s+777",
]


def create_sandbox_tools(session_key: str, user_id: str) -> list[StructuredTool]:
    """创建 CLI 沙箱执行工具（MVP stub 版本）"""

    async def _exec_command(command: str, timeout: int = 60) -> str:
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, command):
                return "ERROR: 命令被安全策略阻止。"

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
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

    async def _read_file(path: str) -> str:
        return await _exec_command(f"cat {path}")

    async def _write_file(path: str, content: str) -> str:
        return await _exec_command(
            f"cat << 'HEREDOC_EOF' > {path}\n{content}\nHEREDOC_EOF"
        )

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
