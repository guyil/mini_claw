"""飞书开放平台 API 服务

封装 tenant_access_token / user_access_token 管理和文档读写操作。

Token 策略:
- 优先使用 user_access_token（以用户身份调用，能访问用户可见的全部文档）
- 当用户无飞书 token 时回退到 tenant_access_token（应用身份，仅能访问应用协作者文档）

认证体系说明:
- tenant_access_token: 应用身份，只能操作应用有权限的资源
- user_access_token: 用户身份，能操作用户可见的资源
- 日历/任务等个人资源必须使用 user_access_token，否则用户看不到
"""

from __future__ import annotations

import logging
import re
import time
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)

FEISHU_BASE = "https://open.feishu.cn/open-apis"
FEISHU_AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
FEISHU_APP_TOKEN_URL = f"{FEISHU_BASE}/auth/v3/app_access_token/internal"
FEISHU_REFRESH_URL = f"{FEISHU_BASE}/authen/v1/oidc/refresh_access_token"

FEISHU_OAUTH_SCOPES = (
    "docx:document:readonly docx:document "
    "wiki:wiki:readonly wiki:wiki "
    "drive:drive:readonly drive:drive "
    "bitable:app bitable:app:readonly "
    "calendar:calendar:read calendar:calendar.event:create "
    "calendar:calendar.event:read "
    "task:task task:task:read task:task:write "
    "im:message im:message:readonly "
    "contact:user.base:readonly contact:contact.base:readonly"
)

_tenant_token_cache: dict[str, tuple[str, float]] = {}
_app_token_cache: dict[str, tuple[str, float]] = {}

_TOKEN_REFRESH_BUFFER_SECONDS = 60


async def get_tenant_token() -> str:
    """获取 tenant_access_token（自动缓存，过期前 60s 刷新）"""
    cached = _tenant_token_cache.get("tenant")
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
        _tenant_token_cache["tenant"] = (token, time.time() + expire - 60)
        return token


async def _get_app_access_token() -> str:
    """获取 app_access_token（用于 OIDC 刷新，不同于 tenant_access_token）"""
    cached = _app_token_cache.get("app")
    if cached and cached[1] > time.time():
        return cached[0]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            FEISHU_APP_TOKEN_URL,
            json={
                "app_id": settings.feishu_app_id,
                "app_secret": settings.feishu_app_secret,
            },
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取 app_access_token 失败: {data.get('msg')}")

        token = data["app_access_token"]
        expire = data.get("expire", 7200)
        _app_token_cache["app"] = (token, time.time() + expire - 60)
        return token


async def refresh_user_feishu_token(db: AsyncSession, user) -> str | None:
    """使用 refresh_token 刷新用户的 feishu access_token

    飞书 OIDC 刷新接口要求使用 app_access_token (非 tenant_access_token)
    """
    if not user.feishu_refresh_token:
        logger.warning("用户 %s 无 feishu_refresh_token，无法刷新", user.id)
        return None

    try:
        app_token = await _get_app_access_token()
    except Exception:
        logger.warning("刷新用户飞书 token 时无法获取 app_access_token")
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                FEISHU_REFRESH_URL,
                headers={"Authorization": f"Bearer {app_token}"},
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": user.feishu_refresh_token,
                },
            )
            data = resp.json()

            if data.get("code") != 0:
                logger.warning(
                    "刷新飞书用户 token 失败: code=%s msg=%s",
                    data.get("code"), data.get("msg"),
                )
                return None

            new_token = data["data"]["access_token"]
            new_refresh = data["data"].get("refresh_token", user.feishu_refresh_token)
            expires_in = data["data"].get("expires_in", 7200)

            user.feishu_access_token = new_token
            user.feishu_refresh_token = new_refresh
            user.feishu_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            await db.flush()

            logger.info("已刷新用户 %s 的飞书 token", user.id)
            return new_token
    except Exception:
        logger.exception("刷新飞书用户 token 时发生异常")
        return None


async def get_user_feishu_token(db: AsyncSession, user_id: str) -> str | None:
    """获取用户的 feishu user_access_token

    - 未过期时直接返回
    - 即将过期（<60s）或已过期时自动刷新
    - 用户不存在、无飞书 token、刷新失败时返回 None
    """
    from app.models.user import User

    try:
        uid = _uuid.UUID(user_id)
    except ValueError:
        logger.debug("user_id=%s 不是合法 UUID，跳过飞书 token 查询", user_id)
        return None

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()

    if user is None:
        logger.debug("用户 %s 不存在", user_id)
        return None

    if not user.feishu_access_token:
        logger.debug("用户 %s 未绑定飞书账号", user_id)
        return None

    now = datetime.now(timezone.utc)
    expires_at = user.feishu_token_expires_at

    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if (expires_at - now).total_seconds() > _TOKEN_REFRESH_BUFFER_SECONDS:
            return user.feishu_access_token

    refreshed = await refresh_user_feishu_token(db, user)
    if refreshed:
        return refreshed

    logger.warning(
        "用户 %s 飞书 token 刷新失败，尝试使用现有 token（可能仍然有效）",
        user_id,
    )
    return user.feishu_access_token


