"""Sandbox Pool Manager — Docker 沙箱容器池

MVP 阶段的骨架实现，后续接入 Docker SDK 实现真正的容器管理。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class SandboxSession:
    container_id: str
    session_key: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: datetime = field(default_factory=datetime.utcnow)


class SandboxPoolManager:
    """Session-scoped Docker 容器池管理器 (MVP stub)"""

    def __init__(
        self,
        image: str = "mclaw-sandbox:latest",
        warm_pool_size: int = 2,
        max_active: int = 10,
        idle_timeout_minutes: int = 10,
    ):
        self.image = image
        self.warm_pool_size = warm_pool_size
        self.max_active = max_active
        self.idle_timeout = timedelta(minutes=idle_timeout_minutes)
        self.active: dict[str, SandboxSession] = {}
        logger.info(
            "SandboxPoolManager initialized (stub mode): "
            f"image={image}, warm={warm_pool_size}, max={max_active}"
        )

    async def initialize(self):
        logger.info("SandboxPoolManager.initialize() — stub, no containers created")

    async def execute(
        self,
        session_key: str,
        user_id: str,
        command: str,
        env_vars: dict | None = None,
        timeout: int = 60,
    ) -> str:
        """MVP: 直接返回提示信息，不实际执行 Docker"""
        logger.info(f"Sandbox execute (stub): session={session_key}, cmd={command[:100]}")
        return (
            f"[Sandbox Stub] 命令已记录但未在 Docker 中执行: {command[:200]}\n"
            "Docker 沙箱功能将在容器可用后启用。"
        )

    async def release_session(self, session_key: str):
        self.active.pop(session_key, None)

    async def cleanup_idle(self):
        pass
