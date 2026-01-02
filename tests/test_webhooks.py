"""Tests for the webhooks module."""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastband.webhooks.models import (
    DeliveryStatus,
    WebhookDelivery,
    WebhookEvent,
    WebhookSubscription,
)
from fastband.webhooks.service import WebhookService, WebhookServiceConfig


class TestWebhookEvent:
    """Tests for WebhookEvent enum."""

    def test_event_values(self):
        """Test event value format."""
        assert WebhookEvent.TICKET_CREATED.value == "ticket.created"
        assert WebhookEvent.TICKET_CLAIMED.value == "ticket.claimed"
        assert WebhookEvent.AGENT_STARTED.value == "agent.started"
        assert WebhookEvent.ALL.value == "*"

    def test_from_ops_log_event(self):
        """Test mapping from ops_log EventType strings."""
        assert WebhookEvent.from_ops_log_event("ticket_claimed") == WebhookEvent.TICKET_CLAIMED
        assert WebhookEvent.from_ops_log_event("ticket_completed") == WebhookEvent.TICKET_COMPLETED
        assert WebhookEvent.from_ops_log_event("agent_started") == WebhookEvent.AGENT_STARTED
        assert WebhookEvent.from_ops_log_event("unknown") is None


class TestWebhookSubscription:
    """Tests for WebhookSubscription model."""

    def test_create_subscription(self):
        """Test creating a new subscription."""
        sub = WebhookSubscription.create(
            url="https://example.com/webhook",
            events=["ticket.created", "ticket.completed"],
            secret="my-secret-key",
            name="Test Webhook",
            description="A test webhook",
        )

        assert sub.id
        assert sub.url == "https://example.com/webhook"
        assert len(sub.events) == 2
        assert WebhookEvent.TICKET_CREATED in sub.events
        assert WebhookEvent.TICKET_COMPLETED in sub.events
        assert sub.secret == "my-secret-key"
        assert sub.name == "Test Webhook"
        assert sub.active is True
        assert sub.total_deliveries == 0

    def test_should_deliver(self):
        """Test subscription event filtering."""
        sub = WebhookSubscription.create(
            url="https://example.com/webhook",
            events=["ticket.created"],
            secret="secret",
        )

        assert sub.should_deliver(WebhookEvent.TICKET_CREATED) is True
        assert sub.should_deliver(WebhookEvent.TICKET_COMPLETED) is False

    def test_should_deliver_all(self):
        """Test subscription with wildcard events."""
        sub = WebhookSubscription.create(
            url="https://example.com/webhook",
            events=["*"],
            secret="secret",
        )

        assert sub.should_deliver(WebhookEvent.TICKET_CREATED) is True
        assert sub.should_deliver(WebhookEvent.AGENT_STARTED) is True

    def test_should_not_deliver_when_inactive(self):
        """Test inactive subscription doesn't deliver."""
        sub = WebhookSubscription.create(
            url="https://example.com/webhook",
            events=["ticket.created"],
            secret="secret",
        )
        sub.active = False

        assert sub.should_deliver(WebhookEvent.TICKET_CREATED) is False

    def test_record_delivery_success(self):
        """Test recording successful delivery."""
        sub = WebhookSubscription.create(
            url="https://example.com/webhook",
            events=["ticket.created"],
            secret="secret",
        )

        sub.record_delivery(success=True)

        assert sub.total_deliveries == 1
        assert sub.successful_deliveries == 1
        assert sub.failed_deliveries == 0
        assert sub.last_error is None
        assert sub.last_delivery_at is not None

    def test_record_delivery_failure(self):
        """Test recording failed delivery."""
        sub = WebhookSubscription.create(
            url="https://example.com/webhook",
            events=["ticket.created"],
            secret="secret",
        )

        sub.record_delivery(success=False, error="Connection refused")

        assert sub.total_deliveries == 1
        assert sub.successful_deliveries == 0
        assert sub.failed_deliveries == 1
        assert sub.last_error == "Connection refused"

    def test_to_dict_and_from_dict(self):
        """Test serialization round trip."""
        sub = WebhookSubscription.create(
            url="https://example.com/webhook",
            events=["ticket.created", "ticket.completed"],
            secret="secret123",
            name="Test",
            description="A test",
            metadata={"key": "value"},
        )
        sub.record_delivery(success=True)

        data = sub.to_dict()
        restored = WebhookSubscription.from_dict(data)

        assert restored.id == sub.id
        assert restored.url == sub.url
        assert restored.events == sub.events
        assert restored.secret == sub.secret
        assert restored.name == sub.name
        assert restored.active == sub.active
        assert restored.total_deliveries == 1


