"""飞书开放平台 API 服务

封装 tenant_access_token 管理和文档读写操作。
"""

from __future__ import annotations

import logging
import re
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"

_token_cache: dict[str, tuple[str, float]] = {}


async def get_tenant_token() -> str:
    """获取 tenant_access_token（自动缓存，过期前 60s 刷新）"""
    cached = _token_cache.get("tenant")
    if cached and cached[1] > time.time():
        return cached[0]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
            json={
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret,
            },
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 tenant_access_token 失败: {data.get('msg')}")

        token = data["tenant_access_token"]
        expire = data.get("expire", 7200)
        _token_cache["tenant"] = (token, time.time() + expire - 60)
        return token


def extract_document_id(url_or_token: str) -> str:
    """从飞书文档 URL 或 token 中提取 document_id

    支持格式:
      - https://xxx.feishu.cn/docx/MJLgdRKd...
      - https://xxx.feishu.cn/wiki/MJLgdRKd...
      - MJLgdRKd...（直接 token）
    """
    m = re.search(r"(?:docx|docs|wiki)/([A-Za-z0-9]+)", url_or_token)
    if m:
        return m.group(1)
    return url_or_token.strip().split("/")[-1].split("?")[0]


async def read_document(url_or_token: str) -> str:
    """读取飞书文档纯文本内容"""
    doc_id = extract_document_id(url_or_token)
    token = await get_tenant_token()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/raw_content",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()

        if data.get("code") != 0:
            msg = data.get("msg", "未知错误")
            code = data.get("code")
            return f"读取文档失败（code={code}）: {msg}"

        return data["data"]["content"]


async def create_document(title: str, content: str, folder_token: str = "") -> str:
    """创建飞书文档并写入文本内容，返回文档链接

    步骤:
    1. POST /docx/v1/documents 创建空文档
    2. POST /docx/v1/documents/{id}/blocks/{id}/children 添加段落块
    """
    token = await get_tenant_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        create_body: dict = {"title": title}
        if folder_token:
            create_body["folder_token"] = folder_token

        resp = await client.post(
            f"{FEISHU_BASE}/docx/v1/documents",
            headers=headers,
            json=create_body,
        )
        data = resp.json()
        if data.get("code") != 0:
            msg = data.get("msg", "未知错误")
            return f"创建文档失败: {msg}"

        doc_id = data["data"]["document"]["document_id"]

        paragraphs = content.split("\n")
        blocks = []
        for para in paragraphs:
            blocks.append({
                "block_type": 2,
                "text": {
                    "elements": [
                        {
                            "text_run": {
                                "content": para,
                            }
                        }
                    ],
                    "style": {},
                },
            })
            if len(blocks) >= 50:
                break

        if blocks:
            resp2 = await client.post(
                f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                headers=headers,
                json={"children": blocks, "index": 0},
            )
            data2 = resp2.json()
            if data2.get("code") != 0:
                logger.warning("写入文档内容失败: %s", data2.get("msg"))

        doc_url = f"https://jaq9yklovs.feishu.cn/docx/{doc_id}"
        return f"文档已创建: {title}\n链接: {doc_url}"
