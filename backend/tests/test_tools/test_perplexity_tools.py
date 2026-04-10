"""Perplexity 搜索工具测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.perplexity_tools import create_perplexity_tools


@pytest.fixture
def perplexity_tools():
    with patch("app.tools.perplexity_tools.settings") as mock_settings:
        mock_settings.perplexity_api_key = "pplx-test-key"
        yield create_perplexity_tools()


def _make_mock_response(status_code: int, json_data: dict | None = None, error: Exception | None = None):
    """httpx.Response 的 json() 和 raise_for_status() 是同步方法，用 MagicMock"""
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    if error:
        resp.raise_for_status.side_effect = error
    return resp


def _make_mock_client(response=None, post_side_effect=None):
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    if post_side_effect:
        mock_client.post = AsyncMock(side_effect=post_side_effect)
    else:
        mock_client.post = AsyncMock(return_value=response)
    return mock_client


def test_creates_web_search_tool(perplexity_tools):
    names = [t.name for t in perplexity_tools]
    assert "web_search" in names
    assert len(perplexity_tools) == 1


def test_no_tools_without_api_key():
    with patch("app.tools.perplexity_tools.settings") as mock_settings:
        mock_settings.perplexity_api_key = ""
        tools = create_perplexity_tools()
    assert len(tools) == 0


@pytest.mark.asyncio
async def test_web_search_returns_answer_with_citations(perplexity_tools):
    tool = next(t for t in perplexity_tools if t.name == "web_search")

    resp = _make_mock_response(200, {
        "choices": [{"message": {"content": "Python 3.12 于 2023 年 10 月发布。"}}],
        "citations": [
            "https://www.python.org/downloads/release/python-3120/",
            "https://docs.python.org/3/whatsnew/3.12.html",
        ],
    })
    mock_client = _make_mock_client(response=resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await tool.ainvoke({"query": "Python 3.12 release date"})

    assert "Python 3.12" in result
    assert "python.org" in result
    mock_client.post.assert_called_once()
    call_kwargs = mock_client.post.call_args
    payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert payload["model"] == "sonar"
    assert any("Python 3.12" in m["content"] for m in payload["messages"])


@pytest.mark.asyncio
async def test_web_search_handles_api_error(perplexity_tools):
    tool = next(t for t in perplexity_tools if t.name == "web_search")

    resp = _make_mock_response(401, error=Exception("401 Unauthorized"))
    mock_client = _make_mock_client(response=resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await tool.ainvoke({"query": "test query"})

    assert "搜索失败" in result


@pytest.mark.asyncio
async def test_web_search_handles_network_error(perplexity_tools):
    tool = next(t for t in perplexity_tools if t.name == "web_search")

    mock_client = _make_mock_client(post_side_effect=Exception("Connection timeout"))

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await tool.ainvoke({"query": "test query"})

    assert "搜索失败" in result


@pytest.mark.asyncio
async def test_web_search_no_citations(perplexity_tools):
    tool = next(t for t in perplexity_tools if t.name == "web_search")

    resp = _make_mock_response(200, {
        "choices": [{"message": {"content": "这是搜索结果。"}}],
    })
    mock_client = _make_mock_client(response=resp)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await tool.ainvoke({"query": "some query"})

    assert "这是搜索结果" in result
