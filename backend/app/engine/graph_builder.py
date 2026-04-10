"""动态 LangGraph 构建器

为指定 Bot 动态构建 StateGraph：
1. 从 DB 加载 Bot 配置（soul, instructions, user_context, enabled_skills）
2. 加载 Skill 列表的摘要（name + description）
3. 组装 Tool 集合（内置 tools + Skill 依赖的 tools）
4. 构建图：memory → router → (direct_answer | skill_loader → skill_executor) → END
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.nodes import (
    memory_node,
    route_after_router,
    route_after_skill_executor,
    router_node,
    skill_executor_node,
    skill_loader_node,
)
from app.engine.state import AgentState
from app.services.bot_service import get_bot_config
from app.services.skill_service import get_skills_summary
from app.services.sandbox_pool import SandboxPoolManager
from app.tools.memory_tools import create_memory_tools
from app.tools.sandbox_tools import create_sandbox_tools
from app.tools.feishu_tools import create_feishu_tools
from app.tools.perplexity_tools import create_perplexity_tools
from app.tools.schedule_tools import create_schedule_tools
from app.tools.skill_install_tools import create_skill_install_tools
from app.tools.web_tools import create_web_tools

logger = logging.getLogger(__name__)


def _create_activate_skill_tool() -> BaseTool:
    """创建 activate_skill 工具 — Agent 用它来选择要执行的 Skill"""
    from langchain_core.tools import tool

    @tool
    def activate_skill(skill_name: str) -> str:
        """激活一个 Skill 开始执行。传入 Skill 名称。"""
        return f"Skill '{skill_name}' 已激活，正在加载指令..."

    return activate_skill


def _create_skill_complete_tool() -> BaseTool:
    """创建 skill_complete 工具 — 标记 Skill 执行完成"""
    from langchain_core.tools import tool

    @tool
    def skill_complete(summary: str) -> str:
        """标记当前 Skill 执行完成。传入执行摘要。"""
        return f"Skill 执行完成: {summary}"

    return skill_complete


def _get_default_bot_config() -> dict[str, Any]:
    """返回默认 Bot 配置（无 DB 时使用）"""
    from app.config import settings
    return {
        "id": "default",
        "name": "小爪助手",
        "soul": settings.default_bot_soul,
        "instructions": settings.default_bot_instructions,
        "user_context": None,
        "model_name": settings.default_model,
        "temperature": settings.default_temperature,
        "enabled_skills": [],
    }


async def build_agent_graph(
    db: AsyncSession | None,
    bot_id: str,
    user_id: str,
    session_key: str,
    reference_urls: list[str] | None = None,
    sandbox_pool: SandboxPoolManager | None = None,
) -> tuple[StateGraph, dict[str, Any]]:
    """为指定 Bot 动态构建 LangGraph StateGraph

    当 db 为 None 或 bot_id 为 "default" 时使用默认配置，不依赖数据库。

    Returns:
        (graph, initial_state) — graph 待 compile，initial_state 供 astream 使用
    """
    bot_config = None

    if db is not None and bot_id != "default":
        try:
            bot_config = await get_bot_config(db, bot_id)
        except (ValueError, Exception) as e:
            logger.warning("从 DB 加载 Bot 配置失败 (%s)，使用默认配置", e)

    if bot_config is None:
        bot_config = _get_default_bot_config()

    if db is not None and bot_config.get("enabled_skills"):
        skills_summary = await get_skills_summary(db, bot_config["enabled_skills"])
    else:
        skills_summary = []

    all_tools: list[BaseTool] = []
    all_tools.append(_create_activate_skill_tool())
    all_tools.append(_create_skill_complete_tool())
    all_tools.extend(create_memory_tools(db, bot_id))
    all_tools.extend(create_sandbox_tools(session_key, user_id, sandbox_pool=sandbox_pool))
    all_tools.extend(create_feishu_tools(db, user_id))
    all_tools.extend(create_web_tools(reference_urls=reference_urls))
    all_tools.extend(create_perplexity_tools())
    all_tools.extend(create_schedule_tools(user_id, bot_id, session_key))
    all_tools.extend(create_skill_install_tools(db, bot_id, user_id))

    shared_kwargs: dict[str, Any] = {
        "db": db,
        "tools": all_tools,
    }

    def _bind(fn, **extra):
        """将 db / tools 等注入到节点函数，同时传递 RunnableConfig 以支持流式事件追踪"""
        from langchain_core.runnables import RunnableConfig

        async def wrapper(state: AgentState, config: RunnableConfig) -> dict:
            return await fn(state, config=config, **{**shared_kwargs, **extra})
        wrapper.__name__ = fn.__name__
        return wrapper

    graph = StateGraph(AgentState)

    graph.add_node("memory", _bind(memory_node))
    graph.add_node("router", _bind(router_node))
    graph.add_node("tool_executor", ToolNode(all_tools))
    graph.add_node("skill_loader", _bind(skill_loader_node))
    graph.add_node("skill_executor", _bind(skill_executor_node))
    graph.add_node("skill_tool_executor", ToolNode(all_tools))

    graph.add_edge(START, "memory")
    graph.add_edge("memory", "router")

    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "direct_answer": END,
            "use_tool": "tool_executor",
            "use_skill": "skill_loader",
        },
    )

    graph.add_edge("tool_executor", "router")

    graph.add_edge("skill_loader", "skill_executor")
    graph.add_conditional_edges(
        "skill_executor",
        route_after_skill_executor,
        {
            "continue": "skill_tool_executor",
            "done": END,
        },
    )
    graph.add_edge("skill_tool_executor", "skill_executor")

    initial_state: dict[str, Any] = {
        "messages": [],
        "bot_config": bot_config,
        "available_skills": skills_summary,
        "active_skill": None,
        "skill_instructions": "",
        "skill_assets": [],
        "skill_required_tools": None,
        "memory_context": "",
        "session_key": session_key,
        "user_id": user_id,
        "bot_id": bot_id,
    }

    return graph, initial_state
