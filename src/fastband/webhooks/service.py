"""
Webhook Service - Core webhook management and delivery.

Provides:
- Subscription management (CRUD)
- Event-driven webhook delivery
- HMAC signature generation
- Retry logic with exponential backoff
- Delivery logging
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from fastband.agents.ops_log import EventType
from fastband.core.events import get_event_bus
from fastband.webhooks.models import (
    DeliveryStatus,
    WebhookDelivery,
    WebhookEvent,
    WebhookSubscription,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class WebhookServiceConfig:
    """Webhook service configuration."""

    # Storage
    storage_path: Path | None = None

    # Delivery settings
    timeout_seconds: int = 30
    max_retries: int = 3
    max_concurrent_deliveries: int = 10

    # Security
    signature_header: str = "X-Fastband-Signature"
    signature_algorithm: str = "sha256"

    # Event bus integration
    subscribe_to_events: bool = True

    @classmethod
    def from_env(cls) -> "WebhookServiceConfig":
        """Create config from environment variables."""
        storage_path = os.getenv("FASTBAND_WEBHOOK_STORAGE")
        return cls(
            storage_path=Path(storage_path) if storage_path else None,
            timeout_seconds=int(os.getenv("FASTBAND_WEBHOOK_TIMEOUT", "30")),
            max_retries=int(os.getenv("FASTBAND_WEBHOOK_MAX_RETRIES", "3")),
            max_concurrent_deliveries=int(
                os.getenv("FASTBAND_WEBHOOK_MAX_CONCURRENT", "10")
            ),
        )


# =============================================================================
# WEBHOOK SERVICE
# =============================================================================


class WebhookService:
    """
    Webhook management and delivery service.

    Handles webhook subscriptions, event listening, and HTTP delivery
    with HMAC signatures and retry logic.

    Example:
        service = WebhookService(config)
        await service.start()

        # Register webhook
        sub = await service.register(
            url="https://api.example.com/webhook",
            events=["ticket.completed"],
            secret="secret123",
        )

        # Manual delivery (events auto-deliver via event bus)
        await service.deliver(WebhookEvent.TICKET_COMPLETED, {
            "ticket_id": "123",
            "status": "completed"
        })

        await service.stop()
    """

    def __init__(self, config: WebhookServiceConfig | None = None):
        """Initialize webhook service."""
        self.config = config or WebhookServiceConfig.from_env()
        self._subscriptions: dict[str, WebhookSubscription] = {}
        self._deliveries: list[WebhookDelivery] = []
        self._client: httpx.AsyncClient | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._lock = threading.Lock()
        self._started = False
        self._event_subscription_ids: list[str] = []

    async def start(self) -> None:
        """Start the webhook service."""
        if self._started:
            return

        # Load subscriptions from storage
        self._load_subscriptions()

        # Create HTTP client
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout_seconds),
            follow_redirects=False,  # Security: don't follow redirects
        )

        # Create semaphore for concurrent delivery limiting
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_deliveries)

        # Subscribe to event bus
        if self.config.subscribe_to_events:
            self._subscribe_to_event_bus()

        self._started = True
        logger.info(
            f"WebhookService started with {len(self._subscriptions)} subscriptions"
        )

    async def stop(self) -> None:
        """Stop the webhook service."""
        if not self._started:
            return

        # Unsubscribe from event bus
        bus = get_event_bus()
        for sub_id in self._event_subscription_ids:
            bus.unsubscribe(sub_id)
        self._event_subscription_ids.clear()

        # Close HTTP client
        if self._client:
            await self._client.aclose()
            self._client = None

        # Save subscriptions
        self._save_subscriptions()

        self._started = False
        logger.info("WebhookService stopped")

    def _subscribe_to_event_bus(self) -> None:
        """Subscribe to relevant events on the event bus."""
        bus = get_event_bus()

        # Map EventType to WebhookEvent
        event_mappings = [
            (EventType.TICKET_CLAIMED, WebhookEvent.TICKET_CLAIMED),
            (EventType.TICKET_COMPLETED, WebhookEvent.TICKET_COMPLETED),
            (EventType.AGENT_STARTED, WebhookEvent.AGENT_STARTED),
            (EventType.AGENT_STOPPED, WebhookEvent.AGENT_STOPPED),
            (EventType.ERROR, WebhookEvent.AGENT_ERROR),
            (EventType.REBUILD_REQUESTED, WebhookEvent.BUILD_STARTED),
            (EventType.REBUILD_COMPLETE, WebhookEvent.BUILD_COMPLETED),
        ]

        for ops_event, webhook_event in event_mappings:
            sub_id = bus.subscribe(
                ops_event,
                lambda data, we=webhook_event: asyncio.create_task(
                    self._on_event(we, data)
                ),
            )
            self._event_subscription_ids.append(sub_id)

        logger.debug(f"Subscribed to {len(event_mappings)} event types")

    async def _on_event(self, event: WebhookEvent, data: dict[str, Any]) -> None:
        """Handle an event from the event bus."""
        logger.debug(f"Received event {event.value}: {data}")
        await self.deliver(event, data)

    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================

    async def register(
        self,
        url: str,
        events: list[str],
        secret: str,
        name: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WebhookSubscription:
        """
        Register a new webhook subscription.

        Args:
            url: Webhook endpoint URL (HTTPS required in production)
            events: List of event types to subscribe to
            secret: Shared secret for HMAC signature verification
            name: Optional friendly name
            description: Optional description
            metadata: Optional custom metadata

        Returns:
            Created WebhookSubscription
        """
        subscription = WebhookSubscription.create(
            url=url,
            events=events,
            secret=secret,
            name=name,
            description=description,
            metadata=metadata,
        )

        with self._lock:
            self._subscriptions[subscription.id] = subscription
            self._save_subscriptions()

        logger.info(f"Registered webhook {subscription.id} for {url}")
        return subscription

    async def unregister(self, subscription_id: str) -> bool:
        """
        Unregister a webhook subscription.

        Args:
            subscription_id: Subscription ID to remove

        Returns:
            True if subscription was found and removed
        """
        with self._lock:
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]
                self._save_subscriptions()
                logger.info(f"Unregistered webhook {subscription_id}")
                return True
        return False

    async def get_subscription(self, subscription_id: str) -> WebhookSubscription | None:
        """Get a subscription by ID."""
        return self._subscriptions.get(subscription_id)

    async def list_subscriptions(
        self,
        active_only: bool = False,
    ) -> list[WebhookSubscription]:
        """List all webhook subscriptions."""
        subs = list(self._subscriptions.values())
        if active_only:
            subs = [s for s in subs if s.active]
        return sorted(subs, key=lambda s: s.created_at, reverse=True)

    async def update_subscription(
        self,
        subscription_id: str,
        *,
        events: list[str] | None = None,
        active: bool | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> WebhookSubscription | None:
        """Update a webhook subscription."""
        with self._lock:
            sub = self._subscriptions.get(subscription_id)
            if not sub:
                return None

            if events is not None:
                sub.events = [WebhookEvent(e) for e in events]
            if active is not None:
                sub.active = active
            if name is not None:
                sub.name = name
            if description is not None:
                sub.description = description

            sub.updated_at = datetime.now(timezone.utc)
            self._save_subscriptions()

        return sub

    # =========================================================================
    # DELIVERY
    # =========================================================================

    async def deliver(
        self,
        event: WebhookEvent,
        payload: dict[str, Any],
    ) -> list[WebhookDelivery]:
        """
        Deliver an event to all matching subscriptions.

        Args:
            event: Event type
            payload: Event payload data

        Returns:
            List of delivery records
        """
        if not self._started:
            logger.warning("WebhookService not started, skipping delivery")
            return []

        # Find matching subscriptions
        matching = [
            sub
            for sub in self._subscriptions.values()
            if sub.should_deliver(event)
        ]

        if not matching:
            return []

        logger.info(f"Delivering {event.value} to {len(matching)} webhooks")

        # Create delivery tasks
        tasks = []
        deliveries = []
        for sub in matching:
            delivery = WebhookDelivery.create(
                subscription_id=sub.id,
                event=event,
                payload=payload,
                max_attempts=self.config.max_retries,
            )
            deliveries.append(delivery)
            tasks.append(self._deliver_to_subscription(sub, delivery))

        # Execute deliveries concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        # Store delivery records
        self._deliveries.extend(deliveries)
        # Keep only last 1000 deliveries
        if len(self._deliveries) > 1000:
            self._deliveries = self._deliveries[-1000:]

        return deliveries

    async def _deliver_to_subscription(
        self,
        subscription: WebhookSubscription,
        delivery: WebhookDelivery,
    ) -> None:
        """Deliver to a single subscription with retries."""
        async with self._semaphore:  # Limit concurrent deliveries
            while delivery.status in (DeliveryStatus.PENDING, DeliveryStatus.RETRYING):
                success = await self._send_webhook(subscription, delivery)
                if success:
                    break
                if delivery.status == DeliveryStatus.RETRYING:
                    # Wait for retry
                    if delivery.next_retry_at:
                        wait_seconds = (
                            delivery.next_retry_at - datetime.now(timezone.utc)
                        ).total_seconds()
                        if wait_seconds > 0:
                            await asyncio.sleep(wait_seconds)

        # Update subscription stats
        subscription.record_delivery(
            success=delivery.status == DeliveryStatus.DELIVERED,
            error=delivery.error_message,
        )
        self._save_subscriptions()

    async def _send_webhook(
        self,
        subscription: WebhookSubscription,
        delivery: WebhookDelivery,
    ) -> bool:
        """Send a single webhook request."""
        # Prepare payload
        body = json.dumps(
            {
                "event": delivery.event.value,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                "delivery_id": delivery.id,
                "data": delivery.payload,
            },
            default=str,
        )

        # Generate signature
        signature = self._generate_signature(subscription.secret, body)

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            self.config.signature_header: signature,
            "X-Fastband-Event": delivery.event.value,
            "X-Fastband-Delivery": delivery.id,
        }

        start_time = time.time()

        try:
            response = await self._client.post(
                subscription.url,
                content=body,
                headers=headers,
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            if 200 <= response.status_code < 300:
                delivery.mark_delivered(
                    status_code=response.status_code,
                    body=response.text,
                    response_time_ms=response_time_ms,
                )
                logger.info(
                    f"Webhook delivered to {subscription.url} "
                    f"(status={response.status_code}, time={response_time_ms}ms)"
                )
                return True
            else:
                delivery.mark_failed(
                    error=f"HTTP {response.status_code}",
                    status_code=response.status_code,
                    body=response.text,
                )
                logger.warning(
                    f"Webhook delivery failed to {subscription.url}: "
                    f"HTTP {response.status_code}"
                )
                return False

        except httpx.TimeoutException:
            delivery.mark_failed(error="Request timed out")
            logger.warning(f"Webhook timed out: {subscription.url}")
            return False
        except httpx.RequestError as e:
            delivery.mark_failed(error=str(e))
            logger.warning(f"Webhook request error: {e}")
            return False
        except Exception as e:
            delivery.mark_failed(error=str(e))
            logger.error(f"Webhook delivery error: {e}")
            return False

    def _generate_signature(self, secret: str, body: str) -> str:
        """Generate HMAC signature for webhook payload."""
        signature = hmac.new(
            secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{self.config.signature_algorithm}={signature}"

    # =========================================================================
    # DELIVERY HISTORY
    # =========================================================================

    async def get_deliveries(
        self,
        subscription_id: str | None = None,
        status: DeliveryStatus | None = None,
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        """Get delivery history with optional filters."""
        deliveries = self._deliveries

        if subscription_id:
            deliveries = [d for d in deliveries if d.subscription_id == subscription_id]
        if status:
            deliveries = [d for d in deliveries if d.status == status]

        return sorted(deliveries, key=lambda d: d.created_at, reverse=True)[:limit]

    async def retry_delivery(self, delivery_id: str) -> WebhookDelivery | None:
        """Manually retry a failed delivery."""
        for delivery in self._deliveries:
            if delivery.id == delivery_id:
                if delivery.status != DeliveryStatus.FAILED:
                    logger.warning(f"Cannot retry delivery {delivery_id}: not failed")
                    return None

                # Reset for retry
                delivery.status = DeliveryStatus.PENDING
                delivery.attempt = 1

                # Find subscription
                sub = self._subscriptions.get(delivery.subscription_id)
                if sub:
                    await self._deliver_to_subscription(sub, delivery)

                return delivery

        return None

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def _get_storage_path(self) -> Path:
        """Get the storage path for subscriptions."""
        if self.config.storage_path:
            return self.config.storage_path
        # Default to ~/.fastband/webhooks.json
        default_path = Path.home() / ".fastband" / "webhooks.json"
        default_path.parent.mkdir(parents=True, exist_ok=True)
        return default_path

    def _load_subscriptions(self) -> None:
        """Load subscriptions from storage."""
        path = self._get_storage_path()
        if not path.exists():
            return

        try:
            data = json.loads(path.read_text())
            for sub_data in data.get("subscriptions", []):
                sub = WebhookSubscription.from_dict(sub_data)
                self._subscriptions[sub.id] = sub
            logger.info(f"Loaded {len(self._subscriptions)} webhooks from {path}")
        except Exception as e:
            logger.error(f"Failed to load webhooks: {e}")

    def _save_subscriptions(self) -> None:
        """Save subscriptions to storage."""
        path = self._get_storage_path()
        try:
            data = {
                "subscriptions": [
                    sub.to_dict() for sub in self._subscriptions.values()
                ],
                "saved_at": datetime.now(timezone.utc).isoformat() + "Z",
            }
            path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.error(f"Failed to save webhooks: {e}")


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_webhook_service: WebhookService | None = None
_service_lock = threading.Lock()


def get_webhook_service(
    config: WebhookServiceConfig | None = None,
) -> WebhookService:
    """
    Get or create the global webhook service instance.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        WebhookService instance
    """
    global _webhook_service

    if _webhook_service is None:
        with _service_lock:
            if _webhook_service is None:
                _webhook_service = WebhookService(config)

    return _webhook_service


def reset_webhook_service() -> None:
    """Reset the global webhook service (for testing)."""
    global _webhook_service
    with _service_lock:
        _webhook_service = None
