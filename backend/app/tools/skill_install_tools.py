"""Skill 安装工具 — 让 Agent 从 URL 下载并安装技能包

使用方式与 memory_tools / feishu_tools 相同：
通过 create_skill_install_tools(db, bot_id, user_id) 注入依赖。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.tools import StructuredTool

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def create_skill_install_tools(
    db: "AsyncSession | None",
    bot_id: str,
    user_id: str,
) -> list[StructuredTool]:
    """创建技能安装工具集"""

    async def _install_skill(url: str) -> str:
        """从 URL 下载并安装一个技能包（支持 skills-hub.cc 页面链接或直接 zip 地址）。
        安装完成后技能会自动启用。传入技能包的 URL。"""
        if db is None:
            return "ERROR: 数据库连接不可用，无法安装技能"

        try:
            from app.services.skill_installer import install_skill_from_url

            result = await install_skill_from_url(
                db=db,
                url=url,
                bot_id=bot_id,
                user_id=user_id,
            )
            await db.commit()

            status_text = "安装" if result["status"] == "installed" else "更新"
            return (
                f"技能 '{result['name']}' 已{status_text}成功！\n"
                f"描述：{result['description']}\n"
                f"包含 {result['asset_count']} 个附属文件（脚本/文档）。\n"
                f"技能已自动启用，可以通过 activate_skill 使用。"
            )
        except ValueError as e:
            return f"安装失败: {e}"
        except Exception as e:
            logger.exception("技能安装异常")
            return f"安装过程中发生错误: {e}"

    return [
        StructuredTool.from_function(
            coroutine=_install_skill,
            name="install_skill",
            description=(
                "从 URL 下载并安装一个 AI 技能包。"
                "支持 skills-hub.cc 页面链接或直接 zip 下载地址。"
                "安装完成后技能会自动启用到当前 Bot。"
                "传入技能包的完整 URL。"
            ),
        ),
    ]
