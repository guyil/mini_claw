"""飞书 SDK Client 工厂

缓存 Client 实例，支持 tenant_access_token 和 user_access_token 两种认证模式。
参考 OpenClaw 的 client.ts 实现。
"""

from __future__ import annotations

import logging

import lark_oapi as lark

from app.config import settings

logger = logging.getLogger(__name__)

_client_cache: dict[str, lark.Client] = {}

FEISHU_HTTP_TIMEOUT = 30
FEISHU_MEDIA_HTTP_TIMEOUT = 120

DOMAIN_MAP = {
    "feishu": lark.FEISHU_DOMAIN,
    "lark": lark.LARK_DOMAIN,
}


def _resolve_domain() -> str:
    domain_key = settings.feishu_domain.lower()
    return DOMAIN_MAP.get(domain_key, lark.FEISHU_DOMAIN)


def get_feishu_client() -> lark.Client:
    """获取飞书 SDK Client（tenant_access_token 模式，自动缓存）"""
    app_id = settings.feishu_app_id
    app_secret = settings.feishu_app_secret
    if not app_id or not app_secret:
        raise RuntimeError("飞书 App ID 或 App Secret 未配置")

    cache_key = f"{app_id}:{app_secret}"
    if cache_key in _client_cache:
        return _client_cache[cache_key]

    client = (
        lark.Client.builder()
        .app_id(app_id)
        .app_secret(app_secret)
        .domain(_resolve_domain())
        .timeout(FEISHU_HTTP_TIMEOUT)
        .enable_set_token(True)
        .log_level(lark.LogLevel.WARNING)
        .build()
    )
    _client_cache[cache_key] = client
    logger.info("创建飞书 Client: app_id=%s, domain=%s", app_id[:8], settings.feishu_domain)
    return client


def clear_client_cache() -> None:
    """清除客户端缓存（测试用）"""
    _client_cache.clear()


def get_doc_url_base() -> str:
    """获取飞书文档 URL 基础路径"""
    if settings.feishu_domain.lower() == "lark":
        return "https://open.larksuite.com"
    return "https://open.feishu.cn"
