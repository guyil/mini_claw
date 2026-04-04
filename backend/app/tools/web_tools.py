"""Web 工具 — 网页内容抓取

提供 web_fetch 工具，使用 httpx 获取网页并用 BeautifulSoup 提取正文。
对 Amazon 产品页做特殊处理，提取 listing 关键信息。
"""

from __future__ import annotations

import logging
import re

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _is_amazon_url(url: str) -> bool:
    return bool(re.search(r"amazon\.(com|co\.\w+|de|fr|it|es|ca|com\.au)", url))


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
            bullet_text = "\n".join(f"  - {li.get_text(strip=True)}" for li in items if li.get_text(strip=True))
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
    """通用网页正文提取"""
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

    if len(text) > 5000:
        text = text[:5000] + "\n\n... (内容已截断)"

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


def create_web_tools(reference_urls: list[str] | None = None) -> list[StructuredTool]:
    """创建 web 工具集

    Args:
        reference_urls: 从用户消息中提取的原始 URL，用于恢复被 LLM 脱敏的 URL
    """
    _ref_urls = reference_urls or []

    async def _web_fetch(url: str) -> str:
        """抓取网页内容并提取正文。对 Amazon 产品页会自动解析 listing 详情。"""
        import httpx

        url = _recover_url(url, _ref_urls)

        try:
            async with httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                headers=_HEADERS,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except httpx.HTTPStatusError as e:
            return f"HTTP 错误 {e.response.status_code}: {url}"
        except Exception as e:
            return f"请求失败: {e}"

        if _is_amazon_url(url):
            return _extract_amazon_listing(html)

        return _extract_general_content(html, url)

    return [
        StructuredTool.from_function(
            coroutine=_web_fetch,
            name="web_fetch",
            description=(
                "抓取指定 URL 的网页内容并返回结构化文本。"
                "对 Amazon 产品页会自动解析 listing 详情（标题、价格、评分、卖点等）。"
                "传入完整的 URL。"
            ),
        ),
    ]
