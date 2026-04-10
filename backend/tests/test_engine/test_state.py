"""State 定义测试"""

from app.engine.state import AgentState


def test_agent_state_structure():
    """验证 AgentState 包含所有必需字段"""
    annotations = AgentState.__annotations__
    required_keys = [
        "messages",
        "bot_config",
        "available_skills",
        "active_skill",
        "skill_instructions",
        "skill_assets",
        "memory_context",
        "session_key",
        "user_id",
        "bot_id",
    ]
    for key in required_keys:
        assert key in annotations, f"AgentState 缺少字段: {key}"
