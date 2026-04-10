"""测试 feishu_service 中基于用户身份的 token 获取与刷新逻辑"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.feishu_service import get_user_feishu_token, refresh_user_feishu_token


def _make_user(
    *,
    access_token: str | None = "valid-user-token",
    refresh_token: str | None = "valid-refresh-token",
    expires_at: datetime | None = None,
    feishu_open_id: str | None = "ou_test_open_id",
):
    """构造一个模拟 User 对象"""
    user = MagicMock()
    user.id = uuid.uuid4()
    user.feishu_access_token = access_token
    user.feishu_refresh_token = refresh_token
    user.feishu_token_expires_at = expires_at or (
        datetime.now(timezone.utc) + timedelta(hours=1)
    )
    user.feishu_open_id = feishu_open_id
    return user


def _mock_db_with_user(user):
    """构造一个能返回指定 User 的 mock db session"""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute.return_value = result
    return db


# ── get_user_feishu_token ────────────────────────────


@pytest.mark.asyncio
async def test_returns_valid_token_when_not_expired():
    """用户 token 未过期时直接返回"""
    user = _make_user(expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    db = _mock_db_with_user(user)

    token = await get_user_feishu_token(db, str(user.id))

    assert token == "valid-user-token"


@pytest.mark.asyncio
async def test_returns_none_when_user_not_found():
    """用户不存在时返回 None"""
    db = _mock_db_with_user(None)

    token = await get_user_feishu_token(db, str(uuid.uuid4()))

    assert token is None


@pytest.mark.asyncio
async def test_returns_none_when_no_feishu_token():
    """用户没有飞书 token（密码注册用户）时返回 None"""
    user = _make_user(access_token=None, refresh_token=None, feishu_open_id=None)
    db = _mock_db_with_user(user)

    token = await get_user_feishu_token(db, str(user.id))

    assert token is None


@pytest.mark.asyncio
async def test_refreshes_token_when_expired():
    """token 过期时自动刷新并更新 DB"""
    user = _make_user(
        access_token="expired-token",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db = _mock_db_with_user(user)

    with patch(
        "app.services.feishu_service.refresh_user_feishu_token",
        new_callable=AsyncMock,
        return_value="new-refreshed-token",
    ):
        token = await get_user_feishu_token(db, str(user.id))

    assert token == "new-refreshed-token"


@pytest.mark.asyncio
async def test_refreshes_token_when_about_to_expire():
    """token 即将过期（<60s）时也触发刷新"""
    user = _make_user(
        access_token="about-to-expire-token",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
    )
    db = _mock_db_with_user(user)

    with patch(
        "app.services.feishu_service.refresh_user_feishu_token",
        new_callable=AsyncMock,
        return_value="refreshed-token",
    ):
        token = await get_user_feishu_token(db, str(user.id))

    assert token == "refreshed-token"


@pytest.mark.asyncio
async def test_returns_existing_token_when_refresh_fails():
    """刷新失败时回退到现有 token（可能仍然有效）"""
    user = _make_user(
        access_token="expired-token",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db = _mock_db_with_user(user)

    with patch(
        "app.services.feishu_service.refresh_user_feishu_token",
        new_callable=AsyncMock,
        return_value=None,
    ):
        token = await get_user_feishu_token(db, str(user.id))

    assert token == "expired-token"


# ── refresh_user_feishu_token ────────────────────────


@pytest.mark.asyncio
async def test_refresh_calls_feishu_api_and_updates_db():
    """刷新时调用飞书 API 并更新 DB 中的 token"""
    user = _make_user(refresh_token="my-refresh-token")
    db = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "code": 0,
        "data": {
            "access_token": "brand-new-token",
            "refresh_token": "brand-new-refresh",
            "expires_in": 7200,
        },
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.feishu_service.httpx.AsyncClient", return_value=mock_client),
        patch(
            "app.services.feishu_service._get_app_access_token",
            new_callable=AsyncMock,
            return_value="app-token-for-refresh",
        ),
    ):
        result = await refresh_user_feishu_token(db, user)

    assert result == "brand-new-token"
    assert user.feishu_access_token == "brand-new-token"
    assert user.feishu_refresh_token == "brand-new-refresh"
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_returns_none_on_api_error():
    """飞书 API 返回错误时返回 None"""
    user = _make_user(refresh_token="bad-refresh-token")
    db = AsyncMock()

    mock_response = MagicMock()
    mock_response.json.return_value = {"code": 99999, "msg": "invalid refresh_token"}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.services.feishu_service.httpx.AsyncClient", return_value=mock_client),
        patch(
            "app.services.feishu_service._get_app_access_token",
            new_callable=AsyncMock,
            return_value="app-token",
        ),
    ):
        result = await refresh_user_feishu_token(db, user)

    assert result is None


@pytest.mark.asyncio
async def test_refresh_returns_none_when_no_refresh_token():
    """没有 refresh_token 时直接返回 None"""
    user = _make_user(refresh_token=None)
    db = AsyncMock()

    result = await refresh_user_feishu_token(db, user)

    assert result is None
