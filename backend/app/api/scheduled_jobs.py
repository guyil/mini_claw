"""定时任务管理 API

提供：
- GET    /scheduled-jobs              — 列出用户的定时任务
- GET    /scheduled-jobs/{id}         — 获取任务详情
- POST   /scheduled-jobs              — 创建定时任务
- PUT    /scheduled-jobs/{id}         — 更新定时任务
- DELETE /scheduled-jobs/{id}         — 删除定时任务
- POST   /scheduled-jobs/{id}/run     — 手动触发任务
- GET    /scheduled-jobs/{id}/runs    — 获取执行历史
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user_id
from app.database import get_db
from app.schemas.scheduled_job import (
    ScheduledJobCreate,
    ScheduledJobResponse,
    ScheduledJobRunResponse,
    ScheduledJobUpdate,
)

router = APIRouter(prefix="/scheduled-jobs", tags=["scheduled-jobs"])


def _get_scheduler():
    from app.tools.schedule_tools import _scheduler_service
    if _scheduler_service is None:
        raise HTTPException(status_code=503, detail="定时任务调度器未启动")
    return _scheduler_service


@router.get("", response_model=list[ScheduledJobResponse])
async def list_jobs(
    include_disabled: bool = Query(False),
    user_id: str = Depends(get_current_user_id),
):
    """列出当前用户的定时任务"""
    scheduler = _get_scheduler()
    jobs = await scheduler.list_jobs(
        uuid.UUID(user_id), include_disabled=include_disabled
    )
    return [ScheduledJobResponse.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=ScheduledJobResponse)
async def get_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """获取单个定时任务详情"""
    scheduler = _get_scheduler()
    job = await scheduler.get_job(uuid.UUID(job_id), uuid.UUID(user_id))
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ScheduledJobResponse.model_validate(job)


@router.post("", response_model=ScheduledJobResponse, status_code=201)
async def create_job(
    data: ScheduledJobCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建定时任务"""
    scheduler = _get_scheduler()

    from app.models.bot import Bot
    from sqlalchemy import select

    uid = uuid.UUID(user_id)
    result = await db.execute(
        select(Bot.id).where(Bot.owner_id == uid, Bot.is_active.is_(True)).limit(1)
    )
    bot_row = result.fetchone()
    bot_id = bot_row[0] if bot_row else None

    job = await scheduler.add_job(
        user_id=uid,
        bot_id=bot_id,
        conversation_id=None,
        name=data.name,
        description=data.description,
        schedule_type=data.schedule_type,
        schedule_config=data.schedule_config.model_dump(exclude_none=True),
        payload_message=data.payload_message,
        payload_config=data.payload_config,
        delivery_mode=data.delivery_mode,
        delivery_config=data.delivery_config,
        delete_after_run=data.delete_after_run,
    )
    return ScheduledJobResponse.model_validate(job)


@router.put("/{job_id}", response_model=ScheduledJobResponse)
async def update_job(
    job_id: str,
    data: ScheduledJobUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """更新定时任务"""
    scheduler = _get_scheduler()

    kwargs = data.model_dump(exclude_none=True)
    if "schedule_config" in kwargs and kwargs["schedule_config"]:
        kwargs["schedule_config"] = {
            k: v for k, v in kwargs["schedule_config"].items() if v is not None
        }

    job = await scheduler.update_job(
        uuid.UUID(job_id), uuid.UUID(user_id), **kwargs
    )
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在或无权修改")
    return ScheduledJobResponse.model_validate(job)


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """删除定时任务"""
    scheduler = _get_scheduler()
    ok = await scheduler.remove_job(uuid.UUID(job_id), uuid.UUID(user_id))
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在或无权删除")
    return {"ok": True}


@router.post("/{job_id}/run")
async def run_job(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """手动触发定时任务"""
    scheduler = _get_scheduler()
    ok = await scheduler.run_now(uuid.UUID(job_id), uuid.UUID(user_id))
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在或无权执行")
    return {"ok": True, "message": "任务已标记为立即执行"}


@router.get("/{job_id}/runs", response_model=list[ScheduledJobRunResponse])
async def get_job_runs(
    job_id: str,
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
):
    """获取任务执行历史"""
    scheduler = _get_scheduler()
    job = await scheduler.get_job(uuid.UUID(job_id), uuid.UUID(user_id))
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    runs = await scheduler.get_job_runs(uuid.UUID(job_id), limit=limit)
    return [ScheduledJobRunResponse.model_validate(r) for r in runs]
