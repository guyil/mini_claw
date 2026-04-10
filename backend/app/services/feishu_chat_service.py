"""飞书群聊与消息服务

参考 OpenClaw extensions/feishu/src/chat.ts 实现。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.services.feishu_service import get_tenant_token

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"


async def _get_headers(user_token: str | None = None) -> dict[str, str]:
    token = user_token or await get_tenant_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


async def get_chat_info(chat_id: str, *, user_token: str | None = None) -> dict[str, Any]:
    """获取群聊信息"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/im/v1/chats/{chat_id}", headers=headers,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取群聊信息失败: {data.get('msg')}"}

        chat = data.get("data", {})
        return {
            "chat_id": chat_id,
            "name": chat.get("name"),
            "description": chat.get("description"),
            "owner_id": chat.get("owner_id"),
            "user_count": chat.get("user_count"),
            "chat_mode": chat.get("chat_mode"),
            "chat_type": chat.get("chat_type"),
        }


async def get_chat_members(
    chat_id: str,
    page_size: int = 50,
    page_token: str = "",
    member_id_type: str = "open_id",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """获取群成员列表"""
    headers = await _get_headers(user_token)
    params: dict[str, Any] = {
        "page_size": min(max(1, page_size), 100),
        "member_id_type": member_id_type,
    }
    if page_token:
        params["page_token"] = page_token

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/im/v1/chats/{chat_id}/members",
            headers=headers, params=params,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取群成员失败: {data.get('msg')}"}

        return {
            "chat_id": chat_id,
            "has_more": data.get("data", {}).get("has_more"),
            "page_token": data.get("data", {}).get("page_token"),
            "members": [
                {
                    "member_id": m.get("member_id"),
                    "name": m.get("name"),
                    "tenant_key": m.get("tenant_key"),
                    "member_id_type": m.get("member_id_type"),
                }
                for m in data.get("data", {}).get("items", [])
            ],
        }


async def get_member_info(
    member_id: str,
    member_id_type: str = "open_id",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """获取用户详细信息"""
    headers = await _get_headers(user_token)
    params = {"user_id_type": member_id_type, "department_id_type": "open_department_id"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/contact/v3/users/{member_id}",
            headers=headers, params=params,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取用户信息失败: {data.get('msg')}"}

        user = data.get("data", {}).get("user", {})
        return {
            "member_id": member_id,
            "member_id_type": member_id_type,
            "open_id": user.get("open_id"),
            "name": user.get("name"),
            "en_name": user.get("en_name"),
            "email": user.get("email"),
            "mobile": user.get("mobile"),
            "avatar": user.get("avatar"),
            "department_ids": user.get("department_ids"),
            "job_title": user.get("job_title"),
            "status": user.get("status"),
        }


async def send_message(
    receive_id: str,
    content: str,
    msg_type: str = "text",
    receive_id_type: str = "chat_id",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """发送消息"""
    headers = await _get_headers(user_token)

    if msg_type == "text":
        body_content = json.dumps({"text": content})
    elif msg_type == "interactive":
        body_content = content
    else:
        body_content = content

    body = {
        "receive_id": receive_id,
        "msg_type": msg_type,
        "content": body_content,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/im/v1/messages",
            headers=headers, json=body,
            params={"receive_id_type": receive_id_type},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"发送消息失败: {data.get('msg')}"}

        msg = data.get("data", {})
        return {
            "success": True,
            "message_id": msg.get("message_id"),
            "chat_id": msg.get("chat_id"),
        }


async def send_card(
    receive_id: str,
    card_content: dict[str, Any],
    receive_id_type: str = "chat_id",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """发送卡片消息"""
    return await send_message(
        receive_id,
        json.dumps(card_content),
        msg_type="interactive",
        receive_id_type=receive_id_type,
        user_token=user_token,
    )
