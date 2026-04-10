"""飞书日历服务

使用飞书 Calendar v4 API。

认证说明:
- user_access_token: 操作用户自己的日历，事件在用户飞书客户端可见
- tenant_access_token: 操作应用身份的日历，事件仅在应用上下文可见，用户看不到
- 日历/任务类操作强烈建议使用 user_access_token

时间格式:
- 飞书 API 使用 Unix 时间戳（秒），如 "1609430400"
- 本服务自动处理: 传入秒级时间戳字符串即可
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.services.feishu_service import get_tenant_token

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"


def _resolve_token_info(user_token: str | None) -> str:
    """返回当前使用的认证身份描述"""
    return "user_access_token（用户身份）" if user_token else "tenant_access_token（应用身份）"


async def _get_headers(user_token: str | None = None) -> dict[str, str]:
    token = user_token or await get_tenant_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


async def get_calendar_list(*, user_token: str | None = None) -> dict[str, Any]:
    """获取日历列表"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/calendar/v4/calendars", headers=headers,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取日历列表失败: {data.get('msg')}"}

        calendars = [
            {
                "calendar_id": c.get("calendar_id"),
                "summary": c.get("summary"),
                "description": c.get("description"),
                "type": c.get("type"),
                "role": c.get("role"),
            }
            for c in data.get("data", {}).get("calendar_list", [])
        ]
        result: dict[str, Any] = {
            "calendars": calendars,
            "auth_type": _resolve_token_info(user_token),
        }
        if not user_token:
            result["warning"] = (
                "当前使用应用身份（tenant_access_token），"
                "只能访问应用自身的日历。要操作用户的个人日历，"
                "请确保用户已通过飞书 OAuth 登录并授予 calendar 权限。"
            )
        return result


def _pick_calendar(
    calendars: list[dict[str, Any]],
    need_write: bool = False,
) -> str:
    """从日历列表中选择最合适的日历

    优先级：owner > writer > reader (need_write=False 时也包含 reader)
    """
    writable_roles = ("owner", "writer")
    readable_roles = ("owner", "writer", "reader")

    for role_set in (writable_roles, readable_roles) if need_write else (readable_roles,):
        for c in calendars:
            if c.get("type") == "primary" and c.get("role") in role_set:
                return c["calendar_id"]

    if calendars:
        return calendars[0]["calendar_id"]
    return ""


async def list_events(
    days: int = 7,
    calendar_id: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """列出日程事件"""
    headers = await _get_headers(user_token)

    if not calendar_id:
        cal_list = await get_calendar_list(user_token=user_token)
        if "error" in cal_list:
            return cal_list
        calendars = cal_list.get("calendars", [])
        calendar_id = _pick_calendar(calendars, need_write=False)
        if not calendar_id:
            return {
                "error": "未找到可用日历",
                "events": [],
                "auth_type": _resolve_token_info(user_token),
            }

    now_ts = int(time.time())
    end_ts = now_ts + days * 86400

    params: dict[str, Any] = {
        "start_time": str(now_ts),
        "end_time": str(end_ts),
        "page_size": 50,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/calendar/v4/calendars/{calendar_id}/events",
            headers=headers, params=params,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {
                "error": f"获取日程失败 (code={data.get('code')}): {data.get('msg')}",
                "auth_type": _resolve_token_info(user_token),
            }

        events = [
            {
                "event_id": e.get("event_id"),
                "summary": e.get("summary"),
                "description": e.get("description"),
                "start_time": e.get("start_time", {}).get("timestamp"),
                "end_time": e.get("end_time", {}).get("timestamp"),
                "status": e.get("status"),
                "visibility": e.get("visibility"),
            }
            for e in data.get("data", {}).get("items", [])
        ]
        return {
            "calendar_id": calendar_id,
            "events": events,
            "auth_type": _resolve_token_info(user_token),
        }


async def create_event(
    summary: str,
    start_time: str,
    end_time: str,
    calendar_id: str = "",
    attendees: list[str] | None = None,
    description: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """创建日程

    start_time / end_time: Unix 时间戳（秒），如 "1609430400"
    """
    headers = await _get_headers(user_token)

    if not calendar_id:
        cal_list = await get_calendar_list(user_token=user_token)
        if "error" in cal_list:
            return cal_list
        calendars = cal_list.get("calendars", [])
        calendar_id = _pick_calendar(calendars, need_write=True)
        if not calendar_id:
            return {"error": "未找到可写的日历，请确保已授予日历权限"}

    body: dict[str, Any] = {
        "summary": summary,
        "start_time": {"timestamp": str(start_time)},
        "end_time": {"timestamp": str(end_time)},
    }
    if description:
        body["description"] = description
    if attendees:
        body["attendees"] = [{"type": "user", "user_id": a} for a in attendees]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/calendar/v4/calendars/{calendar_id}/events",
            headers=headers, json=body,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {
                "error": f"创建日程失败 (code={data.get('code')}): {data.get('msg')}",
                "auth_type": _resolve_token_info(user_token),
            }

        event = data.get("data", {}).get("event", {})
        result: dict[str, Any] = {
            "success": True,
            "event_id": event.get("event_id"),
            "summary": summary,
            "auth_type": _resolve_token_info(user_token),
        }
        if not user_token:
            result["warning"] = (
                "日程已通过应用身份创建，但可能不会出现在用户的飞书日历中。"
                "要让用户看到日程，请确保用户已通过飞书 OAuth 登录。"
            )
        return result
