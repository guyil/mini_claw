"""System Prompt 组装器

将 Soul + Instructions + User Context + Available Skills + Memory 拼装为完整的 system prompt。
"""

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
- 需要更早的信息时，调用 memory_search 语义搜索
- 需要特定日期的详细记录时，调用 memory_get_recent
"""


def build_system_prompt(
    soul: str,
    instructions: str | None,
    user_context: str | None,
    skills: list[dict[str, str]],
    memory: str,
) -> str:
    """拼装完整的 system prompt"""
    parts: list[str] = []

    parts.append(f"# 你的身份\n\n{soul}")

    if instructions:
        parts.append(f"# 工作指令\n\n{instructions}")

    if user_context:
        parts.append(f"# 用户画像\n\n{user_context}")

    if skills:
        skill_list = "\n".join(
            f"- **{s['name']}**: {s['description']}" for s in skills
        )
        parts.append(
            f"# 可用技能 (Skills)\n\n"
            f"当判断需要使用某个技能时，调用 activate_skill 工具并传入技能名称。\n\n"
            f"{skill_list}"
        )

    parts.append(MEMORY_INSTRUCTIONS)

    parts.append(
        "# 重要：数据保真规则\n\n"
        "用户消息中的所有标识符（ASIN、产品编号、URL、文档ID等）"
        "必须原样使用，绝对不能修改、替换或脱敏。"
        "在调用工具时，请将用户提供的原始值直接传入参数。"
    )

    if memory:
        parts.append(f"# 已知记忆\n\n{memory}")

    return "\n\n---\n\n".join(parts)


def build_skill_execution_prompt(skill_instructions: str) -> str:
    """构建 Skill 执行阶段的 system prompt"""
    return (
        "你现在要执行以下 Skill。严格按照工作流步骤执行，"
        "使用可用的 tools 完成每一步。完成后调用 skill_complete 工具。\n\n"
        f"{skill_instructions}"
    )
