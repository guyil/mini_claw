"""Web 工具 — 网页内容抓取 (Crawl4AI 版)

使用 Crawl4AI 进行网页抓取，支持 JavaScript 渲染和反爬虫绕过。
对 Amazon 产品页做特殊处理，从渲染后的 HTML 提取 listing 关键信息。
通用网页直接使用 Crawl4AI 的 Markdown 输出，确保 LLM 可读性。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

_MAX_CONTENT_LENGTH = 20000


def _is_amazon_url(url: str) -> bool:
    return bool(re.search(r"amazon\.(com|co\.\w+|de|fr|it|es|ca|com\.au)", url))


def _detect_amazon_page_type(url: str) -> str:
    """判断 Amazon URL 的页面类型：product / bestsellers / search / other"""
    if re.search(r"/dp/[A-Z0-9]{4,10}", url):
        return "product"
    if re.search(r"/(gp/)?bestsellers/", url) or "/zgbs/" in url:
        return "bestsellers"
    if re.search(r"/s\?", url) or "/s/" in url:
        return "search"
    return "other"


def _extract_amazon_list_page(html: str, page_type: str) -> str | None:
    """从 Amazon 列表页 (Best Sellers / 搜索结果) 提取产品列表

    返回结构化文本，如果无法提取则返回 None。
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    products: list[dict[str, str]] = []

    if page_type == "bestsellers":
        items = soup.find_all("div", id="gridItemRoot")
        if not items:
            items = soup.find_all("div", class_="zg-grid-general-faceout")

        for item in items:
            product: dict[str, str] = {}

            rank_el = item.find("span", class_="zg-bdg-text")
            if rank_el:
                product["rank"] = rank_el.get_text(strip=True)

            link_el = item.find("a", class_="a-link-normal", href=re.compile(r"/dp/[A-Z0-9]"))
            if link_el:
                href = link_el.get("href", "")
                asin_match = re.search(r"/dp/([A-Z0-9]{10})", href)
                if asin_match:
                    product["asin"] = asin_match.group(1)

            title_el = item.find("span", class_=re.compile(r"a-size-.*a-text-normal"))
            if not title_el:
                title_el = item.find("div", class_="_cDEzb_p13n-sc-css-line-clamp-1_1Fn1y")
            if not title_el and link_el:
                img = link_el.find("img")
                if img and img.get("alt"):
                    product["title"] = img["alt"]
            if title_el:
                product["title"] = title_el.get_text(strip=True)

            rating_el = item.find("span", class_="a-icon-alt")
            if rating_el:
                product["rating"] = rating_el.get_text(strip=True)

            price_el = item.find("span", class_="a-offscreen")
            if price_el:
                product["price"] = price_el.get_text(strip=True)

            review_els = item.find_all("span", class_="a-size-small")
            for el in review_els:
                text = el.get_text(strip=True)
                if text and re.match(r"[\d,]+$", text):
                    product["reviews"] = text
                    break

            if product.get("title") or product.get("asin"):
                products.append(product)

    elif page_type == "search":
        items = soup.find_all("div", attrs={"data-component-type": "s-search-result"})

        for idx, item in enumerate(items, 1):
            product: dict[str, str] = {"rank": f"#{idx}"}

            asin = item.get("data-asin", "")
            if asin:
                product["asin"] = asin

            title_el = item.find("h2")
            if title_el:
                product["title"] = title_el.get_text(strip=True)

            rating_el = item.find("span", class_="a-icon-alt")
            if rating_el:
                product["rating"] = rating_el.get_text(strip=True)

            price_el = item.find("span", class_="a-offscreen")
            if price_el:
                product["price"] = price_el.get_text(strip=True)

            review_els = item.find_all("span", class_="a-size-base")
            for el in review_els:
                text = el.get_text(strip=True)
                if text and re.match(r"[\d,]+$", text):
                    product["reviews"] = text
                    break

            if product.get("title") or product.get("asin"):
                products.append(product)

    if not products:
        return None

    lines: list[str] = [f"**Amazon 列表页抓取结果** (共 {len(products)} 个商品)\n"]
    for p in products:
        rank = p.get("rank", "?")
        title = p.get("title", "未知标题")
        asin = p.get("asin", "")
        price = p.get("price", "")
        rating = p.get("rating", "")
        reviews = p.get("reviews", "")

        line = f"**{rank}** {title}"
        if asin:
            line += f"\n  - ASIN: {asin}"
            line += f" | 链接: https://www.amazon.com/dp/{asin}"
        if price:
            line += f"\n  - 价格: {price}"
        if rating:
            line += f"\n  - 评分: {rating}"
        if reviews:
            line += f" | 评论数: {reviews}"
        lines.append(line)

    return "\n\n".join(lines)


