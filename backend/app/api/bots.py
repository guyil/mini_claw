"""Bot CRUD API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user_id
from app.database import get_db
from app.schemas.bot import BotCreate, BotUpdate
from app.services.bot_service import create_bot, get_bot_config, list_bots, update_bot

router = APIRouter(prefix="/bots", tags=["bots"])


@router.get("/")
async def list_bots_endpoint(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await list_bots(db, user_id)


@router.post("/")
async def create_bot_endpoint(
    data: BotCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await create_bot(db, user_id, data.model_dump())
    return result


@router.get("/{bot_id}")
async def get_bot_endpoint(
    bot_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    bot = await get_bot_config(db, bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot 不存在")
    return bot


@router.patch("/{bot_id}")
async def update_bot_endpoint(
    bot_id: str,
    data: BotUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    update_data = data.model_dump(exclude_unset=True)
    result = await update_bot(db, bot_id, update_data)
    if result is None:
        raise HTTPException(status_code=404, detail="Bot 不存在")
    return result
