"""飞书文档操作服务

提供完整的飞书文档 CRUD 操作，参考 OpenClaw 的 docx.ts 实现。
使用 httpx 直接调用飞书 Open API（lark_oapi SDK 的 docx 模块功能有限）。
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.services.feishu_service import extract_document_id, get_tenant_token

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"

BLOCK_TYPE_NAMES: dict[int, str] = {
    1: "Page", 2: "Text", 3: "Heading1", 4: "Heading2", 5: "Heading3",
    6: "Heading4", 7: "Heading5", 8: "Heading6", 9: "Heading7",
    10: "Heading8", 11: "Heading9", 12: "Bullet", 13: "Ordered",
    14: "Code", 15: "Quote", 17: "Todo", 18: "Bitable", 22: "Divider",
    23: "File", 27: "Image", 31: "Table", 32: "TableCell",
}

MAX_BLOCKS_PER_INSERT = 50


async def _get_headers(user_token: str | None = None) -> dict[str, str]:
    token = user_token or await get_tenant_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }


async def read_doc(
    doc_url_or_token: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """读取文档，返回纯文本内容 + 块统计 + 结构化提示"""
    doc_id = extract_document_id(doc_url_or_token)
    headers = await _get_headers(user_token)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/raw_content",
            headers=headers,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"读取文档失败 (code={data.get('code')}): {data.get('msg')}"}

        content = data["data"]["content"]

        blocks_resp = await client.get(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks",
            headers=headers,
            params={"page_size": 500},
        )
        blocks_data = blocks_resp.json()

        block_stats: dict[str, int] = {}
        has_structured = False
        if blocks_data.get("code") == 0:
            items = blocks_data.get("data", {}).get("items", [])
            for item in items:
                bt = item.get("block_type", 0)
                name = BLOCK_TYPE_NAMES.get(bt, f"type_{bt}")
                block_stats[name] = block_stats.get(name, 0) + 1
                if bt in (18, 27, 31):
                    has_structured = True

        result: dict[str, Any] = {
            "doc_token": doc_id,
            "content": content,
            "block_types": block_stats,
        }
        if has_structured:
            result["hint"] = (
                "文档包含表格/图片等结构化内容，"
                "使用 action='list_blocks' 获取完整块数据"
            )
        return result


async def write_doc(
    doc_url_or_token: str,
    markdown: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """用 Markdown 替换整个文档内容"""
    doc_id = extract_document_id(doc_url_or_token)
    headers = await _get_headers(user_token)

    async with httpx.AsyncClient(timeout=60) as client:
        blocks_resp = await client.get(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks",
            headers=headers,
            params={"page_size": 500},
        )
        blocks_data = blocks_resp.json()
        if blocks_data.get("code") != 0:
            return {"error": f"获取文档块失败: {blocks_data.get('msg')}"}

        items = blocks_data.get("data", {}).get("items", [])
        page_block_id = doc_id
        child_ids = []
        for item in items:
            bid = item.get("block_id", "")
            if item.get("block_type") == 1:
                page_block_id = bid
            elif item.get("parent_id") == page_block_id:
                child_ids.append(bid)

        for bid in child_ids:
            await client.request(
                "DELETE",
                f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{bid}",
                headers=headers,
            )

        new_blocks = _markdown_to_blocks(markdown)
        inserted = 0
        for i in range(0, len(new_blocks), MAX_BLOCKS_PER_INSERT):
            batch = new_blocks[i : i + MAX_BLOCKS_PER_INSERT]
            resp = await client.post(
                f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{page_block_id}/children",
                headers=headers,
                json={"children": batch, "index": inserted},
            )
            r = resp.json()
            if r.get("code") != 0:
                return {"error": f"写入内容失败: {r.get('msg')}", "inserted": inserted}
            inserted += len(batch)

        return {"success": True, "doc_token": doc_id, "blocks_written": inserted}


async def append_doc(
    doc_url_or_token: str,
    markdown: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """在文档末尾追加 Markdown 内容"""
    doc_id = extract_document_id(doc_url_or_token)
    headers = await _get_headers(user_token)

    new_blocks = _markdown_to_blocks(markdown)

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
            headers=headers,
            json={"children": new_blocks, "index": -1},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"追加内容失败: {data.get('msg')}"}

        return {"success": True, "doc_token": doc_id, "blocks_appended": len(new_blocks)}


async def insert_doc(
    doc_url_or_token: str,
    markdown: str,
    after_block_id: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """在指定块之后插入 Markdown 内容"""
    doc_id = extract_document_id(doc_url_or_token)
    headers = await _get_headers(user_token)

    new_blocks = _markdown_to_blocks(markdown)

    async with httpx.AsyncClient(timeout=60) as client:
        blocks_resp = await client.get(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{after_block_id}",
            headers=headers,
        )
        block_data = blocks_resp.json()
        if block_data.get("code") != 0:
            return {"error": f"找不到目标块: {block_data.get('msg')}"}

        parent_id = block_data.get("data", {}).get("block", {}).get("parent_id", doc_id)

        parent_resp = await client.get(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{parent_id}",
            headers=headers,
        )
        parent_data = parent_resp.json()
        children = parent_data.get("data", {}).get("block", {}).get("children", [])

        index = 0
        for i, cid in enumerate(children):
            if cid == after_block_id:
                index = i + 1
                break

        resp = await client.post(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{parent_id}/children",
            headers=headers,
            json={"children": new_blocks, "index": index},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"插入内容失败: {data.get('msg')}"}

        return {"success": True, "doc_token": doc_id, "blocks_inserted": len(new_blocks)}


async def create_doc(
    title: str,
    folder_token: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """创建新文档"""
    headers = await _get_headers(user_token)

    create_body: dict[str, str] = {"title": title}
    if folder_token:
        create_body["folder_token"] = folder_token

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/docx/v1/documents",
            headers=headers,
            json=create_body,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"创建文档失败: {data.get('msg')}"}

        doc_info = data["data"]["document"]
        doc_id = doc_info["document_id"]

        from app.services.feishu_client import get_doc_url_base
        url_base = get_doc_url_base()
        doc_url = f"{url_base}/docx/{doc_id}"

        return {
            "success": True,
            "doc_token": doc_id,
            "title": title,
            "url": doc_url,
            "revision_id": doc_info.get("revision_id"),
        }


async def list_blocks(
    doc_url_or_token: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """列出文档所有块"""
    doc_id = extract_document_id(doc_url_or_token)
    headers = await _get_headers(user_token)

    all_items: list[dict] = []
    page_token = None

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict[str, Any] = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            resp = await client.get(
                f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks",
                headers=headers,
                params=params,
            )
            data = resp.json()
            if data.get("code") != 0:
                return {"error": f"获取块列表失败: {data.get('msg')}"}

            items = data.get("data", {}).get("items", [])
            all_items.extend(items)
            page_token = data.get("data", {}).get("page_token")
            if not page_token or not data.get("data", {}).get("has_more"):
                break

    blocks = []
    for item in all_items:
        bt = item.get("block_type", 0)
        block_info: dict[str, Any] = {
            "block_id": item.get("block_id"),
            "block_type": bt,
            "type_name": BLOCK_TYPE_NAMES.get(bt, f"type_{bt}"),
            "parent_id": item.get("parent_id"),
        }
        if item.get("children"):
            block_info["children"] = item["children"]

        content_key = _get_content_key(bt)
        if content_key and content_key in item:
            block_info[content_key] = item[content_key]

        blocks.append(block_info)

    return {"doc_token": doc_id, "blocks": blocks, "total": len(blocks)}


async def get_block(
    doc_url_or_token: str,
    block_id: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """获取单个块的详细信息"""
    doc_id = extract_document_id(doc_url_or_token)
    headers = await _get_headers(user_token)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{block_id}",
            headers=headers,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"获取块失败: {data.get('msg')}"}

        return {"block": data.get("data", {}).get("block")}


async def update_block(
    doc_url_or_token: str,
    block_id: str,
    content: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """更新块的文本内容"""
    doc_id = extract_document_id(doc_url_or_token)
    headers = await _get_headers(user_token)

    update_body = {
        "update_text_elements": {
            "elements": [{"text_run": {"content": content}}],
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{block_id}",
            headers=headers,
            json=update_body,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"更新块失败: {data.get('msg')}"}

        return {"success": True, "block_id": block_id}


async def delete_block(
    doc_url_or_token: str,
    block_id: str,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """删除一个块"""
    doc_id = extract_document_id(doc_url_or_token)
    headers = await _get_headers(user_token)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            "DELETE",
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{block_id}",
            headers=headers,
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"删除块失败: {data.get('msg')}"}

        return {"success": True, "block_id": block_id}


async def create_table(
    doc_url_or_token: str,
    row_size: int,
    column_size: int,
    parent_block_id: str = "",
    column_width: list[int] | None = None,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """在文档中创建表格"""
    doc_id = extract_document_id(doc_url_or_token)
    headers = await _get_headers(user_token)
    parent = parent_block_id or doc_id

    table_block: dict[str, Any] = {
        "block_type": 31,
        "table": {
            "property": {
                "row_size": row_size,
                "column_size": column_size,
            }
        },
    }
    if column_width:
        table_block["table"]["property"]["column_width"] = column_width

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{parent}/children",
            headers=headers,
            json={"children": [table_block], "index": -1},
        )
        data = resp.json()
        if data.get("code") != 0:
            return {"error": f"创建表格失败: {data.get('msg')}"}

        children = data.get("data", {}).get("children", {})
        return {"success": True, "doc_token": doc_id, "table": children}


async def write_table_cells(
    doc_url_or_token: str,
    table_block_id: str,
    values: list[list[str]],
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """向表格单元格写入内容"""
    doc_id = extract_document_id(doc_url_or_token)
    headers = await _get_headers(user_token)

    async with httpx.AsyncClient(timeout=30) as client:
        block_resp = await client.get(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{table_block_id}",
            headers=headers,
        )
        block_data = block_resp.json()
        if block_data.get("code") != 0:
            return {"error": f"获取表格块失败: {block_data.get('msg')}"}

        block = block_data.get("data", {}).get("block", {})
        cell_ids = block.get("children", [])

        table_prop = block.get("table", {}).get("property", {})
        col_size = table_prop.get("column_size", 0)
        if not col_size:
            return {"error": "无法确定表格列数"}

        cells_written = 0
        for row_idx, row_values in enumerate(values):
            for col_idx, cell_value in enumerate(row_values):
                cell_index = row_idx * col_size + col_idx
                if cell_index >= len(cell_ids):
                    break
                cell_id = cell_ids[cell_index]

                update_body = {
                    "update_text_elements": {
                        "elements": [{"text_run": {"content": str(cell_value)}}],
                    }
                }
                resp = await client.patch(
                    f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{cell_id}",
                    headers=headers,
                    json=update_body,
                )
                if resp.json().get("code") == 0:
                    cells_written += 1

        return {"success": True, "cells_written": cells_written}


async def create_table_with_values(
    doc_url_or_token: str,
    row_size: int,
    column_size: int,
    values: list[list[str]],
    parent_block_id: str = "",
    column_width: list[int] | None = None,
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """一步创建带数据的表格"""
    create_result = await create_table(
        doc_url_or_token, row_size, column_size,
        parent_block_id, column_width, user_token=user_token,
    )
    if "error" in create_result:
        return create_result

    table_info = create_result.get("table", {})
    table_block_id_list = list(table_info.keys()) if isinstance(table_info, dict) else []
    if not table_block_id_list:
        return {"error": "表格创建成功但无法获取表格块 ID"}

    table_bid = table_block_id_list[0]
    write_result = await write_table_cells(
        doc_url_or_token, table_bid, values, user_token=user_token,
    )
    return {**create_result, **write_result}


async def upload_image(
    doc_url_or_token: str,
    url: str = "",
    file_path: str = "",
    parent_block_id: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """上传图片到文档"""
    doc_id = extract_document_id(doc_url_or_token)

    if not url and not file_path:
        return {"error": "需要提供 url 或 file_path"}

    image_data: bytes
    filename = "image.png"

    if url:
        async with httpx.AsyncClient(timeout=120) as client:
            img_resp = await client.get(url)
            if img_resp.status_code != 200:
                return {"error": f"下载图片失败: HTTP {img_resp.status_code}"}
            image_data = img_resp.content
            filename = url.split("/")[-1].split("?")[0] or filename
    else:
        import os
        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}
        with open(file_path, "rb") as f:
            image_data = f.read()
        filename = os.path.basename(file_path)

    parent = parent_block_id or doc_id
    token = user_token or await get_tenant_token()

    async with httpx.AsyncClient(timeout=120) as client:
        upload_resp = await client.post(
            f"{FEISHU_BASE}/drive/v1/medias/upload_all",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "file_name": filename,
                "parent_type": "docx_image",
                "parent_node": doc_id,
                "size": str(len(image_data)),
            },
            files={"file": (filename, image_data)},
        )
        upload_data = upload_resp.json()
        if upload_data.get("code") != 0:
            return {"error": f"上传图片失败: {upload_data.get('msg')}"}

        file_token = upload_data["data"]["file_token"]

        block = {
            "block_type": 27,
            "image": {"token": file_token},
        }
        insert_resp = await client.post(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{parent}/children",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={"children": [block], "index": -1},
        )
        insert_data = insert_resp.json()
        if insert_data.get("code") != 0:
            return {"error": f"插入图片块失败: {insert_data.get('msg')}"}

        return {"success": True, "file_token": file_token, "doc_token": doc_id}


async def upload_file(
    doc_url_or_token: str,
    url: str = "",
    file_path: str = "",
    parent_block_id: str = "",
    filename: str = "",
    *,
    user_token: str | None = None,
) -> dict[str, Any]:
    """上传文件附件到文档"""
    doc_id = extract_document_id(doc_url_or_token)

    if not url and not file_path:
        return {"error": "需要提供 url 或 file_path"}

    file_data: bytes
    final_name = filename or "file"

    if url:
        async with httpx.AsyncClient(timeout=120) as client:
            dl_resp = await client.get(url)
            if dl_resp.status_code != 200:
                return {"error": f"下载文件失败: HTTP {dl_resp.status_code}"}
            file_data = dl_resp.content
            if not filename:
                final_name = url.split("/")[-1].split("?")[0] or "file"
    else:
        import os
        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}
        with open(file_path, "rb") as f:
            file_data = f.read()
        if not filename:
            final_name = os.path.basename(file_path)

    parent = parent_block_id or doc_id
    token = user_token or await get_tenant_token()

    async with httpx.AsyncClient(timeout=120) as client:
        upload_resp = await client.post(
            f"{FEISHU_BASE}/drive/v1/medias/upload_all",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "file_name": final_name,
                "parent_type": "docx_file",
                "parent_node": doc_id,
                "size": str(len(file_data)),
            },
            files={"file": (final_name, file_data)},
        )
        upload_data = upload_resp.json()
        if upload_data.get("code") != 0:
            return {"error": f"上传文件失败: {upload_data.get('msg')}"}

        file_token = upload_data["data"]["file_token"]

        block = {
            "block_type": 23,
            "file": {"token": file_token},
        }
        insert_resp = await client.post(
            f"{FEISHU_BASE}/docx/v1/documents/{doc_id}/blocks/{parent}/children",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={"children": [block], "index": -1},
        )
        insert_data = insert_resp.json()
        if insert_data.get("code") != 0:
            return {"error": f"插入文件块失败: {insert_data.get('msg')}"}

        return {"success": True, "file_token": file_token, "doc_token": doc_id}


def _get_content_key(block_type: int) -> str | None:
    """根据块类型返回对应的内容字段名"""
    mapping = {
        2: "text", 3: "heading1", 4: "heading2", 5: "heading3",
        6: "heading4", 7: "heading5", 8: "heading6", 9: "heading7",
        10: "heading8", 11: "heading9", 12: "bullet", 13: "ordered",
        14: "code", 15: "quote", 17: "todo", 22: "divider",
        27: "image", 23: "file", 31: "table", 32: "table_cell",
    }
    return mapping.get(block_type)


def _markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    """将 Markdown 文本转换为飞书文档块列表

    支持: 标题 (#), 无序列表 (-/*/+), 有序列表 (1.), 代码块 (```),
    引用 (>), 分割线 (---), 粗体/斜体/删除线, 链接, 普通段落
    """
    lines = markdown.split("\n")
    blocks: list[dict[str, Any]] = []
    i = 0
    in_code_block = False
    code_lines: list[str] = []
    code_lang = ""

    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            if in_code_block:
                blocks.append(_make_code_block("\n".join(code_lines), code_lang))
                code_lines = []
                code_lang = ""
                in_code_block = False
            else:
                in_code_block = True
                code_lang = line[3:].strip()
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("# "):
            blocks.append(_make_heading_block(stripped[2:], 3))
        elif stripped.startswith("## "):
            blocks.append(_make_heading_block(stripped[3:], 4))
        elif stripped.startswith("### "):
            blocks.append(_make_heading_block(stripped[4:], 5))
        elif stripped.startswith("#### "):
            blocks.append(_make_heading_block(stripped[5:], 6))
        elif stripped.startswith("##### "):
            blocks.append(_make_heading_block(stripped[6:], 7))
        elif stripped.startswith("###### "):
            blocks.append(_make_heading_block(stripped[7:], 8))
        elif re.match(r"^- \[[ xX]\]\s", stripped):
            checked = stripped[3] in ("x", "X")
            content = stripped[6:]
            blocks.append(_make_todo_block(content, checked))
        elif re.match(r"^[-*+]\s", stripped):
            blocks.append(_make_list_block(stripped[2:], 12))
        elif re.match(r"^\d+\.\s", stripped):
            content = re.sub(r"^\d+\.\s", "", stripped)
            blocks.append(_make_list_block(content, 13))
        elif stripped.startswith("> "):
            blocks.append(_make_text_block(stripped[2:], 15))
        elif stripped in ("---", "***", "___"):
            blocks.append({"block_type": 22, "divider": {}})
        else:
            blocks.append(_make_text_block(stripped, 2))

        i += 1

    if in_code_block and code_lines:
        blocks.append(_make_code_block("\n".join(code_lines), code_lang))

    return blocks


def _parse_inline_elements(text: str) -> list[dict[str, Any]]:
    """解析内联格式（粗体、斜体、删除线、链接）"""
    elements: list[dict[str, Any]] = []
    pattern = re.compile(
        r"\*\*\*(.+?)\*\*\*"
        r"|\*\*(.+?)\*\*"
        r"|\*(.+?)\*"
        r"|~~(.+?)~~"
        r"|\[([^\]]+)\]\(([^)]+)\)"
        r"|([^*~\[]+)"
    )
    for m in pattern.finditer(text):
        if m.group(1):
            elements.append({
                "text_run": {
                    "content": m.group(1),
                    "text_element_style": {"bold": True, "italic": True},
                }
            })
        elif m.group(2):
            elements.append({
                "text_run": {
                    "content": m.group(2),
                    "text_element_style": {"bold": True},
                }
            })
        elif m.group(3):
            elements.append({
                "text_run": {
                    "content": m.group(3),
                    "text_element_style": {"italic": True},
                }
            })
        elif m.group(4):
            elements.append({
                "text_run": {
                    "content": m.group(4),
                    "text_element_style": {"strikethrough": True},
                }
            })
        elif m.group(5):
            elements.append({
                "text_run": {
                    "content": m.group(5),
                    "text_element_style": {"link": {"url": m.group(6)}},
                }
            })
        elif m.group(7):
            elements.append({"text_run": {"content": m.group(7)}})

    if not elements:
        elements.append({"text_run": {"content": text}})

    return elements


def _make_text_block(content: str, block_type: int = 2) -> dict[str, Any]:
    """创建文本块"""
    content_key = {
        2: "text", 15: "quote",
    }.get(block_type, "text")
    return {
        "block_type": block_type,
        content_key: {
            "elements": _parse_inline_elements(content),
            "style": {},
        },
    }


def _make_heading_block(content: str, block_type: int) -> dict[str, Any]:
    """创建标题块"""
    key_map = {
        3: "heading1", 4: "heading2", 5: "heading3",
        6: "heading4", 7: "heading5", 8: "heading6",
    }
    key = key_map.get(block_type, "heading1")
    return {
        "block_type": block_type,
        key: {
            "elements": _parse_inline_elements(content),
            "style": {},
        },
    }


def _make_list_block(content: str, block_type: int) -> dict[str, Any]:
    """创建列表块"""
    key = "bullet" if block_type == 12 else "ordered"
    return {
        "block_type": block_type,
        key: {
            "elements": _parse_inline_elements(content),
            "style": {},
        },
    }


def _make_code_block(content: str, language: str = "") -> dict[str, Any]:
    """创建代码块"""
    lang_map = {
        "python": 49, "py": 49, "javascript": 24, "js": 24,
        "typescript": 62, "ts": 62, "java": 23, "go": 18,
        "rust": 52, "sql": 56, "bash": 5, "sh": 5,
        "json": 26, "yaml": 67, "html": 22, "css": 11,
    }
    lang_id = lang_map.get(language.lower(), 49) if language else 49

    return {
        "block_type": 14,
        "code": {
            "elements": [{"text_run": {"content": content}}],
            "style": {"language": lang_id, "wrap": True},
        },
    }


def _make_todo_block(content: str, checked: bool = False) -> dict[str, Any]:
    """创建待办事项块"""
    return {
        "block_type": 17,
        "todo": {
            "elements": _parse_inline_elements(content),
            "style": {"done": checked},
        },
    }
