"""飞书文档服务测试"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.feishu_doc_service import (
    BLOCK_TYPE_NAMES,
    _get_content_key,
    _make_code_block,
    _make_heading_block,
    _make_list_block,
    _make_text_block,
    _make_todo_block,
    _markdown_to_blocks,
    _parse_inline_elements,
)


class TestBlockTypeNames:
    def test_covers_common_types(self):
        assert BLOCK_TYPE_NAMES[1] == "Page"
        assert BLOCK_TYPE_NAMES[2] == "Text"
        assert BLOCK_TYPE_NAMES[31] == "Table"
        assert BLOCK_TYPE_NAMES[27] == "Image"

    def test_heading_types(self):
        for i in range(3, 12):
            assert f"Heading{i - 2}" == BLOCK_TYPE_NAMES.get(i, f"Heading{i - 2}")


class TestGetContentKey:
    def test_text_type(self):
        assert _get_content_key(2) == "text"

    def test_heading_types(self):
        assert _get_content_key(3) == "heading1"
        assert _get_content_key(5) == "heading3"

    def test_table(self):
        assert _get_content_key(31) == "table"

    def test_unknown_type(self):
        assert _get_content_key(999) is None


class TestMakeTextBlock:
    def test_basic_text(self):
        block = _make_text_block("Hello")
        assert block["block_type"] == 2
        assert block["text"]["elements"][0]["text_run"]["content"] == "Hello"

    def test_quote_block(self):
        block = _make_text_block("quoted", 15)
        assert block["block_type"] == 15
        assert "quote" in block


class TestMakeHeadingBlock:
    def test_h1(self):
        block = _make_heading_block("Title", 3)
        assert block["block_type"] == 3
        assert "heading1" in block

    def test_h3(self):
        block = _make_heading_block("Sub", 5)
        assert block["block_type"] == 5
        assert "heading3" in block


class TestMakeListBlock:
    def test_bullet(self):
        block = _make_list_block("item", 12)
        assert block["block_type"] == 12
        assert "bullet" in block

    def test_ordered(self):
        block = _make_list_block("item", 13)
        assert block["block_type"] == 13
        assert "ordered" in block


class TestMakeCodeBlock:
    def test_python(self):
        block = _make_code_block("print('hi')", "python")
        assert block["block_type"] == 14
        assert block["code"]["style"]["language"] == 49

    def test_javascript(self):
        block = _make_code_block("console.log(1)", "javascript")
        assert block["code"]["style"]["language"] == 24

    def test_no_language(self):
        block = _make_code_block("code")
        assert block["block_type"] == 14


class TestMakeTodoBlock:
    def test_unchecked(self):
        block = _make_todo_block("task", False)
        assert block["block_type"] == 17
        assert block["todo"]["style"]["done"] is False

    def test_checked(self):
        block = _make_todo_block("done task", True)
        assert block["todo"]["style"]["done"] is True


class TestParseInlineElements:
    def test_plain_text(self):
        elems = _parse_inline_elements("hello")
        assert len(elems) == 1
        assert elems[0]["text_run"]["content"] == "hello"

    def test_bold(self):
        elems = _parse_inline_elements("**bold**")
        assert elems[0]["text_run"]["text_element_style"]["bold"] is True

    def test_italic(self):
        elems = _parse_inline_elements("*italic*")
        assert elems[0]["text_run"]["text_element_style"]["italic"] is True

    def test_strikethrough(self):
        elems = _parse_inline_elements("~~deleted~~")
        assert elems[0]["text_run"]["text_element_style"]["strikethrough"] is True

    def test_link(self):
        elems = _parse_inline_elements("[text](https://url.com)")
        style = elems[0]["text_run"]["text_element_style"]
        assert style["link"]["url"] == "https://url.com"

    def test_mixed_formatting(self):
        elems = _parse_inline_elements("hello **bold** and *italic*")
        assert len(elems) >= 3


class TestMarkdownToBlocks:
    def test_complex_document(self):
        md = """# Title

Some text with **bold** and *italic*.

## Section

- bullet 1
- bullet 2

1. ordered
2. list

```python
x = 1
```

> A quote

---

- [ ] todo
- [x] done
"""
        blocks = _markdown_to_blocks(md)
        types = [b["block_type"] for b in blocks]
        assert 3 in types   # h1
        assert 4 in types   # h2
        assert 2 in types   # text
        assert 12 in types  # bullet
        assert 13 in types  # ordered
        assert 14 in types  # code
        assert 15 in types  # quote
        assert 22 in types  # divider
        assert 17 in types  # todo
