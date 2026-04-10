"""定时任务交付服务 — 将 Agent 运行结果交付给用户

支持三种交付模式:
- chat: 保存到对话消息表（用户打开对话即可看到）
- feishu: 通过飞书机器人发送消息
- webhook: HTTP POST 到指定 URL
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from app.database import async_session_factory

logger = logging.getLogger(__name__)


class DeliveryService:
    async def deliver(
        self,
        mode: str,
        config: dict[str, Any] | None,
        user_id: uuid.UUID,
        bot_id: uuid.UUID | None,
        conversation_id: uuid.UUID | None,
        job_name: str,
        content: str,
    ):
        """根据 mode 路由到对应的交付方法"""
        config = config or {}
        try:
            if mode == "chat":
                await self._deliver_chat(
                    user_id, bot_id, conversation_id, job_name, content
                )
            elif mode == "feishu":
                await self._deliver_feishu(config, job_name, content)
            elif mode == "webhook":
                await self._deliver_webhook(config, job_name, content)
            else:
                logger.warning("未知的交付模式: %s，回退到 chat", mode)
                await self._deliver_chat(
                    user_id, bot_id, conversation_id, job_name, content
                )
        except Exception:
            logger.exception("交付失败 (mode=%s, job=%s)", mode, job_name)
            raise

    async def _deliver_chat(
        self,
        user_id: uuid.UUID,
        bot_id: uuid.UUID | None,
        conversation_id: uuid.UUID | None,
        job_name: str,
        content: str,
    ):
        """保存 AI 响应到对话消息表"""
        from app.models.conversation import Conversation
        from app.models.message import Message

        async with async_session_factory() as db:
            if not conversation_id:
                conv = Conversation(
                    user_id=user_id,
                    bot_id=bot_id or uuid.uuid4(),
                    title=f"[定时] {job_name}",
                )
                db.add(conv)
                await db.flush()
                conversation_id = conv.id

            msg = Message(
                conversation_id=conversation_id,
                role="ai",
                content=content,
                metadata_={"source": "scheduled_job", "job_name": job_name},
            )
            db.add(msg)
            await db.commit()

            logger.info(
                "定时任务结果已保存到对话 %s (job=%s)", conversation_id, job_name
            )

    async def _deliver_feishu(
        self,
        config: dict[str, Any],
        job_name: str,
        content: str,
    ):
        """通过飞书机器人发送消息"""
        from app.services.feishu_service import get_tenant_token, FEISHU_BASE

        receive_id = config.get("chat_id") or config.get("user_id")
        receive_type = "chat_id" if config.get("chat_id") else "open_id"

        if not receive_id:
            raise ValueError("飞书交付缺少 chat_id 或 user_id")

        token = await get_tenant_token()

        msg_content = {
            "text": f"📋 定时任务「{job_name}」执行结果:\n\n{content}"
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{FEISHU_BASE}/im/v1/messages",
                params={"receive_id_type": receive_type},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": receive_id,
                    "msg_type": "text",
                    "content": __import__("json").dumps(msg_content, ensure_ascii=False),
                },
            )
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"飞书发送消息失败: {data.get('msg')}")

            logger.info("定时任务结果已发送到飞书 (job=%s)", job_name)

    async def _deliver_webhook(
        self,
        config: dict[str, Any],
        job_name: str,
        content: str,
    ):
        """HTTP POST 到指定 URL"""
        url = config.get("url")
        if not url:
            raise ValueError("webhook 交付缺少 url 配置")

        payload = {
            "job_name": job_name,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        }

        headers = config.get("headers", {})

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info("定时任务结果已 POST 到 %s (job=%s)", url, job_name)
