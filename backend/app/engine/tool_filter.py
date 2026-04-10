"""Tool Filter — 按 Skill 需求过滤工具

Skill 执行时只注入 required_tools 声明的工具 + skill_complete，
减少无关工具干扰，提升 Skill 执行准确性。
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

ALWAYS_AVAILABLE_TOOLS = {"skill_complete"}


def filter_tools_for_skill(
    all_tools: list[BaseTool],
    required_tools: list[str] | None,
) -> list[BaseTool]:
    """根据 Skill 的 required_tools 过滤工具列表

    Args:
        all_tools: 所有可用工具
        required_tools: Skill 声明需要的工具名列表。
                        None 或空列表表示不限制（返回全部工具）。

    Returns:
        过滤后的工具列表（始终包含 skill_complete）
    """
    if not required_tools:
        return list(all_tools)

    allowed = set(required_tools) | ALWAYS_AVAILABLE_TOOLS
    return [t for t in all_tools if t.name in allowed]
