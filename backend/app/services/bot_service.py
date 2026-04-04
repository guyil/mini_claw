"""Bot 业务逻辑"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bot import Bot


async def get_bot_config(db: AsyncSession, bot_id: str) -> dict[str, Any] | None:
    """从数据库加载 Bot 配置（用于构建 Agent Graph）"""
    result = await db.execute(select(Bot).where(Bot.id == uuid.UUID(bot_id)))
    bot = result.scalar_one_or_none()
    if bot is None:
        return None

    return {
        "id": str(bot.id),
        "name": bot.name,
        "soul": bot.soul,
        "instructions": bot.instructions,
        "user_context": bot.user_context,
        "model_name": bot.model_name,
        "temperature": bot.temperature,
        "enabled_skills": [str(s) for s in (bot.enabled_skills or [])],
    }


async def list_bots(db: AsyncSession, owner_id: str) -> list[dict]:
    result = await db.execute(
        select(Bot).where(Bot.owner_id == uuid.UUID(owner_id), Bot.is_active.is_(True))
    )
    bots = result.scalars().all()
    return [
        {
            "id": str(b.id),
            "name": b.name,
            "model_name": b.model_name,
            "is_active": b.is_active,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in bots
    ]


async def create_bot(db: AsyncSession, owner_id: str, data: dict) -> dict:
    bot = Bot(
        owner_id=uuid.UUID(owner_id),
        name=data["name"],
        soul=data["soul"],
        instructions=data.get("instructions"),
        user_context=data.get("user_context"),
        model_name=data.get("model_name", "openai/gpt-4o-mini"),
        temperature=data.get("temperature", 0.7),
        enabled_skills=[uuid.UUID(s) for s in data.get("enabled_skills", [])],
    )
    db.add(bot)
    await db.flush()
    return {"id": str(bot.id), "name": bot.name}


async def update_bot(db: AsyncSession, bot_id: str, data: dict) -> dict | None:
    result = await db.execute(select(Bot).where(Bot.id == uuid.UUID(bot_id)))
    bot = result.scalar_one_or_none()
    if bot is None:
        return None

    for key in ("name", "soul", "instructions", "user_context", "model_name", "temperature"):
        if key in data:
            setattr(bot, key, data[key])

    if "enabled_skills" in data:
        bot.enabled_skills = [uuid.UUID(s) for s in data["enabled_skills"]]

    await db.flush()
    return {"id": str(bot.id), "name": bot.name}
