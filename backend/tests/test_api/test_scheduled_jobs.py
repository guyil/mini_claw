"""定时任务 API 端点测试

验证:
- CRUD API 调用
- 权限检查
- 请求/响应格式
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_current_user_id
from app.main import app


@pytest.fixture
def mock_user_id():
    return str(uuid.uuid4())


@pytest.fixture
def mock_auth(mock_user_id):
    """Override FastAPI 依赖注入的认证"""
    app.dependency_overrides[get_current_user_id] = lambda: mock_user_id
    yield mock_user_id
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def mock_scheduler():
    scheduler = MagicMock()
    with patch("app.api.scheduled_jobs._get_scheduler", return_value=scheduler):
        yield scheduler


@pytest.fixture
def sample_job():
    job = MagicMock()
    job.id = uuid.uuid4()
    job.user_id = uuid.uuid4()
    job.bot_id = None
    job.conversation_id = None
    job.name = "Daily Report"
    job.description = "每日竞品报告"
    job.enabled = True
    job.delete_after_run = False
    job.schedule_type = "cron"
    job.schedule_config = {"cron_expr": "0 9 * * *", "timezone": "Asia/Shanghai"}
    job.payload_message = "分析竞品数据"
    job.payload_config = None
    job.delivery_mode = "chat"
    job.delivery_config = None
    job.next_run_at = datetime.now(timezone.utc)
    job.last_run_at = None
    job.last_run_status = None
    job.last_error = None
    job.last_result_summary = None
    job.consecutive_errors = 0
    job.run_count = 0
    job.created_at = datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)
    return job


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


class TestListJobs:
    def test_list_empty(self, client, mock_auth, mock_scheduler):
        mock_scheduler.list_jobs = AsyncMock(return_value=[])
        response = client.get("/scheduled-jobs")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_jobs(self, client, mock_auth, mock_scheduler, sample_job):
        mock_scheduler.list_jobs = AsyncMock(return_value=[sample_job])
        response = client.get("/scheduled-jobs")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Daily Report"


class TestGetJob:
    def test_get_existing(self, client, mock_auth, mock_scheduler, sample_job):
        mock_scheduler.get_job = AsyncMock(return_value=sample_job)
        response = client.get(f"/scheduled-jobs/{sample_job.id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Daily Report"

    def test_get_nonexistent(self, client, mock_auth, mock_scheduler):
        mock_scheduler.get_job = AsyncMock(return_value=None)
        response = client.get(f"/scheduled-jobs/{uuid.uuid4()}")
        assert response.status_code == 404


class TestDeleteJob:
    def test_delete_success(self, client, mock_auth, mock_scheduler, sample_job):
        mock_scheduler.remove_job = AsyncMock(return_value=True)
        response = client.delete(f"/scheduled-jobs/{sample_job.id}")
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_delete_nonexistent(self, client, mock_auth, mock_scheduler):
        mock_scheduler.remove_job = AsyncMock(return_value=False)
        response = client.delete(f"/scheduled-jobs/{uuid.uuid4()}")
        assert response.status_code == 404


class TestRunJob:
    def test_run_success(self, client, mock_auth, mock_scheduler, sample_job):
        mock_scheduler.run_now = AsyncMock(return_value=True)
        response = client.post(f"/scheduled-jobs/{sample_job.id}/run")
        assert response.status_code == 200
        assert response.json()["ok"] is True

    def test_run_nonexistent(self, client, mock_auth, mock_scheduler):
        mock_scheduler.run_now = AsyncMock(return_value=False)
        response = client.post(f"/scheduled-jobs/{uuid.uuid4()}/run")
        assert response.status_code == 404


class TestGetJobRuns:
    def test_get_runs(self, client, mock_auth, mock_scheduler, sample_job):
        mock_scheduler.get_job = AsyncMock(return_value=sample_job)

        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()
        mock_run.job_id = sample_job.id
        mock_run.started_at = datetime.now(timezone.utc)
        mock_run.finished_at = datetime.now(timezone.utc)
        mock_run.status = "ok"
        mock_run.error = None
        mock_run.result_summary = "执行成功"
        mock_run.duration_ms = 1500

        mock_scheduler.get_job_runs = AsyncMock(return_value=[mock_run])
        response = client.get(f"/scheduled-jobs/{sample_job.id}/runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "ok"
