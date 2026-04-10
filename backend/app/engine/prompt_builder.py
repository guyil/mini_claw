"""System Prompt 组装器

将 Soul + Instructions + User Context + Available Skills + Memory 拼装为完整的 system prompt。
借鉴 OpenClaw 的 prompt 架构，增加执行偏好、工具调用风格、回复风格、安全边界、运行时上下文等关键要素。

P2 增强: 稳定前缀（soul + instructions + 常量 sections）+ 动态后缀（memory），
         最大化 prompt cache 命中率。
P3 增强: before_prompt_build / after_prompt_build hook 扩展点。
"""

from datetime import datetime

from app.engine.hooks import PromptHookContext, prompt_hooks

MEMORY_INSTRUCTIONS = """
## 记忆管理规则

你有能力记住跨会话的信息。以下规则决定了你如何管理记忆。

### 主动记忆（对话中实时触发）
当以下情况出现时，立即调用 memory_write：
- 用户显式要求："记住XX"、"以后XX"、"我偏好XX"
- 用户透露业务关键信息（品类变化、目标调整、新竞品发现）
- 你完成了分析任务，有值得保留的结论或数据
- 用户纠正了你的错误（记住正确做法，避免重犯）
- 你注意到了用户的工作模式

### 不该记的
- 一次性问题
- 用户说"不用记"、"这次而已"的内容
- 密码、银行卡号等敏感信息

### 用户画像更新
当用户告诉你重要的身份/业务变化时，调用 update_user_context 更新画像。

### 记忆冲突处理
如果新信息与已有记忆矛盾，用 memory_search 找到旧记忆，用 memory_update 更新，不要重复创建。

### 回忆
- 每次对话开始时，系统已自动加载你的长期记忆和最近 2 天日志
- 回答关于之前工作、决策、偏好、待办事项的问题前，先用 memory_search 确认
- 需要更早的信息时，调用 memory_search 语义搜索
- 需要特定日期的详细记录时，调用 memory_get_recent
- 如果搜索后仍不确定，如实告知而不是编造
"""

EXECUTION_BIAS = """
## 执行偏好

- 用户要求你做某件事时，立即动手，不要停在计划或承诺阶段
- 当工具可用且下一步明确时，纯评论式回复是不完整的
- 如果工作需要多步完成，先发一条简短进度说明，然后立即开始执行
"""

TOOL_CALL_STYLE = """
## 工具调用风格

- 常规、低风险的工具调用：直接调用，不需要解说
- 仅在以下情况解说：多步骤任务、复杂问题、敏感操作（如删除）、用户主动要求
- 解说要简短有价值，不要重复显而易见的步骤
"""

REPLY_STYLE = """
## 回复风格

- 不要用"好的！"、"没问题！"、"很好的问题！"开头，直接回答
- 简洁时简洁，需要深入时深入，根据问题复杂度调整
- 有自己的判断，如果用户方向有问题，直接指出并说明理由
- 涉及数据时标注来源和置信度
- 用结构化格式（表格、列表）呈现复杂信息
"""

SAFETY = """
## 安全边界

### 可以自主执行
- 查询、搜索、数据分析、记忆读写、内部工具调用

### 需要确认后执行
- 发送飞书消息、操作外部系统、执行不可逆操作

### 数据保真
- 用户消息中的所有标识符（ASIN、产品编号、URL、文档ID等）必须原样使用，绝对不能修改、替换或脱敏
- 调用工具时，将用户提供的原始值直接传入参数
"""

FEISHU_AUTH_GUIDE = """
## 飞书认证引导

当使用飞书工具时，如果返回结果中包含 `auth_required: true` 和 `authorize_url`，说明用户需要授权飞书权限。
请按以下方式引导用户：

1. 简要说明需要授权的原因（如"创建日历日程需要日历权限"）
2. 将 authorize_url 作为**可点击链接**展示给用户，格式如：
   [点击这里授权飞书权限](授权链接)
3. 告诉用户：点击链接 → 在飞书页面同意授权 → 回到对话继续
4. 用户回来后，直接重新执行之前失败的操作，不需要再次确认

注意：
- 不要尝试在没有权限的情况下反复调用工具
- 如果多个工具都缺少权限，只需要引导用户授权一次（授权包含所有权限）
- 授权链接每次生成都不同，请使用最新返回的链接
"""

_WEEKDAY_NAMES = "一二三四五六日"


def build_runtime_context(model_name: str | None = None) -> str:
    """构建运行时上下文（当前时间、模型等动态信息）"""
    now = datetime.now()
    lines = [f"当前时间：{now.strftime('%Y-%m-%d %H:%M')} (星期{_WEEKDAY_NAMES[now.weekday()]})"]
    if model_name:
        lines.append(f"当前模型：{model_name}")
    return "# 运行时上下文\n\n" + "\n".join(lines)


