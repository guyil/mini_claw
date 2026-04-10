"""测试飞书工具 user token 传递路径"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.feishu_tools import create_feishu_tools


@pytest.fixture
def mock_db():
    return AsyncMock()


class TestFeishuToolsWithDB:
    """验证工具创建和 token 传递"""

    @patch("app.tools.feishu_tools.settings")
    def test_create_feishu_tools_accepts_db_param(self, mock_settings, mock_db):
        mock_settings.feishu_app_id = "test_id"
        mock_settings.feishu_app_secret = "test_secret"
        mock_settings.feishu_tools_doc = True
        mock_settings.feishu_tools_wiki = False
        mock_settings.feishu_tools_drive = False
        mock_settings.feishu_tools_chat = False
        mock_settings.feishu_tools_bitable = False
        mock_settings.feishu_tools_perm = False
        mock_settings.feishu_tools_calendar = False
        mock_settings.feishu_tools_task = False

        tools = create_feishu_tools(mock_db, "test-user-id")
        names = [t.name for t in tools]
        assert "feishu_doc" in names

    @patch("app.tools.feishu_tools.settings")
    def test_create_feishu_tools_accepts_none_db(self, mock_settings):
        mock_settings.feishu_app_id = "test_id"
        mock_settings.feishu_app_secret = "test_secret"
        mock_settings.feishu_tools_doc = True
        mock_settings.feishu_tools_wiki = False
        mock_settings.feishu_tools_drive = False
        mock_settings.feishu_tools_chat = False
        mock_settings.feishu_tools_bitable = False
        mock_settings.feishu_tools_perm = False
        mock_settings.feishu_tools_calendar = False
        mock_settings.feishu_tools_task = False

        tools = create_feishu_tools(None, "test-user-id")
        names = [t.name for t in tools]
        assert "feishu_doc" in names

    @patch("app.tools.feishu_tools.settings")
    def test_no_tools_without_credentials(self, mock_settings):
        mock_settings.feishu_app_id = ""
        mock_settings.feishu_app_secret = ""
        tools = create_feishu_tools(None, "test-user")
        assert tools == []

    @patch("app.tools.feishu_tools.settings")
    @pytest.mark.asyncio
    async def test_doc_tool_read_action_calls_service(self, mock_settings, mock_db):
        """feishu_doc action=read 调用 doc_svc.read_doc"""
        mock_settings.feishu_app_id = "test_id"
        mock_settings.feishu_app_secret = "test_secret"
        mock_settings.feishu_tools_doc = True
        mock_settings.feishu_tools_wiki = False
        mock_settings.feishu_tools_drive = False
        mock_settings.feishu_tools_chat = False
        mock_settings.feishu_tools_bitable = False
        mock_settings.feishu_tools_perm = False
        mock_settings.feishu_tools_calendar = False
        mock_settings.feishu_tools_task = False

        tools = create_feishu_tools(mock_db, "test-user-id")
        doc_tool = next(t for t in tools if t.name == "feishu_doc")

        with (
            patch("app.tools.feishu_tools.get_user_feishu_token", new_callable=AsyncMock) as mock_get,
            patch("app.services.feishu_doc_service.read_doc", new_callable=AsyncMock) as mock_read,
        ):
            mock_get.return_value = "user-token-123"
            mock_read.return_value = {"content": "文档内容", "doc_token": "abc123"}

            result = await doc_tool.ainvoke({
                "action": "read",
                "doc_token": "https://feishu.cn/docx/abc123",
            })

        mock_get.assert_awaited_once_with(mock_db, "test-user-id")
        assert "文档内容" in result

    @patch("app.tools.feishu_tools.settings")
    @pytest.mark.asyncio
    async def test_doc_tool_create_action_calls_service(self, mock_settings, mock_db):
        """feishu_doc action=create 调用 doc_svc.create_doc"""
        mock_settings.feishu_app_id = "test_id"
        mock_settings.feishu_app_secret = "test_secret"
        mock_settings.feishu_tools_doc = True
        mock_settings.feishu_tools_wiki = False
        mock_settings.feishu_tools_drive = False
        mock_settings.feishu_tools_chat = False
        mock_settings.feishu_tools_bitable = False
        mock_settings.feishu_tools_perm = False
        mock_settings.feishu_tools_calendar = False
        mock_settings.feishu_tools_task = False

        tools = create_feishu_tools(mock_db, "test-user-id")
        doc_tool = next(t for t in tools if t.name == "feishu_doc")

        with (
            patch("app.tools.feishu_tools.get_user_feishu_token", new_callable=AsyncMock) as mock_get,
            patch("app.services.feishu_doc_service.create_doc", new_callable=AsyncMock) as mock_create,
        ):
            mock_get.return_value = "user-token-456"
            mock_create.return_value = {"success": True, "doc_token": "new123", "title": "测试"}

            result = await doc_tool.ainvoke({
                "action": "create",
                "title": "测试文档",
            })

        assert "测试" in result