class TestWebhookDelivery:
    """Tests for WebhookDelivery model."""

    def test_create_delivery(self):
        """Test creating a new delivery record."""
        delivery = WebhookDelivery.create(
            subscription_id="sub-123",
            event=WebhookEvent.TICKET_CREATED,
            payload={"ticket_id": "123"},
            max_attempts=3,
        )

        assert delivery.id
        assert delivery.subscription_id == "sub-123"
        assert delivery.event == WebhookEvent.TICKET_CREATED
        assert delivery.status == DeliveryStatus.PENDING
        assert delivery.attempt == 1
        assert delivery.max_attempts == 3
        assert delivery.payload == {"ticket_id": "123"}

    def test_mark_delivered(self):
        """Test marking delivery as successful."""
        delivery = WebhookDelivery.create(
            subscription_id="sub-123",
            event=WebhookEvent.TICKET_CREATED,
            payload={},
        )

        delivery.mark_delivered(
            status_code=200,
            body='{"ok": true}',
            response_time_ms=150,
        )

        assert delivery.status == DeliveryStatus.DELIVERED
        assert delivery.response_status == 200
        assert delivery.response_time_ms == 150
        assert delivery.delivered_at is not None
        assert delivery.error_message is None

    def test_mark_failed_with_retry(self):
        """Test marking delivery as failed with retry available."""
        delivery = WebhookDelivery.create(
            subscription_id="sub-123",
            event=WebhookEvent.TICKET_CREATED,
            payload={},
            max_attempts=3,
        )

        delivery.mark_failed(error="Connection timeout", status_code=None)

        assert delivery.status == DeliveryStatus.RETRYING
        assert delivery.attempt == 2
        assert delivery.error_message == "Connection timeout"
        assert delivery.next_retry_at is not None

    def test_mark_failed_no_more_retries(self):
        """Test marking delivery as permanently failed."""
        delivery = WebhookDelivery.create(
            subscription_id="sub-123",
            event=WebhookEvent.TICKET_CREATED,
            payload={},
            max_attempts=1,
        )

        delivery.mark_failed(error="Connection refused")

        assert delivery.status == DeliveryStatus.FAILED
        assert delivery.error_message == "Connection refused"

    def test_to_dict(self):
        """Test serialization to dict."""
        delivery = WebhookDelivery.create(
            subscription_id="sub-123",
            event=WebhookEvent.TICKET_CREATED,
            payload={"data": "value"},
        )

        data = delivery.to_dict()

        assert data["id"] == delivery.id
        assert data["event"] == "ticket.created"
        assert data["status"] == "pending"
        assert data["payload"] == {"data": "value"}


