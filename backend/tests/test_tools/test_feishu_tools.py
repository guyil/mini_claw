"""飞书 tools stub 测试"""

import pytest

from app.tools.feishu_tools import create_feishu_tools


@pytest.fixture
def feishu_tools():
    return create_feishu_tools("test-user")


def test_creates_feishu_tools(feishu_tools):
    names = [t.name for t in feishu_tools]
    assert "feishu_calendar_list" in names
    assert "feishu_calendar_create" in names
    assert "feishu_doc_read" in names
    assert "feishu_doc_create" in names
    assert "feishu_send_message" in names
    assert "feishu_task_create" in names


@pytest.mark.asyncio
async def test_calendar_list_stub(feishu_tools):
    tool = next(t for t in feishu_tools if t.name == "feishu_calendar_list")
    result = await tool.ainvoke({"days": 7})
    assert "Stub" in result
    assert "日程" in result


@pytest.mark.asyncio
async def test_doc_create_stub(feishu_tools):
    tool = next(t for t in feishu_tools if t.name == "feishu_doc_create")
    result = await tool.ainvoke({"title": "测试文档", "content_markdown": "# Hello"})
    assert "Stub" in result
    assert "测试文档" in result
