"""LangGraph 图节点实现

定义 Agent 工作流中的每个节点：
- memory_node: 检索相关记忆
- router_node: 路由判断（直接回答 / 调用 Skill / 调用 Tool）
- skill_loader_node: 加载选中 Skill 的完整指令
- skill_executor_node: 按 Skill 指令逐步执行
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from app.config import settings
from app.engine.prompt_builder import build_skill_execution_prompt, build_system_prompt
from app.engine.state import AgentState

logger = logging.getLogger(__name__)


def _create_llm(bot_config: dict) -> ChatOpenAI:
    """根据 Bot 配置和全局设置创建 LLM 实例

    使用 ChatOpenAI 连接 LiteLLM Proxy（OpenAI 兼容 API），
    比 ChatLiteLLM 有更可靠的 tool calling 支持。
    """
    model = bot_config.get("model_name", settings.default_model)
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": bot_config.get("temperature", settings.default_temperature),
        "streaming": True,
    }
    if settings.litellm_api_base:
        base = settings.litellm_api_base.rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        kwargs["base_url"] = base
    if settings.litellm_api_key:
        kwargs["api_key"] = settings.litellm_api_key
    return ChatOpenAI(**kwargs)


async def memory_node(state: AgentState, **kwargs: Any) -> dict:
    """检索与当前消息相关的记忆，注入到 state.memory_context"""
    db = kwargs.get("db")
    bot_id = state.get("bot_id", "default")

    if db is None or bot_id == "default":
        return {"memory_context": ""}

    try:
        from app.services.memory_service import load_memory_context

        last_msg = state["messages"][-1].content if state["messages"] else ""
        memory_text = await load_memory_context(db, bot_id, last_msg)
        return {"memory_context": memory_text}
    except Exception as e:
        logger.warning("加载记忆失败: %s", e)
        return {"memory_context": ""}


async def router_node(state: AgentState, **kwargs: Any) -> dict:
    """路由节点：LLM 判断直接回答还是需要调用 Skill"""
    bot_config = state["bot_config"]
    tools = kwargs.get("tools", [])
    config: RunnableConfig = kwargs.get("config", {})

    llm = _create_llm(bot_config)
    if tools:
        llm = llm.bind_tools(tools)

    system_prompt = build_system_prompt(
        soul=bot_config.get("soul", ""),
        instructions=bot_config.get("instructions"),
        user_context=bot_config.get("user_context"),
        skills=state.get("available_skills", []),
        memory=state.get("memory_context", ""),
    )

    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    response = await llm.ainvoke(messages, config=config)

    return {"messages": [response]}


async def skill_loader_node(state: AgentState, **kwargs: Any) -> dict:
    """加载选中 Skill 的完整指令

    从消息历史中提取 activate_skill 工具调用的参数来确定 skill_name，
    不依赖 state["active_skill"]（该字段在工具未实际执行时不会被设置）。
    """
    from app.services.skill_service import get_skill_instructions

    db = kwargs.get("db")
    skill_name = state.get("active_skill")

    if not skill_name:
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc["name"] == "activate_skill":
                        skill_name = tc["args"].get("skill_name", "")
                        break
            if skill_name:
                break

    tool_responses: list[ToolMessage] = []
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["name"] == "activate_skill":
                    tool_responses.append(
                        ToolMessage(
                            content=f"Skill '{skill_name}' 已激活，正在加载指令...",
                            tool_call_id=tc["id"],
                            name="activate_skill",
                        )
                    )
            break

    if not skill_name or db is None:
        return {
            "skill_instructions": "",
            "active_skill": skill_name,
            "messages": tool_responses,
        }

    instructions = await get_skill_instructions(db, skill_name)
    return {
        "skill_instructions": instructions or "",
        "active_skill": skill_name,
        "messages": tool_responses,
    }


async def skill_executor_node(state: AgentState, **kwargs: Any) -> dict:
    """执行 Skill 指令（LLM 按 instructions 逐步执行并调用 tools）"""
    bot_config = state["bot_config"]
    tools = kwargs.get("tools", [])
    config: RunnableConfig = kwargs.get("config", {})

    llm = _create_llm(bot_config)
    if tools:
        llm = llm.bind_tools(tools)

    execution_prompt = build_skill_execution_prompt(state["skill_instructions"])

    messages = [SystemMessage(content=execution_prompt)] + list(state["messages"])
    response = await llm.ainvoke(messages, config=config)

    result_messages: list = [response]

    if isinstance(response, AIMessage) and response.tool_calls:
        for tc in response.tool_calls:
            if tc["name"] == "skill_complete":
                result_messages.append(
                    ToolMessage(
                        content=tc["args"].get("summary", "Skill 执行完成"),
                        tool_call_id=tc["id"],
                        name="skill_complete",
                    )
                )

    return {"messages": result_messages}


def route_after_router(state: AgentState) -> str:
    """路由条件：检查最后一条 AI 消息是否调用了 activate_skill"""
    last_msg = state["messages"][-1]

    if not isinstance(last_msg, AIMessage):
        return "direct_answer"

    if last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            if tc["name"] == "activate_skill":
                return "use_skill"
        return "use_tool"

    return "direct_answer"


def route_after_skill_executor(state: AgentState) -> str:
    """Skill 执行后检查是否完成"""
    last_msg = state["messages"][-1]

    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        for tc in last_msg.tool_calls:
            if tc["name"] == "skill_complete":
                return "done"
        return "continue"

    return "done"
