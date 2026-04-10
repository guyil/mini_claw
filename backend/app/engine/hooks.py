"""Hook Registry — Prompt 组装生命周期扩展点

参考 OpenClaw 的 before_prompt_build / after_prompt_build hook 机制，
允许插件在 prompt 组装前后注入/修改内容。

支持的 hook 事件：
- before_prompt_build: prompt 组装前，可注入 prepend_sections
- after_prompt_build: prompt 组装后，可追加 append_sections
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

HookName = str
HookCallback = Callable[["PromptHookContext"], "PromptHookContext"]


@dataclass
class PromptHookContext:
    """Hook 回调接收和返回的上下文"""

    soul: str
    instructions: str | None
    user_context: str | None
    skills: list[dict[str, str]]
    memory: str
    prepend_sections: list[str] = field(default_factory=list)
    append_sections: list[str] = field(default_factory=list)


class HookRegistry:
    """Hook 注册表 — 管理 prompt 生命周期 hook"""

    def __init__(self) -> None:
        self._hooks: dict[HookName, list[HookCallback]] = {}

    def register(self, event: HookName, callback: HookCallback) -> None:
        """注册一个 hook 回调"""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)

    def fire(self, event: HookName, ctx: PromptHookContext) -> PromptHookContext:
        """触发指定事件的所有 hook，顺序执行"""
        callbacks = self._hooks.get(event, [])
        for cb in callbacks:
            try:
                ctx = cb(ctx)
            except Exception as e:
                logger.warning("Hook %s 执行失败: %s", event, e)
        return ctx

    def clear(self, event: HookName | None = None) -> None:
        """清除指定事件或所有 hook"""
        if event is None:
            self._hooks.clear()
        elif event in self._hooks:
            del self._hooks[event]


# 全局 hook 注册表实例
prompt_hooks = HookRegistry()
