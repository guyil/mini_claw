"""飞书多维表格操作服务

参考 OpenClaw extensions/feishu/src/bitable.ts 实现。
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse, parse_qs

import httpx

from app.services.feishu_service import get_tenant_token

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"

FIELD_TYPE_NAMES: dict[int, str] = {
    1: "Text", 2: "Number", 3: "SingleSelect", 4: "MultiSelect",
    5: "DateTime", 7: "Checkbox", 11: "User", 13: "Phone",
    15: "URL", 17: "Attachment", 18: "SingleLink", 19: "Lookup",
    20: "Formula", 21: "DuplexLink", 22: "Location", 23: "GroupChat",
    1001: "CreatedTime", 1002: "ModifiedTime", 1003: "CreatedUser",
    1004: "ModifiedUser", 1005: "AutoNumber",
}


async def _get_headers(user_token: str | None = None) -> dict[str, str]:
    token = user_token or await get_tenant_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}


def parse_bitable_url(url: str) -> dict[str, Any] | None:
    """解析多维表格 URL，提取 token 和 table_id"""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        table_id = qs.get("table", [None])[0]

        wiki_match = re.search(r"/wiki/([A-Za-z0-9]+)", parsed.path)
        if wiki_match:
            return {"token": wiki_match.group(1), "table_id": table_id, "is_wiki": True}

        base_match = re.search(r"/base/([A-Za-z0-9]+)", parsed.path)
        if base_match:
            return {"token": base_match.group(1), "table_id": table_id, "is_wiki": False}

        return None
    except Exception:
        return None


async def _get_app_token_from_wiki(
    node_token: str, *, user_token: str | None = None
) -> str:
    """从知识库节点获取多维表格的 app_token"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/wiki/v2/spaces/get_node",
            headers=headers, params={"token": node_token},
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取节点信息失败: {data.get('msg')}")

        node = data.get("data", {}).get("node", {})
        if node.get("obj_type") != "bitable":
            raise RuntimeError(f"节点类型不是多维表格: {node.get('obj_type')}")
        return node["obj_token"]


async def get_bitable_meta(url: str, *, user_token: str | None = None) -> dict[str, Any]:
    """从 URL 获取多维表格元数据"""
    parsed = parse_bitable_url(url)
    if not parsed:
        return {"error": "无效的 URL 格式，请提供 /base/XXX 或 /wiki/XXX 格式的 URL"}

    try:
        if parsed["is_wiki"]:
            app_token = await _get_app_token_from_wiki(parsed["token"], user_token=user_token)
        else:
            app_token = parsed["token"]
    except RuntimeError as e:
        return {"error": str(e)}

    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/bitable/v1/apps/{app_token}",
            headers=headers,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取多维表格信息失败: {data.get('msg')}"}

        result: dict[str, Any] = {
            "app_token": app_token,
            "name": data.get("data", {}).get("app", {}).get("name"),
            "table_id": parsed.get("table_id"),
        }

        if not parsed.get("table_id"):
            tables_resp = await client.get(
                f"{FEISHU_BASE}/bitable/v1/apps/{app_token}/tables",
                headers=headers,
            )
            if tables_resp.json().get("code") == 0:
                tables = [
                    {"table_id": t.get("table_id"), "name": t.get("name")}
                    for t in tables_resp.json().get("data", {}).get("items", [])
                ]
                result["tables"] = tables

        return result


async def list_fields(
    app_token: str, table_id: str, *, user_token: str | None = None
) -> dict[str, Any]:
    """列出表格字段"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            headers=headers,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取字段列表失败: {data.get('msg')}"}

        fields = [
            {
                "field_id": f.get("field_id"),
                "field_name": f.get("field_name"),
                "type": f.get("type"),
                "type_name": FIELD_TYPE_NAMES.get(f.get("type", 0), f"type_{f.get('type')}"),
                "is_primary": f.get("is_primary"),
            }
            for f in data.get("data", {}).get("items", [])
        ]
        return {"fields": fields, "total": len(fields)}


async def list_records(
    app_token: str,
    table_id: str,
    page_size: int = 100,
    page_token: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """列出记录"""
    headers = await _get_headers(user_token)
    params: dict[str, Any] = {"page_size": min(page_size, 500)}
    if page_token:
        params["page_token"] = page_token

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            headers=headers, params=params,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取记录列表失败: {data.get('msg')}"}

        return {
            "records": data.get("data", {}).get("items", []),
            "has_more": data.get("data", {}).get("has_more", False),
            "page_token": data.get("data", {}).get("page_token"),
            "total": data.get("data", {}).get("total"),
        }


async def get_record(
    app_token: str, table_id: str, record_id: str, *, user_token: str | None = None
) -> dict[str, Any]:
    """获取单条记录"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            headers=headers,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取记录失败: {data.get('msg')}"}

        return {"record": data.get("data", {}).get("record")}


async def create_record(
    app_token: str, table_id: str, fields: dict[str, Any], *, user_token: str | None = None
) -> dict[str, Any]:
    """创建记录"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            headers=headers, json={"fields": fields},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"创建记录失败: {data.get('msg')}"}

        return {"record": data.get("data", {}).get("record")}


async def update_record(
    app_token: str,
    table_id: str,
    record_id: str,
    fields: dict[str, Any],
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """更新记录"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(
            f"{FEISHU_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            headers=headers, json={"fields": fields},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"更新记录失败: {data.get('msg')}"}

        return {"record": data.get("data", {}).get("record")}


async def create_bitable_app(
    name: str, folder_token: str = "", *, user_token: str | None = None
) -> dict[str, Any]:
    """创建多维表格"""
    headers = await _get_headers(user_token)
    body: dict[str, Any] = {"name": name}
    if folder_token:
        body["folder_token"] = folder_token

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/bitable/v1/apps",
            headers=headers, json=body,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"创建多维表格失败: {data.get('msg')}"}

        app = data.get("data", {}).get("app", {})
        return {
            "app_token": app.get("app_token"),
            "name": app.get("name"),
            "url": app.get("url"),
        }


async def create_field(
    app_token: str,
    table_id: str,
    field_name: str,
    field_type: int,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """创建字段"""
    headers = await _get_headers(user_token)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            headers=headers,
            json={"field_name": field_name, "type": field_type},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"创建字段失败: {data.get('msg')}"}

        return {"field": data.get("data", {}).get("field")}
