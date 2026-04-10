"""Skill 安装服务 — 下载、解压、解析 SKILL.md 技能包

支持的来源：
- 直接 zip URL
- skills-hub.cc 技能页面 URL（自动推断下载地址）

SKILL.md 格式（AgentSkills 兼容）：
    ---
    name: skill_name
    description: 技能描述
    version: 1.0.0
    ---
    ## Instructions
    ...
"""

from __future__ import annotations

import io
import logging
import re
import uuid
import zipfile
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

_SKILLS_HUB_PATTERN = re.compile(
    r"skills-hub\.cc/skill/([0-9a-f-]+)_(.+)"
)

_SKIP_PREFIXES = ("__MACOSX/", ".DS_Store")
_SKIP_SUFFIXES = (".DS_Store",)

MAX_ASSET_SIZE = 512 * 1024  # 512 KB per asset


def parse_skill_md(content: str) -> dict[str, Any]:
    """解析 SKILL.md 文件，返回结构化数据。

    Returns:
        {
            "name": str,
            "description": str,
            "version": str,
            "instructions": str,
            "category": str | None,
            "required_tools": list[str],
            ...other frontmatter fields
        }

    Raises:
        ValueError: SKILL.md 格式不合法
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError("SKILL.md 缺少 YAML frontmatter (--- ... ---)")

    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"SKILL.md frontmatter YAML 解析失败: {e}") from e

    if not isinstance(frontmatter, dict):
        raise ValueError("SKILL.md frontmatter 格式不正确，应为键值对")

    name = frontmatter.get("name")
    if not name:
        raise ValueError("SKILL.md 缺少必填字段: name")

    description = frontmatter.get("description")
    if not description:
        raise ValueError("SKILL.md 缺少必填字段: description")

    body = content[match.end():].strip()

    return {
        "name": str(name).strip(),
        "display_name": frontmatter.get("display_name"),
        "description": str(description).strip(),
        "version": str(frontmatter.get("version", "1.0.0")).strip(),
        "category": frontmatter.get("category"),
        "required_tools": frontmatter.get("required_tools", []),
        "required_env_vars": frontmatter.get("required_env_vars", []),
        "instructions": body,
    }


def _should_skip(name: str) -> bool:
    """跳过 macOS 元数据和隐藏文件"""
    for prefix in _SKIP_PREFIXES:
        if name.startswith(prefix):
            return True
    for suffix in _SKIP_SUFFIXES:
        if name.endswith(suffix):
            return True
    return False


def _is_binary_content(data: bytes) -> bool:
    """简单启发式：如果前 8KB 含有 null 字节则视为二进制"""
    return b"\x00" in data[:8192]


def extract_skill_from_zip_bytes(data: bytes) -> dict[str, Any]:
    """从 zip 字节流中提取 SKILL.md 和附属资产。

    支持两种 zip 结构：
    1. 扁平结构：SKILL.md 在根目录
    2. 嵌套结构：SKILL.md 在单个子目录下（如 GitHub release）

    Returns:
        {
            "skill": {name, description, version, instructions, ...},
            "assets": [{filename, content, is_binary}, ...]
        }

    Raises:
        ValueError: zip 中找不到 SKILL.md
    """
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [n for n in zf.namelist() if not _should_skip(n)]

        skill_md_path = None
        root_prefix = ""

        for n in names:
            basename = n.rsplit("/", 1)[-1] if "/" in n else n
            if basename == "SKILL.md":
                skill_md_path = n
                parts = n.rsplit("/", 1)
                root_prefix = parts[0] + "/" if len(parts) > 1 else ""
                break

        if not skill_md_path:
            raise ValueError("zip 包中未找到 SKILL.md 文件")

        skill_md_content = zf.read(skill_md_path).decode("utf-8")
        skill_data = parse_skill_md(skill_md_content)

        assets: list[dict[str, Any]] = []
        for n in names:
            if n == skill_md_path:
                continue
            if n.endswith("/"):
                continue

            raw = zf.read(n)
            if len(raw) > MAX_ASSET_SIZE:
                logger.warning("跳过过大的文件: %s (%d bytes)", n, len(raw))
                continue

            relative = n[len(root_prefix):] if root_prefix and n.startswith(root_prefix) else n
            is_binary = _is_binary_content(raw)

            assets.append({
                "filename": relative,
                "content": raw.hex() if is_binary else raw.decode("utf-8", errors="replace"),
                "is_binary": is_binary,
            })

    return {"skill": skill_data, "assets": assets}


def resolve_download_url(url: str) -> str:
    """将技能页面 URL 转换为 zip 下载地址。

    - skills-hub.cc 页面 URL → 推断 API 下载地址
    - 直接 zip URL → 原样返回
    - 其他 URL → 原样返回（交给 httpx 处理）
    """
    match = _SKILLS_HUB_PATTERN.search(url)
    if match:
        skill_id = match.group(1)
        slug = match.group(2)
        return f"https://skills-hub.cc/api/download/{skill_id}_{slug}"

    return url


async def download_skill_zip(url: str) -> bytes:
    """下载 zip 文件并返回字节内容。

    Raises:
        ValueError: 下载失败
    """
    import httpx

    download_url = resolve_download_url(url)
    logger.info("下载技能包: %s", download_url)

    try:
        async with httpx.AsyncClient(
            timeout=60,
            follow_redirects=True,
        ) as client:
            resp = await client.get(download_url)
            resp.raise_for_status()
            return resp.content
    except httpx.HTTPStatusError as e:
        raise ValueError(f"下载失败 HTTP {e.response.status_code}: {download_url}") from e
    except Exception as e:
        raise ValueError(f"下载失败: {e}") from e


async def install_skill_from_url(
    db: "AsyncSession",  # noqa: F821
    url: str,
    bot_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """完整的技能安装流程：下载 → 解析 → 入库 → 启用。

    Returns:
        {"skill_id": str, "name": str, "status": "installed" | "updated"}
    """
    from sqlalchemy import select

    from app.models.bot import Bot
    from app.models.skill import Skill, SkillAsset

    zip_bytes = await download_skill_zip(url)
    parsed = extract_skill_from_zip_bytes(zip_bytes)
    skill_data = parsed["skill"]
    asset_list = parsed["assets"]

    result = await db.execute(
        select(Skill).where(Skill.name == skill_data["name"])
    )
    existing = result.scalar_one_or_none()

    if existing:
        for key in ("description", "instructions", "version", "category", "required_tools"):
            if key in skill_data and skill_data[key] is not None:
                setattr(existing, key, skill_data[key])
        existing.source = "skills-hub"
        existing.source_url = url

        for asset in existing.assets:
            await db.delete(asset)
        await db.flush()

        for asset_data in asset_list:
            db.add(SkillAsset(
                skill_id=existing.id,
                filename=asset_data["filename"],
                content=asset_data["content"],
                is_binary=asset_data["is_binary"],
            ))

        skill_id = str(existing.id)
        status = "updated"
    else:
        skill = Skill(
            name=skill_data["name"],
            display_name=skill_data.get("display_name") or skill_data["name"],
            description=skill_data["description"],
            category=skill_data.get("category"),
            version=skill_data.get("version", "1.0.0"),
            instructions=skill_data["instructions"],
            required_tools=skill_data.get("required_tools", []),
            required_env_vars=skill_data.get("required_env_vars", []),
            source="skills-hub",
            source_url=url,
            scope="global",
            created_by=uuid.UUID(user_id) if user_id else None,
        )
        db.add(skill)
        await db.flush()

        for asset_data in asset_list:
            db.add(SkillAsset(
                skill_id=skill.id,
                filename=asset_data["filename"],
                content=asset_data["content"],
                is_binary=asset_data["is_binary"],
            ))

        skill_id = str(skill.id)
        status = "installed"

    if bot_id:
        try:
            bot_result = await db.execute(
                select(Bot).where(Bot.id == uuid.UUID(bot_id))
            )
            bot = bot_result.scalar_one_or_none()
            if bot:
                current = bot.enabled_skills or []
                skill_uuid = uuid.UUID(skill_id)
                if skill_uuid not in current:
                    bot.enabled_skills = [*current, skill_uuid]
        except Exception as e:
            logger.warning("自动启用 skill 失败: %s", e)

    await db.flush()

    return {
        "skill_id": skill_id,
        "name": skill_data["name"],
        "description": skill_data["description"],
        "status": status,
        "asset_count": len(asset_list),
    }
