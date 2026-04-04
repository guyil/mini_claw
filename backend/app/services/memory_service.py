"""Memory 业务逻辑

处理记忆的 CRUD、语义搜索和会话启动时的自动加载。
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory


async def load_memory_context(
    db: AsyncSession,
    bot_id: str,
    user_message: str = "",
) -> str:
    """会话开始时加载记忆，拼装为文本注入 system prompt"""
    bid = uuid.UUID(bot_id)
    parts: list[str] = []

    # 1. 长期记忆（按重要性排序，最多 20 条）
    result = await db.execute(
        select(Memory.content)
        .where(Memory.bot_id == bid, Memory.type == "long_term")
        .order_by(Memory.importance.desc())
        .limit(20)
    )
    long_term = result.scalars().all()
    if long_term:
        items = "\n".join(f"- {m}" for m in long_term)
        parts.append(f"## 长期记忆\n{items}")

    # 2. 最近 2 天的日志
    cutoff = date.today() - timedelta(days=2)
    result = await db.execute(
        select(Memory.content, Memory.memory_date)
        .where(
            Memory.bot_id == bid,
            Memory.type == "daily",
            Memory.memory_date >= cutoff,
        )
        .order_by(Memory.memory_date.desc(), Memory.created_at.desc())
        .limit(10)
    )
    daily = result.all()
    if daily:
        items = "\n".join(f"- [{d.memory_date}] {d.content}" for d in daily)
        parts.append(f"## 近期工作日志\n{items}")

    return "\n\n".join(parts) if parts else ""


async def write_memory(
    db: AsyncSession,
    bot_id: str,
    content: str,
    memory_type: str = "long_term",
    importance: float = 0.5,
    source: str = "agent_learned",
) -> str:
    """写入一条记忆"""
    mem = Memory(
        bot_id=uuid.UUID(bot_id),
        type=memory_type,
        content=content,
        importance=importance,
        source=source,
        memory_date=date.today() if memory_type == "daily" else None,
    )
    db.add(mem)
    await db.commit()
    return str(mem.id)


async def search_memory(
    db: AsyncSession,
    bot_id: str,
    query: str,
    limit: int = 5,
) -> list[dict]:
    """搜索记忆（当前使用文本模糊匹配，后续可升级为向量搜索）"""
    bid = uuid.UUID(bot_id)
    cutoff = date.today() - timedelta(days=30)

    result = await db.execute(
        select(Memory)
        .where(
            Memory.bot_id == bid,
            Memory.content.ilike(f"%{query}%"),
        )
        .order_by(Memory.importance.desc())
        .limit(limit)
    )
    memories = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "type": m.type,
            "content": m.content,
            "importance": m.importance,
            "memory_date": str(m.memory_date) if m.memory_date else None,
        }
        for m in memories
    ]


async def update_memory(
    db: AsyncSession,
    memory_id: str,
    bot_id: str,
    new_content: str,
) -> bool:
    """更新一条记忆"""
    result = await db.execute(
        select(Memory).where(
            Memory.id == uuid.UUID(memory_id),
            Memory.bot_id == uuid.UUID(bot_id),
        )
    )
    mem = result.scalar_one_or_none()
    if mem is None:
        return False

    mem.content = new_content
    await db.flush()
    return True


async def delete_memory(
    db: AsyncSession,
    memory_id: str,
    bot_id: str,
) -> bool:
    """删除一条记忆"""
    result = await db.execute(
        select(Memory).where(
            Memory.id == uuid.UUID(memory_id),
            Memory.bot_id == uuid.UUID(bot_id),
        )
    )
    mem = result.scalar_one_or_none()
    if mem is None:
        return False

    await db.delete(mem)
    await db.flush()
    return True


async def get_recent_memories(
    db: AsyncSession,
    bot_id: str,
    days: int = 2,
) -> list[dict]:
    """获取最近 N 天的日志"""
    bid = uuid.UUID(bot_id)
    cutoff = date.today() - timedelta(days=days)

    result = await db.execute(
        select(Memory)
        .where(
            Memory.bot_id == bid,
            Memory.type == "daily",
            Memory.memory_date >= cutoff,
        )
        .order_by(Memory.memory_date.desc(), Memory.created_at.desc())
    )
    memories = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "content": m.content,
            "memory_date": str(m.memory_date) if m.memory_date else None,
        }
        for m in memories
    ]
