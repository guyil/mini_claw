"""定时任务模型 — 持久化 Agent 创建的定时任务和执行历史"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bots.id"), nullable=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    delete_after_run: Mapped[bool] = mapped_column(Boolean, default=False)

    # "at" = 一次性定时, "interval" = 固定间隔, "cron" = cron 表达式
    schedule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # at: {"at": "2026-04-07T09:00:00+08:00"}
    # interval: {"seconds": 3600}
    # cron: {"cron_expr": "0 9 * * 1-5", "timezone": "Asia/Shanghai"}
    schedule_config: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # 触发时给 Agent 的 prompt
    payload_message: Mapped[str] = mapped_column(Text, nullable=False)
    # 可选覆盖: {"model": "...", "temperature": 0.5}
    payload_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # "chat" / "feishu" / "webhook"
    delivery_mode: Mapped[str] = mapped_column(String(20), default="chat")
    # chat: {} | feishu: {"chat_id": "..."} | webhook: {"url": "https://..."}
    delivery_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ---- 运行时状态 ----
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_run_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_errors: Mapped[int] = mapped_column(Integer, default=0)
    run_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ScheduledJobRun(Base):
    __tablename__ = "scheduled_job_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
