"""飞书权限管理服务

参考 OpenClaw extensions/feishu/src/perm.ts 实现。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.feishu_service import get_tenant_token

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"


async def _get_headers(user_token: str | None = None) -> dict[str, str]:
    token = user_token or await get_tenant_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


async def list_members(
    token: str, doc_type: str, *, user_token: str | None = None
) -> dict[str, Any]:
    """列出协作者"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/drive/v1/permissions/{token}/members",
            headers=headers, params={"type": doc_type},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取协作者列表失败: {data.get('msg')}"}

        members = [
            {
                "member_type": m.get("member_type"),
                "member_id": m.get("member_id"),
                "perm": m.get("perm"),
                "name": m.get("name"),
            }
            for m in data.get("data", {}).get("items", [])
        ]
        return {"members": members}


async def add_member(
    token: str,
    doc_type: str,
    member_type: str,
    member_id: str,
    perm: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """添加协作者"""
    headers = await _get_headers(user_token)
    body = {
        "member_type": member_type,
        "member_id": member_id,
        "perm": perm,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/drive/v1/permissions/{token}/members",
            headers=headers, json=body,
            params={"type": doc_type, "need_notification": "false"},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"添加协作者失败: {data.get('msg')}"}

        return {"success": True, "member": data.get("data", {}).get("member")}


async def remove_member(
    token: str,
    doc_type: str,
    member_type: str,
    member_id: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """移除协作者"""
    headers = await _get_headers(user_token)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            "DELETE",
            f"{FEISHU_BASE}/drive/v1/permissions/{token}/members/{member_id}",
            headers=headers,
            params={"type": doc_type, "member_type": member_type},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"移除协作者失败: {data.get('msg')}"}

        return {"success": True}
