"""飞书 Tools

feishu_doc_read 和 feishu_doc_create 使用真实飞书 API，
其余工具仍为 Stub 实现（后续按需接入）。
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool


def create_feishu_tools(user_id: str) -> list[StructuredTool]:
    """创建飞书操作工具集"""

    async def _feishu_calendar_list(days: int = 7) -> str:
        return (
            "[Stub] 未来 7 天日程:\n"
            "- 2026-04-07 10:00 周一团队站会\n"
            "- 2026-04-08 14:00 选品评审会\n"
            "- 2026-04-10 09:00 供应商电话会议"
        )

    async def _feishu_calendar_create(
        title: str,
        start: str,
        end: str,
        attendees: str = "",
        description: str = "",
    ) -> str:
        return f"[Stub] 日程已创建: {title} ({start} - {end})"

    async def _feishu_doc_read(doc_url_or_token: str) -> str:
        from app.services.feishu_service import read_document
        return await read_document(doc_url_or_token)

    async def _feishu_doc_create(
        title: str, content_markdown: str, folder_token: str = ""
    ) -> str:
        from app.services.feishu_service import create_document
        return await create_document(title, content_markdown, folder_token)

    async def _feishu_sheet_read(
        spreadsheet_token: str, sheet_name: str = "", range: str = "A1:D10"
    ) -> str:
        return f"[Stub] 表格数据（{spreadsheet_token} {range}）:\n| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |"

    async def _feishu_sheet_write(
        spreadsheet_token: str, sheet_id: str = "", range: str = "", data: str = "[]"
    ) -> str:
        return f"[Stub] 已写入数据到表格 {spreadsheet_token}"

    async def _feishu_send_message(
        chat_id: str, text: str, msg_type: str = "text"
    ) -> str:
        return f"[Stub] 消息已发送到 {chat_id}"

    async def _feishu_task_create(
        title: str, due_date: str = "", assignee_email: str = "", description: str = ""
    ) -> str:
        return f"[Stub] 任务已创建: {title}"

    return [
        StructuredTool.from_function(
            coroutine=_feishu_calendar_list,
            name="feishu_calendar_list",
            description="查看未来 N 天的飞书日历日程。默认 7 天。",
        ),
        StructuredTool.from_function(
            coroutine=_feishu_calendar_create,
            name="feishu_calendar_create",
            description="创建飞书日历日程。",
        ),
        StructuredTool.from_function(
            coroutine=_feishu_doc_read,
            name="feishu_doc_read",
            description="读取飞书文档内容，返回纯文本。传入文档 URL 或 document_token。",
        ),
        StructuredTool.from_function(
            coroutine=_feishu_doc_create,
            name="feishu_doc_create",
            description="创建飞书文档并写入文本内容。返回文档链接。",
        ),
        StructuredTool.from_function(
            coroutine=_feishu_sheet_read,
            name="feishu_sheet_read",
            description="读取飞书电子表格指定范围的数据。",
        ),
        StructuredTool.from_function(
            coroutine=_feishu_sheet_write,
            name="feishu_sheet_write",
            description="向飞书电子表格写入数据。",
        ),
        StructuredTool.from_function(
            coroutine=_feishu_send_message,
            name="feishu_send_message",
            description="向飞书群聊或个人发送消息。",
        ),
        StructuredTool.from_function(
            coroutine=_feishu_task_create,
            name="feishu_task_create",
            description="创建飞书任务并设置截止日期和负责人。",
        ),
    ]
