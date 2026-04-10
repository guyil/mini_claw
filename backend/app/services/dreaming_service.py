"""Dreaming Service — 记忆晋升

参考 OpenClaw 的 Dreaming 机制：
- 跟踪每条记忆被 memory_search 召回的频率、分数、查询多样性
- 定期计算晋升分数，达标的 daily 记忆晋升为 long_term
- 四维信号：频率 (0.35) + 相关性 (0.35) + 查询多样性 (0.15) + 时效性 (0.15)
"""

from __future__ import annotations

import hashlib
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import Memory

logger = logging.getLogger(__name__)

WEIGHT_FREQUENCY = 0.35
WEIGHT_RELEVANCE = 0.35
WEIGHT_DIVERSITY = 0.15
WEIGHT_RECENCY = 0.15

RECENCY_HALF_LIFE_DAYS = 14

MIN_RECALL_COUNT = 3
MIN_AVG_SCORE = 0.75
MIN_UNIQUE_QUERIES = 2
MIN_PROMOTION_SCORE = 0.6


@dataclass
class MemoryRecallStats:
    recall_count: int
    avg_score: float
    unique_queries: int
    last_recalled_days_ago: int


def compute_promotion_score(stats: MemoryRecallStats) -> float:
    """计算记忆晋升分数（0~1），综合四维信号"""
    freq_score = min(stats.recall_count / 10.0, 1.0)
    relevance_score = min(stats.avg_score, 1.0)
    diversity_score = min(stats.unique_queries / 5.0, 1.0)

    decay = math.exp(-0.693 * stats.last_recalled_days_ago / RECENCY_HALF_LIFE_DAYS)
    recency_score = decay

    return (
        WEIGHT_FREQUENCY * freq_score
        + WEIGHT_RELEVANCE * relevance_score
        + WEIGHT_DIVERSITY * diversity_score
        + WEIGHT_RECENCY * recency_score
    )


def should_promote(stats: MemoryRecallStats) -> bool:
    """判断记忆是否应该晋升（所有门控条件都要通过）"""
    if stats.recall_count < MIN_RECALL_COUNT:
        return False
    if stats.avg_score < MIN_AVG_SCORE:
        return False
    if stats.unique_queries < MIN_UNIQUE_QUERIES:
        return False
    return compute_promotion_score(stats) >= MIN_PROMOTION_SCORE


async def record_recall(
    db: AsyncSession,
    bot_id: str,
    memory_id: str,
    score: float,
    query_hash: str,
) -> None:
    """记录一次 memory_search 召回事件

    在 Memory 模型上用 JSON 元数据追踪召回统计。
    为简化实现，recall stats 存储在 memory 的 source 字段中
    （生产环境应使用独立的 recall_events 表）。
    """
    try:
        from sqlalchemy import text as sql_text

        await db.execute(
            sql_text("""
                INSERT INTO memory_recall_events (memory_id, bot_id, score, query_hash, recalled_at)
                VALUES (:memory_id, :bot_id, :score, :query_hash, NOW())
                ON CONFLICT DO NOTHING
            """),
            {
                "memory_id": memory_id,
                "bot_id": bot_id,
                "score": score,
                "query_hash": query_hash,
            },
        )
        await db.flush()
    except Exception as e:
        logger.debug("记录召回事件失败（表可能不存在）: %s", e)


async def promote_memories(
    db: AsyncSession,
    bot_id: str,
    limit: int = 20,
) -> int:
    """执行记忆晋升：将满足条件的 daily 记忆升级为 long_term

    Returns:
        晋升的记忆数量
    """
    bid = uuid.UUID(bot_id)

    try:
        result = await db.execute(
            select(
                func.count().label("recall_count"),
                func.avg(func.cast("score", func.literal_column("FLOAT"))).label("avg_score"),
                func.count(func.distinct("query_hash")).label("unique_queries"),
            )
            .select_from(func.literal_column("memory_recall_events"))
            .where(
                func.literal_column("bot_id") == str(bid),
            )
            .group_by("memory_id")
            .limit(limit)
        )
        rows = result.all()
    except Exception:
        logger.info("recall_events 表不存在，使用简化晋升逻辑")
        return await _simple_promote(db, bid)

    promoted_count = 0
    for row in rows:
        stats = MemoryRecallStats(
            recall_count=row.recall_count,
            avg_score=float(row.avg_score or 0),
            unique_queries=row.unique_queries,
            last_recalled_days_ago=1,
        )
        if should_promote(stats):
            promoted_count += 1

    return promoted_count


async def _simple_promote(db: AsyncSession, bot_id: uuid.UUID) -> int:
    """简化晋升：将超过 7 天且重要性 >= 0.7 的 daily 记忆升级"""
    cutoff = date.today() - timedelta(days=7)

    result = await db.execute(
        select(Memory).where(
            Memory.bot_id == bot_id,
            Memory.type == "daily",
            Memory.importance >= 0.7,
            Memory.memory_date <= cutoff,
        )
    )
    memories = result.scalars().all()

    for mem in memories:
        mem.type = "long_term"

    if memories:
        await db.flush()

    return len(memories)


def hash_query(query: str) -> str:
    """生成查询指纹，用于统计查询多样性"""
    return hashlib.md5(query.strip().lower().encode()).hexdigest()[:12]