def _extract_amazon_listing(html: str) -> str:
    """从 Amazon 产品页 HTML 提取 listing 关键信息"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    parts: list[str] = []

    title_el = soup.find("span", id="productTitle")
    if title_el:
        parts.append(f"**产品标题**: {title_el.get_text(strip=True)}")

    brand_el = soup.find("a", id="bylineInfo")
    if brand_el:
        parts.append(f"**品牌**: {brand_el.get_text(strip=True)}")

    price_el = soup.find("span", class_="a-price-whole")
    price_frac = soup.find("span", class_="a-price-fraction")
    price_sym = soup.find("span", class_="a-price-symbol")
    if price_el:
        price = price_el.get_text(strip=True)
        if price_frac:
            price += price_frac.get_text(strip=True)
        if price_sym:
            price = price_sym.get_text(strip=True) + price
        parts.append(f"**价格**: {price}")

    rating_el = soup.find("span", {"data-hook": "rating-out-of-text"})
    if rating_el:
        parts.append(f"**评分**: {rating_el.get_text(strip=True)}")

    review_count_el = soup.find("span", id="acrCustomerReviewText")
    if review_count_el:
        parts.append(f"**评论数**: {review_count_el.get_text(strip=True)}")

    bullets_el = soup.find("div", id="feature-bullets")
    if bullets_el:
        items = bullets_el.find_all("span", class_="a-list-item")
        if items:
            bullet_text = "\n".join(
                f"  - {li.get_text(strip=True)}" for li in items if li.get_text(strip=True)
            )
            parts.append(f"**卖点 (Bullet Points)**:\n{bullet_text}")

    desc_el = soup.find("div", id="productDescription")
    if desc_el:
        desc_text = desc_el.get_text(strip=True)[:1000]
        parts.append(f"**产品描述**: {desc_text}")

    aplus_el = soup.find("div", id="aplus")
    if aplus_el:
        aplus_text = aplus_el.get_text(" ", strip=True)[:800]
        parts.append(f"**A+ 内容摘要**: {aplus_text}")

    category_el = soup.find("div", id="wayfinding-breadcrumbs_container")
    if category_el:
        crumbs = [a.get_text(strip=True) for a in category_el.find_all("a")]
        if crumbs:
            parts.append(f"**类目**: {' > '.join(crumbs)}")

    bsr_el = soup.find("th", string=re.compile(r"Best Sellers Rank", re.I))
    if bsr_el and bsr_el.find_next_sibling("td"):
        bsr_text = bsr_el.find_next_sibling("td").get_text(" ", strip=True)[:300]
        parts.append(f"**BSR (Best Sellers Rank)**: {bsr_text}")

    if not parts:
        body_text = soup.get_text(" ", strip=True)[:3000]
        return f"未能解析 Amazon listing 结构，原始文本:\n{body_text}"

    return "\n\n".join(parts)


def _extract_general_content(html: str, url: str) -> str:
    """通用网页正文提取 — 当 Crawl4AI markdown 不可用时的后备"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else ""

    main = soup.find("main") or soup.find("article") or soup.find("div", {"role": "main"})
    if main:
        text = main.get_text("\n", strip=True)
    else:
        text = soup.body.get_text("\n", strip=True) if soup.body else soup.get_text("\n", strip=True)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = "\n".join(lines)

    if len(text) > _MAX_CONTENT_LENGTH:
        text = text[:_MAX_CONTENT_LENGTH] + "\n\n... (内容已截断)"

    result = f"**页面标题**: {title}\n**URL**: {url}\n\n{text}"
    return result


_SANITIZED_PATTERN = re.compile(r"__[A-Z_]+_\d+__")


def _recover_url(sanitized_url: str, reference_urls: list[str]) -> str:
    """当 LLM 对 URL 中的标识符做了脱敏处理时，尝试从用户原始输入中恢复"""
    if not _SANITIZED_PATTERN.search(sanitized_url):
        return sanitized_url

    if len(reference_urls) == 1:
        return reference_urls[0]

    from urllib.parse import urlparse

    sanitized_host = urlparse(sanitized_url).netloc
    for ref_url in reference_urls:
        ref_host = urlparse(ref_url).netloc
        if ref_host and ref_host == sanitized_host:
            return ref_url

    return reference_urls[0] if reference_urls else sanitized_url


