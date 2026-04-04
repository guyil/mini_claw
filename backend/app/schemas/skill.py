"""Skill schemas"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SkillCreate(BaseModel):
    name: str
    display_name: str | None = None
    description: str
    category: str | None = None
    version: str = "1.0.0"
    instructions: str
    required_tools: list[str] = []
    required_env_vars: list[str] = []
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    scope: str = "global"
    source: str | None = None
    source_url: str | None = None


class SkillUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    version: str | None = None
    instructions: str | None = None
    required_tools: list[str] | None = None
    required_env_vars: list[str] | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    scope: str | None = None
