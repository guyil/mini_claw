"""飞书云空间操作服务

参考 OpenClaw extensions/feishu/src/drive.ts 实现。
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


async def list_files(
    folder_token: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """列出文件夹内容"""
    headers = await _get_headers(user_token)
    params: dict[str, Any] = {}
    if folder_token:
        params["folder_token"] = folder_token

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/drive/v1/files",
            headers=headers, params=params,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取文件列表失败: {data.get('msg')}"}

        files = [
            {
                "token": f.get("token"),
                "name": f.get("name"),
                "type": f.get("type"),
                "url": f.get("url"),
                "created_time": f.get("created_time"),
                "modified_time": f.get("modified_time"),
                "owner_id": f.get("owner_id"),
            }
            for f in data.get("data", {}).get("files", [])
        ]
        return {"files": files}


async def get_file_info(
    file_token: str,
    file_type: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """获取文件元信息"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/drive/v1/metas",
            headers=headers,
            params={"request_docs": f'[{{"doc_token":"{file_token}","doc_type":"{file_type}"}}]'},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取文件信息失败: {data.get('msg')}"}

        metas = data.get("data", {}).get("metas", [])
        if not metas:
            return {"error": "文件未找到"}
        return {"file": metas[0]}


async def create_folder(
    name: str,
    folder_token: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """创建文件夹"""
    headers = await _get_headers(user_token)
    body: dict[str, Any] = {"name": name, "folder_token": folder_token or ""}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/drive/v1/files/create_folder",
            headers=headers, json=body,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"创建文件夹失败: {data.get('msg')}"}

        return {
            "success": True,
            "token": data.get("data", {}).get("token"),
            "url": data.get("data", {}).get("url"),
        }


async def move_file(
    file_token: str,
    file_type: str,
    target_folder_token: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """移动文件"""
    headers = await _get_headers(user_token)
    body = {"type": file_type, "folder_token": target_folder_token}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/drive/v1/files/{file_token}/move",
            headers=headers, json=body,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"移动文件失败: {data.get('msg')}"}

        return {"success": True, "task_id": data.get("data", {}).get("task_id")}


async def delete_file(
    file_token: str,
    file_type: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """删除文件"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            "DELETE",
            f"{FEISHU_BASE}/drive/v1/files/{file_token}",
            headers=headers, params={"type": file_type},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"删除文件失败: {data.get('msg')}"}

        return {"success": True, "task_id": data.get("data", {}).get("task_id")}


async def list_comments(
    file_token: str,
    file_type: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """列出文件评论"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/drive/v1/files/{file_token}/comments",
            headers=headers, params={"file_type": file_type},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取评论列表失败: {data.get('msg')}"}

        return {"comments": data.get("data", {}).get("items", [])}


async def add_comment(
    file_token: str,
    file_type: str,
    content: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """添加评论"""
    headers = await _get_headers(user_token)
    body = {
        "file_type": file_type,
        "content": {"elements": [{"type": "text_run", "text_run": {"text": content}}]},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/drive/v1/files/{file_token}/comments",
            headers=headers, json=body,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"添加评论失败: {data.get('msg')}"}

        return {"success": True, "comment": data.get("data")}


async def reply_comment(
    file_token: str,
    file_type: str,
    comment_id: str,
    content: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """回复评论"""
    headers = await _get_headers(user_token)
    body = {
        "content": {"elements": [{"type": "text_run", "text_run": {"text": content}}]},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/drive/v1/files/{file_token}/comments/{comment_id}/replies",
            headers=headers, json=body, params={"file_type": file_type},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"回复评论失败: {data.get('msg')}"}

        return {"success": True, "reply": data.get("data")}
