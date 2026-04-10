"""schedule_task 工具测试

验证:
- 工具创建和 schema
- 各 action 的行为
- schedule_config 构建逻辑
- 错误处理
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.schedule_tools import (
    _build_schedule_config,
    _format_schedule,
    create_schedule_tools,
    set_scheduler_service,
)


class TestBuildScheduleConfig:
    """schedule_config 构建逻辑"""

    def test_at_valid(self):
        config = _build_schedule_config("at", "2026-04-07T09:00:00+08:00", "Asia/Shanghai")
        assert config is not None
        assert config["at"] == "2026-04-07T09:00:00+08:00"
        assert config["timezone"] == "Asia/Shanghai"

    def test_at_invalid_timestamp(self):
        config = _build_schedule_config("at", "not-a-date", "UTC")
        assert config is None

    def test_interval_valid(self):
        config = _build_schedule_config("interval", "3600", "UTC")
        assert config is not None
        assert config["seconds"] == 3600

    def test_interval_invalid_string(self):
        config = _build_schedule_config("interval", "abc", "UTC")
        assert config is None

    def test_interval_zero(self):
        config = _build_schedule_config("interval", "0", "UTC")
        assert config is None

    def test_interval_negative(self):
        config = _build_schedule_config("interval", "-100", "UTC")
        assert config is None

    def test_cron_valid(self):
        config = _build_schedule_config("cron", "0 9 * * 1-5", "Asia/Shanghai")
        assert config is not None
        assert config["cron_expr"] == "0 9 * * 1-5"

    def test_cron_invalid(self):
        config = _build_schedule_config("cron", "not a cron", "UTC")
        assert config is None

    def test_unknown_type(self):
        config = _build_schedule_config("unknown", "value", "UTC")
        assert config is None


class TestFormatSchedule:
    """调度配置格式化"""

    def test_at_format(self):
        result = _format_schedule("at", {"at": "2026-04-07T09:00:00+08:00", "timezone": "CST"})
        assert "一次性" in result

    def test_interval_hours(self):
        result = _format_schedule("interval", {"seconds": 7200})
        assert "2 小时" in result

    def test_interval_minutes(self):
        result = _format_schedule("interval", {"seconds": 300})
        assert "5 分钟" in result

    def test_interval_seconds(self):
        result = _format_schedule("interval", {"seconds": 30})
        assert "30 秒" in result

    def test_cron_format(self):
        result = _format_schedule("cron", {"cron_expr": "0 9 * * *", "timezone": "UTC"})
        assert "cron" in result
        assert "0 9 * * *" in result


class TestCreateScheduleTools:
    """工具创建和基本行为"""

    def test_creates_one_tool(self):
        tools = create_schedule_tools("user-id", "bot-id")
        assert len(tools) == 1
        assert tools[0].name == "schedule_task"

    def test_tool_has_description(self):
        tools = create_schedule_tools("user-id", "bot-id")
        assert "定时任务" in tools[0].description


class TestScheduleTaskActions:
    """schedule_task 各 action 的行为"""

    @pytest.fixture(autouse=True)
    def setup_mock_scheduler(self):
        self.mock_scheduler = MagicMock()
        set_scheduler_service(self.mock_scheduler)
        yield
        set_scheduler_service(None)

    @pytest.fixture
    def tool(self):
        tools = create_schedule_tools(str(uuid.uuid4()), str(uuid.uuid4()))
        return tools[0]

    @pytest.mark.asyncio
    async def test_list_empty(self, tool):
        self.mock_scheduler.list_jobs = AsyncMock(return_value=[])
        result = await tool.ainvoke({"action": "list"})
        assert "还没有" in result

    @pytest.mark.asyncio
    async def test_list_with_jobs(self, tool):
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.name = "Daily Report"
        mock_job.enabled = True
        mock_job.schedule_type = "cron"
        mock_job.schedule_config = {"cron_expr": "0 9 * * *", "timezone": "UTC"}
        mock_job.next_run_at = "2026-04-07T09:00:00+00:00"
        mock_job.run_count = 5

        self.mock_scheduler.list_jobs = AsyncMock(return_value=[mock_job])
        result = await tool.ainvoke({"action": "list"})
        assert "Daily Report" in result
        assert "1 个" in result

    @pytest.mark.asyncio
    async def test_add_missing_name(self, tool):
        result = await tool.ainvoke({
            "action": "add",
            "schedule_type": "cron",
            "schedule_value": "0 9 * * *",
            "message": "test",
        })
        assert "名称" in result

    @pytest.mark.asyncio
    async def test_add_missing_schedule_type(self, tool):
        result = await tool.ainvoke({
            "action": "add",
            "name": "Test",
            "schedule_value": "0 9 * * *",
            "message": "test",
        })
        assert "schedule_type" in result

    @pytest.mark.asyncio
    async def test_add_missing_message(self, tool):
        result = await tool.ainvoke({
            "action": "add",
            "name": "Test",
            "schedule_type": "cron",
            "schedule_value": "0 9 * * *",
        })
        assert "message" in result

    @pytest.mark.asyncio
    async def test_add_success(self, tool):
        mock_job = MagicMock()
        mock_job.id = uuid.uuid4()
        mock_job.name = "My Task"
        mock_job.schedule_type = "cron"
        mock_job.schedule_config = {"cron_expr": "0 9 * * *", "timezone": "Asia/Shanghai"}
        mock_job.next_run_at = "2026-04-07T09:00:00+08:00"
        mock_job.delivery_mode = "chat"

        self.mock_scheduler.add_job = AsyncMock(return_value=mock_job)
        result = await tool.ainvoke({
            "action": "add",
            "name": "My Task",
            "schedule_type": "cron",
            "schedule_value": "0 9 * * *",
            "message": "请分析竞品数据",
        })
        assert "已创建" in result
        assert "My Task" in result

    @pytest.mark.asyncio
    async def test_remove_missing_id(self, tool):
        result = await tool.ainvoke({"action": "remove"})
        assert "ID" in result

    @pytest.mark.asyncio
    async def test_remove_success(self, tool):
        job_id = str(uuid.uuid4())
        self.mock_scheduler.remove_job = AsyncMock(return_value=True)
        result = await tool.ainvoke({"action": "remove", "job_id": job_id})
        assert "已删除" in result

    @pytest.mark.asyncio
    async def test_run_now_success(self, tool):
        job_id = str(uuid.uuid4())
        self.mock_scheduler.run_now = AsyncMock(return_value=True)
        result = await tool.ainvoke({"action": "run_now", "job_id": job_id})
        assert "立即执行" in result

    @pytest.mark.asyncio
    async def test_no_scheduler_service(self):
        set_scheduler_service(None)
        tools = create_schedule_tools(str(uuid.uuid4()), str(uuid.uuid4()))
        result = await tools[0].ainvoke({"action": "list"})
        assert "未启动" in result
