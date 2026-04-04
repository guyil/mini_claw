"""Prompt builder 单元测试"""

from app.engine.prompt_builder import build_system_prompt, build_skill_execution_prompt


def test_build_system_prompt_full():
    prompt = build_system_prompt(
        soul="你是一个数据驱动的选品分析师",
        instructions="每次分析前先查询 BSR 数据",
        user_context="小美，负责家居品类，主做美国站",
        skills=[
            {"name": "competitor-analysis", "description": "竞品分析"},
            {"name": "listing-optimizer", "description": "Listing 优化"},
        ],
        memory="- 竞品品牌A的BSR上月下降30%",
    )

    assert "你是一个数据驱动的选品分析师" in prompt
    assert "每次分析前先查询 BSR 数据" in prompt
    assert "小美" in prompt
    assert "competitor-analysis" in prompt
    assert "listing-optimizer" in prompt
    assert "activate_skill" in prompt
    assert "记忆管理规则" in prompt
    assert "竞品品牌A" in prompt


def test_build_system_prompt_minimal():
    prompt = build_system_prompt(
        soul="你是一个助手",
        instructions=None,
        user_context=None,
        skills=[],
        memory="",
    )

    assert "你是一个助手" in prompt
    assert "记忆管理规则" in prompt


def test_build_skill_execution_prompt():
    prompt = build_skill_execution_prompt("1. 提取 ASIN\n2. 调用 scraper\n3. 生成报告")
    assert "严格按照工作流步骤执行" in prompt
    assert "提取 ASIN" in prompt
    assert "skill_complete" in prompt
