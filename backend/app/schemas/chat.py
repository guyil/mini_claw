"""Chat 请求/响应 schema"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class MessagePart(BaseModel):
    type: str
    text: str | None = None


class ChatMessage(BaseModel):
    role: str | None = None
    parts: list[MessagePart] = []


class ChatCommand(BaseModel):
    type: str
    message: ChatMessage | None = None
    # add-tool-result 命令
    tool_call_id: str | None = None
    result: Any | None = None


class ChatRequest(BaseModel):
    """assistant-transport 协议的请求体"""
    state: dict | None = None
    commands: list[ChatCommand] = []
    system: str | None = None
    threadId: str | None = None
    parentId: str | None = None

    # 自定义扩展字段
    bot_id: str | None = None
