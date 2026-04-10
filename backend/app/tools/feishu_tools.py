"""飞书工具集

将飞书各服务模块整合为 LangChain StructuredTool，按工具组条件注册。
参考 OpenClaw 的 action-based 工具设计模式。

认证集成:
- 包含 feishu_auth 工具，允许 AI 在对话中引导用户完成飞书授权
- 所有飞书工具在权限不足时自动返回授权引导信息
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import StructuredTool
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.feishu_service import (
    build_feishu_authorize_url,
    diagnose_feishu_auth,
    get_user_feishu_token,
)

logger = logging.getLogger(__name__)

_AUTH_REQUIRED_HINT = (
    "需要用户授权飞书权限。请引导用户点击以下链接完成授权，"
    "授权完成后用户回到对话即可继续操作。"
)


def _json_result(data: Any) -> str:
    """序列化结果，自动检测权限错误并注入授权引导"""
    if isinstance(data, dict) and "error" in data:
        _inject_auth_hint(data)
    return json.dumps(data, ensure_ascii=False, indent=2)


_FEISHU_AUTH_ERROR_CODES = {
    "99991679",  # user_access_token invalid
    "99991668",  # token expired
    "99991664",  # token invalid
    "99991663",  # no permission
    "99991672",  # insufficient scope
}


def _inject_auth_hint(result: dict[str, Any]) -> dict[str, Any]:
    """当检测到飞书 token 失效或权限不足时，在结果中注入授权引导

    仅匹配飞书特定的认证/权限错误码，避免误匹配 field validation 等无关错误。
    """
    msg = str(result.get("error", ""))
    is_auth_error = any(code in msg for code in _FEISHU_AUTH_ERROR_CODES)
    if not is_auth_error and "Unauthorized" in msg:
        is_auth_error = True
    if is_auth_error:
        result["auth_required"] = True
        result["authorize_url"] = build_feishu_authorize_url(source="chat")
        result["auth_hint"] = _AUTH_REQUIRED_HINT
    return result


def create_feishu_tools(
    db: AsyncSession | None, user_id: str
) -> list[StructuredTool]:
    """创建飞书工具集，根据 settings 中的开关条件注册"""

    if not settings.feishu_app_id or not settings.feishu_app_secret:
        return []

    async def _get_token() -> str | None:
        if db is None:
            return None
        try:
            return await get_user_feishu_token(db, user_id)
        except Exception:
            return None

    tools: list[StructuredTool] = []

    tools.append(_create_auth_tool(db, user_id))

    if settings.feishu_tools_doc:
        tools.append(_create_doc_tool(_get_token))

    if settings.feishu_tools_wiki:
        tools.append(_create_wiki_tool(_get_token))

    if settings.feishu_tools_drive:
        tools.append(_create_drive_tool(_get_token))

    if settings.feishu_tools_chat:
        tools.extend(_create_chat_tools(_get_token))

    if settings.feishu_tools_bitable:
        tools.extend(_create_bitable_tools(_get_token))

    if settings.feishu_tools_perm:
        tools.append(_create_perm_tool(_get_token))

    if settings.feishu_tools_calendar:
        tools.extend(_create_calendar_tools(_get_token))

    if settings.feishu_tools_task:
        tools.extend(_create_task_tools(_get_token))

    return tools


def _create_auth_tool(db: AsyncSession | None, user_id: str) -> StructuredTool:
    """创建飞书认证工具，支持在对话中完成授权"""

    async def _feishu_auth(action: str = "check") -> str:
        if action == "authorize":
            url = build_feishu_authorize_url(source="chat")
            return _json_result({
                "authorize_url": url,
                "instructions": (
                    "请点击上方链接完成飞书授权。授权后飞书会跳转回应用页面，"
                    "回到本对话即可继续操作。授权将获得以下权限：\n"
                    "- 文档读写\n- 知识库管理\n- 云空间管理\n"
                    "- 日历日程\n- 任务管理\n- 消息收发\n- 多维表格"
                ),
            })

        if action == "check":
            if db is None:
                return _json_result({
                    "status": "no_database",
                    "message": "数据库不可用，无法检查认证状态",
                })

            token = await get_user_feishu_token(db, user_id)
            if token:
                return _json_result({
                    "status": "ready",
                    "message": "飞书已授权，token 有效，可以直接执行飞书操作。",
                    "has_valid_token": True,
                })

            result = await diagnose_feishu_auth(db, user_id)
            if result.get("recommendations"):
                result["authorize_url"] = build_feishu_authorize_url(source="chat")
            return _json_result(result)

        return _json_result({"error": f"未知的 action: {action}，支持: check, authorize"})

    return StructuredTool.from_function(
        coroutine=_feishu_auth,
        name="feishu_auth",
        description=(
            "飞书认证管理。仅在飞书操作返回认证错误时才需要调用。\n"
            "用户通过飞书登录后已自动获得全部飞书权限，通常无需额外授权。\n"
            "Actions:\n"
            "- check: 检查当前飞书认证状态\n"
            "- authorize: 生成授权链接（仅在 token 失效时使用）"
        ),
    )


def _create_doc_tool(get_token) -> StructuredTool:
    from app.services import feishu_doc_service as doc_svc

    async def _feishu_doc(
        action: str,
        doc_token: str = "",
        content: str = "",
        title: str = "",
        folder_token: str = "",
        block_id: str = "",
        after_block_id: str = "",
        row_size: int = 0,
        column_size: int = 0,
        table_block_id: str = "",
        values: str = "[]",
        parent_block_id: str = "",
        url: str = "",
        file_path: str = "",
        filename: str = "",
        column_width: str = "",
    ) -> str:
        user_token = await get_token()
        kw: dict[str, Any] = {"user_token": user_token}
        try:
            if action == "read":
                return _json_result(await doc_svc.read_doc(doc_token, **kw))
            elif action == "write":
                return _json_result(await doc_svc.write_doc(doc_token, content, **kw))
            elif action == "append":
                return _json_result(await doc_svc.append_doc(doc_token, content, **kw))
            elif action == "insert":
                return _json_result(
                    await doc_svc.insert_doc(doc_token, content, after_block_id, **kw)
                )
            elif action == "create":
                return _json_result(await doc_svc.create_doc(title, folder_token, **kw))
            elif action == "list_blocks":
                return _json_result(await doc_svc.list_blocks(doc_token, **kw))
            elif action == "get_block":
                return _json_result(await doc_svc.get_block(doc_token, block_id, **kw))
            elif action == "update_block":
                return _json_result(
                    await doc_svc.update_block(doc_token, block_id, content, **kw)
                )
            elif action == "delete_block":
                return _json_result(await doc_svc.delete_block(doc_token, block_id, **kw))
            elif action == "create_table":
                cw = json.loads(column_width) if column_width else None
                return _json_result(
                    await doc_svc.create_table(
                        doc_token, row_size, column_size, parent_block_id, cw, **kw
                    )
                )
            elif action == "write_table_cells":
                vals = json.loads(values)
                return _json_result(
                    await doc_svc.write_table_cells(doc_token, table_block_id, vals, **kw)
                )
            elif action == "create_table_with_values":
                vals = json.loads(values)
                cw = json.loads(column_width) if column_width else None
                return _json_result(
                    await doc_svc.create_table_with_values(
                        doc_token, row_size, column_size, vals, parent_block_id, cw, **kw
                    )
                )
            elif action == "upload_image":
                return _json_result(
                    await doc_svc.upload_image(
                        doc_token, url=url, file_path=file_path,
                        parent_block_id=parent_block_id, **kw,
                    )
                )
            elif action == "upload_file":
                return _json_result(
                    await doc_svc.upload_file(
                        doc_token, url=url, file_path=file_path,
                        parent_block_id=parent_block_id, filename=filename, **kw,
                    )
                )
            else:
                return _json_result({"error": f"未知的 action: {action}"})
        except Exception as e:
            return _json_result({"error": str(e)})

    return StructuredTool.from_function(
        coroutine=_feishu_doc,
        name="feishu_doc",
        description=(
            "飞书文档操作。Actions: read, write, append, insert, create, "
            "list_blocks, get_block, update_block, delete_block, "
            "create_table, write_table_cells, create_table_with_values, "
            "upload_image, upload_file。"
            "从 URL 提取 doc_token: https://xxx.feishu.cn/docx/ABC → doc_token='ABC'"
        ),
    )


def _create_wiki_tool(get_token) -> StructuredTool:
    from app.services import feishu_wiki_service as wiki_svc

    async def _feishu_wiki(
        action: str,
        space_id: str = "",
        token: str = "",
        node_token: str = "",
        title: str = "",
        obj_type: str = "docx",
        parent_node_token: str = "",
        target_space_id: str = "",
        target_parent_token: str = "",
    ) -> str:
        user_token = await get_token()
        kw: dict[str, Any] = {"user_token": user_token}
        try:
            if action == "spaces":
                return _json_result(await wiki_svc.list_spaces(**kw))
            elif action == "nodes":
                return _json_result(
                    await wiki_svc.list_nodes(space_id, parent_node_token, **kw)
                )
            elif action == "get":
                return _json_result(await wiki_svc.get_node(token, **kw))
            elif action == "create":
                return _json_result(
                    await wiki_svc.create_node(
                        space_id, title, obj_type, parent_node_token, **kw
                    )
                )
            elif action == "move":
                return _json_result(
                    await wiki_svc.move_node(
                        space_id, node_token, target_space_id, target_parent_token, **kw
                    )
                )
            elif action == "rename":
                return _json_result(
                    await wiki_svc.rename_node(space_id, node_token, title, **kw)
                )
            else:
                return _json_result({"error": f"未知的 action: {action}"})
        except Exception as e:
            return _json_result({"error": str(e)})

    return StructuredTool.from_function(
        coroutine=_feishu_wiki,
        name="feishu_wiki",
        description=(
            "飞书知识库操作。Actions: spaces, nodes, get, create, move, rename。"
            "编辑知识库页面内容: 先用 get 获取 obj_token，再用 feishu_doc 读写。"
        ),
    )


def _create_drive_tool(get_token) -> StructuredTool:
    from app.services import feishu_drive_service as drive_svc

    async def _feishu_drive(
        action: str,
        folder_token: str = "",
        file_token: str = "",
        file_type: str = "docx",
        name: str = "",
        target_folder_token: str = "",
        comment_id: str = "",
        content: str = "",
    ) -> str:
        user_token = await get_token()
        kw: dict[str, Any] = {"user_token": user_token}
        try:
            if action == "list":
                return _json_result(await drive_svc.list_files(folder_token, **kw))
            elif action == "info":
                return _json_result(await drive_svc.get_file_info(file_token, file_type, **kw))
            elif action == "create_folder":
                return _json_result(await drive_svc.create_folder(name, folder_token, **kw))
            elif action == "move":
                return _json_result(
                    await drive_svc.move_file(file_token, file_type, target_folder_token, **kw)
                )
            elif action == "delete":
                return _json_result(await drive_svc.delete_file(file_token, file_type, **kw))
            elif action == "list_comments":
                return _json_result(
                    await drive_svc.list_comments(file_token, file_type, **kw)
                )
            elif action == "add_comment":
                return _json_result(
                    await drive_svc.add_comment(file_token, file_type, content, **kw)
                )
            elif action == "reply_comment":
                return _json_result(
                    await drive_svc.reply_comment(
                        file_token, file_type, comment_id, content, **kw
                    )
                )
            else:
                return _json_result({"error": f"未知的 action: {action}"})
        except Exception as e:
            return _json_result({"error": str(e)})

    return StructuredTool.from_function(
        coroutine=_feishu_drive,
        name="feishu_drive",
        description=(
            "飞书云空间操作。Actions: list, info, create_folder, move, delete, "
            "list_comments, add_comment, reply_comment。"
        ),
    )


def _create_chat_tools(get_token) -> list[StructuredTool]:
    from app.services import feishu_chat_service as chat_svc

    async def _feishu_chat(
        action: str,
        chat_id: str = "",
        member_id: str = "",
        member_id_type: str = "open_id",
        page_size: int = 50,
        page_token: str = "",
    ) -> str:
        user_token = await get_token()
        kw: dict[str, Any] = {"user_token": user_token}
        try:
            if action == "info":
                return _json_result(await chat_svc.get_chat_info(chat_id, **kw))
            elif action == "members":
                return _json_result(
                    await chat_svc.get_chat_members(
                        chat_id, page_size, page_token, member_id_type, **kw
                    )
                )
            elif action == "member_info":
                return _json_result(
                    await chat_svc.get_member_info(member_id, member_id_type, **kw)
                )
            else:
                return _json_result({"error": f"未知的 action: {action}"})
        except Exception as e:
            return _json_result({"error": str(e)})

    async def _feishu_message(
        receive_id: str,
        content: str,
        msg_type: str = "text",
        receive_id_type: str = "chat_id",
    ) -> str:
        user_token = await get_token()
        try:
            result = await chat_svc.send_message(
                receive_id, content, msg_type, receive_id_type, user_token=user_token,
            )
            return _json_result(result)
        except Exception as e:
            return _json_result({"error": str(e)})

    return [
        StructuredTool.from_function(
            coroutine=_feishu_chat,
            name="feishu_chat",
            description=(
                "飞书群聊信息查询。Actions: info, members, member_info。"
            ),
        ),
        StructuredTool.from_function(
            coroutine=_feishu_message,
            name="feishu_message",
            description="向飞书群聊或用户发送消息。支持 text 和 interactive 类型。",
        ),
    ]


def _create_bitable_tools(get_token) -> list[StructuredTool]:
    from app.services import feishu_bitable_service as bt_svc

    async def _bt_get_meta(url: str) -> str:
        user_token = await get_token()
        try:
            return _json_result(await bt_svc.get_bitable_meta(url, user_token=user_token))
        except Exception as e:
            return _json_result({"error": str(e)})

    async def _bt_list_fields(app_token: str, table_id: str) -> str:
        user_token = await get_token()
        try:
            return _json_result(
                await bt_svc.list_fields(app_token, table_id, user_token=user_token)
            )
        except Exception as e:
            return _json_result({"error": str(e)})

    async def _bt_list_records(
        app_token: str, table_id: str, page_size: int = 100, page_token: str = ""
    ) -> str:
        user_token = await get_token()
        try:
            return _json_result(
                await bt_svc.list_records(
                    app_token, table_id, page_size, page_token, user_token=user_token
                )
            )
        except Exception as e:
            return _json_result({"error": str(e)})

    async def _bt_get_record(app_token: str, table_id: str, record_id: str) -> str:
        user_token = await get_token()
        try:
            return _json_result(
                await bt_svc.get_record(app_token, table_id, record_id, user_token=user_token)
            )
        except Exception as e:
            return _json_result({"error": str(e)})

    async def _bt_create_record(app_token: str, table_id: str, fields: str = "{}") -> str:
        user_token = await get_token()
        try:
            return _json_result(
                await bt_svc.create_record(
                    app_token, table_id, json.loads(fields), user_token=user_token
                )
            )
        except Exception as e:
            return _json_result({"error": str(e)})

    async def _bt_update_record(
        app_token: str, table_id: str, record_id: str, fields: str = "{}"
    ) -> str:
        user_token = await get_token()
        try:
            return _json_result(
                await bt_svc.update_record(
                    app_token, table_id, record_id, json.loads(fields), user_token=user_token
                )
            )
        except Exception as e:
            return _json_result({"error": str(e)})

    async def _bt_create_app(name: str, folder_token: str = "") -> str:
        user_token = await get_token()
        try:
            return _json_result(
                await bt_svc.create_bitable_app(name, folder_token, user_token=user_token)
            )
        except Exception as e:
            return _json_result({"error": str(e)})

    async def _bt_create_field(
        app_token: str, table_id: str, field_name: str, field_type: int = 1
    ) -> str:
        user_token = await get_token()
        try:
            return _json_result(
                await bt_svc.create_field(
                    app_token, table_id, field_name, field_type, user_token=user_token
                )
            )
        except Exception as e:
            return _json_result({"error": str(e)})

    return [
        StructuredTool.from_function(
            coroutine=_bt_get_meta, name="feishu_bitable_get_meta",
            description="获取飞书多维表格元数据。传入多维表格 URL。",
        ),
        StructuredTool.from_function(
            coroutine=_bt_list_fields, name="feishu_bitable_list_fields",
            description="列出多维表格字段。需要 app_token 和 table_id。",
        ),
        StructuredTool.from_function(
            coroutine=_bt_list_records, name="feishu_bitable_list_records",
            description="列出多维表格记录。需要 app_token 和 table_id。",
        ),
        StructuredTool.from_function(
            coroutine=_bt_get_record, name="feishu_bitable_get_record",
            description="获取多维表格单条记录。需要 app_token, table_id, record_id。",
        ),
        StructuredTool.from_function(
            coroutine=_bt_create_record, name="feishu_bitable_create_record",
            description="创建多维表格记录。fields 为 JSON 字符串 {字段名: 值}。",
        ),
        StructuredTool.from_function(
            coroutine=_bt_update_record, name="feishu_bitable_update_record",
            description="更新多维表格记录。fields 为 JSON 字符串 {字段名: 值}。",
        ),
        StructuredTool.from_function(
            coroutine=_bt_create_app, name="feishu_bitable_create_app",
            description="创建新的多维表格。",
        ),
        StructuredTool.from_function(
            coroutine=_bt_create_field, name="feishu_bitable_create_field",
            description="在多维表格中创建字段。field_type: 1=Text, 2=Number, 3=SingleSelect, 5=DateTime 等。",
        ),
    ]


def _create_perm_tool(get_token) -> StructuredTool:
    from app.services import feishu_perm_service as perm_svc

    async def _feishu_perm(
        action: str,
        token: str = "",
        doc_type: str = "docx",
        member_type: str = "",
        member_id: str = "",
        perm: str = "view",
    ) -> str:
        user_token = await get_token()
        kw: dict[str, Any] = {"user_token": user_token}
        try:
            if action == "list":
                return _json_result(await perm_svc.list_members(token, doc_type, **kw))
            elif action == "add":
                return _json_result(
                    await perm_svc.add_member(token, doc_type, member_type, member_id, perm, **kw)
                )
            elif action == "remove":
                return _json_result(
                    await perm_svc.remove_member(token, doc_type, member_type, member_id, **kw)
                )
            else:
                return _json_result({"error": f"未知的 action: {action}"})
        except Exception as e:
            return _json_result({"error": str(e)})

    return StructuredTool.from_function(
        coroutine=_feishu_perm,
        name="feishu_perm",
        description=(
            "飞书文档权限管理。Actions: list, add, remove。"
            "perm: view/edit/full_access。"
            "member_type: email/openid/userid/openchat/opendepartmentid。"
        ),
    )


def _create_calendar_tools(get_token) -> list[StructuredTool]:
    from app.services import feishu_calendar_service as cal_svc

    async def _cal_list(days: int = 7, calendar_id: str = "") -> str:
        user_token = await get_token()
        try:
            return _json_result(
                await cal_svc.list_events(days, calendar_id, user_token=user_token)
            )
        except Exception as e:
            return _json_result({"error": str(e)})

    async def _cal_create(
        summary: str,
        start_time: str,
        end_time: str,
        calendar_id: str = "",
        attendees: str = "",
        description: str = "",
    ) -> str:
        user_token = await get_token()
        attendee_list = [a.strip() for a in attendees.split(",") if a.strip()] if attendees else []
        try:
            return _json_result(
                await cal_svc.create_event(
                    summary, start_time, end_time, calendar_id,
                    attendee_list or None, description, user_token=user_token,
                )
            )
        except Exception as e:
            return _json_result({"error": str(e)})

    return [
        StructuredTool.from_function(
            coroutine=_cal_list, name="feishu_calendar_list",
            description="查看飞书日历日程。days: 查看未来几天，默认 7 天。",
        ),
        StructuredTool.from_function(
            coroutine=_cal_create, name="feishu_calendar_create",
            description="创建飞书日历日程。start_time/end_time 为时间戳。attendees 为逗号分隔的用户 ID。",
        ),
    ]


def _create_task_tools(get_token) -> list[StructuredTool]:
    from app.services import feishu_task_service as task_svc

    async def _task_list() -> str:
        user_token = await get_token()
        try:
            return _json_result(await task_svc.list_tasks(user_token=user_token))
        except Exception as e:
            return _json_result({"error": str(e)})

    async def _task_create(
        summary: str,
        due: str = "",
        assignees: str = "",
        description: str = "",
    ) -> str:
        user_token = await get_token()
        assignee_list = [a.strip() for a in assignees.split(",") if a.strip()] if assignees else []
        try:
            return _json_result(
                await task_svc.create_task(
                    summary, due, assignee_list or None, description, user_token=user_token,
                )
            )
        except Exception as e:
            return _json_result({"error": str(e)})

    return [
        StructuredTool.from_function(
            coroutine=_task_list, name="feishu_task_list",
            description="列出飞书任务。",
        ),
        StructuredTool.from_function(
            coroutine=_task_create, name="feishu_task_create",
            description="创建飞书任务。due 为时间戳，assignees 为逗号分隔的用户 ID。",
        ),
    ]
