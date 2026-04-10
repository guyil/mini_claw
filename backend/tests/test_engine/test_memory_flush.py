"""Memory Flush 单元测试

P2: compaction 前插入 system turn 保存关键信息
"""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.engine.memory_flush import build_flush_prompt, should_flush_before_compaction


class TestShouldFlushBeforeCompaction:
    def test_should_flush_when_compacting(self):
        msgs = [HumanMessage(content=f"msg {i}") for i in range(20)]
        assert should_flush_before_compaction(msgs, is_compacting=True) is True

    def test_should_not_flush_when_not_compacting(self):
        msgs = [HumanMessage(content="hi")]
        assert should_flush_before_compaction(msgs, is_compacting=False) is False

    def test_should_not_flush_short_conversation(self):
        msgs = [HumanMessage(content="hi"), AIMessage(content="hello")]
        assert should_flush_before_compaction(msgs, is_compacting=True) is False


class TestBuildFlushPrompt:
    def test_prompt_instructs_memory_save(self):
        prompt = build_flush_prompt()
        assert "memory_write" in prompt or "记忆" in prompt

    def test_prompt_is_non_empty(self):
        prompt = build_flush_prompt()
        assert len(prompt) > 50
