"""Embedding Service 单元测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.embedding_service import compute_embedding, compute_embedding_batch


@pytest.mark.asyncio
async def test_compute_embedding_returns_list_of_floats():
    fake_vector = [0.1] * 1536
    with patch("app.services.embedding_service._call_embedding_api", new_callable=AsyncMock) as m:
        m.return_value = [fake_vector]
        result = await compute_embedding("hello world")
        assert isinstance(result, list)
        assert len(result) == 1536
        m.assert_called_once()


@pytest.mark.asyncio
async def test_compute_embedding_empty_text_returns_none():
    result = await compute_embedding("")
    assert result is None

    result = await compute_embedding("   ")
    assert result is None


@pytest.mark.asyncio
async def test_compute_embedding_batch_returns_list():
    fake_vectors = [[0.1] * 1536, [0.2] * 1536]
    with patch("app.services.embedding_service._call_embedding_api", new_callable=AsyncMock) as m:
        m.return_value = fake_vectors
        results = await compute_embedding_batch(["hello", "world"])
        assert len(results) == 2
        assert all(len(v) == 1536 for v in results)


@pytest.mark.asyncio
async def test_compute_embedding_batch_empty_list():
    results = await compute_embedding_batch([])
    assert results == []


@pytest.mark.asyncio
async def test_compute_embedding_handles_api_error():
    with patch("app.services.embedding_service._call_embedding_api", new_callable=AsyncMock) as m:
        m.side_effect = Exception("API down")
        result = await compute_embedding("hello")
        assert result is None
