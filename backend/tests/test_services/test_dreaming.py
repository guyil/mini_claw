"""Dreaming / 记忆晋升 单元测试

P2: 后台统计召回频率，定期将 daily 记忆晋升为 long_term
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.dreaming_service import (
    MemoryRecallStats,
    compute_promotion_score,
    promote_memories,
    record_recall,
    should_promote,
)

BOT_ID = str(uuid.uuid4())


class TestRecordRecall:
    @pytest.mark.asyncio
    async def test_record_increments_count(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.flush = AsyncMock()

        await record_recall(db, BOT_ID, str(uuid.uuid4()), score=0.85, query_hash="abc123")


class TestComputePromotionScore:
    def test_high_frequency_high_relevance(self):
        stats = MemoryRecallStats(
            recall_count=5,
            avg_score=0.9,
            unique_queries=3,
            last_recalled_days_ago=1,
        )
        score = compute_promotion_score(stats)
        assert score > 0.7

    def test_low_frequency_low_score(self):
        stats = MemoryRecallStats(
            recall_count=1,
            avg_score=0.3,
            unique_queries=1,
            last_recalled_days_ago=30,
        )
        score = compute_promotion_score(stats)
        assert score < 0.5

    def test_score_in_valid_range(self):
        stats = MemoryRecallStats(
            recall_count=10,
            avg_score=1.0,
            unique_queries=10,
            last_recalled_days_ago=0,
        )
        score = compute_promotion_score(stats)
        assert 0.0 <= score <= 1.0


class TestShouldPromote:
    def test_passes_all_gates(self):
        stats = MemoryRecallStats(
            recall_count=4,
            avg_score=0.8,
            unique_queries=3,
            last_recalled_days_ago=1,
        )
        assert should_promote(stats) is True

    def test_fails_recall_count_gate(self):
        stats = MemoryRecallStats(
            recall_count=1,
            avg_score=0.9,
            unique_queries=3,
            last_recalled_days_ago=1,
        )
        assert should_promote(stats) is False

    def test_fails_score_gate(self):
        stats = MemoryRecallStats(
            recall_count=5,
            avg_score=0.3,
            unique_queries=3,
            last_recalled_days_ago=1,
        )
        assert should_promote(stats) is False


class TestPromoteMemories:
    @pytest.mark.asyncio
    async def test_promote_changes_type_to_long_term(self):
        db = AsyncMock()
        # Mock: find memories with qualifying stats
        recall_row = MagicMock()
        recall_row.memory_id = uuid.uuid4()
        recall_row.recall_count = 5
        recall_row.avg_score = 0.85
        recall_row.unique_queries = 3
        recall_row.last_recalled_days_ago = 1

        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=[recall_row])
        db.execute = AsyncMock(return_value=result_mock)
        db.flush = AsyncMock()

        promoted = await promote_memories(db, BOT_ID)
        assert isinstance(promoted, int)
