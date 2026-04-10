"""管理面板 API — 只读查看所有 Agent 信息"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user_id
from app.database import get_db
from app.models.bot import Bot
from app.models.conversation import Conversation
from app.models.memory import Memory
from app.models.skill import Skill

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/agents")
async def list_all_agents(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取所有 Agent（Bot）详情，包含关联的用户、技能、记忆统计"""
    result = await db.execute(
        select(Bot).options(selectinload(Bot.owner)).order_by(Bot.created_at.desc())
    )
    bots = result.scalars().all()

    all_skill_ids: set[uuid.UUID] = set()
    for bot in bots:
        if bot.enabled_skills:
            all_skill_ids.update(bot.enabled_skills)

    skills_map: dict[uuid.UUID, dict] = {}
    if all_skill_ids:
        skill_result = await db.execute(
            select(Skill).where(Skill.id.in_(all_skill_ids))
        )
        for s in skill_result.scalars().all():
            skills_map[s.id] = {
                "id": str(s.id),
                "name": s.name,
                "display_name": s.display_name,
                "description": s.description,
                "category": s.category,
                "version": s.version,
                "instructions": s.instructions,
                "required_tools": s.required_tools or [],
                "scope": s.scope,
                "is_active": s.is_active,
            }

    bot_ids = [bot.id for bot in bots]

    memory_counts: dict[uuid.UUID, dict[str, int]] = {}
    if bot_ids:
        mem_result = await db.execute(
            select(Memory.bot_id, Memory.type, func.count(Memory.id))
            .where(Memory.bot_id.in_(bot_ids))
            .group_by(Memory.bot_id, Memory.type)
        )
        for bot_id, mem_type, cnt in mem_result:
            memory_counts.setdefault(bot_id, {})[mem_type] = cnt

    conv_counts: dict[uuid.UUID, int] = {}
    if bot_ids:
        conv_result = await db.execute(
            select(Conversation.bot_id, func.count(Conversation.id))
            .where(Conversation.bot_id.in_(bot_ids))
            .group_by(Conversation.bot_id)
        )
        for bot_id, cnt in conv_result:
            conv_counts[bot_id] = cnt

    agents = []
    for bot in bots:
        skills = []
        if bot.enabled_skills:
            for sid in bot.enabled_skills:
                if sid in skills_map:
                    skills.append(skills_map[sid])
                else:
                    skills.append({"id": str(sid), "name": "未知技能", "is_active": False})

        owner = bot.owner
        agents.append({
            "id": str(bot.id),
            "name": bot.name,
            "is_active": bot.is_active,
            "model_name": bot.model_name,
            "temperature": bot.temperature,
            "soul": bot.soul,
            "instructions": bot.instructions,
            "user_context": bot.user_context,
            "created_at": bot.created_at.isoformat() if bot.created_at else None,
            "updated_at": bot.updated_at.isoformat() if bot.updated_at else None,
            "owner": {
                "id": str(owner.id),
                "username": owner.username,
                "display_name": owner.display_name,
                "email": owner.email,
            } if owner else None,
            "skills": skills,
            "memory_stats": memory_counts.get(bot.id, {}),
            "conversation_count": conv_counts.get(bot.id, 0),
        })

    return agents


@router.get("/agents/{bot_id}/memories")
async def get_agent_memories(
    bot_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """获取指定 Agent 的所有记忆条目"""
    bot_uuid = uuid.UUID(bot_id)

    bot_result = await db.execute(select(Bot.id).where(Bot.id == bot_uuid))
    if bot_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Agent 不存在")

    result = await db.execute(
        select(Memory)
        .where(Memory.bot_id == bot_uuid)
        .order_by(Memory.created_at.desc())
    )
    memories = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "type": m.type,
            "content": m.content,
            "source": m.source,
            "importance": m.importance,
            "memory_date": m.memory_date.isoformat() if m.memory_date else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "expires_at": m.expires_at.isoformat() if m.expires_at else None,
        }
        for m in memories
    ]
