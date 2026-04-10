"""定时任务 Pydantic schemas — API 请求/响应校验"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ScheduleConfig(BaseModel):
    """调度配置 — 根据 schedule_type 使用不同字段"""
    at: str | None = Field(None, description="ISO-8601 时间戳 (schedule_type=at)")
    seconds: int | None = Field(None, description="间隔秒数 (schedule_type=interval)")
    cron_expr: str | None = Field(None, description="cron 表达式 (schedule_type=cron)")
    timezone: str = Field("Asia/Shanghai", description="IANA 时区")


class ScheduledJobCreate(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = None
    schedule_type: Literal["at", "interval", "cron"]
    schedule_config: ScheduleConfig
    payload_message: str = Field(..., description="触发时给 Agent 的 prompt")
    payload_config: dict[str, Any] | None = None
    delivery_mode: Literal["chat", "feishu", "webhook"] = "chat"
    delivery_config: dict[str, Any] | None = None
    delete_after_run: bool = False


class ScheduledJobUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    description: str | None = None
    schedule_type: Literal["at", "interval", "cron"] | None = None
    schedule_config: ScheduleConfig | None = None
    payload_message: str | None = None
    payload_config: dict[str, Any] | None = None
    delivery_mode: Literal["chat", "feishu", "webhook"] | None = None
    delivery_config: dict[str, Any] | None = None
    enabled: bool | None = None
    delete_after_run: bool | None = None


class ScheduledJobResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    bot_id: uuid.UUID | None
    conversation_id: uuid.UUID | None
    name: str
    description: str | None
    enabled: bool
    delete_after_run: bool
    schedule_type: str
    schedule_config: dict[str, Any]
    payload_message: str
    payload_config: dict[str, Any] | None
    delivery_mode: str
    delivery_config: dict[str, Any] | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_status: str | None
    last_error: str | None
    last_result_summary: str | None
    consecutive_errors: int
    run_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduledJobRunResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    status: str
    error: str | None
    result_summary: str | None
    duration_ms: int | None

    model_config = {"from_attributes": True}