# ── Crawl4AI 浏览器实例管理 ────────────────────────────


class CrawlerManager:
    """管理 Crawl4AI 浏览器实例的生命周期。

    惰性初始化：首次调用 get_crawler() 时启动浏览器。
    复用实例：后续调用返回同一浏览器，避免重复启动开销。
    应用退出时调用 shutdown() 释放资源。
    """

    def __init__(self) -> None:
        self._crawler: AsyncWebCrawler | None = None
        self._started: bool = False

    async def get_crawler(self) -> AsyncWebCrawler:
        if not self._started:
            browser_config = BrowserConfig(
                headless=True,
                enable_stealth=True,
                extra_args=["--disable-blink-features=AutomationControlled"],
            )
            self._crawler = AsyncWebCrawler(config=browser_config)
            await self._crawler.start()
            self._started = True
            logger.info("Crawl4AI 浏览器实例已启动 (stealth mode)")
        return self._crawler  # type: ignore[return-value]

    async def shutdown(self) -> None:
        if self._started and self._crawler:
            try:
                await self._crawler.close()
            except Exception as e:
                logger.warning("关闭 Crawl4AI 浏览器时出错: %s", e)
            self._started = False
            self._crawler = None
            logger.info("Crawl4AI 浏览器实例已关闭")


_crawler_manager = CrawlerManager()


async def shutdown_crawler() -> None:
    """供 app lifespan 调用，关闭全局 Crawl4AI 浏览器"""
    await _crawler_manager.shutdown()


# ── 核心抓取逻辑 ──────────────────────────────────────


async def _fetch_with_crawl4ai(url: str) -> dict[str, Any]:
    """使用 Crawl4AI 抓取网页，返回 markdown 和 html"""
    crawler = await _crawler_manager.get_crawler()

    config = CrawlerRunConfig(
        wait_until="load",
        simulate_user=True,
        excluded_tags=["nav", "header", "footer", "aside", "noscript"],
        remove_overlay_elements=True,
    )

    result = await crawler.arun(url=url, config=config)

    if not result.success:
        raise RuntimeError(f"Crawl4AI 抓取失败: {result.error_message}")

    return {
        "markdown": result.markdown or "",
        "html": result.html or "",
        "url": result.url or url,
    }


# ── 工具创建 ──────────────────────────────────────────


def create_web_tools(reference_urls: list[str] | None = None) -> list[StructuredTool]:
    """创建 web 工具集

    Args:
        reference_urls: 从用户消息中提取的原始 URL，用于恢复被 LLM 脱敏的 URL
    """
    _ref_urls = reference_urls or []

    async def _web_fetch(url: str) -> str:
        """抓取网页内容并提取正文。支持 JS 渲染和反爬虫绕过。
        对 Amazon 产品页会自动解析 listing 详情，
        对 Best Sellers / 搜索结果页会提取产品列表。"""
        url = _recover_url(url, _ref_urls)

        try:
            result = await _fetch_with_crawl4ai(url)
        except Exception as e:
            return f"抓取失败: {e}"

        if _is_amazon_url(url):
            page_type = _detect_amazon_page_type(url)

            if page_type == "product":
                listing = _extract_amazon_listing(result["html"])
                if not listing.startswith("未能解析"):
                    return listing

            elif page_type in ("bestsellers", "search"):
                list_result = _extract_amazon_list_page(result["html"], page_type)
                if list_result:
                    return list_result

        markdown = result["markdown"]
        if markdown and len(markdown.strip()) > 50:
            if len(markdown) > _MAX_CONTENT_LENGTH:
                markdown = markdown[:_MAX_CONTENT_LENGTH] + "\n\n... (内容已截断)"
            return f"**URL**: {result['url']}\n\n{markdown}"

        return _extract_general_content(result["html"], result["url"])

    return [
        StructuredTool.from_function(
            coroutine=_web_fetch,
            name="web_fetch",
            description=(
                "抓取指定 URL 的网页内容并返回结构化文本。"
                "使用浏览器渲染，支持 JavaScript 动态页面和反爬虫绕过。"
                "对 Amazon 产品页会自动解析 listing 详情（标题、价格、评分、卖点等）。"
                "传入完整的 URL。"
            ),
        ),
    ]