async def diagnose_feishu_auth(db: AsyncSession, user_id: str) -> dict[str, Any]:
    """诊断飞书认证状态，返回详细的 token 和权限信息"""
    from app.models.user import User

    result: dict[str, Any] = {
        "app_configured": bool(settings.feishu_app_id and settings.feishu_app_secret),
        "tenant_token": {"status": "unknown"},
        "user_token": {"status": "unknown"},
        "recommendations": [],
    }

    if not result["app_configured"]:
        result["recommendations"].append("未配置飞书 App ID / App Secret")
        return result

    try:
        tenant_token = await get_tenant_token()
        result["tenant_token"] = {
            "status": "valid",
            "token_preview": tenant_token[:10] + "..." if tenant_token else None,
        }
    except Exception as e:
        result["tenant_token"] = {"status": "error", "message": str(e)}
        result["recommendations"].append("tenant_access_token 获取失败，检查 App ID/Secret")

    try:
        uid = _uuid.UUID(user_id)
    except ValueError:
        result["user_token"] = {"status": "invalid_user_id", "user_id": user_id}
        result["recommendations"].append("当前 user_id 不是有效 UUID，无法查询飞书绑定状态")
        return result

    user_result = await db.execute(select(User).where(User.id == uid))
    user = user_result.scalar_one_or_none()

    if user is None:
        result["user_token"] = {"status": "user_not_found"}
        result["recommendations"].append("用户不存在")
        return result

    if not user.feishu_open_id:
        result["user_token"] = {"status": "not_linked"}
        result["recommendations"].append(
            "用户未通过飞书 OAuth 登录。日历/任务等操作将使用应用身份，"
            "创建的资源用户无法在飞书中看到。请先通过 /auth/feishu/login 登录。"
        )
        return result

    result["user_token"]["feishu_open_id"] = user.feishu_open_id
    has_token = bool(user.feishu_access_token)
    result["user_token"]["has_access_token"] = has_token

    if not has_token:
        result["user_token"]["status"] = "no_token"
        result["recommendations"].append("用户已绑定飞书但无 access_token，请重新登录")
        return result

    now = datetime.now(timezone.utc)
    expires_at = user.feishu_token_expires_at
    if expires_at:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        remaining = (expires_at - now).total_seconds()
        result["user_token"]["expires_at"] = expires_at.isoformat()
        result["user_token"]["remaining_seconds"] = int(remaining)

        if remaining <= 0:
            result["user_token"]["status"] = "expired"
            token = await refresh_user_feishu_token(db, user)
            if token:
                result["user_token"]["status"] = "refreshed"
                result["user_token"]["message"] = "token 已过期但成功刷新"
            else:
                result["recommendations"].append(
                    "user_access_token 已过期且刷新失败。请重新通过飞书 OAuth 登录。"
                )
        elif remaining < _TOKEN_REFRESH_BUFFER_SECONDS:
            result["user_token"]["status"] = "expiring_soon"
            token = await refresh_user_feishu_token(db, user)
            if token:
                result["user_token"]["status"] = "refreshed"
        else:
            result["user_token"]["status"] = "valid"
    else:
        result["user_token"]["status"] = "valid_no_expiry"

    if result["user_token"]["status"] in ("valid", "refreshed", "valid_no_expiry"):
        user_token = user.feishu_access_token
        scopes = await _check_token_scopes(user_token)
        result["user_token"]["scopes_check"] = scopes

        if scopes.get("status") == "error":
            result["recommendations"].append(
                "user_access_token 验证失败，可能已失效。请重新通过飞书 OAuth 登录。"
            )
        else:
            result["user_token"]["all_scopes_requested"] = True
            result["user_token"]["message"] = (
                "token 有效，登录时已请求全部所需权限（文档/日历/任务/云空间/多维表格等）"
            )

    return result


async def _check_token_scopes(user_token: str) -> dict[str, Any]:
    """通过调用飞书 API 检查 user_access_token 的有效性

    飞书 OIDC 没有提供 scope introspection API，无法直接列出 token 已授权的 scope。
    因此只验证 token 有效性。scope 在登录时已通过 FEISHU_OAUTH_SCOPES 全部请求。
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{FEISHU_BASE}/authen/v1/user_info",
                headers={"Authorization": f"Bearer {user_token}"},
            )
            data = resp.json()
            if data.get("code") != 0:
                return {"status": "error", "code": data.get("code"), "message": data.get("msg")}
            return {
                "status": "valid",
                "scopes_note": "飞书不提供 scope 查询接口，登录时已请求全部所需 scope",
                "requested_scopes": FEISHU_OAUTH_SCOPES,
                "user_info": {
                    "name": data.get("data", {}).get("name"),
                    "open_id": data.get("data", {}).get("open_id"),
                },
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def build_feishu_authorize_url(source: str = "chat") -> str:
    """生成飞书 OAuth 授权 URL

    source: 标记授权来源，用于回调时的路由决策
    """
    params = {
        "client_id": settings.feishu_app_id,
        "redirect_uri": settings.feishu_redirect_uri,
        "response_type": "code",
        "state": f"{source}_{_uuid.uuid4().hex[:16]}",
        "scope": FEISHU_OAUTH_SCOPES,
    }
    return f"{FEISHU_AUTHORIZE_URL}?{urlencode(params)}"


def extract_document_id(url_or_token: str) -> str:
    """从飞书文档 URL 或 token 中提取 document_id

    支持格式:
      - https://xxx.feishu.cn/docx/ABC123...
      - https://xxx.feishu.cn/wiki/ABC123...
      - https://xxx.feishu.cn/base/ABC123...
      - https://xxx.feishu.cn/sheets/ABC123...
      - https://xxx.larksuite.com/docx/ABC123...
      - ABC123...（直接 token）
    """
    m = re.search(r"(?:docx|docs|wiki|base|sheets|bitable)/([A-Za-z0-9]+)", url_or_token)
    if m:
        return m.group(1)
    return url_or_token.strip().split("/")[-1].split("?")[0]
