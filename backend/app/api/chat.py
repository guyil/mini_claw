"""Chat API — /assistant 端点

使用 assistant-stream 协议与前端 assistant-ui 对接。
前端使用 useAssistantTransportRuntime，期望 aui-state 协议（state 更新），
通过 append_langgraph_event 将 LangGraph 流式事件映射到 controller.state。
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from jose import JWTError, jwt
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from assistant_stream import RunController, create_run
from assistant_stream.modules.langgraph import append_langgraph_event
from assistant_stream.serialization import DataStreamResponse

from app.config import settings
from app.database import get_db_optional
from app.engine.graph_builder import build_agent_graph
from app.models.bot import Bot
from app.models.conversation import Conversation

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_user_id_from_token(request: Request) -> str | None:
    """尝试从 Authorization header 中解析 user_id，失败则返回 None"""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


async def _resolve_bot_id(db: AsyncSession | None, user_id: str | None) -> str:
    """自动解析用户的 Bot ID"""
    if db is None:
        return "default"

    if user_id:
        try:
            result = await db.execute(
                select(Bot.id)
                .where(Bot.owner_id == uuid.UUID(user_id), Bot.is_active.is_(True))
                .limit(1)
            )
            row = result.fetchone()
            if row:
                return str(row[0])
        except Exception:
            pass

    try:
        result = await db.execute(
            select(Bot.id).where(Bot.is_active.is_(True)).order_by(Bot.created_at).limit(1)
        )
        row = result.fetchone()
        if row:
            return str(row[0])
    except Exception:
        pass

    return "default"


async def _auto_title(db: AsyncSession, conv_id: uuid.UUID, first_message: str):
    """用首条消息自动生成对话标题（取前 30 字）"""
    title = first_message.strip()[:30]
    if not title:
        return
    try:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conv = result.scalar_one_or_none()
        if conv and conv.title == "新对话":
            conv.title = title
            await db.flush()
    except Exception:
        pass


def _state_messages_to_langchain(state_messages: list[dict[str, Any]]) -> list:
    """将 controller.state 中的消息（LangChain JSON 格式）转换为 LangChain 消息对象

    前端通过 assistant-transport 协议传回的 state.messages 包含完整的对话历史。
    每条消息的 type 字段标识角色：human / ai / tool。
    """
    lc_messages = []
    for msg in state_messages:
        if not isinstance(msg, dict):
            continue
        msg_type = msg.get("type", "")
        content = msg.get("content", "")

        if msg_type == "human":
            lc_messages.append(HumanMessage(content=content))
        elif msg_type == "ai":
            kwargs: dict[str, Any] = {"content": content}
            if msg.get("tool_calls"):
                kwargs["tool_calls"] = msg["tool_calls"]
            if msg.get("id"):
                kwargs["id"] = msg["id"]
            lc_messages.append(AIMessage(**kwargs))
        elif msg_type == "tool":
            lc_messages.append(ToolMessage(
                content=content,
                tool_call_id=msg.get("tool_call_id", ""),
            ))

    return lc_messages


@router.post("/assistant")
async def chat_endpoint(
    request: Request,
    db: AsyncSession | None = Depends(get_db_optional),
):
    """assistant-transport 协议的主端点"""
    body = await request.json()

    state = body.get("state")
    commands = body.get("commands", [])
    thread_id = body.get("threadId")

    jwt_user_id = _extract_user_id_from_token(request)
    user_id = jwt_user_id or body.get("user_id", str(uuid.uuid4()))

    bot_id = await _resolve_bot_id(db, jwt_user_id)

    input_messages: list[HumanMessage] = []
    for cmd in commands:
        if cmd.get("type") == "add-message":
            msg = cmd.get("message", {})
            parts = msg.get("parts", [])
            text_parts = [
                p.get("text", "") for p in parts
                if p.get("type") == "text" and p.get("text")
            ]
            if text_parts:
                input_messages.append(HumanMessage(content=" ".join(text_parts)))

    url_pattern = re.compile(r"https?://[^\s<>\"']+")
    reference_urls: list[str] = []
    for msg in input_messages:
        reference_urls.extend(url_pattern.findall(msg.content))

    if thread_id and db and jwt_user_id and input_messages:
        try:
            conv_uuid = uuid.UUID(thread_id)
            await _auto_title(db, conv_uuid, input_messages[0].content)
        except (ValueError, Exception):
            pass

    session_key = f"bot-{bot_id}:user-{user_id}:session-{thread_id or 'default'}"

    async def run_callback(controller: RunController):
        if controller.state is None:
            controller.state = {}
        if "messages" not in controller.state:
            controller.state["messages"] = []

        history_lc = _state_messages_to_langchain(controller.state["messages"])

        for msg in input_messages:
            controller.state["messages"].append({
                "type": "human",
                "content": msg.content,
            })

        graph, initial_state = await build_agent_graph(
            db=db,
            bot_id=bot_id,
            user_id=user_id,
            session_key=session_key,
            reference_urls=reference_urls,
        )
        compiled = graph.compile()
        config = {"configurable": {"thread_id": session_key}}

        initial_state["messages"] = history_lc + input_messages

        async for namespace, event_type, chunk in compiled.astream(
            initial_state,
            config=config,
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            append_langgraph_event(
                controller.state,
                namespace,
                event_type,
                chunk,
            )

    stream = create_run(run_callback, state=state)
    return DataStreamResponse(stream)
