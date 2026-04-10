"""定时任务 LangChain Tools — Agent 在对话中创建/管理定时任务

使用场景:
- 用户: "每天早上 9 点给我发一份竞品价格报告"
- 用户: "提醒我下周一检查广告投放数据"
- 用户: "每周五下午帮我总结本周运营数据"
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

_NO_DB_MSG = "定时任务功能需要数据库支持，当前未连接数据库。"

# 模块级别引用，在 app 启动时由 integration 设置
_scheduler_service = None


def set_scheduler_service(service):
    """由 main.py lifespan 调用，注入 SchedulerService 实例"""
    global _scheduler_service
    _scheduler_service = service


def create_schedule_tools(
    user_id: str,
    bot_id: str,
    conversation_id: str | None = None,
) -> list[StructuredTool]:
    """创建定时任务工具集"""

    async def _schedule_task(
        action: Literal["list", "add", "update", "remove", "run_now"],
        name: str = "",
        schedule_type: str = "",
        schedule_value: str = "",
        timezone: str = "Asia/Shanghai",
        message: str = "",
        delivery_mode: str = "chat",
        job_id: str = "",
        enabled: bool = True,
        description: str = "",
    ) -> str:
        """管理定时任务。

        action 说明:
        - list: 列出所有定时任务
        - add: 创建新的定时任务
        - update: 修改已有任务
        - remove: 删除任务
        - run_now: 立即触发一次任务

        schedule_type + schedule_value 说明:
        - at + ISO-8601 时间戳: 一次性定时任务，如 "2026-04-07T09:00:00+08:00"
        - interval + 秒数: 周期性任务，如 "3600" 表示每小时
        - cron + cron 表达式: 如 "0 9 * * 1-5" 表示工作日每天 9 点

        delivery_mode 说明:
        - chat: 结果保存到对话中（默认）
        - feishu: 通过飞书发送
        - webhook: POST 到指定 URL
        """
        if _scheduler_service is None:
            return "定时任务调度器未启动。"

        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            return _NO_DB_MSG

        if action == "list":
            return await _handle_list(uid)
        elif action == "add":
            return await _handle_add(
                uid, bot_id, conversation_id,
                name, schedule_type, schedule_value, timezone,
                message, delivery_mode, description,
            )
        elif action == "update":
            return await _handle_update(
                uid, job_id, name, schedule_type, schedule_value,
                timezone, message, delivery_mode, enabled, description,
            )
        elif action == "remove":
            return await _handle_remove(uid, job_id)
        elif action == "run_now":
            return await _handle_run_now(uid, job_id)
        else:
            return f"未知的 action: {action}"

    return [
        StructuredTool.from_function(
            coroutine=_schedule_task,
            name="schedule_task",
            description=(
                "创建和管理定时任务。"
                "当用户要求定时提醒、周期性报告、延迟跟进时使用。\n"
                "支持一次性定时(at)、固定间隔(interval)、cron表达式(cron)三种调度方式。\n"
                "示例:\n"
                "- '每天9点发竞品报告' → add, cron, '0 9 * * *'\n"
                "- '下周一提醒我' → add, at, '2026-04-13T09:00:00+08:00'\n"
                "- '每2小时检查一次' → add, interval, '7200'\n"
                "- '查看我的定时任务' → list\n"
                "- '取消那个提醒' → remove, job_id=..."
            ),
        ),
    ]


async def _handle_list(user_id: uuid.UUID) -> str:
    jobs = await _scheduler_service.list_jobs(user_id, include_disabled=True)
    if not jobs:
        return "你还没有创建任何定时任务。"

    lines = [f"📋 你的定时任务 ({len(jobs)} 个):\n"]
    for j in jobs:
        status = "✅" if j.enabled else "⏸️"
        sched = _format_schedule(j.schedule_type, j.schedule_config)
        lines.append(
            f"{status} **{j.name}** (ID: {str(j.id)[:8]})\n"
            f"   调度: {sched}\n"
            f"   下次执行: {j.next_run_at or '未安排'}\n"
            f"   已执行: {j.run_count} 次"
        )
    return "\n".join(lines)


async def _handle_add(
    user_id: uuid.UUID,
    bot_id: str,
    conversation_id: str | None,
    name: str,
    schedule_type: str,
    schedule_value: str,
    timezone: str,
    message: str,
    delivery_mode: str,
    description: str,
) -> str:
    if not name:
        return "请提供任务名称 (name)。"
    if not schedule_type or schedule_type not in ("at", "interval", "cron"):
        return "请提供有效的 schedule_type: at, interval, 或 cron。"
    if not schedule_value:
        return "请提供 schedule_value (时间戳/秒数/cron表达式)。"
    if not message:
        return "请提供 message — 任务触发时 Agent 需要执行的指令。"

    schedule_config = _build_schedule_config(schedule_type, schedule_value, timezone)
    if schedule_config is None:
        return f"schedule_value 格式无效: {schedule_value}"

    bid = None
    try:
        bid = uuid.UUID(bot_id) if bot_id != "default" else None
    except ValueError:
        pass

    conv_id = None
    if conversation_id:
        try:
            conv_id = uuid.UUID(conversation_id)
        except ValueError:
            pass

    job = await _scheduler_service.add_job(
        user_id=user_id,
        bot_id=bid,
        conversation_id=conv_id,
        name=name,
        description=description or None,
        schedule_type=schedule_type,
        schedule_config=schedule_config,
        payload_message=message,
        delivery_mode=delivery_mode,
    )

    sched = _format_schedule(job.schedule_type, job.schedule_config)
    return (
        f"✅ 定时任务已创建!\n"
        f"- 名称: {job.name}\n"
        f"- ID: {str(job.id)[:8]}\n"
        f"- 调度: {sched}\n"
        f"- 下次执行: {job.next_run_at}\n"
        f"- 交付方式: {job.delivery_mode}"
    )


async def _handle_update(
    user_id: uuid.UUID,
    job_id: str,
    name: str,
    schedule_type: str,
    schedule_value: str,
    timezone: str,
    message: str,
    delivery_mode: str,
    enabled: bool,
    description: str,
) -> str:
    if not job_id:
        return "请提供要修改的任务 ID (job_id)。"

    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        return f"无效的 job_id: {job_id}"

    kwargs: dict = {}
    if name:
        kwargs["name"] = name
    if description:
        kwargs["description"] = description
    if message:
        kwargs["payload_message"] = message
    if delivery_mode:
        kwargs["delivery_mode"] = delivery_mode
    if not enabled:
        kwargs["enabled"] = enabled

    if schedule_type and schedule_value:
        schedule_config = _build_schedule_config(schedule_type, schedule_value, timezone)
        if schedule_config is None:
            return f"schedule_value 格式无效: {schedule_value}"
        kwargs["schedule_type"] = schedule_type
        kwargs["schedule_config"] = schedule_config

    if not kwargs:
        return "没有需要更新的字段。"

    job = await _scheduler_service.update_job(jid, user_id, **kwargs)
    if job is None:
        return f"未找到任务 {job_id}，或你没有权限修改。"

    return f"✅ 任务 {job.name} 已更新。下次执行: {job.next_run_at}"


async def _handle_remove(user_id: uuid.UUID, job_id: str) -> str:
    if not job_id:
        return "请提供要删除的任务 ID (job_id)。"

    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        return f"无效的 job_id: {job_id}"

    ok = await _scheduler_service.remove_job(jid, user_id)
    if not ok:
        return f"未找到任务 {job_id}，或你没有权限删除。"

    return f"✅ 定时任务 {job_id[:8]} 已删除。"


async def _handle_run_now(user_id: uuid.UUID, job_id: str) -> str:
    if not job_id:
        return "请提供要执行的任务 ID (job_id)。"

    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        return f"无效的 job_id: {job_id}"

    ok = await _scheduler_service.run_now(jid, user_id)
    if not ok:
        return f"未找到任务 {job_id}，或你没有权限执行。"

    return f"✅ 任务 {job_id[:8]} 已标记为立即执行，将在调度器下一轮检查时运行。"


def _build_schedule_config(
    schedule_type: str, schedule_value: str, timezone: str
) -> dict | None:
    """将 tool 参数转换为 schedule_config 字典"""
    if schedule_type == "at":
        try:
            from datetime import datetime as dt
            dt.fromisoformat(schedule_value)
        except ValueError:
            return None
        return {"at": schedule_value, "timezone": timezone}

    if schedule_type == "interval":
        try:
            seconds = int(schedule_value)
            if seconds <= 0:
                return None
        except ValueError:
            return None
        return {"seconds": seconds, "timezone": timezone}

    if schedule_type == "cron":
        from croniter import croniter
        if not croniter.is_valid(schedule_value):
            return None
        return {"cron_expr": schedule_value, "timezone": timezone}

    return None


def _format_schedule(schedule_type: str, schedule_config: dict) -> str:
    """格式化调度配置为人类可读字符串"""
    tz = schedule_config.get("timezone", "Asia/Shanghai")
    if schedule_type == "at":
        return f"一次性: {schedule_config.get('at')} ({tz})"
    if schedule_type == "interval":
        seconds = schedule_config.get("seconds", 0)
        if seconds >= 3600:
            return f"每 {seconds // 3600} 小时"
        if seconds >= 60:
            return f"每 {seconds // 60} 分钟"
        return f"每 {seconds} 秒"
    if schedule_type == "cron":
        return f"cron: {schedule_config.get('cron_expr')} ({tz})"
    return str(schedule_config)
