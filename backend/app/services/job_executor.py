"""定时任务执行器 — 构建 Agent 图、非流式运行、收集响应、交付结果"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.scheduled_job import ScheduledJob

logger = logging.getLogger(__name__)


class JobExecutor:
    def __init__(self, timeout_seconds: int = 120):
        self._timeout = timeout_seconds

    async def execute(self, job_id: uuid.UUID) -> str:
        """执行定时任务：构建 Agent → 运行 → 交付结果

        Returns:
            AI 响应文本
        """
        async with async_session_factory() as db:
            result = await db.execute(
                select(ScheduledJob).where(ScheduledJob.id == job_id)
            )
            job = result.scalar_one_or_none()
            if not job:
                raise ValueError(f"任务不存在: {job_id}")
            if not job.enabled:
                raise ValueError(f"任务已禁用: {job_id}")

            job_data = {
                "id": job.id,
                "user_id": job.user_id,
                "bot_id": job.bot_id,
                "conversation_id": job.conversation_id,
                "payload_message": job.payload_message,
                "payload_config": job.payload_config,
                "delivery_mode": job.delivery_mode,
                "delivery_config": job.delivery_config,
                "name": job.name,
            }

        ai_response = await self._run_agent(job_data)

        await self._deliver(job_data, ai_response)

        return ai_response

    async def _run_agent(self, job_data: dict[str, Any]) -> str:
        """构建并运行 Agent 图，返回 AI 最终响应文本"""
        from app.engine.graph_builder import build_agent_graph

        user_id = str(job_data["user_id"])
        bot_id = str(job_data["bot_id"]) if job_data["bot_id"] else "default"
        session_key = f"scheduled-job:{job_data['id']}"
        payload_message = job_data["payload_message"]

        async with async_session_factory() as db:
            graph, initial_state = await build_agent_graph(
                db=db,
                bot_id=bot_id,
                user_id=user_id,
                session_key=session_key,
            )

            compiled = graph.compile()

            now_str = _format_current_time()
            enriched_message = (
                f"[定时任务触发 - {job_data['name']}]\n"
                f"当前时间: {now_str}\n\n"
                f"{payload_message}"
            )

            initial_state["messages"] = [HumanMessage(content=enriched_message)]

            config = {"configurable": {"thread_id": session_key}}
            final_state = await compiled.ainvoke(initial_state, config=config)

        return _extract_ai_response(final_state)

    async def _deliver(self, job_data: dict[str, Any], ai_response: str):
        """将 AI 响应交付给用户"""
        from app.services.delivery_service import DeliveryService

        delivery = DeliveryService()
        await delivery.deliver(
            mode=job_data["delivery_mode"],
            config=job_data["delivery_config"],
            user_id=job_data["user_id"],
            bot_id=job_data["bot_id"],
            conversation_id=job_data["conversation_id"],
            job_name=job_data["name"],
            content=ai_response,
        )


def _extract_ai_response(final_state: dict[str, Any]) -> str:
    """从 Agent 最终状态中提取 AI 响应文本"""
    messages = final_state.get("messages", [])

    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            content = msg.content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        parts.append(part.get("text", ""))
                    elif isinstance(part, str):
                        parts.append(part)
                return "\n".join(parts)
            if isinstance(content, str) and content.strip():
                return content

    return ""


def _format_current_time() -> str:
    """格式化当前时间（东八区）"""
    from datetime import datetime, timezone, timedelta
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst)
    return now.strftime("%Y-%m-%d %H:%M:%S CST")
