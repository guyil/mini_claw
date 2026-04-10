"""Prompt Cache 稳定性单元测试

P2: 稳定前缀 + 动态后缀分离
"""

from __future__ import annotations

import pytest

from app.engine.prompt_builder import build_system_prompt


class TestPromptCacheStability:
    def test_stable_prefix_identical_across_calls(self):
        """相同 soul/instructions 生成的 prompt 前缀应相同"""
        p1 = build_system_prompt(
            soul="你是小爪",
            instructions="回答要简洁",
            user_context=None,
            skills=[],
            memory="记忆A",
            model_name="gpt-4o",
        )
        p2 = build_system_prompt(
            soul="你是小爪",
            instructions="回答要简洁",
            user_context=None,
            skills=[],
            memory="记忆B",
            model_name="gpt-4o",
        )
        # 提取稳定前缀（memory 之前的部分）
        prefix1 = p1.split("# 已知记忆")[0] if "# 已知记忆" in p1 else p1
        prefix2 = p2.split("# 已知记忆")[0] if "# 已知记忆" in p2 else p2
        assert prefix1 == prefix2

    def test_memory_at_end_of_prompt(self):
        """Memory 应在 prompt 的末尾区域"""
        prompt = build_system_prompt(
            soul="你是小爪",
            instructions=None,
            user_context=None,
            skills=[],
            memory="这是记忆内容",
            model_name="gpt-4o",
        )
        memory_pos = prompt.find("# 已知记忆")
        runtime_pos = prompt.find("# 运行时上下文")
        # 运行时上下文应在记忆之前（稳定区），记忆在最后（动态区）
        assert memory_pos > runtime_pos

    def test_skills_order_deterministic(self):
        """Skills 列表顺序应确定性"""
        skills = [
            {"name": "B技能", "description": "desc B"},
            {"name": "A技能", "description": "desc A"},
        ]
        p1 = build_system_prompt("soul", None, None, skills, "", None)
        p2 = build_system_prompt("soul", None, None, skills, "", None)
        assert p1 == p2
