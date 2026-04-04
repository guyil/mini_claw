"""Bot schemas"""

from __future__ import annotations

from pydantic import BaseModel


class BotCreate(BaseModel):
    name: str
    soul: str
    instructions: str | None = None
    user_context: str | None = None
    model_name: str = "openai/gpt-4o-mini"
    temperature: float = 0.7
    enabled_skills: list[str] = []


class BotUpdate(BaseModel):
    name: str | None = None
    soul: str | None = None
    instructions: str | None = None
    user_context: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    enabled_skills: list[str] | None = None
