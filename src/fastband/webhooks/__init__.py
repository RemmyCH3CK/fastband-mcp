"""
Fastband Webhooks - External event notification system.

Provides webhook support for ticket and agent events:
- Subscribe external URLs to specific event types
- HMAC signature verification for security
- Automatic retries with exponential backoff
- Delivery logging and status tracking

Example:
    from fastband.webhooks import WebhookService, get_webhook_service

    # Get the global service
    service = get_webhook_service()

    # Register a webhook
    subscription = await service.register(
        url="https://example.com/webhook",
        events=["ticket_claimed", "ticket_completed"],
        secret="my-secret-key",
        name="My Integration",
    )

    # List webhooks
    webhooks = await service.list_subscriptions()

    # Delete a webhook
    await service.unregister(subscription.id)
"""

from fastband.webhooks.models import (
    DeliveryStatus,
    WebhookDelivery,
    WebhookEvent,
    WebhookSubscription,
)
from fastband.webhooks.service import (
    WebhookService,
    WebhookServiceConfig,
    get_webhook_service,
)

__all__ = [
    # Models
    "WebhookSubscription",
    "WebhookEvent",
    "WebhookDelivery",
    "DeliveryStatus",
    # Service
    "WebhookService",
    "WebhookServiceConfig",
    "get_webhook_service",
]
