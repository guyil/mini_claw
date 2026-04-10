"""对话管理 API

提供：
- GET  /conversations              — 当前用户的对话列表
- POST /conversations              — 创建新对话
- PATCH /conversations/{id}        — 更新对话标题
- DELETE /conversations/{id}       — 删除对话
- GET  /conversations/{id}/messages — 获取对话历史消息
- GET  /user/bot                   — 获取/自动创建当前用户的 Bot
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user_id
from app.config import settings
from app.database import get_db
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.skill import Skill

router = APIRouter(tags=["conversations"])


class ConversationCreate(BaseModel):
    title: str = "新对话"


class ConversationUpdate(BaseModel):
    title: str


# ── 用户 Bot 自动匹配/创建 ────────────────────────────


@router.get("/user/bot")
async def get_or_create_user_bot(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的 Bot，如不存在则自动创建"""
    uid = uuid.UUID(user_id)

    result = await db.execute(
        select(Bot).where(Bot.owner_id == uid, Bot.is_active.is_(True)).limit(1)
    )
    bot = result.scalar_one_or_none()

    if bot is None:
        skill_result = await db.execute(
            select(Skill.id).where(Skill.is_active.is_(True))
        )
        skill_ids = [row[0] for row in skill_result.fetchall()]

        bot = Bot(
            owner_id=uid,
            name="小爪助手",
            soul=settings.default_bot_soul,
            instructions=settings.default_bot_instructions,
            model_name=settings.default_model,
            temperature=settings.default_temperature,
            enabled_skills=skill_ids,
        )
        db.add(bot)
        await db.flush()
        await db.commit()

    return {
        "id": str(bot.id),
        "name": bot.name,
        "soul": bot.soul[:100],
        "model_name": bot.model_name,
    }


# ── 对话 CRUD ────────────────────────────────────────


@router.get("/conversations")
async def list_conversations(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户的所有对话，按更新时间倒序"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == uuid.UUID(user_id))
        .order_by(Conversation.updated_at.desc())
    )
    convs = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convs
    ]


@router.post("/conversations")
async def create_conversation(
    data: ConversationCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """创建新对话"""
    uid = uuid.UUID(user_id)

    result = await db.execute(
        select(Bot).where(Bot.owner_id == uid, Bot.is_active.is_(True)).limit(1)
    )
    bot = result.scalar_one_or_none()
    if bot is None:
        raise HTTPException(status_code=400, detail="请先创建 Bot")

    conv = Conversation(
        user_id=uid,
        bot_id=bot.id,
        title=data.title,
    )
    db.add(conv)
    await db.flush()
    await db.commit()

    return {
        "id": str(conv.id),
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
    }


@router.patch("/conversations/{conv_id}")
async def update_conversation(
    conv_id: str,
    data: ConversationUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """更新对话标题"""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == uuid.UUID(conv_id),
            Conversation.user_id == uuid.UUID(user_id),
        )
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    conv.title = data.title
    await db.flush()
    await db.commit()
    return {"id": str(conv.id), "title": conv.title}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """删除对话"""
    await db.execute(
        delete(Conversation).where(
            Conversation.id == uuid.UUID(conv_id),
            Conversation.user_id == uuid.UUID(user_id),
        )
    )
    await db.commit()
    return {"ok": True}


@router.get("/conversations/{conv_id}/messages")
async def get_conversation_messages(
    conv_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取对话的历史消息，用于前端恢复对话上下文"""
    conv_uuid = uuid.UUID(conv_id)

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid,
            Conversation.user_id == uuid.UUID(user_id),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_uuid)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    return [
        {
            "type": msg.role,
            "content": msg.content,
            **(
                {
                    k: v
                    for k, v in (msg.metadata_ or {}).items()
                    if k in ("tool_calls", "id", "tool_call_id")
                }
            ),
        }
        for msg in messages
    ]
