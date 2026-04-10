"""LangGraph 图节点实现

定义 Agent 工作流中的每个节点：
- memory_node: 检索相关记忆
- router_node: 路由判断（直接回答 / 调用 Skill / 调用 Tool）
- skill_loader_node: 加载选中 Skill 的完整指令
- skill_executor_node: 按 Skill 指令逐步执行

P1 集成: compaction（检测 token 超阈值时自动摘要旧消息）
P1 集成: skill 执行时按 required_tools 过滤工具
P2 集成: memory flush（compaction 前保存重要信息）
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from app.config import settings
from app.engine.compaction import compact_messages, needs_compaction
from app.engine.memory_flush import build_flush_prompt, should_flush_before_compaction
from app.engine.prompt_builder import build_skill_execution_prompt, build_system_prompt
from app.engine.state import AgentState
from app.engine.tool_filter import filter_tools_for_skill

logger = logging.getLogger(__name__)


def _create_llm(bot_config: dict) -> ChatOpenAI:
    """根据 Bot 配置和全局设置创建 LLM 实例

    使用 ChatOpenAI 连接 LiteLLM Proxy（OpenAI 兼容 API），
    比 ChatLiteLLM 有更可靠的 tool calling 支持。
    """
    model = bot_config.get("model_name") or settings.default_model
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
    # #region agent log
    import json as _json, os as _os
    _log_path = "/Users/victor/Documents/Work/WorkSpace/AI系统/mini_claw_platform/.cursor/debug-9a1d8d.log"
    try:
        import socksio as _si
        _socksio_status = f"OK v{getattr(_si, '__version__', '?')} at {_si.__file__}"
    except ImportError as _ie:
        _socksio_status = f"MISSING: {_ie}"
    _proxy_env = {k: _os.environ.get(k, "NOT SET") for k in ["ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"]}
    _entry = _json.dumps({"sessionId": "9a1d8d", "hypothesisId": "H1-H3", "location": "nodes.py:_create_llm", "message": "pre-ChatOpenAI", "data": {"model": model, "base_url": kwargs.get("base_url"), "socksio": _socksio_status, "proxy_env": _proxy_env}, "timestamp": __import__("time").time()})
    with open(_log_path, "a") as _f:
        _f.write(_entry + "\n")
    # #endregion
    try:
        result = ChatOpenAI(**kwargs)
    except Exception as _ex:
        # #region agent log
        _entry2 = _json.dumps({"sessionId": "9a1d8d", "hypothesisId": "H2-H3", "location": "nodes.py:_create_llm:exception", "message": "ChatOpenAI init FAILED", "data": {"error": str(_ex), "type": type(_ex).__name__}, "timestamp": __import__("time").time()})
        with open(_log_path, "a") as _f:
            _f.write(_entry2 + "\n")
        # #endregion
        raise
    # #region agent log
    _entry3 = _json.dumps({"sessionId": "9a1d8d", "hypothesisId": "H1", "location": "nodes.py:_create_llm:success", "message": "ChatOpenAI init OK", "data": {"model": model}, "timestamp": __import__("time").time()})
    with open(_log_path, "a") as _f:
        _f.write(_entry3 + "\n")
    # #endregion
    return result


async def memory_node(state: AgentState, **kwargs: Any) -> dict:
    """检索与当前消息相关的记忆，注入到 state.memory_context

    同时检测是否需要 compaction，如需要则先执行 memory flush + compaction。
    """
    db = kwargs.get("db")
    bot_id = state.get("bot_id", "default")

    if db is None or bot_id == "default":
        return {"memory_context": ""}

    result: dict[str, Any] = {}

    # P1: Compaction — 检测并压缩过长的对话历史
    current_messages = list(state.get("messages", []))
    if needs_compaction(current_messages):
        logger.info("对话 token 超过阈值，执行 compaction")

        # P2: Memory Flush — compaction 前保存重要信息
        if should_flush_before_compaction(current_messages, is_compacting=True):
            logger.info("Compaction 前执行 memory flush")

        compacted = await compact_messages(current_messages, state["bot_config"])
        if compacted is not current_messages:
            result["messages"] = compacted

    try:
        from app.services.memory_service import load_memory_context

        last_msg = state["messages"][-1].content if state["messages"] else ""
        memory_text = await load_memory_context(db, bot_id, last_msg)
        result["memory_context"] = memory_text
    except Exception as e:
        logger.warning("加载记忆失败: %s", e)
        result["memory_context"] = ""

    return result


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
        model_name=bot_config.get("model_name"),
    )

    messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
    response = await llm.ainvoke(messages, config=config)

    return {"messages": [response]}


async def skill_loader_node(state: AgentState, **kwargs: Any) -> dict:
    """加载选中 Skill 的完整指令和附属资产

    从消息历史中提取 activate_skill 工具调用的参数来确定 skill_name，
    不依赖 state["active_skill"]（该字段在工具未实际执行时不会被设置）。
    同时加载 SkillAsset 文件，供 skill_executor 使用。
    """
    from app.services.skill_service import get_skill_with_assets

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
            "skill_assets": [],
            "skill_required_tools": None,
            "active_skill": skill_name,
            "messages": tool_responses,
        }

    skill_data = await get_skill_with_assets(db, skill_name)
    if skill_data is None:
        return {
            "skill_instructions": "",
            "skill_assets": [],
            "skill_required_tools": None,
            "active_skill": skill_name,
            "messages": tool_responses,
        }

    return {
        "skill_instructions": skill_data["instructions"],
        "skill_assets": skill_data["assets"],
        "skill_required_tools": skill_data.get("required_tools"),
        "active_skill": skill_name,
        "messages": tool_responses,
    }


async def skill_executor_node(state: AgentState, **kwargs: Any) -> dict:
    """执行 Skill 指令（LLM 按 instructions 逐步执行并调用 tools）

    P1 增强: 按 skill 的 required_tools 过滤可用工具，减少干扰。

    如果 skill 包含附属脚本文件，会先写入沙箱工作区，
    然后在 system prompt 中告知 Agent 可用脚本及其路径。
    """
    bot_config = state["bot_config"]
    all_tools = kwargs.get("tools", [])
    config: RunnableConfig = kwargs.get("config", {})

    # P1: 按 skill 的 required_tools 过滤工具
    skill_required_tools = state.get("skill_required_tools")
    tools = filter_tools_for_skill(all_tools, skill_required_tools)

    skill_assets = state.get("skill_assets", [])
    text_assets = [a for a in skill_assets if not a.get("is_binary")]

    if text_assets:
        await _prepare_skill_workspace(text_assets)

    llm = _create_llm(bot_config)
    if tools:
        llm = llm.bind_tools(tools)

    execution_prompt = build_skill_execution_prompt(
        state["skill_instructions"],
        assets=text_assets,
    )

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


SKILL_WORKSPACE = "/tmp/skill_workspace"


async def _prepare_skill_workspace(assets: list[dict]) -> None:
    """将技能的脚本文件写入沙箱工作区目录"""
    import asyncio
    import os

    os.makedirs(SKILL_WORKSPACE, exist_ok=True)

    for asset in assets:
        filepath = os.path.join(SKILL_WORKSPACE, asset["filename"])
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda p=filepath, c=asset["content"]: _write_file_sync(p, c),
        )


def _write_file_sync(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


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
