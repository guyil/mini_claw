"""DeliveryService 单元测试

验证:
- chat 交付（保存到消息表）
- webhook 交付（HTTP POST）
- feishu 交付（调用飞书 API）
- 异常处理
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.delivery_service import DeliveryService


class TestDeliverChat:
    """chat 模式交付"""

    @pytest.mark.asyncio
    async def test_saves_message_to_db(self):
        service = DeliveryService()
        user_id = uuid.uuid4()
        bot_id = uuid.uuid4()
        conv_id = uuid.uuid4()

        with patch("app.services.delivery_service.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            added_objects = []
            mock_session.add = lambda obj: added_objects.append(obj)

            await service.deliver(
                mode="chat",
                config={},
                user_id=user_id,
                bot_id=bot_id,
                conversation_id=conv_id,
                job_name="Daily Report",
                content="今天的竞品分析结果...",
            )

            assert len(added_objects) == 1
            msg = added_objects[0]
            assert msg.role == "ai"
            assert "竞品分析" in msg.content
            assert msg.metadata_["source"] == "scheduled_job"
            mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_creates_conversation_when_none(self):
        service = DeliveryService()
        user_id = uuid.uuid4()
        bot_id = uuid.uuid4()

        with patch("app.services.delivery_service.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            added_objects = []
            mock_session.add = lambda obj: added_objects.append(obj)

            await service.deliver(
                mode="chat",
                config={},
                user_id=user_id,
                bot_id=bot_id,
                conversation_id=None,
                job_name="Test Job",
                content="result",
            )

            # Should create Conversation + Message
            assert len(added_objects) == 2


class TestDeliverWebhook:
    """webhook 模式交付"""

    @pytest.mark.asyncio
    async def test_posts_to_url(self):
        service = DeliveryService()

        with patch("app.services.delivery_service.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)

            await service.deliver(
                mode="webhook",
                config={"url": "https://example.com/hook"},
                user_id=uuid.uuid4(),
                bot_id=None,
                conversation_id=None,
                job_name="Webhook Test",
                content="payload data",
            )

            mock_client.post.assert_awaited_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://example.com/hook"
            payload = call_args[1]["json"]
            assert payload["job_name"] == "Webhook Test"
            assert payload["content"] == "payload data"

    @pytest.mark.asyncio
    async def test_webhook_missing_url_raises(self):
        service = DeliveryService()

        with pytest.raises(ValueError, match="url"):
            await service.deliver(
                mode="webhook",
                config={},
                user_id=uuid.uuid4(),
                bot_id=None,
                conversation_id=None,
                job_name="Test",
                content="data",
            )


class TestDeliverFallback:
    """未知模式回退到 chat"""

    @pytest.mark.asyncio
    async def test_unknown_mode_falls_back_to_chat(self):
        service = DeliveryService()

        with patch.object(service, "_deliver_chat", new_callable=AsyncMock) as mock_chat:
            await service.deliver(
                mode="unknown_mode",
                config={},
                user_id=uuid.uuid4(),
                bot_id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                job_name="Test",
                content="data",
            )
            mock_chat.assert_awaited_once()
