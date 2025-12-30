"""
Fastband AI Hub - Stripe Billing Integration.

Handles subscription management, usage metering, and invoicing
through the Stripe API.
"""

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastband.hub.models import SubscriptionTier

logger = logging.getLogger(__name__)


class SubscriptionStatus(str, Enum):
    """Stripe subscription status."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"


class PaymentStatus(str, Enum):
    """Payment status."""

    SUCCEEDED = "succeeded"
    PENDING = "pending"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass(slots=True)
class BillingConfig:
    """Stripe billing configuration.

    Attributes:
        stripe_secret_key: Stripe secret API key
        stripe_publishable_key: Stripe publishable key
        stripe_webhook_secret: Webhook signing secret
        price_ids: Mapping of tier to Stripe price ID
        free_trial_days: Days of free trial for new subscriptions
        metered_price_id: Price ID for metered usage
    """

    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    price_ids: dict[SubscriptionTier, str] = field(default_factory=dict)
    free_trial_days: int = 14
    metered_price_id: str = ""

    @classmethod
    def from_env(cls) -> "BillingConfig":
        """Load configuration from environment variables."""
        return cls(
            stripe_secret_key=os.getenv("STRIPE_SECRET_KEY", ""),
            stripe_publishable_key=os.getenv("STRIPE_PUBLISHABLE_KEY", ""),
            stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET", ""),
            price_ids={
                SubscriptionTier.FREE: os.getenv("STRIPE_PRICE_FREE", ""),
                SubscriptionTier.PRO: os.getenv("STRIPE_PRICE_PRO", ""),
                SubscriptionTier.ENTERPRISE: os.getenv("STRIPE_PRICE_ENTERPRISE", ""),
            },
            free_trial_days=int(os.getenv("STRIPE_FREE_TRIAL_DAYS", "14")),
            metered_price_id=os.getenv("STRIPE_PRICE_METERED", ""),
        )


@dataclass(slots=True)
class Customer:
    """Stripe customer.

    Attributes:
        id: Stripe customer ID
        email: Customer email
        name: Customer name
        user_id: Fastband user ID
        created_at: Customer creation time
        metadata: Additional metadata
    """

    id: str
    email: str
    name: str | None = None
    user_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Subscription:
    """Stripe subscription.

    Attributes:
        id: Stripe subscription ID
        customer_id: Stripe customer ID
        tier: Subscription tier
        status: Subscription status
        current_period_start: Start of current billing period
        current_period_end: End of current billing period
        cancel_at_period_end: Whether subscription cancels at period end
        trial_end: Trial period end date
        metadata: Additional metadata
    """

    id: str
    customer_id: str
    tier: SubscriptionTier
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool = False
    trial_end: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)

    @property
    def is_trialing(self) -> bool:
        """Check if subscription is in trial."""
        return self.status == SubscriptionStatus.TRIALING


@dataclass(slots=True)
class Invoice:
    """Stripe invoice.

    Attributes:
        id: Stripe invoice ID
        customer_id: Stripe customer ID
        subscription_id: Related subscription ID
        amount_due: Amount due in cents
        amount_paid: Amount paid in cents
        currency: Currency code
        status: Invoice status
        created_at: Invoice creation time
        paid_at: Payment time
        hosted_invoice_url: URL to hosted invoice
        invoice_pdf: URL to PDF invoice
    """

    id: str
    customer_id: str
    subscription_id: str | None
    amount_due: int
    amount_paid: int
    currency: str
    status: str
    created_at: datetime
    paid_at: datetime | None = None
    hosted_invoice_url: str | None = None
    invoice_pdf: str | None = None


@dataclass(slots=True)
class UsageMeter:
    """Usage metering for billing.

    Attributes:
        user_id: User identifier
        messages_count: Total messages sent
        tokens_used: Total tokens consumed
        api_calls: Total API calls
        last_reported: Last time usage was reported to Stripe
    """

    user_id: str
    messages_count: int = 0
    tokens_used: int = 0
    api_calls: int = 0
    last_reported: datetime | None = None


class StripeBilling:
    """
    Stripe billing client.

    Handles subscription lifecycle, usage metering, and invoicing.

    Example:
        billing = StripeBilling(config)
        await billing.initialize()

        # Create customer
        customer = await billing.create_customer(email="user@example.com", user_id="123")

        # Create subscription
        subscription = await billing.create_subscription(
            customer_id=customer.id,
            tier=SubscriptionTier.PRO,
        )

        # Report usage
        await billing.report_usage(customer_id, messages=100, tokens=50000)

        # Get invoices
        invoices = await billing.list_invoices(customer_id)
    """

    def __init__(self, config: BillingConfig | None = None):
        """Initialize billing client.

        Args:
            config: Billing configuration
        """
        self.config = config or BillingConfig.from_env()
        self._stripe = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the Stripe client."""
        if self._initialized:
            return

        if not self.config.stripe_secret_key:
            logger.warning("Stripe secret key not configured")
            return

        try:
            import stripe

            stripe.api_key = self.config.stripe_secret_key
            self._stripe = stripe
            self._initialized = True
            logger.info("Stripe billing initialized")

        except ImportError:
            logger.warning("stripe not installed. Run: pip install stripe")
        except Exception as e:
            logger.error(f"Failed to initialize Stripe: {e}")

    async def create_customer(
        self,
        email: str,
        user_id: str,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Customer:
        """Create a Stripe customer.

        Args:
            email: Customer email
            user_id: Fastband user ID
            name: Customer name
            metadata: Additional metadata

        Returns:
            Created customer

        Raises:
            Exception: If creation fails
        """
        if not self._initialized:
            raise RuntimeError("Billing not initialized")

        customer_metadata = metadata or {}
        customer_metadata["fastband_user_id"] = user_id

        stripe_customer = self._stripe.Customer.create(
            email=email,
            name=name,
            metadata=customer_metadata,
        )

        return Customer(
            id=stripe_customer.id,
            email=email,
            name=name,
            user_id=user_id,
            created_at=datetime.fromtimestamp(stripe_customer.created),
            metadata=customer_metadata,
        )

    async def get_customer(
        self,
        customer_id: str,
    ) -> Customer | None:
        """Get customer by ID.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Customer or None if not found
        """
        if not self._initialized:
            return None

        try:
            stripe_customer = self._stripe.Customer.retrieve(customer_id)

            return Customer(
                id=stripe_customer.id,
                email=stripe_customer.email,
                name=stripe_customer.name,
                user_id=stripe_customer.metadata.get("fastband_user_id"),
                created_at=datetime.fromtimestamp(stripe_customer.created),
                metadata=dict(stripe_customer.metadata),
            )

        except self._stripe.error.InvalidRequestError:
            return None

    async def get_customer_by_user(
        self,
        user_id: str,
    ) -> Customer | None:
        """Get customer by Fastband user ID.

        Args:
            user_id: Fastband user ID

        Returns:
            Customer or None if not found
        """
        if not self._initialized:
            return None

        try:
            # Sanitize user_id to prevent injection attacks
            safe_user_id = user_id.replace("\\", "\\\\").replace('"', '\\"')
            customers = self._stripe.Customer.search(
                query=f'metadata["fastband_user_id"]:"{safe_user_id}"',
            )

            if customers.data:
                c = customers.data[0]
                return Customer(
                    id=c.id,
                    email=c.email,
                    name=c.name,
                    user_id=user_id,
                    created_at=datetime.fromtimestamp(c.created),
                    metadata=dict(c.metadata),
                )

        except Exception as e:
            logger.error(f"Customer search error: {e}")

        return None

    async def create_subscription(
        self,
        customer_id: str,
        tier: SubscriptionTier,
        trial_days: int | None = None,
    ) -> Subscription:
        """Create a subscription for a customer.

        Args:
            customer_id: Stripe customer ID
            tier: Subscription tier
            trial_days: Trial period days (default: from config)

        Returns:
            Created subscription

        Raises:
            Exception: If creation fails
        """
        if not self._initialized:
            raise RuntimeError("Billing not initialized")

        price_id = self.config.price_ids.get(tier)
        if not price_id:
            raise ValueError(f"No price ID configured for tier: {tier}")

        params = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "metadata": {"tier": tier.value},
        }

        # Add trial if specified
        trial = trial_days if trial_days is not None else self.config.free_trial_days
        if trial > 0:
            params["trial_period_days"] = trial

        stripe_sub = self._stripe.Subscription.create(**params)

        return self._parse_subscription(stripe_sub, tier)

    async def get_subscription(
        self,
        subscription_id: str,
    ) -> Subscription | None:
        """Get subscription by ID.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Subscription or None if not found
        """
        if not self._initialized:
            return None

        try:
            stripe_sub = self._stripe.Subscription.retrieve(subscription_id)
            tier_str = stripe_sub.metadata.get("tier", "free")
            try:
                tier = SubscriptionTier(tier_str)
            except ValueError:
                tier = SubscriptionTier.FREE

            return self._parse_subscription(stripe_sub, tier)

        except self._stripe.error.InvalidRequestError:
            return None

    async def get_customer_subscription(
        self,
        customer_id: str,
    ) -> Subscription | None:
        """Get active subscription for a customer.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Active subscription or None
        """
        if not self._initialized:
            return None

        try:
            subscriptions = self._stripe.Subscription.list(
                customer=customer_id,
                status="active",
                limit=1,
            )

            if subscriptions.data:
                sub = subscriptions.data[0]
                tier_str = sub.metadata.get("tier", "free")
                try:
                    tier = SubscriptionTier(tier_str)
                except ValueError:
                    tier = SubscriptionTier.FREE

                return self._parse_subscription(sub, tier)

        except Exception as e:
            logger.error(f"Subscription lookup error: {e}")

        return None

    async def update_subscription(
        self,
        subscription_id: str,
        tier: SubscriptionTier,
    ) -> Subscription:
        """Update subscription to a new tier.

        Args:
            subscription_id: Stripe subscription ID
            tier: New subscription tier

        Returns:
            Updated subscription
        """
        if not self._initialized:
            raise RuntimeError("Billing not initialized")

        price_id = self.config.price_ids.get(tier)
        if not price_id:
            raise ValueError(f"No price ID configured for tier: {tier}")

        # Get current subscription
        stripe_sub = self._stripe.Subscription.retrieve(subscription_id)

        # Update to new price
        updated_sub = self._stripe.Subscription.modify(
            subscription_id,
            items=[
                {
                    "id": stripe_sub["items"]["data"][0].id,
                    "price": price_id,
                }
            ],
            metadata={"tier": tier.value},
            proration_behavior="create_prorations",
        )

        return self._parse_subscription(updated_sub, tier)

    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True,
    ) -> Subscription:
        """Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: Cancel at end of billing period

        Returns:
            Canceled subscription
        """
        if not self._initialized:
            raise RuntimeError("Billing not initialized")

        if at_period_end:
            stripe_sub = self._stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
            )
        else:
            stripe_sub = self._stripe.Subscription.delete(subscription_id)

        tier_str = stripe_sub.metadata.get("tier", "free")
        try:
            tier = SubscriptionTier(tier_str)
        except ValueError:
            tier = SubscriptionTier.FREE

        return self._parse_subscription(stripe_sub, tier)

    async def report_usage(
        self,
        customer_id: str,
        messages: int = 0,
        tokens: int = 0,
    ) -> None:
        """Report usage for metered billing.

        Args:
            customer_id: Stripe customer ID
            messages: Number of messages
            tokens: Number of tokens
        """
        if not self._initialized or not self.config.metered_price_id:
            return

        try:
            # Get subscription with metered price
            subscriptions = self._stripe.Subscription.list(
                customer=customer_id,
                status="active",
            )

            for sub in subscriptions.data:
                for item in sub["items"]["data"]:
                    if item.price.id == self.config.metered_price_id:
                        # Report usage
                        self._stripe.SubscriptionItem.create_usage_record(
                            item.id,
                            quantity=messages + (tokens // 1000),  # Convert tokens to units
                            action="increment",
                        )
                        return

        except Exception as e:
            logger.error(f"Usage report error: {e}")

    async def list_invoices(
        self,
        customer_id: str,
        limit: int = 10,
    ) -> list[Invoice]:
        """List invoices for a customer.

        Args:
            customer_id: Stripe customer ID
            limit: Maximum invoices to return

        Returns:
            List of invoices
        """
        if not self._initialized:
            return []

        try:
            invoices = self._stripe.Invoice.list(
                customer=customer_id,
                limit=limit,
            )

            return [
                Invoice(
                    id=inv.id,
                    customer_id=customer_id,
                    subscription_id=inv.subscription,
                    amount_due=inv.amount_due,
                    amount_paid=inv.amount_paid,
                    currency=inv.currency,
                    status=inv.status,
                    created_at=datetime.fromtimestamp(inv.created),
                    paid_at=datetime.fromtimestamp(inv.status_transitions.paid_at)
                    if inv.status_transitions.paid_at
                    else None,
                    hosted_invoice_url=inv.hosted_invoice_url,
                    invoice_pdf=inv.invoice_pdf,
                )
                for inv in invoices.data
            ]

        except Exception as e:
            logger.error(f"Invoice list error: {e}")
            return []

    async def create_checkout_session(
        self,
        customer_id: str,
        tier: SubscriptionTier,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout session for subscription.

        Args:
            customer_id: Stripe customer ID
            tier: Subscription tier
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel

        Returns:
            Checkout session URL
        """
        if not self._initialized:
            raise RuntimeError("Billing not initialized")

        price_id = self.config.price_ids.get(tier)
        if not price_id:
            raise ValueError(f"No price ID configured for tier: {tier}")

        session = self._stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={"metadata": {"tier": tier.value}},
        )

        return session.url

    async def create_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> str:
        """Create a Stripe Customer Portal session.

        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to after portal

        Returns:
            Portal session URL
        """
        if not self._initialized:
            raise RuntimeError("Billing not initialized")

        session = self._stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

        return session.url

    def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> dict[str, Any]:
        """Verify and parse a Stripe webhook.

        Args:
            payload: Raw webhook payload
            signature: Stripe-Signature header

        Returns:
            Parsed event data

        Raises:
            ValueError: If verification fails
        """
        if not self._initialized or not self.config.stripe_webhook_secret:
            raise ValueError("Webhook verification not configured")

        try:
            event = self._stripe.Webhook.construct_event(
                payload,
                signature,
                self.config.stripe_webhook_secret,
            )
            return event

        except self._stripe.error.SignatureVerificationError:
            raise ValueError("Invalid webhook signature")

    def _parse_subscription(
        self,
        stripe_sub,
        tier: SubscriptionTier,
    ) -> Subscription:
        """Parse Stripe subscription to our model."""
        try:
            status = SubscriptionStatus(stripe_sub.status)
        except ValueError:
            status = SubscriptionStatus.ACTIVE

        trial_end = None
        if stripe_sub.trial_end:
            trial_end = datetime.fromtimestamp(stripe_sub.trial_end)

        return Subscription(
            id=stripe_sub.id,
            customer_id=stripe_sub.customer,
            tier=tier,
            status=status,
            current_period_start=datetime.fromtimestamp(stripe_sub.current_period_start),
            current_period_end=datetime.fromtimestamp(stripe_sub.current_period_end),
            cancel_at_period_end=stripe_sub.cancel_at_period_end,
            trial_end=trial_end,
            metadata=dict(stripe_sub.metadata),
        )


# =============================================================================
# GLOBAL SINGLETON
# =============================================================================

_billing: StripeBilling | None = None
_billing_lock = threading.Lock()


def get_billing(config: BillingConfig | None = None) -> StripeBilling:
    """Get or create the global billing client.

    Args:
        config: Optional billing configuration

    Returns:
        Global StripeBilling instance
    """
    global _billing

    with _billing_lock:
        if _billing is None:
            _billing = StripeBilling(config)
        return _billing


def reset_billing() -> None:
    """Reset the global billing client (for testing)."""
    global _billing

    with _billing_lock:
        _billing = None
