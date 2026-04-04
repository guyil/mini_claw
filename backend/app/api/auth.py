"""认证模块

提供：
- 用户名/密码注册登录 (register / login / me)
- 飞书 OAuth 登录 (feishu/login → feishu/callback)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, get_db_optional
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

FEISHU_AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"
FEISHU_APP_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal"
FEISHU_USER_TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token"
FEISHU_USER_INFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"


# ── Pydantic 模型 ────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


# ── JWT 工具 ─────────────────────────────────────────

def _create_token(user_id: str, username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "username": username, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    """从 Bearer token 中解析 user_id（用作路由依赖）"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证信息")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效 token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token 已过期或无效")


# ── 用户名/密码认证 ──────────────────────────────────

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where((User.username == req.username) | (User.email == req.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=pwd_context.hash(req.password),
        display_name=req.display_name,
    )
    db.add(user)
    await db.flush()

    token = _create_token(str(user.id), user.username)
    return TokenResponse(access_token=token, user_id=str(user.id), username=user.username)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if user is None or not pwd_context.verify(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = _create_token(str(user.id), user.username)
    return TokenResponse(access_token=token, user_id=str(user.id), username=user.username)


@router.get("/me")
async def me(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
    }


# ── 飞书 OAuth ───────────────────────────────────────

@router.get("/feishu/login")
async def feishu_login():
    """重定向到飞书 OAuth 授权页面"""
    if not settings.feishu_app_id:
        raise HTTPException(status_code=500, detail="飞书 App ID 未配置")

    params = {
        "client_id": settings.feishu_app_id,
        "redirect_uri": settings.feishu_redirect_uri,
        "response_type": "code",
        "state": uuid.uuid4().hex,
    }
    url = f"{FEISHU_AUTHORIZE_URL}?{urlencode(params)}"
    return RedirectResponse(url=url)


async def _get_feishu_app_access_token() -> str:
    """获取飞书应用的 app_access_token"""
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
            logger.error("获取飞书 app_access_token 失败: %s", data)
            raise HTTPException(status_code=502, detail=f"飞书 API 错误: {data.get('msg')}")
        return data["app_access_token"]


async def _exchange_feishu_code(code: str, app_token: str) -> dict:
    """用授权码换取 user_access_token 和用户信息"""
    async with httpx.AsyncClient(timeout=10) as client:
        # 1. 用 code 换 user_access_token
        token_resp = await client.post(
            FEISHU_USER_TOKEN_URL,
            headers={"Authorization": f"Bearer {app_token}"},
            json={"grant_type": "authorization_code", "code": code},
        )
        token_data = token_resp.json()
        if token_data.get("code") != 0:
            logger.error("飞书 code 换 token 失败: %s", token_data)
            raise HTTPException(status_code=502, detail=f"飞书登录失败: {token_data.get('msg')}")

        user_token = token_data["data"]["access_token"]
        refresh_token = token_data["data"].get("refresh_token", "")
        expires_in = token_data["data"].get("expires_in", 7200)

        # 2. 获取用户信息
        info_resp = await client.get(
            FEISHU_USER_INFO_URL,
            headers={"Authorization": f"Bearer {user_token}"},
        )
        info_data = info_resp.json()
        if info_data.get("code") != 0:
            logger.error("获取飞书用户信息失败: %s", info_data)
            raise HTTPException(status_code=502, detail="获取飞书用户信息失败")

        user_info = info_data["data"]
        return {
            "open_id": user_info["open_id"],
            "name": user_info.get("name", ""),
            "avatar_url": user_info.get("avatar_url", ""),
            "email": user_info.get("email", ""),
            "access_token": user_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
        }


@router.post("/feishu/callback")
async def feishu_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """飞书 OAuth 回调：前端用 code 换取 JWT（JSON 响应）"""
    body = await request.json()
    code = body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="缺少 code 参数")

    app_token = await _get_feishu_app_access_token()
    feishu_user = await _exchange_feishu_code(code, app_token)

    open_id = feishu_user["open_id"]
    result = await db.execute(select(User).where(User.feishu_open_id == open_id))
    user = result.scalar_one_or_none()

    if user is None:
        username = f"feishu_{open_id[:16]}"
        existing = await db.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            username = f"feishu_{uuid.uuid4().hex[:8]}"

        user = User(
            username=username,
            email=feishu_user.get("email") or f"{open_id}@feishu.local",
            hashed_password=pwd_context.hash(uuid.uuid4().hex),
            display_name=feishu_user.get("name"),
            feishu_open_id=open_id,
            feishu_access_token=feishu_user["access_token"],
            feishu_refresh_token=feishu_user["refresh_token"],
            feishu_token_expires_at=datetime.utcnow()
            + timedelta(seconds=feishu_user["expires_in"]),
        )
        db.add(user)
        await db.flush()
    else:
        user.feishu_access_token = feishu_user["access_token"]
        user.feishu_refresh_token = feishu_user["refresh_token"]
        user.feishu_token_expires_at = datetime.utcnow() + timedelta(
            seconds=feishu_user["expires_in"]
        )
        if feishu_user.get("name"):
            user.display_name = feishu_user["name"]
        await db.flush()

    token = _create_token(str(user.id), user.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
    }
