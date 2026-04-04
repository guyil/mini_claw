"""Nodes routing 逻辑测试"""

from langchain_core.messages import AIMessage, HumanMessage

from app.engine.nodes import route_after_router, route_after_skill_executor


def test_route_direct_answer():
    """没有 tool_calls 时应走 direct_answer"""
    state = {
        "messages": [AIMessage(content="这是直接回答")],
    }
    assert route_after_router(state) == "direct_answer"


def test_route_use_skill():
    """调用 activate_skill 时应走 use_skill"""
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "activate_skill", "args": {"skill_name": "test"}, "id": "1"}],
    )
    state = {"messages": [msg]}
    assert route_after_router(state) == "use_skill"


def test_route_use_tool():
    """调用其他 tool 时应走 use_tool"""
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "memory_search", "args": {"query": "test"}, "id": "1"}],
    )
    state = {"messages": [msg]}
    assert route_after_router(state) == "use_tool"


def test_route_human_message():
    """Human message 应走 direct_answer"""
    state = {"messages": [HumanMessage(content="你好")]}
    assert route_after_router(state) == "direct_answer"


def test_skill_executor_done():
    """调用 skill_complete 时应结束"""
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "skill_complete", "args": {"summary": "done"}, "id": "1"}],
    )
    state = {"messages": [msg]}
    assert route_after_skill_executor(state) == "done"


def test_skill_executor_continue():
    """调用其他 tool 时应继续"""
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "memory_write", "args": {"content": "test"}, "id": "1"}],
    )
    state = {"messages": [msg]}
    assert route_after_skill_executor(state) == "continue"


def test_skill_executor_no_tool_calls():
    """无 tool_calls 时应结束"""
    msg = AIMessage(content="分析完成，以下是报告...")
    state = {"messages": [msg]}
    assert route_after_skill_executor(state) == "done"
