"""定时任务调度服务 — asyncio 后台循环 + croniter 表达式解析

启动时从 DB 加载所有启用的任务，计算 next_run_at，
后台 loop 每 30s 查询到期任务并执行。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from croniter import croniter
from sqlalchemy import select, update
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.scheduled_job import ScheduledJob, ScheduledJobRun

logger = logging.getLogger(__name__)


def _is_missing_table_error(exc: Exception) -> bool:
    return isinstance(exc, ProgrammingError) and "UndefinedTableError" in str(exc)

POLL_INTERVAL_SECONDS = 30
MAX_BACKOFF_SECONDS = 3600


def compute_next_run_at(
    schedule_type: str,
    schedule_config: dict,
    base_time: datetime | None = None,
) -> datetime | None:
    """根据调度配置计算下一次运行时间"""
    now = base_time or datetime.now(timezone.utc)
    tz_name = schedule_config.get("timezone", "Asia/Shanghai")

    if schedule_type == "at":
        at_str = schedule_config.get("at")
        if not at_str:
            return None
        from datetime import datetime as dt
        target = dt.fromisoformat(at_str)
        if target.tzinfo is None:
            import zoneinfo
            target = target.replace(tzinfo=zoneinfo.ZoneInfo(tz_name))
        return target if target > now else None

    if schedule_type == "interval":
        seconds = schedule_config.get("seconds")
        if not seconds or seconds <= 0:
            return None
        return now + timedelta(seconds=seconds)

    if schedule_type == "cron":
        cron_expr = schedule_config.get("cron_expr")
        if not cron_expr:
            return None
        import zoneinfo
        tz = zoneinfo.ZoneInfo(tz_name)
        local_now = now.astimezone(tz)
        cron = croniter(cron_expr, local_now)
        next_local = cron.get_next(datetime)
        return next_local.astimezone(timezone.utc)

    return None


class SchedulerService:
    """轻量级异步定时任务调度器

    - 使用 asyncio 后台任务轮询 DB 中到期的任务
    - 使用 croniter 解析 cron 表达式
    - 通过 job_executor 执行到期任务
    """

    def __init__(self, max_concurrent: int = 3, job_timeout: int = 120):
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._max_concurrent = max_concurrent
        self._job_timeout = job_timeout
        self._running_jobs: set[uuid.UUID] = set()
        self._executor = None  # 延迟导入避免循环引用

    def _get_executor(self):
        if self._executor is None:
            from app.services.job_executor import JobExecutor
            self._executor = JobExecutor(timeout_seconds=self._job_timeout)
        return self._executor

    async def start(self):
        """启动调度器后台任务"""
        logger.info("定时任务调度器启动")
        self._table_missing = False
        await self._sync_all_next_run_at()
        if self._table_missing:
            logger.warning("调度器因表缺失而跳过启动，调度功能不可用")
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        """优雅停止调度器"""
        logger.info("定时任务调度器停止中...")
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("定时任务调度器已停止")

    async def _sync_all_next_run_at(self):
        """启动时为所有已启用且 next_run_at 为空的任务计算下次运行时间"""
        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(ScheduledJob).where(
                        ScheduledJob.enabled.is_(True),
                        ScheduledJob.next_run_at.is_(None),
                    )
                )
                jobs = result.scalars().all()
                for job in jobs:
                    next_at = compute_next_run_at(job.schedule_type, job.schedule_config)
                    if next_at:
                        job.next_run_at = next_at
                await db.commit()
                if jobs:
                    logger.info("已为 %d 个任务初始化 next_run_at", len(jobs))
        except Exception as e:
            if _is_missing_table_error(e):
                logger.warning("scheduled_jobs 表不存在，请运行 alembic upgrade head")
                self._table_missing = True
                return
            logger.exception("初始化 next_run_at 失败")

    async def _poll_loop(self):
        """后台轮询循环 — 每 POLL_INTERVAL_SECONDS 检查到期任务"""
        while not self._stop_event.is_set():
            try:
                await self._check_and_run_due_jobs()
            except Exception as e:
                if _is_missing_table_error(e):
                    logger.warning("scheduled_jobs 表不存在，调度器停止轮询")
                    return
                logger.exception("调度循环异常")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=POLL_INTERVAL_SECONDS,
                )
                break
            except asyncio.TimeoutError:
                pass

    async def _check_and_run_due_jobs(self):
        """查询到期任务并并发执行（受 max_concurrent 限制）"""
        now = datetime.now(timezone.utc)
        async with async_session_factory() as db:
            result = await db.execute(
                select(ScheduledJob).where(
                    ScheduledJob.enabled.is_(True),
                    ScheduledJob.next_run_at.isnot(None),
                    ScheduledJob.next_run_at <= now,
                ).order_by(ScheduledJob.next_run_at.asc())
            )
            due_jobs = result.scalars().all()

        tasks = []
        for job in due_jobs:
            if job.id in self._running_jobs:
                continue
            if len(self._running_jobs) >= self._max_concurrent:
                break
            self._running_jobs.add(job.id)
            tasks.append(asyncio.create_task(self._execute_job_wrapper(job.id)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_job_wrapper(self, job_id: uuid.UUID):
        """包装执行单个任务：记录 run、更新状态、处理错误"""
        run_id = uuid.uuid4()
        started_at = datetime.now(timezone.utc)

        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(ScheduledJob).where(ScheduledJob.id == job_id)
                )
                job = result.scalar_one_or_none()
                if not job or not job.enabled:
                    return

                run = ScheduledJobRun(
                    id=run_id,
                    job_id=job_id,
                    started_at=started_at,
                    status="running",
                )
                db.add(run)
                await db.commit()

            executor = self._get_executor()
            ai_response = await asyncio.wait_for(
                executor.execute(job_id),
                timeout=self._job_timeout,
            )

            finished_at = datetime.now(timezone.utc)
            duration_ms = int((finished_at - started_at).total_seconds() * 1000)
            summary = (ai_response or "")[:500]

            async with async_session_factory() as db:
                await db.execute(
                    update(ScheduledJobRun)
                    .where(ScheduledJobRun.id == run_id)
                    .values(
                        finished_at=finished_at,
                        status="ok",
                        result_summary=summary,
                        duration_ms=duration_ms,
                    )
                )
                await db.execute(
                    update(ScheduledJob)
                    .where(ScheduledJob.id == job_id)
                    .values(
                        last_run_at=finished_at,
                        last_run_status="ok",
                        last_error=None,
                        last_result_summary=summary,
                        consecutive_errors=0,
                        run_count=ScheduledJob.run_count + 1,
                        next_run_at=self._compute_next(job_id, db),
                    )
                )
                await db.commit()

                await self._post_run_cleanup(db, job_id)

        except asyncio.TimeoutError:
            await self._mark_job_error(job_id, run_id, started_at, "执行超时")
        except Exception as e:
            await self._mark_job_error(job_id, run_id, started_at, str(e))
        finally:
            self._running_jobs.discard(job_id)

    async def _mark_job_error(
        self,
        job_id: uuid.UUID,
        run_id: uuid.UUID,
        started_at: datetime,
        error_msg: str,
    ):
        """标记任务执行失败并应用退避策略"""
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        logger.error("定时任务 %s 执行失败: %s", job_id, error_msg)

        try:
            async with async_session_factory() as db:
                await db.execute(
                    update(ScheduledJobRun)
                    .where(ScheduledJobRun.id == run_id)
                    .values(
                        finished_at=finished_at,
                        status="error",
                        error=error_msg[:2000],
                        duration_ms=duration_ms,
                    )
                )

                result = await db.execute(
                    select(ScheduledJob).where(ScheduledJob.id == job_id)
                )
                job = result.scalar_one_or_none()
                if not job:
                    await db.commit()
                    return

                new_errors = job.consecutive_errors + 1
                updates: dict = {
                    "last_run_at": finished_at,
                    "last_run_status": "error",
                    "last_error": error_msg[:2000],
                    "consecutive_errors": new_errors,
                    "run_count": ScheduledJob.run_count + 1,
                }

                from app.config import settings
                max_errors = settings.scheduler_max_consecutive_errors
                if new_errors >= max_errors:
                    updates["enabled"] = False
                    updates["next_run_at"] = None
                    logger.warning("任务 %s 连续失败 %d 次，已自动禁用", job_id, new_errors)
                else:
                    backoff = min(
                        60 * (2 ** (new_errors - 1)),
                        MAX_BACKOFF_SECONDS,
                    )
                    updates["next_run_at"] = finished_at + timedelta(seconds=backoff)

                await db.execute(
                    update(ScheduledJob).where(ScheduledJob.id == job_id).values(**updates)
                )
                await db.commit()
        except Exception:
            logger.exception("更新任务错误状态失败 job_id=%s", job_id)

    async def _post_run_cleanup(self, db: AsyncSession, job_id: uuid.UUID):
        """执行后处理：one-shot 删除、计算下次运行时间"""
        result = await db.execute(
            select(ScheduledJob).where(ScheduledJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            return

        if job.schedule_type == "at" and job.delete_after_run:
            job.enabled = False
            job.next_run_at = None
        else:
            next_at = compute_next_run_at(job.schedule_type, job.schedule_config)
            job.next_run_at = next_at

        await db.commit()

    def _compute_next(self, job_id: uuid.UUID, db: AsyncSession):
        """占位 — 实际计算在 _post_run_cleanup 中完成，此处返回 None"""
        return None

    # ---- CRUD 支持（供 tool 和 API 调用）----

    async def add_job(
        self,
        user_id: uuid.UUID,
        bot_id: uuid.UUID | None,
        conversation_id: uuid.UUID | None,
        name: str,
        description: str | None,
        schedule_type: str,
        schedule_config: dict,
        payload_message: str,
        payload_config: dict | None = None,
        delivery_mode: str = "chat",
        delivery_config: dict | None = None,
        delete_after_run: bool = False,
    ) -> ScheduledJob:
        """创建定时任务"""
        next_at = compute_next_run_at(schedule_type, schedule_config)

        async with async_session_factory() as db:
            job = ScheduledJob(
                user_id=user_id,
                bot_id=bot_id,
                conversation_id=conversation_id,
                name=name,
                description=description,
                schedule_type=schedule_type,
                schedule_config=schedule_config,
                payload_message=payload_message,
                payload_config=payload_config,
                delivery_mode=delivery_mode,
                delivery_config=delivery_config,
                delete_after_run=delete_after_run,
                next_run_at=next_at,
                enabled=True,
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)
            logger.info("创建定时任务 %s (%s), 下次运行: %s", job.id, name, next_at)
            return job

    async def update_job(
        self,
        job_id: uuid.UUID,
        user_id: uuid.UUID,
        **kwargs,
    ) -> ScheduledJob | None:
        """更新定时任务（仅允许修改自己的任务）"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(ScheduledJob).where(
                    ScheduledJob.id == job_id,
                    ScheduledJob.user_id == user_id,
                )
            )
            job = result.scalar_one_or_none()
            if not job:
                return None

            schedule_changed = False
            for key, value in kwargs.items():
                if value is not None and hasattr(job, key):
                    setattr(job, key, value)
                    if key in ("schedule_type", "schedule_config"):
                        schedule_changed = True

            if schedule_changed:
                job.next_run_at = compute_next_run_at(
                    job.schedule_type, job.schedule_config
                )
                job.consecutive_errors = 0

            await db.commit()
            await db.refresh(job)
            return job

    async def remove_job(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """删除定时任务"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(ScheduledJob).where(
                    ScheduledJob.id == job_id,
                    ScheduledJob.user_id == user_id,
                )
            )
            job = result.scalar_one_or_none()
            if not job:
                return False
            await db.delete(job)
            await db.commit()
            logger.info("删除定时任务 %s", job_id)
            return True

    async def list_jobs(
        self, user_id: uuid.UUID, include_disabled: bool = False
    ) -> list[ScheduledJob]:
        """列出用户的定时任务"""
        async with async_session_factory() as db:
            query = select(ScheduledJob).where(ScheduledJob.user_id == user_id)
            if not include_disabled:
                query = query.where(ScheduledJob.enabled.is_(True))
            query = query.order_by(ScheduledJob.created_at.desc())
            result = await db.execute(query)
            return list(result.scalars().all())

    async def get_job(
        self, job_id: uuid.UUID, user_id: uuid.UUID
    ) -> ScheduledJob | None:
        """获取单个任务详情"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(ScheduledJob).where(
                    ScheduledJob.id == job_id,
                    ScheduledJob.user_id == user_id,
                )
            )
            return result.scalar_one_or_none()

    async def run_now(self, job_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """手动触发任务（设置 next_run_at 为 now）"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(ScheduledJob).where(
                    ScheduledJob.id == job_id,
                    ScheduledJob.user_id == user_id,
                )
            )
            job = result.scalar_one_or_none()
            if not job:
                return False

            job.next_run_at = datetime.now(timezone.utc)
            job.enabled = True
            await db.commit()
            return True

    async def get_job_runs(
        self, job_id: uuid.UUID, limit: int = 20
    ) -> list[ScheduledJobRun]:
        """获取任务执行历史"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(ScheduledJobRun)
                .where(ScheduledJobRun.job_id == job_id)
                .order_by(ScheduledJobRun.started_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
