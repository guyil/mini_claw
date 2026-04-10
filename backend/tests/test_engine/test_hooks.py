"""Hook 体系单元测试

P3: prompt 组装前后留出插件扩展点
"""

from __future__ import annotations

import pytest

from app.engine.hooks import HookRegistry, PromptHookContext


class TestHookRegistry:
    def test_register_and_fire_before_prompt_build(self):
        registry = HookRegistry()
        modifications = []

        def my_hook(ctx: PromptHookContext) -> PromptHookContext:
            ctx.prepend_sections.append("# 插件注入\n来自测试插件")
            modifications.append("called")
            return ctx

        registry.register("before_prompt_build", my_hook)
        ctx = PromptHookContext(
            soul="soul",
            instructions=None,
            user_context=None,
            skills=[],
            memory="",
            prepend_sections=[],
            append_sections=[],
        )
        result = registry.fire("before_prompt_build", ctx)
        assert len(modifications) == 1
        assert len(result.prepend_sections) == 1

    def test_register_after_prompt_build(self):
        registry = HookRegistry()

        def my_hook(ctx: PromptHookContext) -> PromptHookContext:
            ctx.append_sections.append("# 追加内容")
            return ctx

        registry.register("after_prompt_build", my_hook)
        ctx = PromptHookContext(
            soul="soul",
            instructions=None,
            user_context=None,
            skills=[],
            memory="",
            prepend_sections=[],
            append_sections=[],
        )
        result = registry.fire("after_prompt_build", ctx)
        assert len(result.append_sections) == 1

    def test_multiple_hooks_chain(self):
        registry = HookRegistry()

        def hook1(ctx: PromptHookContext) -> PromptHookContext:
            ctx.prepend_sections.append("section1")
            return ctx

        def hook2(ctx: PromptHookContext) -> PromptHookContext:
            ctx.prepend_sections.append("section2")
            return ctx

        registry.register("before_prompt_build", hook1)
        registry.register("before_prompt_build", hook2)

        ctx = PromptHookContext(
            soul="soul", instructions=None, user_context=None,
            skills=[], memory="", prepend_sections=[], append_sections=[],
        )
        result = registry.fire("before_prompt_build", ctx)
        assert result.prepend_sections == ["section1", "section2"]

    def test_fire_unregistered_hook(self):
        registry = HookRegistry()
        ctx = PromptHookContext(
            soul="soul", instructions=None, user_context=None,
            skills=[], memory="", prepend_sections=[], append_sections=[],
        )
        result = registry.fire("before_prompt_build", ctx)
        assert result == ctx  # unchanged

    def test_clear_hooks(self):
        registry = HookRegistry()

        def my_hook(ctx: PromptHookContext) -> PromptHookContext:
            ctx.prepend_sections.append("x")
            return ctx

        registry.register("before_prompt_build", my_hook)
        registry.clear("before_prompt_build")

        ctx = PromptHookContext(
            soul="soul", instructions=None, user_context=None,
            skills=[], memory="", prepend_sections=[], append_sections=[],
        )
        result = registry.fire("before_prompt_build", ctx)
        assert len(result.prepend_sections) == 0
