"""Compaction — 对话历史压缩

当对话 token 数超过阈值时，将旧消息摘要为结构化 summary，
保留最近 N 条消息和关键决策/标识符。

参考 OpenClaw compaction-safeguard 的设计：
- 多阶段 summarize
- 保留关键标识符（ASIN、URL、文件路径等）
- 结构化 fallback
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_COMPACTION_THRESHOLD = 6000
RECENT_TURNS_PRESERVE = 4

COMPACTION_SYSTEM_PROMPT = """你是对话摘要专家。请将以下对话内容压缩为结构化摘要。

要求：
1. 使用对话中的主要语言书写摘要
2. 保留所有关键决策和结论
3. 保留所有标识符（ASIN、产品编号、URL、文件路径等）原样
4. 保留用户偏好和重要指令
5. 不要翻译或修改代码、路径和错误信息
6. 使用以下格式：

## 对话摘要

### 讨论主题
- <主要讨论的话题>

### 关键决策与结论
- <做出的决定和得出的结论>

### 重要标识符
- <出现过的 ASIN、URL、编号等>

### 用户偏好与指令
- <用户表达的偏好和长期指令>

### 当前状态
- <对话结束时的工作状态>
"""


def estimate_tokens(messages: list[BaseMessage]) -> int:
    """粗略估算 token 数（中文 ~1.5 token/字，英文 ~0.75 token/word）"""
    total_chars = sum(len(m.content) if isinstance(m.content, str) else 0 for m in messages)
    return int(total_chars * 0.7)


def needs_compaction(
    messages: list[BaseMessage],
    threshold: int = DEFAULT_COMPACTION_THRESHOLD,
) -> bool:
    """判断当前对话是否需要 compaction"""
    return estimate_tokens(messages) > threshold


async def _summarize_messages(
    messages: list[BaseMessage],
    bot_config: dict[str, Any],
) -> str:
    """使用 LLM 将消息列表摘要为结构化文本"""
    model = bot_config.get("model_name") or settings.default_model
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": 0.3,
    }
    if settings.litellm_api_base:
        base = settings.litellm_api_base.rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        kwargs["base_url"] = base
    if settings.litellm_api_key:
        kwargs["api_key"] = settings.litellm_api_key

    llm = ChatOpenAI(**kwargs)

    conversation_text = "\n".join(
        f"[{m.type}]: {m.content}" for m in messages if isinstance(m.content, str)
    )

    summary_messages = [
        SystemMessage(content=COMPACTION_SYSTEM_PROMPT),
        HumanMessage(content=f"请摘要以下对话：\n\n{conversation_text}"),
    ]

    response = await llm.ainvoke(summary_messages)
    return response.content


async def compact_messages(
    messages: list[BaseMessage],
    bot_config: dict[str, Any],
    threshold: int = DEFAULT_COMPACTION_THRESHOLD,
    preserve_recent: int = RECENT_TURNS_PRESERVE,
) -> list[BaseMessage]:
    """执行 compaction: 摘要旧消息，保留最近 N 条

    Returns:
        压缩后的消息列表: [SystemMessage(摘要)] + 最近 N 条消息
    """
    if not needs_compaction(messages, threshold):
        return messages

    split_point = max(0, len(messages) - preserve_recent)
    old_messages = messages[:split_point]
    recent_messages = messages[split_point:]

    if not old_messages:
        return messages

    try:
        summary = await _summarize_messages(old_messages, bot_config)
    except Exception as e:
        logger.warning("Compaction 摘要失败: %s", e)
        return messages

    compaction_msg = SystemMessage(
        content=f"[对话历史摘要 — 以下是之前对话的压缩版本]\n\n{summary}"
    )

    return [compaction_msg] + recent_messages
