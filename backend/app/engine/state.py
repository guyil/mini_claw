"""LangGraph Agent 状态定义"""

from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """所有节点共享的状态结构"""

    # 对话消息列表（LangGraph 内置 reducer，自动合并新消息）
    messages: Annotated[list, add_messages]

    # Bot 配置（从 DB 加载，只读）
    bot_config: dict[str, Any]

    # 当前 Bot 已启用的 Skill 摘要列表 [{name, description}]
    available_skills: list[dict[str, str]]

    # 当前正在执行的 Skill 名称（None 表示未激活）
    active_skill: str | None

    # 当前 Skill 的完整指令文本
    skill_instructions: str

    # 从 memory 检索到的上下文
    memory_context: str

    # 会话元数据
    session_key: str
    user_id: str
    bot_id: str
