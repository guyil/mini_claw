"""Compaction 单元测试

P1: 检测 message 长度超阈值时 LLM 摘要旧消息
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.engine.compaction import (
    DEFAULT_COMPACTION_THRESHOLD,
    compact_messages,
    estimate_tokens,
    needs_compaction,
)


class TestEstimateTokens:
    def test_estimate_basic_text(self):
        msgs = [HumanMessage(content="hello world")]
        tokens = estimate_tokens(msgs)
        assert tokens > 0

    def test_estimate_empty_list(self):
        assert estimate_tokens([]) == 0

    def test_estimate_multiple_messages(self):
        msgs = [
            HumanMessage(content="hello " * 100),
            AIMessage(content="response " * 200),
        ]
        tokens = estimate_tokens(msgs)
        assert tokens > 100


class TestNeedsCompaction:
    def test_short_conversation_no_compaction(self):
        msgs = [HumanMessage(content="hi")]
        assert needs_compaction(msgs) is False

    def test_long_conversation_needs_compaction(self):
        msgs = [HumanMessage(content="x " * 5000) for _ in range(20)]
        assert needs_compaction(msgs, threshold=1000) is True

    def test_custom_threshold(self):
        msgs = [HumanMessage(content="word " * 100)]
        assert needs_compaction(msgs, threshold=10) is True
        assert needs_compaction(msgs, threshold=100000) is False


class TestCompactMessages:
    @pytest.mark.asyncio
    async def test_compact_preserves_recent_messages(self):
        """Compaction 应保留最近 N 条消息"""
        old_msgs = [
            HumanMessage(content=f"old message {i} " * 200) for i in range(10)
        ]
        recent_msgs = [
            HumanMessage(content="recent question"),
            AIMessage(content="recent answer"),
        ]
        all_msgs = old_msgs + recent_msgs

        with patch("app.engine.compaction._summarize_messages", new_callable=AsyncMock) as m:
            m.return_value = "Summary of old conversation"
            result = await compact_messages(all_msgs, bot_config={"model_name": "test"})

            assert len(result) >= 2  # at least summary + recent
            assert "Summary" in result[0].content or "摘要" in result[0].content

    @pytest.mark.asyncio
    async def test_compact_returns_original_when_short(self):
        """短对话不应被压缩"""
        msgs = [HumanMessage(content="hi"), AIMessage(content="hello")]
        result = await compact_messages(msgs, bot_config={"model_name": "test"})
        assert result == msgs

    @pytest.mark.asyncio
    async def test_compact_summary_format(self):
        """Compaction 摘要应包含结构化信息"""
        msgs = [HumanMessage(content=f"msg {i} " * 500) for i in range(20)]

        with patch("app.engine.compaction._summarize_messages", new_callable=AsyncMock) as m:
            m.return_value = "## 对话摘要\n- 讨论了产品分析\n- 决定了广告策略"
            result = await compact_messages(msgs, bot_config={"model_name": "test"})
            summary_msg = result[0]
            assert isinstance(summary_msg, SystemMessage)
