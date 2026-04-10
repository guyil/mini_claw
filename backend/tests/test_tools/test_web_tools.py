"""Web tools 测试 (Crawl4AI 版)

验证 web_fetch 工具使用 Crawl4AI 进行网页抓取，
包括 Amazon 页面结构化提取、通用页面 Markdown 输出、
反爬虫 fallback 以及 CrawlerManager 生命周期管理。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Helper 函数测试 ────────────────────────────────────


class TestAmazonUrlDetection:
    def test_amazon_com(self):
        from app.tools.web_tools import _is_amazon_url

        assert _is_amazon_url("https://www.amazon.com/dp/B08TW57FVR")

    def test_amazon_regional(self):
        from app.tools.web_tools import _is_amazon_url

        assert _is_amazon_url("https://www.amazon.co.uk/dp/B08TW57FVR")
        assert _is_amazon_url("https://www.amazon.de/some-product/dp/B123")
        assert _is_amazon_url("https://www.amazon.co.jp/dp/B456")

    def test_non_amazon(self):
        from app.tools.web_tools import _is_amazon_url

        assert not _is_amazon_url("https://www.google.com")
        assert not _is_amazon_url("https://www.alibaba.com")


class TestAmazonListingExtraction:
    def test_full_listing(self):
        from app.tools.web_tools import _extract_amazon_listing

        html = """
        <html><body>
            <span id="productTitle">Wireless Bluetooth Earbuds Pro Max</span>
            <a id="bylineInfo">Visit the TechBrand Store</a>
            <span class="a-price-symbol">$</span>
            <span class="a-price-whole">39.</span>
            <span class="a-price-fraction">99</span>
            <span data-hook="rating-out-of-text">4.5 out of 5</span>
            <span id="acrCustomerReviewText">12,345 ratings</span>
            <div id="feature-bullets">
                <span class="a-list-item">Active Noise Cancellation</span>
                <span class="a-list-item">40 Hour Battery Life</span>
            </div>
            <div id="wayfinding-breadcrumbs_container">
                <a>Electronics</a><a>Headphones</a><a>Earbuds</a>
            </div>
        </body></html>
        """
        result = _extract_amazon_listing(html)
        assert "Wireless Bluetooth Earbuds Pro Max" in result
        assert "TechBrand" in result
        assert "39" in result and "99" in result
        assert "4.5" in result
        assert "12,345" in result
        assert "Active Noise Cancellation" in result
        assert "Electronics" in result

    def test_empty_html_fallback(self):
        from app.tools.web_tools import _extract_amazon_listing

        result = _extract_amazon_listing("<html><body>Empty</body></html>")
        assert "未能解析" in result


class TestAmazonPageTypeDetection:
    def test_bestseller_url(self):
        from app.tools.web_tools import _detect_amazon_page_type

        assert _detect_amazon_page_type(
            "https://www.amazon.com/gp/bestsellers/hpc/8627079011"
        ) == "bestsellers"

    def test_search_url(self):
        from app.tools.web_tools import _detect_amazon_page_type

        assert _detect_amazon_page_type(
            "https://www.amazon.com/s?k=TENS+unit"
        ) == "search"

    def test_product_url(self):
        from app.tools.web_tools import _detect_amazon_page_type

        assert _detect_amazon_page_type(
            "https://www.amazon.com/dp/B08TW57FVR"
        ) == "product"
        assert _detect_amazon_page_type(
            "https://www.amazon.com/Some-Product/dp/B123/ref=sr_1_1"
        ) == "product"

    def test_other_amazon_url(self):
        from app.tools.web_tools import _detect_amazon_page_type

        assert _detect_amazon_page_type(
            "https://www.amazon.com/stores/BrandPage"
        ) == "other"


class TestAmazonListPageExtraction:
    def test_bestsellers_extraction(self):
        from app.tools.web_tools import _extract_amazon_list_page

        html = """
        <html><body>
            <nav>lots of navigation</nav>
            <div id="gridItemRoot">
                <div class="zg-grid-general-faceout">
                    <span class="zg-bdg-text">#1</span>
                    <a class="a-link-normal" href="/dp/B0AAAA1111/ref=zg_bs">
                        <img alt="Product Alpha" src="img1.jpg">
                        <span class="a-size-small a-color-base a-text-normal">
                            Product Alpha - Best Muscle Stimulator
                        </span>
                    </a>
                    <span class="a-icon-alt">4.6 out of 5 stars</span>
                    <span class="a-size-small">111,868</span>
                    <span class="a-price"><span class="a-offscreen">$38.88</span></span>
                </div>
            </div>
            <div id="gridItemRoot">
                <div class="zg-grid-general-faceout">
                    <span class="zg-bdg-text">#2</span>
                    <a class="a-link-normal" href="/dp/B0BBBB2222">
                        <span class="a-size-small a-color-base a-text-normal">
                            Product Beta - EMS Massage Machine
                        </span>
                    </a>
                    <span class="a-icon-alt">4.5 out of 5 stars</span>
                    <span class="a-size-small">3,060</span>
                    <span class="a-price"><span class="a-offscreen">$25.98</span></span>
                </div>
            </div>
        </body></html>
        """
        result = _extract_amazon_list_page(html, "bestsellers")
        assert "Product Alpha" in result
        assert "B0AAAA1111" in result
        assert "Product Beta" in result
        assert "B0BBBB2222" in result
        assert "#1" in result or "1." in result
        assert "$38.88" in result or "38.88" in result

    def test_search_results_extraction(self):
        from app.tools.web_tools import _extract_amazon_list_page

        html = """
        <html><body>
            <div data-component-type="s-search-result" data-asin="B0SRCH0001">
                <h2><a class="a-link-normal" href="/dp/B0SRCH0001">
                    <span>Search Result Product One</span>
                </a></h2>
                <span class="a-icon-alt">4.2 out of 5 stars</span>
                <span class="a-size-base">8,500</span>
                <span class="a-price"><span class="a-offscreen">$19.99</span></span>
            </div>
            <div data-component-type="s-search-result" data-asin="B0SRCH0002">
                <h2><a class="a-link-normal" href="/dp/B0SRCH0002">
                    <span>Search Result Product Two</span>
                </a></h2>
                <span class="a-icon-alt">3.9 out of 5 stars</span>
                <span class="a-price"><span class="a-offscreen">$29.99</span></span>
            </div>
        </body></html>
        """
        result = _extract_amazon_list_page(html, "search")
        assert "Search Result Product One" in result
        assert "B0SRCH0001" in result
        assert "$19.99" in result or "19.99" in result
        assert "Search Result Product Two" in result

    def test_empty_list_page(self):
        from app.tools.web_tools import _extract_amazon_list_page

        result = _extract_amazon_list_page("<html><body>Empty</body></html>", "bestsellers")
        assert result is None


class TestGeneralContentExtraction:
    def test_extracts_main_content(self):
        from app.tools.web_tools import _extract_general_content

        html = """
        <html><head><title>Test Page</title></head>
        <body>
            <nav>Navigation</nav>
            <main><p>Main content here</p></main>
            <footer>Footer</footer>
        </body></html>
        """
        result = _extract_general_content(html, "https://example.com")
        assert "Test Page" in result
        assert "Main content" in result
        assert "Navigation" not in result

    def test_truncates_long_content(self):
        from app.tools.web_tools import _extract_general_content, _MAX_CONTENT_LENGTH

        long_body = "<main>" + "x" * (_MAX_CONTENT_LENGTH + 2000) + "</main>"
        html = f"<html><head><title>Long</title></head><body>{long_body}</body></html>"
        result = _extract_general_content(html, "https://example.com")
        assert "内容已截断" in result


class TestUrlRecovery:
    def test_recovers_sanitized_url(self):
        from app.tools.web_tools import _recover_url

        real = "https://www.amazon.com/dp/B08TW57FVR"
        sanitized = "https://www.amazon.com/dp/__ASIN_0__"
        assert _recover_url(sanitized, [real]) == real

    def test_passthrough_normal_url(self):
        from app.tools.web_tools import _recover_url

        url = "https://www.amazon.com/dp/B08TW57FVR"
        assert _recover_url(url, []) == url

    def test_matches_by_host(self):
        from app.tools.web_tools import _recover_url

        refs = [
            "https://www.google.com/search?q=test",
            "https://www.amazon.com/dp/B08TW57FVR",
        ]
        sanitized = "https://www.amazon.com/dp/__ASIN_0__"
        assert _recover_url(sanitized, refs) == refs[1]


# ── CrawlerManager 测试 ───────────────────────────────


class TestCrawlerManager:
    @pytest.mark.asyncio
    async def test_lazy_init(self):
        from app.tools.web_tools import CrawlerManager

        mgr = CrawlerManager()
        assert not mgr._started
        assert mgr._crawler is None

    @pytest.mark.asyncio
    async def test_get_crawler_starts_browser(self):
        from app.tools.web_tools import CrawlerManager

        mock_crawler = AsyncMock()
        mock_crawler.start = AsyncMock()

        with patch("app.tools.web_tools.AsyncWebCrawler", return_value=mock_crawler):
            mgr = CrawlerManager()
            crawler = await mgr.get_crawler()
            assert crawler is mock_crawler
            mock_crawler.start.assert_awaited_once()
            assert mgr._started

    @pytest.mark.asyncio
    async def test_get_crawler_reuses_instance(self):
        from app.tools.web_tools import CrawlerManager

        mock_crawler = AsyncMock()
        mock_crawler.start = AsyncMock()

        with patch("app.tools.web_tools.AsyncWebCrawler", return_value=mock_crawler):
            mgr = CrawlerManager()
            c1 = await mgr.get_crawler()
            c2 = await mgr.get_crawler()
            assert c1 is c2
            # start should only be called once
            assert mock_crawler.start.await_count == 1

    @pytest.mark.asyncio
    async def test_shutdown(self):
        from app.tools.web_tools import CrawlerManager

        mock_crawler = AsyncMock()
        mock_crawler.start = AsyncMock()
        mock_crawler.close = AsyncMock()

        with patch("app.tools.web_tools.AsyncWebCrawler", return_value=mock_crawler):
            mgr = CrawlerManager()
            await mgr.get_crawler()
            await mgr.shutdown()
            mock_crawler.close.assert_awaited_once()
            assert not mgr._started
            assert mgr._crawler is None


# ── web_fetch 工具集成测试 (mock Crawl4AI) ─────────────


def _make_crawl_result(*, success=True, markdown="", html="", url="https://example.com",
                        error_message=""):
    """构造 mock 的 Crawl4AI 爬取结果"""
    result = MagicMock()
    result.success = success
    result.markdown = markdown
    result.html = html
    result.url = url
    result.error_message = error_message
    return result


class TestWebFetchTool:
    @pytest.fixture
    def mock_crawler_manager(self):
        """Mock 全局 CrawlerManager"""
        mock_mgr = AsyncMock()
        mock_crawler = AsyncMock()
        mock_mgr.get_crawler = AsyncMock(return_value=mock_crawler)
        return mock_mgr, mock_crawler

    @pytest.mark.asyncio
    async def test_general_page_returns_markdown(self, mock_crawler_manager):
        mock_mgr, mock_crawler = mock_crawler_manager
        crawl_result = _make_crawl_result(
            markdown="# Hello World\n\nThis is a test page with useful content.",
            html="<html><body><h1>Hello World</h1><p>This is a test page</p></body></html>",
            url="https://example.com/page",
        )
        mock_crawler.arun = AsyncMock(return_value=crawl_result)

        with patch("app.tools.web_tools._crawler_manager", mock_mgr):
            from app.tools.web_tools import create_web_tools
            tools = create_web_tools()
            web_fetch = next(t for t in tools if t.name == "web_fetch")
            result = await web_fetch.ainvoke({"url": "https://example.com/page"})

        assert "Hello World" in result
        assert "example.com" in result

    @pytest.mark.asyncio
    async def test_amazon_page_uses_structured_extraction(self, mock_crawler_manager):
        mock_mgr, mock_crawler = mock_crawler_manager
        amazon_html = """
        <html><body>
            <span id="productTitle">Test Product XYZ</span>
            <a id="bylineInfo">BrandName Store</a>
            <span class="a-price-whole">29.</span>
            <span class="a-price-fraction">99</span>
            <span data-hook="rating-out-of-text">4.3 out of 5</span>
            <span id="acrCustomerReviewText">5,678 ratings</span>
        </body></html>
        """
        crawl_result = _make_crawl_result(
            markdown="Some raw markdown from crawl4ai",
            html=amazon_html,
            url="https://www.amazon.com/dp/B08TEST123",
        )
        mock_crawler.arun = AsyncMock(return_value=crawl_result)

        with patch("app.tools.web_tools._crawler_manager", mock_mgr):
            from app.tools.web_tools import create_web_tools
            tools = create_web_tools()
            web_fetch = next(t for t in tools if t.name == "web_fetch")
            result = await web_fetch.ainvoke({"url": "https://www.amazon.com/dp/B08TEST123"})

        assert "Test Product XYZ" in result
        assert "BrandName" in result
        assert "29" in result
        assert "4.3" in result

    @pytest.mark.asyncio
    async def test_amazon_bestsellers_structured_extraction(self, mock_crawler_manager):
        """Best Sellers 页面走结构化提取，而非被 nav 噪声截断"""
        mock_mgr, mock_crawler = mock_crawler_manager
        bestsellers_html = """
        <html><body>
            <nav>Huge navigation bar with lots of content</nav>
            <div id="gridItemRoot">
                <div class="zg-grid-general-faceout">
                    <span class="zg-bdg-text">#1</span>
                    <a class="a-link-normal" href="/dp/B0TOP00001/ref=zg_bs">
                        <span class="a-size-small a-color-base a-text-normal">
                            TENS 7000 Digital TENS Unit
                        </span>
                    </a>
                    <span class="a-icon-alt">4.6 out of 5 stars</span>
                    <span class="a-size-small">111,868</span>
                    <span class="a-price"><span class="a-offscreen">$38.88</span></span>
                </div>
            </div>
        </body></html>
        """
        crawl_result = _make_crawl_result(
            markdown="# nav noise " * 500,
            html=bestsellers_html,
            url="https://www.amazon.com/gp/bestsellers/hpc/8627079011",
        )
        mock_crawler.arun = AsyncMock(return_value=crawl_result)

        with patch("app.tools.web_tools._crawler_manager", mock_mgr):
            from app.tools.web_tools import create_web_tools
            tools = create_web_tools()
            web_fetch = next(t for t in tools if t.name == "web_fetch")
            result = await web_fetch.ainvoke({
                "url": "https://www.amazon.com/gp/bestsellers/hpc/8627079011"
            })

        assert "TENS 7000" in result
        assert "B0TOP00001" in result

    @pytest.mark.asyncio
    async def test_amazon_fallback_to_markdown(self, mock_crawler_manager):
        """Amazon 页面无法解析结构时 fallback 到 Crawl4AI markdown"""
        mock_mgr, mock_crawler = mock_crawler_manager
        crawl_result = _make_crawl_result(
            markdown="# Amazon Product Page\n\nSome product content extracted by crawl4ai",
            html="<html><body>Amazon changed their HTML structure completely</body></html>",
            url="https://www.amazon.com/dp/B08TEST123",
        )
        mock_crawler.arun = AsyncMock(return_value=crawl_result)

        with patch("app.tools.web_tools._crawler_manager", mock_mgr):
            from app.tools.web_tools import create_web_tools
            tools = create_web_tools()
            web_fetch = next(t for t in tools if t.name == "web_fetch")
            result = await web_fetch.ainvoke({"url": "https://www.amazon.com/dp/B08TEST123"})

        assert "Amazon Product Page" in result

    @pytest.mark.asyncio
    async def test_crawl_failure_returns_error(self, mock_crawler_manager):
        mock_mgr, mock_crawler = mock_crawler_manager
        crawl_result = _make_crawl_result(
            success=False,
            error_message="Navigation timeout",
        )
        mock_crawler.arun = AsyncMock(return_value=crawl_result)

        with patch("app.tools.web_tools._crawler_manager", mock_mgr):
            from app.tools.web_tools import create_web_tools
            tools = create_web_tools()
            web_fetch = next(t for t in tools if t.name == "web_fetch")
            result = await web_fetch.ainvoke({"url": "https://example.com"})

        assert "抓取失败" in result

    @pytest.mark.asyncio
    async def test_crawler_exception_returns_error(self, mock_crawler_manager):
        mock_mgr, mock_crawler = mock_crawler_manager
        mock_crawler.arun = AsyncMock(side_effect=Exception("Browser crashed"))

        with patch("app.tools.web_tools._crawler_manager", mock_mgr):
            from app.tools.web_tools import create_web_tools
            tools = create_web_tools()
            web_fetch = next(t for t in tools if t.name == "web_fetch")
            result = await web_fetch.ainvoke({"url": "https://example.com"})

        assert "抓取失败" in result
        assert "Browser crashed" in result

    @pytest.mark.asyncio
    async def test_url_recovery_applied(self, mock_crawler_manager):
        """验证 URL 恢复在 Crawl4AI 调用前生效"""
        mock_mgr, mock_crawler = mock_crawler_manager
        crawl_result = _make_crawl_result(
            markdown="Recovered page content with enough chars to pass threshold",
            url="https://www.amazon.com/dp/B08REAL123",
        )
        mock_crawler.arun = AsyncMock(return_value=crawl_result)

        real_url = "https://www.amazon.com/dp/B08REAL123"

        with patch("app.tools.web_tools._crawler_manager", mock_mgr):
            from app.tools.web_tools import create_web_tools
            tools = create_web_tools(reference_urls=[real_url])
            web_fetch = next(t for t in tools if t.name == "web_fetch")
            await web_fetch.ainvoke({"url": "https://www.amazon.com/dp/__ASIN_0__"})

        call_args = mock_crawler.arun.call_args
        called_url = call_args[1].get("url") or call_args[0][0]
        assert called_url == real_url

    @pytest.mark.asyncio
    async def test_content_truncation(self, mock_crawler_manager):
        from app.tools.web_tools import _MAX_CONTENT_LENGTH

        mock_mgr, mock_crawler = mock_crawler_manager
        long_content = "x" * (_MAX_CONTENT_LENGTH + 5000)
        crawl_result = _make_crawl_result(
            markdown=long_content,
            url="https://example.com/long",
        )
        mock_crawler.arun = AsyncMock(return_value=crawl_result)

        with patch("app.tools.web_tools._crawler_manager", mock_mgr):
            from app.tools.web_tools import create_web_tools
            tools = create_web_tools()
            web_fetch = next(t for t in tools if t.name == "web_fetch")
            result = await web_fetch.ainvoke({"url": "https://example.com/long"})

        assert "内容已截断" in result
        assert len(result) < _MAX_CONTENT_LENGTH + 500


class TestToolCreation:
    def test_creates_web_fetch_tool(self):
        with patch("app.tools.web_tools._crawler_manager"):
            from app.tools.web_tools import create_web_tools
            tools = create_web_tools()
            assert len(tools) == 1
            assert tools[0].name == "web_fetch"

    def test_tool_description_mentions_capabilities(self):
        with patch("app.tools.web_tools._crawler_manager"):
            from app.tools.web_tools import create_web_tools
            tools = create_web_tools()
            desc = tools[0].description
            assert "Amazon" in desc or "amazon" in desc
