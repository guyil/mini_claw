"""Memory 业务逻辑

处理记忆的 CRUD、语义搜索和会话启动时的自动加载。
支持 pgvector 向量搜索（P0），当 embedding 不可用时回退到 ILIKE。
支持查询条件化加载（P1），根据用户消息做语义检索。
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory
from app.services.embedding_service import compute_embedding

logger = logging.getLogger(__name__)


async def load_memory_context(
    db: AsyncSession,
    bot_id: str,
    user_message: str = "",
) -> str:
    """会话开始时加载记忆，拼装为文本注入 system prompt

    P1 增强：当 user_message 非空时，使用语义检索返回最相关的记忆，
    而非固定 top-N。无 embedding 时回退到原有逻辑。
    """
    bid = uuid.UUID(bot_id)
    parts: list[str] = []

    if user_message and user_message.strip():
        relevant = await _load_relevant_memories(db, bid, user_message)
        if relevant:
            items = "\n".join(f"- {m}" for m in relevant)
            parts.append(f"## 相关记忆\n{items}")

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


async def _load_relevant_memories(
    db: AsyncSession,
    bot_id: uuid.UUID,
    user_message: str,
    limit: int = 10,
) -> list[str]:
    """根据用户消息做语义检索，返回最相关的记忆内容"""
    query_embedding = await compute_embedding(user_message)
    if query_embedding is None:
        return []

    try:
        result = await db.execute(
            select(Memory.content)
            .where(
                Memory.bot_id == bot_id,
                Memory.embedding.isnot(None),
            )
            .order_by(Memory.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        return list(result.scalars().all())
    except Exception as e:
        logger.warning("语义检索记忆失败: %s", e)
        return []


async def write_memory(
    db: AsyncSession,
    bot_id: str,
    content: str,
    memory_type: str = "long_term",
    importance: float = 0.5,
    source: str = "agent_learned",
) -> str:
    """写入一条记忆，同时计算并存储 embedding"""
    embedding = await compute_embedding(content)

    mem = Memory(
        bot_id=uuid.UUID(bot_id),
        type=memory_type,
        content=content,
        embedding=embedding,
        importance=importance,
        source=source,
        memory_date=date.today() if memory_type == "daily" else None,
    )
    db.add(mem)
    await db.flush()
    return str(mem.id)


async def search_memory(
    db: AsyncSession,
    bot_id: str,
    query: str,
    limit: int = 5,
) -> list[dict]:
    """搜索记忆 — 优先使用向量搜索，无 embedding 时回退到 ILIKE"""
    bid = uuid.UUID(bot_id)
    query_embedding = await compute_embedding(query)

    if query_embedding is not None:
        return await _vector_search(db, bid, query_embedding, query, limit)
    return await _ilike_search(db, bid, query, limit)


async def _vector_search(
    db: AsyncSession,
    bot_id: uuid.UUID,
    query_embedding: list[float],
    query_text: str,
    limit: int,
) -> list[dict]:
    """混合搜索：vector cosine + ILIKE 双路合并"""
    try:
        # 向量搜索
        vec_result = await db.execute(
            select(
                Memory,
                Memory.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(
                Memory.bot_id == bot_id,
                Memory.embedding.isnot(None),
            )
            .order_by("distance")
            .limit(limit)
        )
        vec_memories = vec_result.all()

        # ILIKE 搜索补充
        ilike_result = await db.execute(
            select(Memory)
            .where(
                Memory.bot_id == bot_id,
                Memory.content.ilike(f"%{query_text}%"),
            )
            .order_by(Memory.importance.desc())
            .limit(limit)
        )
        ilike_memories = ilike_result.scalars().all()

        # 合并去重，向量结果优先
        seen_ids: set[uuid.UUID] = set()
        results: list[dict] = []

        for mem, distance in vec_memories:
            if mem.id not in seen_ids:
                seen_ids.add(mem.id)
                results.append(_memory_to_dict(mem, score=1.0 - distance))

        for mem in ilike_memories:
            if mem.id not in seen_ids and len(results) < limit:
                seen_ids.add(mem.id)
                results.append(_memory_to_dict(mem))

        return results[:limit]
    except Exception as e:
        logger.warning("向量搜索失败，回退到 ILIKE: %s", e)
        return await _ilike_search(db, bot_id, query_text, limit)


async def _ilike_search(
    db: AsyncSession,
    bot_id: uuid.UUID,
    query: str,
    limit: int,
) -> list[dict]:
    """ILIKE 文本匹配搜索（回退方案）"""
    result = await db.execute(
        select(Memory)
        .where(
            Memory.bot_id == bot_id,
            Memory.content.ilike(f"%{query}%"),
        )
        .order_by(Memory.importance.desc())
        .limit(limit)
    )
    memories = result.scalars().all()
    return [_memory_to_dict(m) for m in memories]


def _memory_to_dict(mem: Memory, score: float | None = None) -> dict:
    result = {
        "id": str(mem.id),
        "type": mem.type,
        "content": mem.content,
        "importance": mem.importance,
        "memory_date": str(mem.memory_date) if mem.memory_date else None,
    }
    if score is not None:
        result["score"] = round(score, 4)
    return result


async def update_memory(
    db: AsyncSession,
    memory_id: str,
    bot_id: str,
    new_content: str,
) -> bool:
    """更新一条记忆，同时更新 embedding"""
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
    mem.embedding = await compute_embedding(new_content)
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
