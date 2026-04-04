"""Graph builder 单元测试（不依赖数据库）"""

import pytest

from app.engine.graph_builder import build_agent_graph


@pytest.mark.asyncio
async def test_build_agent_graph_returns_initial_state():
    """验证 build_agent_graph 返回正确的初始状态结构"""
    graph, state = await build_agent_graph(
        db=None,
        bot_id="default",
        user_id="test-user-id",
        session_key="bot-1:user-1:session-1",
    )

    assert state["messages"] == []
    assert state["bot_config"]["name"] == "小爪助手"
    assert state["available_skills"] == []
    assert state["active_skill"] is None
    assert state["skill_instructions"] == ""
    assert state["memory_context"] == ""
    assert state["bot_id"] == "default"
    assert state["user_id"] == "test-user-id"
    assert graph is not None