class TestWebhookService:
    """Tests for WebhookService."""

    @pytest.fixture
    def config(self, tmp_path):
        """Create a test config with temp storage."""
        return WebhookServiceConfig(
            storage_path=tmp_path / "webhooks.json",
            timeout_seconds=5,
            max_retries=2,
            subscribe_to_events=False,  # Don't subscribe to event bus in tests
        )

    @pytest.fixture
    def service(self, config):
        """Create a test service."""
        return WebhookService(config)

    @pytest.mark.asyncio
    async def test_start_and_stop(self, service):
        """Test service lifecycle."""
        await service.start()
        assert service._started is True
        assert service._client is not None

        await service.stop()
        assert service._started is False

    @pytest.mark.asyncio
    async def test_register_webhook(self, service):
        """Test registering a webhook."""
        await service.start()

        sub = await service.register(
            url="https://example.com/hook",
            events=["ticket.created"],
            secret="test-secret",
            name="Test Hook",
        )

        assert sub.id
        assert sub.url == "https://example.com/hook"
        assert len(await service.list_subscriptions()) == 1

        await service.stop()

    @pytest.mark.asyncio
    async def test_unregister_webhook(self, service):
        """Test unregistering a webhook."""
        await service.start()

        sub = await service.register(
            url="https://example.com/hook",
            events=["ticket.created"],
            secret="test-secret",
        )

        deleted = await service.unregister(sub.id)
        assert deleted is True
        assert len(await service.list_subscriptions()) == 0

        await service.stop()

    @pytest.mark.asyncio
    async def test_update_subscription(self, service):
        """Test updating a subscription."""
        await service.start()

        sub = await service.register(
            url="https://example.com/hook",
            events=["ticket.created"],
            secret="test-secret",
            name="Original",
        )

        updated = await service.update_subscription(
            sub.id,
            name="Updated",
            active=False,
        )

        assert updated.name == "Updated"
        assert updated.active is False

        await service.stop()

    @pytest.mark.asyncio
    async def test_persistence(self, config):
        """Test that subscriptions persist to storage."""
        service1 = WebhookService(config)
        await service1.start()

        await service1.register(
            url="https://example.com/hook",
            events=["ticket.created"],
            secret="test-secret",
        )
        await service1.stop()

        # Create new service with same config
        service2 = WebhookService(config)
        await service2.start()

        subs = await service2.list_subscriptions()
        assert len(subs) == 1
        assert subs[0].url == "https://example.com/hook"

        await service2.stop()

    @pytest.mark.asyncio
    async def test_generate_signature(self, service):
        """Test HMAC signature generation."""
        signature = service._generate_signature(
            secret="my-secret",
            body='{"event": "test"}',
        )

        assert signature.startswith("sha256=")

        # Verify signature
        expected = hmac.new(
            b"my-secret",
            b'{"event": "test"}',
            hashlib.sha256,
        ).hexdigest()
        assert signature == f"sha256={expected}"

    @pytest.mark.asyncio
    async def test_deliver_to_matching_subscriptions(self, service):
        """Test delivery only goes to matching subscriptions."""
        await service.start()

        # Register two webhooks with different events
        await service.register(
            url="https://example.com/hook1",
            events=["ticket.created"],
            secret="secret1",
        )
        await service.register(
            url="https://example.com/hook2",
            events=["ticket.completed"],
            secret="secret2",
        )

        # Save original client for cleanup
        original_client = service._client

        # Mock the HTTP client
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=MagicMock(
            status_code=200,
            text="OK",
        ))
        mock_client.aclose = AsyncMock()
        service._client = mock_client

        # Deliver a ticket.created event
        deliveries = await service.deliver(
            WebhookEvent.TICKET_CREATED,
            {"ticket_id": "123"},
        )

        # Only one delivery should be created
        assert len(deliveries) == 1
        assert mock_client.post.call_count == 1

        # Verify the URL called
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://example.com/hook1"

        # Restore and close original client
        service._client = original_client
        await service.stop()

    @pytest.mark.asyncio
    async def test_delivery_retry_on_failure(self, service):
        """Test that failed deliveries are retried."""
        await service.start()

        await service.register(
            url="https://example.com/hook",
            events=["ticket.created"],
            secret="secret",
        )

        # Save original client
        original_client = service._client

        # Mock client to fail first, succeed second
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Connection failed")
            return MagicMock(status_code=200, text="OK")

        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.aclose = AsyncMock()
        service._client = mock_client

        deliveries = await service.deliver(
            WebhookEvent.TICKET_CREATED,
            {"ticket_id": "123"},
        )

        # Should have attempted twice (initial + 1 retry)
        assert call_count == 2
        assert deliveries[0].status == DeliveryStatus.DELIVERED

        # Restore and close original client
        service._client = original_client
        await service.stop()


class TestWebhookSignatureVerification:
    """Tests for webhook signature verification (receiver side)."""

    def test_verify_signature(self):
        """Test that receivers can verify webhook signatures."""
        secret = "my-webhook-secret"
        payload = '{"event": "ticket.created", "data": {"id": "123"}}'

        # Generate signature like the sender would
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Verify signature
        received_signature = f"sha256={expected_signature}"
        algorithm, signature = received_signature.split("=", 1)

        computed = hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            getattr(hashlib, algorithm),
        ).hexdigest()

        assert hmac.compare_digest(signature, computed)
