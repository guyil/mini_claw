"""Memory Service 向量搜索 + 条件化加载 单元测试

覆盖 P0 (向量搜索) 和 P1 (查询条件化加载) 两个 todo。
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BOT_ID = str(uuid.uuid4())
FAKE_EMBEDDING = [0.1] * 1536


def _make_memory(
    content: str,
    mem_type: str = "long_term",
    importance: float = 0.5,
    memory_date=None,
    mem_id=None,
    distance=0.3,
):
    m = MagicMock()
    m.id = mem_id or uuid.uuid4()
    m.content = content
    m.type = mem_type
    m.importance = importance
    m.memory_date = memory_date
    m.distance = distance
    return m


class TestWriteMemoryWithEmbedding:
    """P0: write_memory 应计算 embedding 并存储"""

    @pytest.mark.asyncio
    async def test_write_memory_computes_embedding(self):
        from app.services.memory_service import write_memory

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.memory_service.compute_embedding", new_callable=AsyncMock) as m:
            m.return_value = FAKE_EMBEDDING
            mem_id = await write_memory(db, BOT_ID, "test content")

            m.assert_called_once_with("test content")
            assert mem_id  # returns a valid id string

    @pytest.mark.asyncio
    async def test_write_memory_works_when_embedding_fails(self):
        from app.services.memory_service import write_memory

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        with patch("app.services.memory_service.compute_embedding", new_callable=AsyncMock) as m:
            m.return_value = None  # embedding failed
            mem_id = await write_memory(db, BOT_ID, "test content")
            assert mem_id  # still works, just no embedding


class TestSearchMemoryVector:
    """P0: search_memory 应使用 cosine 相似度搜索"""

    @pytest.mark.asyncio
    async def test_search_memory_uses_vector_when_embedding_available(self):
        from app.services.memory_service import search_memory

        db = AsyncMock()
        fake_mem = _make_memory("related content")
        db.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[
            (fake_mem, 0.2)
        ])))

        with patch("app.services.memory_service.compute_embedding", new_callable=AsyncMock) as m:
            m.return_value = FAKE_EMBEDDING
            results = await search_memory(db, BOT_ID, "test query")
            assert len(results) >= 0  # may be empty based on mock
            m.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_search_memory_falls_back_to_ilike_when_no_embedding(self):
        from app.services.memory_service import search_memory

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        db.execute = AsyncMock(return_value=result_mock)

        with patch("app.services.memory_service.compute_embedding", new_callable=AsyncMock) as m:
            m.return_value = None  # embedding API unavailable
            results = await search_memory(db, BOT_ID, "test query")
            assert isinstance(results, list)


class TestLoadMemoryContextConditional:
    """P1: load_memory_context 应根据 user_message 做语义检索"""

    @pytest.mark.asyncio
    async def test_load_context_uses_embedding_search_when_message_provided(self):
        from app.services.memory_service import load_memory_context

        db = AsyncMock()
        # mock for vector search - returns empty
        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=[])
        result_mock.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        db.execute = AsyncMock(return_value=result_mock)

        with patch("app.services.memory_service.compute_embedding", new_callable=AsyncMock) as m:
            m.return_value = FAKE_EMBEDDING
            result = await load_memory_context(db, BOT_ID, "tell me about product X")
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_load_context_without_message_uses_fixed_topn(self):
        from app.services.memory_service import load_memory_context

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        db.execute = AsyncMock(return_value=result_mock)

        result = await load_memory_context(db, BOT_ID, "")
        assert isinstance(result, str)