def build_system_prompt(
    soul: str,
    instructions: str | None,
    user_context: str | None,
    skills: list[dict[str, str]],
    memory: str,
    model_name: str | None = None,
) -> str:
    """拼装完整的 system prompt

    架构遵循 prompt cache 最佳实践：
    - 稳定前缀: soul + instructions + user_context + skills + 常量 sections + runtime
    - 动态后缀: memory（每次可能不同）

    Section 顺序：
    1. [hook prepend sections]
    2. 身份 (soul)
    3. 工作指令 (instructions)
    4. 用户画像 (user_context)
    5. 可用技能 (skills)
    6. 记忆管理规则
    7. 执行偏好 / 工具调用风格 / 回复风格 / 安全边界
    8. 运行时上下文 (date/time/model)
    9. === CACHE BOUNDARY ===
    10. 已知记忆 (memory) — 动态区
    11. [hook append sections]
    """
    # P3: fire before_prompt_build hook
    hook_ctx = PromptHookContext(
        soul=soul,
        instructions=instructions,
        user_context=user_context,
        skills=skills,
        memory=memory,
        prepend_sections=[],
        append_sections=[],
    )
    hook_ctx = prompt_hooks.fire("before_prompt_build", hook_ctx)

    parts: list[str] = []

    # Hook prepend sections
    parts.extend(hook_ctx.prepend_sections)

    # --- 稳定前缀区 (cache-friendly) ---
    parts.append(f"# 你的身份\n\n{hook_ctx.soul}")

    if hook_ctx.instructions:
        parts.append(f"# 工作指令\n\n{hook_ctx.instructions}")

    if hook_ctx.user_context:
        parts.append(f"# 用户画像\n\n{hook_ctx.user_context}")

    if hook_ctx.skills:
        skill_list = "\n".join(
            f"- **{s['name']}**: {s['description']}" for s in hook_ctx.skills
        )
        parts.append(
            f"# 可用技能 (Skills)\n\n"
            f"回复前先扫描以下技能列表：\n"
            f"- 如果恰好一个技能明确适用：调用 activate_skill 激活它\n"
            f"- 如果多个可能适用：选择最具体的那个\n"
            f"- 如果没有明确适用的：不要激活技能，直接回答\n\n"
            f"{skill_list}"
        )

    parts.append(MEMORY_INSTRUCTIONS)
    parts.append(EXECUTION_BIAS)
    parts.append(TOOL_CALL_STYLE)
    parts.append(REPLY_STYLE)
    parts.append(SAFETY)
    parts.append(FEISHU_AUTH_GUIDE)
    parts.append(build_runtime_context(model_name))

    # --- 动态后缀区 (memory, 每次可能不同) ---
    if hook_ctx.memory:
        parts.append(f"# 已知记忆\n\n{hook_ctx.memory}")

    # Hook append sections
    parts.extend(hook_ctx.append_sections)

    prompt = "\n\n---\n\n".join(parts)

    # P3: fire after_prompt_build hook
    hook_ctx_after = PromptHookContext(
        soul=hook_ctx.soul,
        instructions=hook_ctx.instructions,
        user_context=hook_ctx.user_context,
        skills=hook_ctx.skills,
        memory=hook_ctx.memory,
        prepend_sections=[],
        append_sections=[],
    )
    hook_ctx_after = prompt_hooks.fire("after_prompt_build", hook_ctx_after)

    if hook_ctx_after.append_sections:
        prompt += "\n\n---\n\n" + "\n\n---\n\n".join(hook_ctx_after.append_sections)

    return prompt


def build_skill_execution_prompt(
    skill_instructions: str,
    assets: list[dict] | None = None,
) -> str:
    """构建 Skill 执行阶段的 system prompt

    Args:
        skill_instructions: Skill 的完整指令文本
        assets: Skill 附属的脚本/文档文件列表
    """
    parts = [
        "你现在要执行以下 Skill。严格按照工作流步骤执行，"
        "使用可用的 tools 完成每一步。完成后调用 skill_complete 工具。",
    ]

    if assets:
        script_files = [a for a in assets if a["filename"].endswith(".py")]
        doc_files = [a for a in assets if not a["filename"].endswith(".py")]

        workspace = "/tmp/skill_workspace"
        parts.append(
            f"\n## 可用资源文件\n\n"
            f"以下文件已写入工作区 `{workspace}/`，你可以通过 "
            f"`exec_command` 和 `read_file` 工具使用它们。"
        )

        if script_files:
            listing = "\n".join(
                f"- `{workspace}/{a['filename']}`" for a in script_files
            )
            parts.append(f"\n### 脚本文件\n{listing}")

        if doc_files:
            listing = "\n".join(
                f"- `{workspace}/{a['filename']}`" for a in doc_files
            )
            parts.append(f"\n### 参考文档\n{listing}")

        parts.append(
            "\n使用脚本示例：`exec_command(\"python3 "
            f"{workspace}/scripts/xxx.py arg1 arg2\")`"
        )

    parts.append(f"\n---\n\n{skill_instructions}")

    return "\n".join(parts)
