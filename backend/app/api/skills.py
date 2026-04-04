"""Skill CRUD API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user_id
from app.database import get_db
from app.schemas.skill import SkillCreate, SkillUpdate
from app.services.seed_skills import seed_builtin_skills
from app.services.skill_service import create_skill, list_skills, update_skill

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/")
async def list_skills_endpoint(
    db: AsyncSession = Depends(get_db),
):
    return await list_skills(db)


@router.post("/")
async def create_skill_endpoint(
    data: SkillCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await create_skill(db, data.model_dump(), created_by=user_id)
    return result


@router.post("/seed")
async def seed_skills_endpoint(db: AsyncSession = Depends(get_db)):
    """初始化内置预设 Skills（已存在则跳过）"""
    results = await seed_builtin_skills(db)
    await db.commit()
    return {"results": results}


@router.patch("/{skill_id}")
async def update_skill_endpoint(
    skill_id: str,
    data: SkillUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    update_data = data.model_dump(exclude_unset=True)
    result = await update_skill(db, skill_id, update_data)
    if result is None:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return result
