"""飞书知识库操作服务

参考 OpenClaw extensions/feishu/src/wiki.ts 实现。
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.feishu_service import get_tenant_token

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"

WIKI_ACCESS_HINT = (
    "要授予知识库访问权限：打开知识库 → 设置 → 成员 → 添加机器人。"
    "参考: https://open.feishu.cn/document/server-docs/docs/wiki-v2/wiki-qa"
)


async def _get_headers(user_token: str | None = None) -> dict[str, str]:
    token = user_token or await get_tenant_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


async def list_spaces(*, user_token: str | None = None) -> dict[str, Any]:
    """列出所有可访问的知识库空间"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{FEISHU_BASE}/wiki/v2/spaces", headers=headers)
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取知识库列表失败: {data.get('msg')}"}

        spaces = [
            {
                "space_id": s.get("space_id"),
                "name": s.get("name"),
                "description": s.get("description"),
                "visibility": s.get("visibility"),
            }
            for s in data.get("data", {}).get("items", [])
        ]
        result: dict[str, Any] = {"spaces": spaces}
        if not spaces:
            result["hint"] = WIKI_ACCESS_HINT
        return result


async def list_nodes(
    space_id: str,
    parent_node_token: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """列出知识库节点"""
    headers = await _get_headers(user_token)
    params: dict[str, Any] = {}
    if parent_node_token:
        params["parent_node_token"] = parent_node_token

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}/nodes",
            headers=headers, params=params,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取节点列表失败: {data.get('msg')}"}

        nodes = [
            {
                "node_token": n.get("node_token"),
                "obj_token": n.get("obj_token"),
                "obj_type": n.get("obj_type"),
                "title": n.get("title"),
                "has_child": n.get("has_child"),
            }
            for n in data.get("data", {}).get("items", [])
        ]
        return {"nodes": nodes}


async def get_node(token: str, *, user_token: str | None = None) -> dict[str, Any]:
    """获取节点详情"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/wiki/v2/spaces/get_node",
            headers=headers, params={"token": token},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取节点失败: {data.get('msg')}"}

        node = data.get("data", {}).get("node", {})
        return {
            "node_token": node.get("node_token"),
            "space_id": node.get("space_id"),
            "obj_token": node.get("obj_token"),
            "obj_type": node.get("obj_type"),
            "title": node.get("title"),
            "parent_node_token": node.get("parent_node_token"),
            "has_child": node.get("has_child"),
            "creator": node.get("creator"),
        }


async def create_node(
    space_id: str,
    title: str,
    obj_type: str = "docx",
    parent_node_token: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """创建知识库节点"""
    headers = await _get_headers(user_token)
    body: dict[str, Any] = {
        "obj_type": obj_type,
        "node_type": "origin",
        "title": title,
    }
    if parent_node_token:
        body["parent_node_token"] = parent_node_token

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}/nodes",
            headers=headers, json=body,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"创建节点失败: {data.get('msg')}"}

        node = data.get("data", {}).get("node", {})
        return {
            "node_token": node.get("node_token"),
            "obj_token": node.get("obj_token"),
            "obj_type": node.get("obj_type"),
            "title": node.get("title"),
        }


async def move_node(
    space_id: str,
    node_token: str,
    target_space_id: str = "",
    target_parent_token: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """移动知识库节点"""
    headers = await _get_headers(user_token)
    body: dict[str, Any] = {
        "target_space_id": target_space_id or space_id,
    }
    if target_parent_token:
        body["target_parent_token"] = target_parent_token

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}/nodes/{node_token}/move",
            headers=headers, json=body,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"移动节点失败: {data.get('msg')}"}

        return {"success": True, "node_token": node_token}


async def rename_node(
    space_id: str,
    node_token: str,
    title: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """重命名知识库节点"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/wiki/v2/spaces/{space_id}/nodes/{node_token}/update_title",
            headers=headers, json={"title": title},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"重命名失败: {data.get('msg')}"}

        return {"success": True, "node_token": node_token, "title": title}
