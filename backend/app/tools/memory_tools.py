"""Memory LangChain Tools — Agent 的记忆读写能力

这些 tool 注册到 LangGraph Agent 中，使 Agent 具备跨会话记忆。
无 DB 时返回提示信息，不会抛出异常。
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from sqlalchemy.ext.asyncio import AsyncSession

_NO_DB_MSG = "记忆功能需要数据库支持，当前未连接数据库。"
_NO_BOT_MSG = "记忆功能需要具体的 Bot 配置，当前使用默认模式。"


def _is_valid_bot(db: AsyncSession | None, bot_id: str) -> str | None:
    """检查 db 和 bot_id 是否可用，返回错误消息或 None"""
    if db is None:
        return _NO_DB_MSG
    if bot_id == "default":
        return _NO_BOT_MSG
    return None


def create_memory_tools(db: AsyncSession | None, bot_id: str) -> list[StructuredTool]:
    """为指定 Bot 创建一组记忆 tools"""

    async def _memory_write(content: str, type: str = "long_term", importance: float = 0.5) -> str:
        err = _is_valid_bot(db, bot_id)
        if err:
            return err
        from app.services.memory_service import write_memory

        mem_id = await write_memory(db, bot_id, content, type, importance)
        return f"已记住 ({type}): {content[:80]}... [ID:{mem_id[:8]}]"

    async def _memory_search(query: str, limit: int = 5) -> str:
        err = _is_valid_bot(db, bot_id)
        if err:
            return err
        from app.services.memory_service import search_memory

        results = await search_memory(db, bot_id, query, limit)
        if not results:
            return "没有找到相关记忆。"
        lines = []
        for r in results:
            prefix = "📌" if r["type"] == "long_term" else f"📅 {r['memory_date']}"
            lines.append(f"{prefix} [ID:{r['id'][:8]}] {r['content']}")
        return "\n".join(lines)

    async def _memory_update(memory_id: str, new_content: str) -> str:
        err = _is_valid_bot(db, bot_id)
        if err:
            return err
        from app.services.memory_service import update_memory

        ok = await update_memory(db, memory_id, bot_id, new_content)
        if ok:
            return f"已更新记忆: {new_content[:80]}..."
        return "未找到指定记忆，更新失败。"

    async def _memory_delete(memory_id: str, reason: str = "") -> str:
        err = _is_valid_bot(db, bot_id)
        if err:
            return err
        from app.services.memory_service import delete_memory

        ok = await delete_memory(db, memory_id, bot_id)
        if ok:
            return f"已删除记忆 (原因: {reason})"
        return "未找到指定记忆，删除失败。"

    async def _memory_get_recent(days: int = 2) -> str:
        err = _is_valid_bot(db, bot_id)
        if err:
            return err
        from app.services.memory_service import get_recent_memories

        results = await get_recent_memories(db, bot_id, days)
        if not results:
            return "最近没有工作日志。"
        lines = []
        current_date = None
        for r in results:
            if r["memory_date"] != current_date:
                current_date = r["memory_date"]
                lines.append(f"\n## {current_date}")
            lines.append(f"- {r['content']}")
        return "\n".join(lines)

    async def _update_soul(new_name: str, new_personality: str) -> str:
        """更新 Bot 的名称和人格定义（soul）"""
        err = _is_valid_bot(db, bot_id)
        if err:
            return err
        import uuid as _uuid

        from sqlalchemy import select, update

        from app.models.bot import Bot

        result = await db.execute(select(Bot.soul, Bot.name).where(Bot.id == _uuid.UUID(bot_id)))
        row = result.one_or_none()
        if row is None:
            return "未找到 Bot 记录。"

        updates: dict = {}
        if new_name and new_name.strip():
            updates["name"] = new_name.strip()
        if new_personality and new_personality.strip():
            updates["soul"] = new_personality.strip()

        if not updates:
            return "没有需要更新的内容。"

        await db.execute(
            update(Bot).where(Bot.id == _uuid.UUID(bot_id)).values(**updates)
        )
        await db.flush()

        changed = "、".join(updates.keys())
        return f"已更新 Bot（{changed}）。下次对话将使用新的人格设定。"

    async def _update_user_context(addition: str) -> str:
        err = _is_valid_bot(db, bot_id)
        if err:
            return err
        from datetime import date

        from sqlalchemy import select, update

        from app.models.bot import Bot

        result = await db.execute(select(Bot.user_context).where(Bot.id == bot_id))
        current = result.scalar_one_or_none() or ""
        timestamp = date.today().isoformat()
        new_line = f"\n- [{timestamp}] {addition}"
        updated = current + new_line

        await db.execute(
            update(Bot).where(Bot.id == bot_id).values(user_context=updated)
        )
        await db.flush()
        return f"已更新用户画像: {addition}"

    return [
        StructuredTool.from_function(
            coroutine=_memory_write,
            name="memory_write",
            description=(
                "将信息写入记忆，使其能跨会话持久化。"
                "当用户说'记住XX'、完成分析任务后保留关键结论、或发现用户偏好时使用。"
            ),
        ),
        StructuredTool.from_function(
            coroutine=_memory_search,
            name="memory_search",
            description="语义搜索记忆。即使措辞不同也能找到相关内容。",
        ),
        StructuredTool.from_function(
            coroutine=_memory_update,
            name="memory_update",
            description="更新一条已有的长期记忆（当信息发生变化时）。先用 memory_search 找到旧记忆的 ID。",
        ),
        StructuredTool.from_function(
            coroutine=_memory_delete,
            name="memory_delete",
            description="删除一条过时或错误的记忆。",
        ),
        StructuredTool.from_function(
            coroutine=_memory_get_recent,
            name="memory_get_recent",
            description="获取最近 N 天的工作日志。默认 2 天。",
        ),
        StructuredTool.from_function(
            coroutine=_update_soul,
            name="update_soul",
            description=(
                "更新 Bot 的名称和人格定义。"
                "当用户要求修改名称、角色、性格、说话风格时调用。"
                "修改后下次对话生效。"
            ),
        ),
        StructuredTool.from_function(
            coroutine=_update_user_context,
            name="update_user_context",
            description=(
                "更新用户画像（半自动：Agent 追加，系统通知用户）。"
                "用于记录用户的业务背景、角色变化、长期偏好。"
            ),
        ),
    ]
