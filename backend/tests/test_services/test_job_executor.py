"""JobExecutor 单元测试

验证:
- Agent 图的构建和非流式运行
- AI 响应文本的提取
- 交付逻辑的调用
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.services.job_executor import JobExecutor, _extract_ai_response


class TestExtractAiResponse:
    """从 Agent 最终状态中提取 AI 响应"""

    def test_extracts_text_content(self):
        state = {
            "messages": [
                HumanMessage(content="test"),
                AIMessage(content="这是 AI 的回复"),
            ]
        }
        result = _extract_ai_response(state)
        assert result == "这是 AI 的回复"

    def test_skips_tool_call_messages(self):
        ai_with_tool = AIMessage(content="", tool_calls=[{"name": "test", "args": {}, "id": "1"}])
        ai_final = AIMessage(content="最终回复")
        state = {
            "messages": [
                HumanMessage(content="test"),
                ai_with_tool,
                ai_final,
            ]
        }
        result = _extract_ai_response(state)
        assert result == "最终回复"

    def test_handles_list_content(self):
        state = {
            "messages": [
                AIMessage(content=[
                    {"type": "text", "text": "第一段"},
                    {"type": "text", "text": "第二段"},
                ]),
            ]
        }
        result = _extract_ai_response(state)
        assert "第一段" in result
        assert "第二段" in result

    def test_empty_messages_returns_empty(self):
        state = {"messages": []}
        result = _extract_ai_response(state)
        assert result == ""

    def test_no_ai_messages_returns_empty(self):
        state = {"messages": [HumanMessage(content="hello")]}
        result = _extract_ai_response(state)
        assert result == ""


class TestJobExecutor:
    """JobExecutor 执行逻辑"""

    @pytest.mark.asyncio
    async def test_execute_builds_and_runs_graph(self):
        executor = JobExecutor(timeout_seconds=60)

        job_id = uuid.uuid4()
        user_id = uuid.uuid4()
        bot_id = uuid.uuid4()

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.user_id = user_id
        mock_job.bot_id = bot_id
        mock_job.conversation_id = None
        mock_job.payload_message = "分析竞品数据"
        mock_job.payload_config = None
        mock_job.delivery_mode = "chat"
        mock_job.delivery_config = None
        mock_job.name = "Daily Report"
        mock_job.enabled = True

        with patch("app.services.job_executor.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_job
            mock_session.execute = AsyncMock(return_value=mock_result)

            mock_graph = MagicMock()
            mock_compiled = AsyncMock()
            mock_compiled.ainvoke = AsyncMock(return_value={
                "messages": [
                    HumanMessage(content="test"),
                    AIMessage(content="竞品分析完成，发现3个关键趋势"),
                ]
            })
            mock_graph.compile.return_value = mock_compiled

            with patch("app.engine.graph_builder.build_agent_graph",
                       new_callable=AsyncMock) as mock_build:
                mock_build.return_value = (mock_graph, {"messages": []})

                with patch("app.services.delivery_service.DeliveryService") as mock_delivery_cls:
                    mock_delivery = MagicMock()
                    mock_delivery.deliver = AsyncMock()
                    mock_delivery_cls.return_value = mock_delivery

                    result = await executor.execute(job_id)

                    assert "竞品分析完成" in result
                    mock_build.assert_awaited_once()
                    mock_delivery.deliver.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_nonexistent_job_raises(self):
        executor = JobExecutor()

        with patch("app.services.job_executor.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            with pytest.raises(ValueError, match="不存在"):
                await executor.execute(uuid.uuid4())
