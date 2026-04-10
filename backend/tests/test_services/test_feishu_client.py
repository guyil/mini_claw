"""飞书 Client 工厂测试"""

from unittest.mock import MagicMock, patch

import pytest


class TestFeishuClient:
    """feishu_client 模块测试"""

    def setup_method(self):
        from app.services.feishu_client import clear_client_cache
        clear_client_cache()

    @patch("app.services.feishu_client.settings")
    def test_get_feishu_client_creates_client(self, mock_settings):
        mock_settings.feishu_app_id = "test_app_id"
        mock_settings.feishu_app_secret = "test_secret"
        mock_settings.feishu_domain = "feishu"

        from app.services.feishu_client import get_feishu_client
        client = get_feishu_client()
        assert client is not None

    @patch("app.services.feishu_client.settings")
    def test_get_feishu_client_caches(self, mock_settings):
        mock_settings.feishu_app_id = "test_app_id"
        mock_settings.feishu_app_secret = "test_secret"
        mock_settings.feishu_domain = "feishu"

        from app.services.feishu_client import get_feishu_client
        client1 = get_feishu_client()
        client2 = get_feishu_client()
        assert client1 is client2

    @patch("app.services.feishu_client.settings")
    def test_get_feishu_client_raises_without_credentials(self, mock_settings):
        mock_settings.feishu_app_id = ""
        mock_settings.feishu_app_secret = ""

        from app.services.feishu_client import get_feishu_client
        with pytest.raises(RuntimeError, match="未配置"):
            get_feishu_client()

    @patch("app.services.feishu_client.settings")
    def test_clear_client_cache(self, mock_settings):
        mock_settings.feishu_app_id = "test_app_id"
        mock_settings.feishu_app_secret = "test_secret"
        mock_settings.feishu_domain = "feishu"

        from app.services.feishu_client import get_feishu_client, clear_client_cache
        client1 = get_feishu_client()
        clear_client_cache()
        client2 = get_feishu_client()
        assert client1 is not client2

    def test_extract_document_id_from_docx_url(self):
        from app.services.feishu_service import extract_document_id
        assert extract_document_id("https://xxx.feishu.cn/docx/ABC123def") == "ABC123def"

    def test_extract_document_id_from_wiki_url(self):
        from app.services.feishu_service import extract_document_id
        assert extract_document_id("https://xxx.feishu.cn/wiki/ABC123def") == "ABC123def"

    def test_extract_document_id_from_base_url(self):
        from app.services.feishu_service import extract_document_id
        assert extract_document_id("https://xxx.feishu.cn/base/ABC123def") == "ABC123def"

    def test_extract_document_id_from_sheets_url(self):
        from app.services.feishu_service import extract_document_id
        assert extract_document_id("https://xxx.feishu.cn/sheets/ABC123def") == "ABC123def"

    def test_extract_document_id_from_lark_url(self):
        from app.services.feishu_service import extract_document_id
        assert extract_document_id("https://xxx.larksuite.com/docx/XYZ789abc") == "XYZ789abc"

    def test_extract_document_id_plain_token(self):
        from app.services.feishu_service import extract_document_id
        assert extract_document_id("ABC123def") == "ABC123def"

    @patch("app.services.feishu_client.settings")
    def test_get_doc_url_base_feishu(self, mock_settings):
        mock_settings.feishu_domain = "feishu"
        from app.services.feishu_client import get_doc_url_base
        assert "feishu" in get_doc_url_base()

    @patch("app.services.feishu_client.settings")
    def test_get_doc_url_base_lark(self, mock_settings):
        mock_settings.feishu_domain = "lark"
        from app.services.feishu_client import get_doc_url_base
        assert "larksuite" in get_doc_url_base()
