"""Prompt builder 单元测试"""

from unittest.mock import patch

from app.engine.prompt_builder import (
    EXECUTION_BIAS,
    MEMORY_INSTRUCTIONS,
    REPLY_STYLE,
    SAFETY,
    TOOL_CALL_STYLE,
    build_runtime_context,
    build_skill_execution_prompt,
    build_system_prompt,
)


# ---------------------------------------------------------------------------
# build_system_prompt — full
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# New sections: execution bias, tool call style, reply style, safety
# ---------------------------------------------------------------------------
def test_prompt_contains_execution_bias():
    prompt = build_system_prompt(
        soul="test", instructions=None, user_context=None, skills=[], memory=""
    )
    assert "执行偏好" in prompt
    assert "立即动手" in prompt
    assert "纯评论式回复是不完整的" in prompt


def test_prompt_contains_tool_call_style():
    prompt = build_system_prompt(
        soul="test", instructions=None, user_context=None, skills=[], memory=""
    )
    assert "工具调用风格" in prompt
    assert "直接调用" in prompt


def test_prompt_contains_reply_style():
    prompt = build_system_prompt(
        soul="test", instructions=None, user_context=None, skills=[], memory=""
    )
    assert "回复风格" in prompt
    assert "直接回答" in prompt


def test_prompt_contains_safety():
    prompt = build_system_prompt(
        soul="test", instructions=None, user_context=None, skills=[], memory=""
    )
    assert "安全边界" in prompt
    assert "可以自主执行" in prompt
    assert "需要确认后执行" in prompt
    assert "数据保真" in prompt
    assert "ASIN" in prompt


def test_safety_replaces_old_data_fidelity():
    """Old standalone '数据保真规则' section should not exist; content is in SAFETY."""
    prompt = build_system_prompt(
        soul="test", instructions=None, user_context=None, skills=[], memory=""
    )
    assert "# 重要：数据保真规则" not in prompt
    assert "数据保真" in prompt


# ---------------------------------------------------------------------------
# Memory instructions: no duplicates
# ---------------------------------------------------------------------------
def test_memory_instructions_no_duplicates():
    """MEMORY_INSTRUCTIONS should not contain duplicated subsections."""
    assert MEMORY_INSTRUCTIONS.count("### 不该记的") == 1
    assert MEMORY_INSTRUCTIONS.count("### 用户画像更新") == 1
    assert MEMORY_INSTRUCTIONS.count("### 记忆冲突处理") == 1
    assert MEMORY_INSTRUCTIONS.count("### 回忆") == 1


def test_memory_instructions_proactive_recall():
    """Memory instructions should guide proactive recall before answering."""
    assert "memory_search" in MEMORY_INSTRUCTIONS
    assert "回答" in MEMORY_INSTRUCTIONS or "回复" in MEMORY_INSTRUCTIONS


# ---------------------------------------------------------------------------
# Skill decision flow
# ---------------------------------------------------------------------------
def test_skill_section_structured_decision_flow():
    prompt = build_system_prompt(
        soul="test",
        instructions=None,
        user_context=None,
        skills=[{"name": "test-skill", "description": "desc"}],
        memory="",
    )
    assert "恰好一个技能明确适用" in prompt
    assert "多个可能适用" in prompt
    assert "没有明确适用" in prompt


# ---------------------------------------------------------------------------
# Runtime context
# ---------------------------------------------------------------------------
def test_build_runtime_context_includes_datetime():
    ctx = build_runtime_context()
    assert "当前时间" in ctx
    assert "星期" in ctx


def test_build_runtime_context_includes_model():
    ctx = build_runtime_context(model_name="gpt-4o")
    assert "gpt-4o" in ctx
    assert "当前模型" in ctx


def test_build_runtime_context_no_model():
    ctx = build_runtime_context(model_name=None)
    assert "当前模型" not in ctx


def test_prompt_with_runtime_context():
    prompt = build_system_prompt(
        soul="test",
        instructions=None,
        user_context=None,
        skills=[],
        memory="",
        model_name="gemini-2.0-flash",
    )
    assert "当前时间" in prompt
    assert "gemini-2.0-flash" in prompt


# ---------------------------------------------------------------------------
# Section ordering: identity first, memory last
# ---------------------------------------------------------------------------
def test_section_order():
    prompt = build_system_prompt(
        soul="MY_SOUL",
        instructions="MY_INSTRUCTIONS",
        user_context="MY_USER",
        skills=[{"name": "s", "description": "d"}],
        memory="MY_MEMORY",
        model_name="test-model",
    )
    idx_soul = prompt.index("你的身份")
    idx_instructions = prompt.index("工作指令")
    idx_user = prompt.index("用户画像")
    idx_skills = prompt.index("可用技能")
    idx_memory_rules = prompt.index("记忆管理规则")
    idx_exec = prompt.index("执行偏好")
    idx_tool = prompt.index("工具调用风格")
    idx_reply = prompt.index("回复风格")
    idx_safety = prompt.index("安全边界")
    idx_runtime = prompt.index("运行时上下文")
    idx_known = prompt.index("已知记忆")

    assert idx_soul < idx_instructions < idx_user < idx_skills
    assert idx_skills < idx_memory_rules < idx_exec < idx_tool
    assert idx_tool < idx_reply < idx_safety < idx_runtime < idx_known


# ---------------------------------------------------------------------------
# Constants are non-empty
# ---------------------------------------------------------------------------
def test_constants_non_empty():
    assert len(EXECUTION_BIAS.strip()) > 0
    assert len(TOOL_CALL_STYLE.strip()) > 0
    assert len(REPLY_STYLE.strip()) > 0
    assert len(SAFETY.strip()) > 0


# ---------------------------------------------------------------------------
# Skill execution prompt (unchanged behavior)
# ---------------------------------------------------------------------------
def test_build_skill_execution_prompt():
    prompt = build_skill_execution_prompt("1. 提取 ASIN\n2. 调用 scraper\n3. 生成报告")
    assert "严格按照工作流步骤执行" in prompt
    assert "提取 ASIN" in prompt
    assert "skill_complete" in prompt


def test_build_skill_execution_prompt_with_assets():
    assets = [
        {"filename": "scripts/fill.py", "content": "fill()", "is_binary": False},
        {"filename": "scripts/check.py", "content": "check()", "is_binary": False},
        {"filename": "reference.md", "content": "# Ref", "is_binary": False},
    ]
    prompt = build_skill_execution_prompt("Run the scripts", assets=assets)
    assert "可用资源文件" in prompt
    assert "scripts/fill.py" in prompt
    assert "scripts/check.py" in prompt
    assert "reference.md" in prompt
    assert "exec_command" in prompt
    assert "/tmp/skill_workspace" in prompt


def test_build_skill_execution_prompt_no_assets():
    prompt = build_skill_execution_prompt("Simple instructions", assets=[])
    assert "可用资源文件" not in prompt
    assert "Simple instructions" in prompt
