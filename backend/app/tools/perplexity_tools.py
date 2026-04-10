"""Perplexity 搜索工具 — 使用 Perplexity Sonar API 进行联网搜索

提供 web_search 工具，Agent 可以用它搜索实时网络信息并获取带引用来源的回答。
"""

from __future__ import annotations

import logging

from langchain_core.tools import BaseTool, StructuredTool

from app.config import settings

logger = logging.getLogger(__name__)

_PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
_DEFAULT_MODEL = "sonar"


def create_perplexity_tools() -> list[BaseTool]:
    """创建 Perplexity 搜索工具集

    当 PERPLEXITY_API_KEY 未配置时返回空列表，不影响其他工具正常工作。
    """
    api_key = settings.perplexity_api_key
    if not api_key:
        logger.info("PERPLEXITY_API_KEY 未配置，web_search 工具不可用")
        return []

    async def _web_search(query: str) -> str:
        """搜索互联网获取实时信息。传入搜索查询关键词，返回搜索结果摘要和来源链接。"""
        import httpx

        payload = {
            "model": _DEFAULT_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一个搜索助手。请用中文回答问题，给出准确、结构化的信息。"
                        "如果涉及数据，请标注数据来源和时效性。"
                    ),
                },
                {"role": "user", "content": query},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    _PERPLEXITY_API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning("Perplexity 搜索失败: %s", e)
            return f"搜索失败: {e}"

        answer = data["choices"][0]["message"]["content"]
        citations: list[str] = data.get("citations", [])

        if citations:
            refs = "\n".join(f"  [{i + 1}] {url}" for i, url in enumerate(citations))
            return f"{answer}\n\n**参考来源**:\n{refs}"

        return answer

    return [
        StructuredTool.from_function(
            coroutine=_web_search,
            name="web_search",
            description=(
                "搜索互联网获取实时信息。适用于查询最新数据、市场趋势、竞品信息、"
                "产品评价、行业新闻等需要联网搜索的场景。传入搜索关键词或问题。"
            ),
        ),
    ]
