"""飞书工具集测试

验证工具注册逻辑、条件注册、action 分发。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestFeishuToolsRegistration:
    """工具注册测试"""

    @patch("app.tools.feishu_tools.settings")
    def test_returns_empty_without_credentials(self, mock_settings):
        mock_settings.feishu_app_id = ""
        mock_settings.feishu_app_secret = ""
        from app.tools.feishu_tools import create_feishu_tools
        tools = create_feishu_tools(None, "user1")
        assert tools == []

    @patch("app.tools.feishu_tools.settings")
    def test_registers_all_tools_by_default(self, mock_settings):
        mock_settings.feishu_app_id = "test_id"
        mock_settings.feishu_app_secret = "test_secret"
        mock_settings.feishu_tools_doc = True
        mock_settings.feishu_tools_wiki = True
        mock_settings.feishu_tools_drive = True
        mock_settings.feishu_tools_chat = True
        mock_settings.feishu_tools_bitable = True
        mock_settings.feishu_tools_perm = False
        mock_settings.feishu_tools_calendar = True
        mock_settings.feishu_tools_task = True

        from app.tools.feishu_tools import create_feishu_tools
        tools = create_feishu_tools(None, "user1")

        tool_names = {t.name for t in tools}
        assert "feishu_doc" in tool_names
        assert "feishu_wiki" in tool_names
        assert "feishu_drive" in tool_names
        assert "feishu_chat" in tool_names
        assert "feishu_message" in tool_names
        assert "feishu_calendar_list" in tool_names
        assert "feishu_calendar_create" in tool_names
        assert "feishu_task_list" in tool_names
        assert "feishu_task_create" in tool_names
        assert "feishu_perm" not in tool_names

        assert "feishu_bitable_get_meta" in tool_names
        assert "feishu_bitable_list_fields" in tool_names
        assert "feishu_bitable_list_records" in tool_names
        assert "feishu_bitable_get_record" in tool_names
        assert "feishu_bitable_create_record" in tool_names
        assert "feishu_bitable_update_record" in tool_names
        assert "feishu_bitable_create_app" in tool_names
        assert "feishu_bitable_create_field" in tool_names

    @patch("app.tools.feishu_tools.settings")
    def test_perm_enabled_when_configured(self, mock_settings):
        mock_settings.feishu_app_id = "test_id"
        mock_settings.feishu_app_secret = "test_secret"
        mock_settings.feishu_tools_doc = False
        mock_settings.feishu_tools_wiki = False
        mock_settings.feishu_tools_drive = False
        mock_settings.feishu_tools_chat = False
        mock_settings.feishu_tools_bitable = False
        mock_settings.feishu_tools_perm = True
        mock_settings.feishu_tools_calendar = False
        mock_settings.feishu_tools_task = False

        from app.tools.feishu_tools import create_feishu_tools
        tools = create_feishu_tools(None, "user1")

        tool_names = {t.name for t in tools}
        assert "feishu_perm" in tool_names
        assert "feishu_auth" in tool_names
        assert len(tools) == 2

    @patch("app.tools.feishu_tools.settings")
    def test_tool_count_all_enabled(self, mock_settings):
        mock_settings.feishu_app_id = "test_id"
        mock_settings.feishu_app_secret = "test_secret"
        mock_settings.feishu_tools_doc = True
        mock_settings.feishu_tools_wiki = True
        mock_settings.feishu_tools_drive = True
        mock_settings.feishu_tools_chat = True
        mock_settings.feishu_tools_bitable = True
        mock_settings.feishu_tools_perm = True
        mock_settings.feishu_tools_calendar = True
        mock_settings.feishu_tools_task = True

        from app.tools.feishu_tools import create_feishu_tools
        tools = create_feishu_tools(None, "user1")

        # auth(1) + doc(1) + wiki(1) + drive(1) + chat(2) + bitable(8) + perm(1) + cal(2) + task(2) = 19
        assert len(tools) == 19


class TestDocTool:
    """feishu_doc 工具 action 分发测试"""

    @patch("app.tools.feishu_tools.settings")
    def test_doc_tool_has_correct_description(self, mock_settings):
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

        from app.tools.feishu_tools import create_feishu_tools
        tools = create_feishu_tools(None, "user1")
        doc_tool = next(t for t in tools if t.name == "feishu_doc")
        assert doc_tool.name == "feishu_doc"
        assert "read" in doc_tool.description
        assert "write" in doc_tool.description
        assert "create_table" in doc_tool.description


class TestBitableURLParsing:
    """多维表格 URL 解析测试"""

    def test_parse_base_url(self):
        from app.services.feishu_bitable_service import parse_bitable_url
        result = parse_bitable_url("https://xxx.feishu.cn/base/ABC123?table=tbl456")
        assert result is not None
        assert result["token"] == "ABC123"
        assert result["table_id"] == "tbl456"
        assert result["is_wiki"] is False

    def test_parse_wiki_url(self):
        from app.services.feishu_bitable_service import parse_bitable_url
        result = parse_bitable_url("https://xxx.feishu.cn/wiki/XYZ789?table=tblABC")
        assert result is not None
        assert result["token"] == "XYZ789"
        assert result["table_id"] == "tblABC"
        assert result["is_wiki"] is True

    def test_parse_url_without_table_id(self):
        from app.services.feishu_bitable_service import parse_bitable_url
        result = parse_bitable_url("https://xxx.feishu.cn/base/ABC123")
        assert result is not None
        assert result["token"] == "ABC123"
        assert result["table_id"] is None

    def test_parse_invalid_url(self):
        from app.services.feishu_bitable_service import parse_bitable_url
        result = parse_bitable_url("https://xxx.feishu.cn/docx/ABC123")
        assert result is None


class TestMarkdownToBlocks:
    """Markdown → 飞书块转换测试"""

    def test_heading_conversion(self):
        from app.services.feishu_doc_service import _markdown_to_blocks
        blocks = _markdown_to_blocks("# Title\n## Subtitle")
        assert len(blocks) == 2
        assert blocks[0]["block_type"] == 3
        assert blocks[1]["block_type"] == 4

    def test_bullet_list(self):
        from app.services.feishu_doc_service import _markdown_to_blocks
        blocks = _markdown_to_blocks("- item1\n- item2")
        assert len(blocks) == 2
        assert blocks[0]["block_type"] == 12
        assert blocks[1]["block_type"] == 12

    def test_ordered_list(self):
        from app.services.feishu_doc_service import _markdown_to_blocks
        blocks = _markdown_to_blocks("1. first\n2. second")
        assert len(blocks) == 2
        assert blocks[0]["block_type"] == 13

    def test_code_block(self):
        from app.services.feishu_doc_service import _markdown_to_blocks
        blocks = _markdown_to_blocks("```python\nprint('hi')\n```")
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 14
        assert "code" in blocks[0]

    def test_divider(self):
        from app.services.feishu_doc_service import _markdown_to_blocks
        blocks = _markdown_to_blocks("---")
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 22

    def test_quote(self):
        from app.services.feishu_doc_service import _markdown_to_blocks
        blocks = _markdown_to_blocks("> quote text")
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 15

    def test_todo(self):
        from app.services.feishu_doc_service import _markdown_to_blocks
        blocks = _markdown_to_blocks("- [ ] unchecked\n- [x] checked")
        assert len(blocks) == 2
        assert blocks[0]["block_type"] == 17
        assert blocks[0]["todo"]["style"]["done"] is False
        assert blocks[1]["todo"]["style"]["done"] is True

    def test_plain_text(self):
        from app.services.feishu_doc_service import _markdown_to_blocks
        blocks = _markdown_to_blocks("Hello World")
        assert len(blocks) == 1
        assert blocks[0]["block_type"] == 2

    def test_empty_lines_skipped(self):
        from app.services.feishu_doc_service import _markdown_to_blocks
        blocks = _markdown_to_blocks("line1\n\nline2")
        assert len(blocks) == 2

    def test_inline_bold(self):
        from app.services.feishu_doc_service import _parse_inline_elements
        elements = _parse_inline_elements("hello **bold** world")
        assert len(elements) == 3
        assert elements[1]["text_run"]["text_element_style"]["bold"] is True

    def test_inline_link(self):
        from app.services.feishu_doc_service import _parse_inline_elements
        elements = _parse_inline_elements("[click](https://example.com)")
        assert len(elements) == 1
        assert "link" in elements[0]["text_run"]["text_element_style"]


class TestFieldTypeNames:
    """字段类型名称映射测试"""

    def test_common_types(self):
        from app.services.feishu_bitable_service import FIELD_TYPE_NAMES
        assert FIELD_TYPE_NAMES[1] == "Text"
        assert FIELD_TYPE_NAMES[2] == "Number"
        assert FIELD_TYPE_NAMES[3] == "SingleSelect"
        assert FIELD_TYPE_NAMES[5] == "DateTime"
        assert FIELD_TYPE_NAMES[7] == "Checkbox"

    def test_system_types(self):
        from app.services.feishu_bitable_service import FIELD_TYPE_NAMES
        assert FIELD_TYPE_NAMES[1001] == "CreatedTime"
        assert FIELD_TYPE_NAMES[1005] == "AutoNumber"
