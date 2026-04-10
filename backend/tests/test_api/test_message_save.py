"""测试消息保存逻辑

验证 AI/tool 消息能正确从 state 中提取并保存到数据库。
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.chat import _save_message_to_db


class FakeMessage:
    """模拟数据库中的 Message 对象"""

    def __init__(self, role: str, content: str, metadata_: dict | None = None):
        self.id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.role = role
        self.content = content
        self.metadata_ = metadata_


class TestSaveMessageToDB:
    """测试 _save_message_to_db 函数"""

    @pytest.mark.asyncio
    async def test_save_ai_message(self):
        db = AsyncMock()
        db.add = MagicMock()
        thread_id = str(uuid.uuid4())

        await _save_message_to_db(db, thread_id, "ai", "你好，我是AI助手")

        db.add.assert_called_once()
        msg = db.add.call_args[0][0]
        assert msg.role == "ai"
        assert msg.content == "你好，我是AI助手"
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_with_metadata(self):
        db = AsyncMock()
        db.add = MagicMock()
        thread_id = str(uuid.uuid4())
        metadata = {"tool_calls": [{"name": "test", "args": {}, "id": "tc-1"}]}

        await _save_message_to_db(db, thread_id, "ai", "调用工具", metadata)

        msg = db.add.call_args[0][0]
        assert msg.metadata_ == metadata

    @pytest.mark.asyncio
    async def test_skip_when_db_none(self):
        await _save_message_to_db(None, "thread-1", "ai", "test")

    @pytest.mark.asyncio
    async def test_skip_when_thread_none(self):
        db = AsyncMock()
        await _save_message_to_db(db, None, "ai", "test")
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_rollback_on_flush_failure(self):
        """flush 失败时应 rollback，确保 session 仍可用"""
        db = AsyncMock()
        db.add = MagicMock()
        db.flush.side_effect = Exception("table does not exist")
        thread_id = str(uuid.uuid4())

        await _save_message_to_db(db, thread_id, "human", "test")

        db.rollback.assert_awaited_once()


class TestNewMessageExtraction:
    """测试从 state 中提取新消息的逻辑

    模拟 run_callback 中流式运行后从 controller.state["messages"] 提取
    新增的 AI/tool 消息并保存的过程。
    """

    def _extract_and_prepare_messages(
        self, state_messages: list[dict], msg_count_before: int
    ) -> list[dict[str, Any]]:
        """复现 chat.py 中提取新消息的逻辑"""
        results = []
        new_messages = state_messages[msg_count_before:]
        for msg_data in new_messages:
            if not isinstance(msg_data, dict):
                continue
            role = msg_data.get("type", "")
            if role not in ("ai", "tool"):
                continue
            content = msg_data.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        text_parts.append(part)
                content = "\n".join(text_parts)

            metadata: dict[str, Any] = {}
            if role == "ai":
                if msg_data.get("tool_calls"):
                    metadata["tool_calls"] = msg_data["tool_calls"]
                if msg_data.get("id"):
                    metadata["id"] = msg_data["id"]
            elif role == "tool":
                if msg_data.get("tool_call_id"):
                    metadata["tool_call_id"] = msg_data["tool_call_id"]

            results.append({
                "role": role,
                "content": content,
                "metadata": metadata or None,
            })
        return results

    def test_extracts_ai_message(self):
        state_messages = [
            {"type": "human", "content": "你好"},
            {"type": "ai", "content": "你好！有什么可以帮你的？", "id": "msg-1"},
        ]
        results = self._extract_and_prepare_messages(state_messages, 1)

        assert len(results) == 1
        assert results[0]["role"] == "ai"
        assert results[0]["content"] == "你好！有什么可以帮你的？"
        assert results[0]["metadata"]["id"] == "msg-1"

    def test_extracts_multiple_ai_and_tool_messages(self):
        """当 AI 调用工具时，应保存 AI 消息、tool 消息和最终 AI 回复"""
        state_messages = [
            {"type": "human", "content": "分析竞品"},
            {
                "type": "ai",
                "content": "",
                "id": "msg-1",
                "tool_calls": [{"name": "exec_command", "args": {"command": "curl ..."}, "id": "tc-1"}],
            },
            {"type": "tool", "content": "执行结果...", "tool_call_id": "tc-1"},
            {"type": "ai", "content": "分析结果如下...", "id": "msg-2"},
        ]
        results = self._extract_and_prepare_messages(state_messages, 1)

        assert len(results) == 3
        assert results[0]["role"] == "ai"
        assert results[0]["metadata"]["tool_calls"][0]["name"] == "exec_command"
        assert results[1]["role"] == "tool"
        assert results[1]["metadata"]["tool_call_id"] == "tc-1"
        assert results[2]["role"] == "ai"
        assert results[2]["content"] == "分析结果如下..."

    def test_skips_human_messages(self):
        """不应重复保存 human 消息"""
        state_messages = [
            {"type": "human", "content": "你好"},
            {"type": "human", "content": "第二条"},
            {"type": "ai", "content": "回复"},
        ]
        results = self._extract_and_prepare_messages(state_messages, 0)

        assert len(results) == 1
        assert results[0]["role"] == "ai"

    def test_handles_list_content(self):
        """AI content 可能是 list 格式"""
        state_messages = [
            {"type": "human", "content": "你好"},
            {
                "type": "ai",
                "content": [
                    {"type": "text", "text": "你好！"},
                    {"type": "text", "text": "我是助手。"},
                ],
            },
        ]
        results = self._extract_and_prepare_messages(state_messages, 1)

        assert len(results) == 1
        assert results[0]["content"] == "你好！\n我是助手。"

    def test_handles_empty_content(self):
        """tool_calls-only 的 AI 消息 content 可能为空字符串"""
        state_messages = [
            {"type": "human", "content": "搜索"},
            {
                "type": "ai",
                "content": "",
                "tool_calls": [{"name": "memory_search", "args": {"query": "test"}, "id": "tc-1"}],
            },
        ]
        results = self._extract_and_prepare_messages(state_messages, 1)

        assert len(results) == 1
        assert results[0]["content"] == ""
        assert results[0]["metadata"]["tool_calls"][0]["name"] == "memory_search"
