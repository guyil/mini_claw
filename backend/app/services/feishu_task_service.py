"""飞书任务服务

使用飞书 Task v2 API。

认证说明:
- user_access_token: 创建的任务归属于用户，在用户飞书客户端可见
- tenant_access_token: 创建的任务归属于应用，用户在飞书中看不到
- 任务类操作强烈建议使用 user_access_token
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.feishu_service import get_tenant_token

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"


def _resolve_token_info(user_token: str | None) -> str:
    return "user_access_token（用户身份）" if user_token else "tenant_access_token（应用身份）"


async def _get_headers(user_token: str | None = None) -> dict[str, str]:
    token = user_token or await get_tenant_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


async def list_tasks(*, user_token: str | None = None) -> dict[str, Any]:
    """列出任务"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/task/v2/tasks",
            headers=headers, params={"page_size": 50},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {
                "error": f"获取任务列表失败 (code={data.get('code')}): {data.get('msg')}",
                "auth_type": _resolve_token_info(user_token),
            }

        tasks = [
            {
                "task_id": t.get("task_id"),
                "summary": t.get("summary"),
                "due": t.get("due"),
                "status": t.get("status"),
                "creator_id": t.get("creator_id"),
            }
            for t in data.get("data", {}).get("items", [])
        ]
        result: dict[str, Any] = {
            "tasks": tasks,
            "auth_type": _resolve_token_info(user_token),
        }
        if not user_token:
            result["warning"] = (
                "当前使用应用身份（tenant_access_token），"
                "只能获取应用创建的任务。要获取用户的个人任务，"
                "请确保用户已通过飞书 OAuth 登录并授予 task 权限。"
            )
        return result


async def create_task(
    summary: str,
    due: str = "",
    assignees: list[str] | None = None,
    description: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """创建任务

    due: Unix 时间戳（秒），如 "1609430400"
    """
    headers = await _get_headers(user_token)

    body: dict[str, Any] = {"summary": summary}
    if description:
        body["description"] = description
    if due:
        body["due"] = {"timestamp": str(due), "is_all_day": False}
    if assignees:
        body["members"] = [{"id": a, "type": "user", "role": "assignee"} for a in assignees]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/task/v2/tasks",
            headers=headers, json=body,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {
                "error": f"创建任务失败 (code={data.get('code')}): {data.get('msg')}",
                "auth_type": _resolve_token_info(user_token),
            }

        task = data.get("data", {}).get("task", {})
        result: dict[str, Any] = {
            "success": True,
            "task_id": task.get("task_id"),
            "summary": summary,
            "auth_type": _resolve_token_info(user_token),
        }
        if not user_token:
            result["warning"] = (
                "任务已通过应用身份创建，但不会出现在用户的飞书任务列表中。"
                "要让用户看到任务，请确保用户已通过飞书 OAuth 登录。"
            )
        return result
