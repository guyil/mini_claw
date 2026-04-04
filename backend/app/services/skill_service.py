"""Skill 业务逻辑"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill


async def get_skills_summary(
    db: AsyncSession, skill_ids: list[str]
) -> list[dict[str, str]]:
    """获取 Skill 列表的摘要信息（name + description），用于注入 system prompt"""
    if not skill_ids:
        return []

    uuids = [uuid.UUID(s) for s in skill_ids]
    result = await db.execute(
        select(Skill.name, Skill.description)
        .where(Skill.id.in_(uuids), Skill.is_active.is_(True))
    )
    return [{"name": row.name, "description": row.description} for row in result.all()]


async def get_skill_instructions(db: AsyncSession, skill_name: str) -> str | None:
    """获取 Skill 的完整指令文本"""
    result = await db.execute(
        select(Skill.instructions).where(Skill.name == skill_name)
    )
    row = result.scalar_one_or_none()
    return row


async def list_skills(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Skill).where(Skill.is_active.is_(True)).order_by(Skill.category, Skill.name)
    )
    skills = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "display_name": s.display_name,
            "description": s.description,
            "category": s.category,
            "version": s.version,
            "required_tools": s.required_tools or [],
            "scope": s.scope,
        }
        for s in skills
    ]


async def create_skill(db: AsyncSession, data: dict, created_by: str | None = None) -> dict:
    skill = Skill(
        name=data["name"],
        display_name=data.get("display_name"),
        description=data["description"],
        category=data.get("category"),
        version=data.get("version", "1.0.0"),
        instructions=data["instructions"],
        required_tools=data.get("required_tools", []),
        required_env_vars=data.get("required_env_vars", []),
        input_schema=data.get("input_schema"),
        output_schema=data.get("output_schema"),
        scope=data.get("scope", "global"),
        source=data.get("source"),
        source_url=data.get("source_url"),
        created_by=uuid.UUID(created_by) if created_by else None,
    )
    db.add(skill)
    await db.flush()
    return {"id": str(skill.id), "name": skill.name}


async def update_skill(db: AsyncSession, skill_id: str, data: dict) -> dict | None:
    result = await db.execute(select(Skill).where(Skill.id == uuid.UUID(skill_id)))
    skill = result.scalar_one_or_none()
    if skill is None:
        return None

    updatable = (
        "name", "display_name", "description", "category", "version",
        "instructions", "required_tools", "required_env_vars",
        "input_schema", "output_schema", "scope",
    )
    for key in updatable:
        if key in data:
            setattr(skill, key, data[key])

    await db.flush()
    return {"id": str(skill.id), "name": skill.name}
