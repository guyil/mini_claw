"""Tests for skill_installer service — SKILL.md parsing and zip extraction."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.services.skill_installer import (
    parse_skill_md,
    extract_skill_from_zip_bytes,
    resolve_download_url,
)


# ---------------------------------------------------------------------------
# parse_skill_md
# ---------------------------------------------------------------------------

SIMPLE_SKILL_MD = """\
---
name: test_skill
description: A test skill
version: 1.0.0
---
## Instructions

1. Do step one
2. Do step two
3. Call skill_complete when done
"""

SKILL_MD_NO_VERSION = """\
---
name: pdf_parser
description: Parse PDF forms
---
# PDF Parser

Read the PDF and extract fields.
"""

SKILL_MD_EXTRA_FIELDS = """\
---
name: advanced_skill
description: An advanced skill with metadata
version: 2.0.0
category: analysis
required_tools:
  - web_fetch
  - exec_command
---
## Workflow

Step 1: fetch data
Step 2: analyse
"""

SKILL_MD_NO_FRONTMATTER = """\
# Just instructions

No frontmatter here.
"""


class TestParseSkillMd:
    def test_basic_parse(self):
        result = parse_skill_md(SIMPLE_SKILL_MD)
        assert result["name"] == "test_skill"
        assert result["description"] == "A test skill"
        assert result["version"] == "1.0.0"
        assert "Do step one" in result["instructions"]
        assert "Do step two" in result["instructions"]

    def test_default_version(self):
        result = parse_skill_md(SKILL_MD_NO_VERSION)
        assert result["name"] == "pdf_parser"
        assert result["version"] == "1.0.0"
        assert "Parse PDF forms" in result["description"]

    def test_extra_fields(self):
        result = parse_skill_md(SKILL_MD_EXTRA_FIELDS)
        assert result["name"] == "advanced_skill"
        assert result["category"] == "analysis"
        assert result["required_tools"] == ["web_fetch", "exec_command"]

    def test_no_frontmatter_raises(self):
        with pytest.raises(ValueError, match="frontmatter"):
            parse_skill_md(SKILL_MD_NO_FRONTMATTER)

    def test_missing_name_raises(self):
        md = "---\ndescription: no name\n---\nbody"
        with pytest.raises(ValueError, match="name"):
            parse_skill_md(md)

    def test_missing_description_raises(self):
        md = "---\nname: x\n---\nbody"
        with pytest.raises(ValueError, match="description"):
            parse_skill_md(md)


# ---------------------------------------------------------------------------
# extract_skill_from_zip_bytes
# ---------------------------------------------------------------------------

def _make_zip(files: dict[str, str]) -> bytes:
    """Create an in-memory zip with the given filename->content mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


class TestExtractSkillFromZipBytes:
    def test_flat_zip(self):
        data = _make_zip({
            "SKILL.md": SIMPLE_SKILL_MD,
            "scripts/run.py": "print('hello')",
            "reference.md": "# Reference\nSome docs",
        })
        result = extract_skill_from_zip_bytes(data)
        assert result["skill"]["name"] == "test_skill"
        assert len(result["assets"]) == 2
        filenames = {a["filename"] for a in result["assets"]}
        assert "scripts/run.py" in filenames
        assert "reference.md" in filenames

    def test_nested_directory_zip(self):
        """Zip with a root directory wrapper (common from GitHub releases)."""
        data = _make_zip({
            "pdf_parser_skill/SKILL.md": SIMPLE_SKILL_MD,
            "pdf_parser_skill/scripts/fill.py": "fill()",
            "pdf_parser_skill/scripts/check.py": "check()",
        })
        result = extract_skill_from_zip_bytes(data)
        assert result["skill"]["name"] == "test_skill"
        assert len(result["assets"]) == 2
        filenames = {a["filename"] for a in result["assets"]}
        assert "scripts/fill.py" in filenames
        assert "scripts/check.py" in filenames

    def test_no_skill_md_raises(self):
        data = _make_zip({"readme.md": "# No skill here"})
        with pytest.raises(ValueError, match="SKILL.md"):
            extract_skill_from_zip_bytes(data)

    def test_binary_files_flagged(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("SKILL.md", SIMPLE_SKILL_MD)
            zf.writestr("data.bin", b"\x00\x01\x02\xff" * 100)
        data = buf.getvalue()
        result = extract_skill_from_zip_bytes(data)
        bin_assets = [a for a in result["assets"] if a["is_binary"]]
        assert len(bin_assets) == 1
        assert bin_assets[0]["filename"] == "data.bin"


# ---------------------------------------------------------------------------
# resolve_download_url
# ---------------------------------------------------------------------------

class TestResolveDownloadUrl:
    def test_direct_zip_url(self):
        url = "https://example.com/skill.zip"
        assert resolve_download_url(url) == url

    def test_skills_hub_page_url(self):
        url = "https://skills-hub.cc/skill/5d500dbf-a538-4706-8b27-74c661ae99e6_pdf_parser_skill"
        resolved = resolve_download_url(url)
        assert "download" in resolved
        assert "5d500dbf-a538-4706-8b27-74c661ae99e6" in resolved

    def test_generic_url_passthrough(self):
        url = "https://example.com/some/path"
        assert resolve_download_url(url) == url
