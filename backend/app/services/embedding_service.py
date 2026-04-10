"""Embedding Service — 文本向量化

使用 LiteLLM / OpenAI 兼容 API 生成文本嵌入向量。
当 API 不可用时优雅降级（返回 None），不阻断主流程。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


async def _call_embedding_api(texts: list[str]) -> list[list[float]]:
    """调用 OpenAI 兼容的 embedding API"""
    base_url = settings.litellm_api_base or "https://api.openai.com"
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url += "/v1"

    api_key = settings.litellm_api_key or ""

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/embeddings",
            json={"input": texts, "model": EMBEDDING_MODEL},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()

    return [item["embedding"] for item in data["data"]]


async def compute_embedding(text: str) -> list[float] | None:
    """为单条文本生成 embedding 向量，失败时返回 None"""
    if not text or not text.strip():
        return None

    try:
        results = await _call_embedding_api([text.strip()])
        return results[0] if results else None
    except Exception as e:
        logger.warning("Embedding 计算失败: %s", e)
        return None


async def compute_embedding_batch(texts: list[str]) -> list[list[float]]:
    """批量生成 embedding，失败时返回空列表"""
    if not texts:
        return []

    cleaned = [t.strip() for t in texts if t and t.strip()]
    if not cleaned:
        return []

    try:
        return await _call_embedding_api(cleaned)
    except Exception as e:
        logger.warning("批量 Embedding 计算失败: %s", e)
        return []
