"""SchedulerService 单元测试

验证:
- compute_next_run_at 各调度类型的计算逻辑
- SchedulerService CRUD 操作
- 调度循环的到期检测
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.scheduler_service import compute_next_run_at


class TestComputeNextRunAt:
    """compute_next_run_at 计算下一次运行时间"""

    def test_at_future_time(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        config = {"at": future, "timezone": "UTC"}
        result = compute_next_run_at("at", config)
        assert result is not None
        assert result > datetime.now(timezone.utc)

    def test_at_past_time_returns_none(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        config = {"at": past, "timezone": "UTC"}
        result = compute_next_run_at("at", config)
        assert result is None

    def test_at_missing_value_returns_none(self):
        result = compute_next_run_at("at", {"timezone": "UTC"})
        assert result is None

    def test_interval_seconds(self):
        config = {"seconds": 3600, "timezone": "UTC"}
        now = datetime.now(timezone.utc)
        result = compute_next_run_at("interval", config, base_time=now)
        assert result is not None
        diff = (result - now).total_seconds()
        assert 3599 <= diff <= 3601

    def test_interval_zero_returns_none(self):
        result = compute_next_run_at("interval", {"seconds": 0})
        assert result is None

    def test_interval_negative_returns_none(self):
        result = compute_next_run_at("interval", {"seconds": -100})
        assert result is None

    def test_interval_missing_returns_none(self):
        result = compute_next_run_at("interval", {})
        assert result is None

    def test_cron_expression(self):
        config = {"cron_expr": "0 9 * * *", "timezone": "UTC"}
        result = compute_next_run_at("cron", config)
        assert result is not None
        assert result > datetime.now(timezone.utc)

    def test_cron_with_timezone(self):
        config = {"cron_expr": "0 9 * * *", "timezone": "Asia/Shanghai"}
        result = compute_next_run_at("cron", config)
        assert result is not None

    def test_cron_missing_expr_returns_none(self):
        result = compute_next_run_at("cron", {"timezone": "UTC"})
        assert result is None

    def test_unknown_type_returns_none(self):
        result = compute_next_run_at("unknown", {})
        assert result is None


class TestSchedulerServiceCRUD:
    """SchedulerService 的 CRUD 操作（mock DB）"""

    @pytest.fixture
    def mock_job(self):
        job = MagicMock()
        job.id = uuid.uuid4()
        job.user_id = uuid.uuid4()
        job.name = "test-job"
        job.enabled = True
        job.schedule_type = "interval"
        job.schedule_config = {"seconds": 3600}
        job.next_run_at = datetime.now(timezone.utc) + timedelta(hours=1)
        job.run_count = 0
        job.consecutive_errors = 0
        return job

    @pytest.mark.asyncio
    async def test_add_job(self):
        """验证 add_job 创建任务并计算 next_run_at"""
        from app.services.scheduler_service import SchedulerService

        user_id = uuid.uuid4()

        with patch("app.services.scheduler_service.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_job = MagicMock()
            mock_job.id = uuid.uuid4()
            mock_job.name = "Daily Report"
            mock_job.next_run_at = datetime.now(timezone.utc) + timedelta(hours=1)
            mock_session.refresh = AsyncMock(return_value=None)

            service = SchedulerService()

            # patch the session to capture the added job
            added_objects = []
            mock_session.add = lambda obj: added_objects.append(obj)

            job = await service.add_job(
                user_id=user_id,
                bot_id=None,
                conversation_id=None,
                name="Daily Report",
                description="Daily competitor analysis",
                schedule_type="cron",
                schedule_config={"cron_expr": "0 9 * * *", "timezone": "UTC"},
                payload_message="分析今天的竞品数据",
            )

            assert len(added_objects) == 1
            created = added_objects[0]
            assert created.name == "Daily Report"
            assert created.schedule_type == "cron"
            assert created.next_run_at is not None
            mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_jobs(self, mock_job):
        """验证 list_jobs 返回用户的任务列表"""
        from app.services.scheduler_service import SchedulerService

        with patch("app.services.scheduler_service.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_job]
            mock_session.execute = AsyncMock(return_value=mock_result)

            service = SchedulerService()
            jobs = await service.list_jobs(mock_job.user_id)

            assert len(jobs) == 1
            assert jobs[0].name == "test-job"

    @pytest.mark.asyncio
    async def test_remove_job(self, mock_job):
        """验证 remove_job 删除任务"""
        from app.services.scheduler_service import SchedulerService

        with patch("app.services.scheduler_service.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_job
            mock_session.execute = AsyncMock(return_value=mock_result)

            service = SchedulerService()
            ok = await service.remove_job(mock_job.id, mock_job.user_id)

            assert ok is True
            mock_session.delete.assert_awaited_once_with(mock_job)
            mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_remove_nonexistent_job(self):
        """删除不存在的任务返回 False"""
        from app.services.scheduler_service import SchedulerService

        with patch("app.services.scheduler_service.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            service = SchedulerService()
            ok = await service.remove_job(uuid.uuid4(), uuid.uuid4())

            assert ok is False
