"""飞书服务模块综合测试

测试各服务模块的导入、函数签名和纯逻辑（不涉及网络调用）。
"""

from __future__ import annotations

import pytest


class TestFeishuClientModule:
    """feishu_client 模块测试"""

    def test_import(self):
        from app.services.feishu_client import (
            DOMAIN_MAP,
            FEISHU_HTTP_TIMEOUT,
            FEISHU_MEDIA_HTTP_TIMEOUT,
            clear_client_cache,
            get_doc_url_base,
            get_feishu_client,
        )
        assert FEISHU_HTTP_TIMEOUT == 30
        assert FEISHU_MEDIA_HTTP_TIMEOUT == 120
        assert "feishu" in DOMAIN_MAP
        assert "lark" in DOMAIN_MAP


class TestFeishuServiceModule:
    """feishu_service 模块测试"""

    def test_import(self):
        from app.services.feishu_service import (
            extract_document_id,
            get_tenant_token,
            get_user_feishu_token,
            refresh_user_feishu_token,
        )

    def test_extract_document_id_various_formats(self):
        from app.services.feishu_service import extract_document_id
        assert extract_document_id("https://x.feishu.cn/docx/ABC") == "ABC"
        assert extract_document_id("https://x.feishu.cn/wiki/DEF") == "DEF"
        assert extract_document_id("https://x.feishu.cn/base/GHI") == "GHI"
        assert extract_document_id("https://x.feishu.cn/sheets/JKL") == "JKL"
        assert extract_document_id("https://x.feishu.cn/bitable/MNO") == "MNO"
        assert extract_document_id("PLAINTOKEN") == "PLAINTOKEN"
        assert extract_document_id("https://x.feishu.cn/docx/ABC?query=1") == "ABC"


class TestDocServiceModule:
    """feishu_doc_service 模块测试"""

    def test_import(self):
        from app.services.feishu_doc_service import (
            append_doc,
            create_doc,
            create_table,
            create_table_with_values,
            delete_block,
            get_block,
            insert_doc,
            list_blocks,
            read_doc,
            update_block,
            upload_file,
            upload_image,
            write_doc,
            write_table_cells,
        )


class TestWikiServiceModule:
    """feishu_wiki_service 模块测试"""

    def test_import(self):
        from app.services.feishu_wiki_service import (
            create_node,
            get_node,
            list_nodes,
            list_spaces,
            move_node,
            rename_node,
        )


class TestDriveServiceModule:
    """feishu_drive_service 模块测试"""

    def test_import(self):
        from app.services.feishu_drive_service import (
            add_comment,
            create_folder,
            delete_file,
            get_file_info,
            list_comments,
            list_files,
            move_file,
            reply_comment,
        )


class TestChatServiceModule:
    """feishu_chat_service 模块测试"""

    def test_import(self):
        from app.services.feishu_chat_service import (
            get_chat_info,
            get_chat_members,
            get_member_info,
            send_card,
            send_message,
        )


class TestBitableServiceModule:
    """feishu_bitable_service 模块测试"""

    def test_import(self):
        from app.services.feishu_bitable_service import (
            create_bitable_app,
            create_field,
            create_record,
            get_bitable_meta,
            get_record,
            list_fields,
            list_records,
            parse_bitable_url,
            update_record,
        )

    def test_parse_bitable_url_base(self):
        from app.services.feishu_bitable_service import parse_bitable_url
        r = parse_bitable_url("https://x.feishu.cn/base/APP123?table=tbl456")
        assert r["token"] == "APP123"
        assert r["table_id"] == "tbl456"
        assert r["is_wiki"] is False

    def test_parse_bitable_url_wiki(self):
        from app.services.feishu_bitable_service import parse_bitable_url
        r = parse_bitable_url("https://x.feishu.cn/wiki/NODE789?table=tblABC")
        assert r["token"] == "NODE789"
        assert r["is_wiki"] is True

    def test_parse_bitable_url_no_table(self):
        from app.services.feishu_bitable_service import parse_bitable_url
        r = parse_bitable_url("https://x.feishu.cn/base/APP123")
        assert r["token"] == "APP123"
        assert r["table_id"] is None

    def test_parse_bitable_url_invalid(self):
        from app.services.feishu_bitable_service import parse_bitable_url
        assert parse_bitable_url("not-a-url") is None
        assert parse_bitable_url("https://x.feishu.cn/docx/ABC") is None

    def test_field_type_names(self):
        from app.services.feishu_bitable_service import FIELD_TYPE_NAMES
        assert FIELD_TYPE_NAMES[1] == "Text"
        assert FIELD_TYPE_NAMES[2] == "Number"
        assert FIELD_TYPE_NAMES[1005] == "AutoNumber"


class TestPermServiceModule:
    """feishu_perm_service 模块测试"""

    def test_import(self):
        from app.services.feishu_perm_service import (
            add_member,
            list_members,
            remove_member,
        )


class TestCalendarServiceModule:
    """feishu_calendar_service 模块测试"""

    def test_import(self):
        from app.services.feishu_calendar_service import (
            create_event,
            get_calendar_list,
            list_events,
        )


class TestTaskServiceModule:
    """feishu_task_service 模块测试"""

    def test_import(self):
        from app.services.feishu_task_service import (
            create_task,
            list_tasks,
        )
