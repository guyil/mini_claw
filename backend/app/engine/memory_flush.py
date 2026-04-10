"""Memory Flush — Compaction 前记忆保存

在 compaction 压缩对话历史之前，插入一个 system turn
提醒 agent 将对话中的重要信息写入长期记忆，防止信息丢失。

参考 OpenClaw 的 MemoryFlushPlan 设计。
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage

MIN_MESSAGES_FOR_FLUSH = 6


def should_flush_before_compaction(
    messages: list[BaseMessage],
    is_compacting: bool,
) -> bool:
    """判断 compaction 前是否需要执行记忆 flush

    条件：正在进行 compaction + 对话有一定长度
    """
    if not is_compacting:
        return False
    return len(messages) >= MIN_MESSAGES_FOR_FLUSH


def build_flush_prompt() -> str:
    """构建记忆 flush 的 system prompt

    提示 agent 在 compaction 摘要前将重要信息保存到记忆中。
    """
    return (
        "## 记忆保存提醒\n\n"
        "对话即将被压缩摘要。请立即检查对话中是否有以下未保存的重要信息，"
        "如有请使用 memory_write 工具保存：\n\n"
        "1. **用户偏好和习惯** — 用户表达的长期偏好、工作习惯\n"
        "2. **关键决策** — 讨论中做出的重要决定和结论\n"
        "3. **业务数据** — 重要的 ASIN、产品信息、竞品数据\n"
        "4. **待办事项** — 用户提到的后续需要处理的事情\n"
        "5. **错误纠正** — 用户纠正过你的地方（记住正确做法）\n\n"
        "注意：只保存尚未在记忆中的信息，避免重复。"
        "如果没有需要保存的信息，不需要任何操作。"
    )
