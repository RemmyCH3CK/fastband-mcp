"""
Fastband CLI - Webhook management commands.

Provides commands for managing webhook subscriptions.
"""

import asyncio

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Create webhooks subcommand app
webhooks_app = typer.Typer(
    name="webhooks",
    help="Webhook management commands",
    no_args_is_help=True,
)


@webhooks_app.command("list")
def webhooks_list(
    active_only: bool = typer.Option(
        False,
        "--active",
        "-a",
        help="Show only active webhooks",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed webhook information",
    ),
):
    """
    List all webhook subscriptions.

    Shows registered webhooks and their delivery stats.
    """
    from fastband.webhooks import get_webhook_service

    async def _list():
        service = get_webhook_service()
        await service.start()
        return await service.list_subscriptions(active_only=active_only)

    subscriptions = asyncio.run(_list())

    if not subscriptions:
        console.print("[yellow]No webhooks registered.[/yellow]")
        console.print("\nTo create a webhook:")
        console.print("  [dim]fastband webhooks create https://example.com/webhook[/dim]")
        return

    table = Table(
        title="Webhook Subscriptions",
        box=box.ROUNDED,
    )
    table.add_column("ID", style="dim", max_width=8)
    table.add_column("Name", style="cyan")
    table.add_column("URL", max_width=40)
    table.add_column("Events", max_width=20)
    table.add_column("Status")
    table.add_column("Deliveries", justify="right")

    if verbose:
        table.add_column("Success Rate", justify="right")
        table.add_column("Last Error", max_width=30)

    for sub in subscriptions:
        status = "[green]Active[/green]" if sub.active else "[dim]Inactive[/dim]"
        events = ", ".join(e.value.split(".")[-1] for e in sub.events[:3])
        if len(sub.events) > 3:
            events += f" +{len(sub.events) - 3}"

        row = [
            sub.id[:8],
            sub.name or "[dim]—[/dim]",
            sub.url[:40] + ("..." if len(sub.url) > 40 else ""),
            events,
            status,
            str(sub.total_deliveries),
        ]

        if verbose:
            success_rate = (
                f"{sub.successful_deliveries / sub.total_deliveries * 100:.0f}%"
                if sub.total_deliveries > 0
                else "[dim]—[/dim]"
            )
            row.append(success_rate)
            row.append(sub.last_error[:30] if sub.last_error else "[dim]—[/dim]")

        table.add_row(*row)

    console.print(table)
    console.print(f"\n[dim]{len(subscriptions)} webhook(s) registered[/dim]")


@webhooks_app.command("create")
def webhooks_create(
    url: str = typer.Argument(
        ...,
        help="Webhook endpoint URL",
    ),
    events: list[str] = typer.Option(
        ["*"],
        "--event",
        "-e",
        help="Event types to subscribe to (can specify multiple)",
    ),
    secret: str = typer.Option(
        None,
        "--secret",
        "-s",
        help="Shared secret for HMAC signature (auto-generated if not provided)",
    ),
    name: str = typer.Option(
        None,
        "--name",
        "-n",
        help="Friendly name for the webhook",
    ),
    description: str = typer.Option(
        None,
        "--description",
        "-d",
        help="Description of the webhook purpose",
    ),
):
    """
    Create a new webhook subscription.

    Events can be specified multiple times:
      fastband webhooks create URL -e ticket.created -e ticket.completed

    Available events:
      ticket.created, ticket.claimed, ticket.updated, ticket.completed,
      ticket.approved, ticket.rejected, ticket.closed, ticket.comment_added,
      agent.started, agent.stopped, agent.error,
      build.started, build.completed, build.failed,
      * (all events)
    """
    import secrets as secrets_module

    from fastband.webhooks import get_webhook_service

    # Validate URL
    if not url.startswith(("http://", "https://")):
        console.print("[red]Error: URL must start with http:// or https://[/red]")
        raise typer.Exit(1)

    # Generate secret if not provided
    if not secret:
        secret = secrets_module.token_urlsafe(32)
        console.print(f"[dim]Generated secret: {secret}[/dim]")

    if len(secret) < 8:
        console.print("[red]Error: Secret must be at least 8 characters[/red]")
        raise typer.Exit(1)

    async def _create():
        service = get_webhook_service()
        await service.start()
        return await service.register(
            url=url,
            events=events,
            secret=secret,
            name=name,
            description=description,
        )

    subscription = asyncio.run(_create())

    console.print(f"\n[green]Created webhook:[/green] {subscription.id}")
    console.print(f"  URL: {subscription.url}")
    console.print(f"  Events: {', '.join(e.value for e in subscription.events)}")
    console.print(f"  Secret: {secret}")
    console.print("\n[dim]Use the secret to verify webhook signatures on your server.[/dim]")
    console.print("[dim]Header: X-Fastband-Signature: sha256=<hmac>[/dim]")


@webhooks_app.command("delete")
def webhooks_delete(
    webhook_id: str = typer.Argument(
        ...,
        help="Webhook ID to delete (can be partial)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """
    Delete a webhook subscription.

    The webhook ID can be a partial match (first 8 characters).
    """
    from fastband.webhooks import get_webhook_service

    async def _find_and_delete():
        service = get_webhook_service()
        await service.start()

        # Find matching webhook
        subscriptions = await service.list_subscriptions()
        matches = [s for s in subscriptions if s.id.startswith(webhook_id)]

        if not matches:
            return None, "not_found"
        if len(matches) > 1:
            return matches, "ambiguous"

        return matches[0], "found"

    subscription, status = asyncio.run(_find_and_delete())

    if status == "not_found":
        console.print(f"[red]Webhook not found: {webhook_id}[/red]")
        raise typer.Exit(1)

    if status == "ambiguous":
        console.print(f"[yellow]Multiple webhooks match '{webhook_id}':[/yellow]")
        for sub in subscription:
            console.print(f"  {sub.id} - {sub.name or sub.url}")
        console.print("\n[dim]Please provide a more specific ID.[/dim]")
        raise typer.Exit(1)

    # Confirm deletion
    if not force:
        console.print(f"Webhook: [cyan]{subscription.name or subscription.url}[/cyan]")
        console.print(f"ID: {subscription.id}")
        console.print(f"Deliveries: {subscription.total_deliveries}")
        confirm = typer.confirm("\nAre you sure you want to delete this webhook?")
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    async def _delete():
        service = get_webhook_service()
        await service.start()
        return await service.unregister(subscription.id)

    deleted = asyncio.run(_delete())

    if deleted:
        console.print(f"[green]Deleted webhook: {subscription.id}[/green]")
    else:
        console.print(f"[red]Failed to delete webhook[/red]")
        raise typer.Exit(1)


@webhooks_app.command("test")
def webhooks_test(
    webhook_id: str = typer.Argument(
        ...,
        help="Webhook ID to test (can be partial)",
    ),
):
    """
    Send a test event to a webhook.

    Sends a test payload to verify the webhook endpoint is working.
    """
    from datetime import datetime, timezone

    from fastband.webhooks import WebhookEvent, get_webhook_service

    async def _test():
        service = get_webhook_service()
        await service.start()

        # Find matching webhook
        subscriptions = await service.list_subscriptions()
        matches = [s for s in subscriptions if s.id.startswith(webhook_id)]

        if not matches:
            return None, None
        if len(matches) > 1:
            console.print(f"[yellow]Multiple webhooks match '{webhook_id}':[/yellow]")
            for sub in matches:
                console.print(f"  {sub.id} - {sub.name or sub.url}")
            return None, None

        subscription = matches[0]

        # Send test event
        test_payload = {
            "type": "test",
            "message": "This is a test webhook delivery from Fastband CLI",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }

        # Temporarily enable ALL event for this subscription
        original_events = subscription.events.copy()
        subscription.events = [WebhookEvent.ALL]

        deliveries = await service.deliver(WebhookEvent.ALL, test_payload)

        # Restore events
        subscription.events = original_events

        # Find delivery for this subscription
        for delivery in deliveries:
            if delivery.subscription_id == subscription.id:
                return subscription, delivery

        return subscription, None

    with console.status("[bold cyan]Sending test webhook...[/bold cyan]"):
        subscription, delivery = asyncio.run(_test())

    if subscription is None:
        console.print(f"[red]Webhook not found: {webhook_id}[/red]")
        raise typer.Exit(1)

    if delivery is None:
        console.print(f"[red]No delivery created for webhook[/red]")
        raise typer.Exit(1)

    console.print(f"\nWebhook: [cyan]{subscription.name or subscription.url}[/cyan]")
    console.print(f"URL: {subscription.url}")

    if delivery.status.value == "delivered":
        console.print(f"\n[green]Test successful![/green]")
        console.print(f"  Status: {delivery.response_status}")
        console.print(f"  Time: {delivery.response_time_ms}ms")
    else:
        console.print(f"\n[red]Test failed![/red]")
        console.print(f"  Status: {delivery.status.value}")
        console.print(f"  Error: {delivery.error_message}")
        if delivery.response_status:
            console.print(f"  HTTP Status: {delivery.response_status}")
        raise typer.Exit(1)


@webhooks_app.command("info")
def webhooks_info(
    webhook_id: str = typer.Argument(
        ...,
        help="Webhook ID to show info for (can be partial)",
    ),
):
    """
    Show detailed information about a webhook.
    """
    from fastband.webhooks import get_webhook_service

    async def _info():
        service = get_webhook_service()
        await service.start()

        subscriptions = await service.list_subscriptions()
        matches = [s for s in subscriptions if s.id.startswith(webhook_id)]

        if not matches:
            return None
        if len(matches) > 1:
            console.print(f"[yellow]Multiple webhooks match '{webhook_id}':[/yellow]")
            for sub in matches:
                console.print(f"  {sub.id} - {sub.name or sub.url}")
            return None

        return matches[0]

    subscription = asyncio.run(_info())

    if subscription is None:
        console.print(f"[red]Webhook not found: {webhook_id}[/red]")
        raise typer.Exit(1)

    # Display info
    status = "[green]Active[/green]" if subscription.active else "[red]Inactive[/red]"

    console.print(Panel(
        f"[bold cyan]{subscription.name or 'Unnamed Webhook'}[/bold cyan]\n"
        f"[dim]{subscription.id}[/dim]",
        title="Webhook Details",
    ))

    console.print(f"\n  URL: {subscription.url}")
    console.print(f"  Status: {status}")

    if subscription.description:
        console.print(f"  Description: {subscription.description}")

    console.print(f"\n  [bold]Events:[/bold]")
    for event in subscription.events:
        console.print(f"    - {event.value}")

    console.print(f"\n  [bold]Statistics:[/bold]")
    console.print(f"    Total deliveries: {subscription.total_deliveries}")
    console.print(f"    Successful: {subscription.successful_deliveries}")
    console.print(f"    Failed: {subscription.failed_deliveries}")

    if subscription.total_deliveries > 0:
        success_rate = subscription.successful_deliveries / subscription.total_deliveries * 100
        console.print(f"    Success rate: {success_rate:.1f}%")

    if subscription.last_delivery_at:
        console.print(f"\n    Last delivery: {subscription.last_delivery_at.isoformat()}")

    if subscription.last_error:
        console.print(f"    [red]Last error: {subscription.last_error}[/red]")

    console.print(f"\n  Created: {subscription.created_at.isoformat()}")
    console.print(f"  Updated: {subscription.updated_at.isoformat()}")


@webhooks_app.command("events")
def webhooks_events():
    """
    List available webhook event types.
    """
    from fastband.webhooks import WebhookEvent

    table = Table(
        title="Webhook Event Types",
        box=box.ROUNDED,
    )
    table.add_column("Event", style="cyan")
    table.add_column("Description")

    event_descriptions = {
        WebhookEvent.TICKET_CREATED: "A new ticket was created",
        WebhookEvent.TICKET_CLAIMED: "An agent claimed a ticket",
        WebhookEvent.TICKET_UPDATED: "A ticket was updated",
        WebhookEvent.TICKET_COMPLETED: "A ticket was marked complete",
        WebhookEvent.TICKET_APPROVED: "A ticket was approved",
        WebhookEvent.TICKET_REJECTED: "A ticket was rejected",
        WebhookEvent.TICKET_CLOSED: "A ticket was closed",
        WebhookEvent.TICKET_COMMENT_ADDED: "A comment was added to a ticket",
        WebhookEvent.AGENT_STARTED: "An agent started working",
        WebhookEvent.AGENT_STOPPED: "An agent stopped working",
        WebhookEvent.AGENT_ERROR: "An agent encountered an error",
        WebhookEvent.CODE_REVIEW_STARTED: "Code review was initiated",
        WebhookEvent.CODE_REVIEW_PASSED: "Code review passed",
        WebhookEvent.CODE_REVIEW_FAILED: "Code review failed",
        WebhookEvent.BUILD_STARTED: "A build was started",
        WebhookEvent.BUILD_COMPLETED: "A build completed successfully",
        WebhookEvent.BUILD_FAILED: "A build failed",
        WebhookEvent.ALL: "Subscribe to all events",
    }

    for event in WebhookEvent:
        table.add_row(
            event.value,
            event_descriptions.get(event, "[dim]—[/dim]"),
        )

    console.print(table)


@webhooks_app.command("toggle")
def webhooks_toggle(
    webhook_id: str = typer.Argument(
        ...,
        help="Webhook ID to toggle (can be partial)",
    ),
):
    """
    Toggle a webhook between active and inactive.
    """
    from fastband.webhooks import get_webhook_service

    async def _toggle():
        service = get_webhook_service()
        await service.start()

        subscriptions = await service.list_subscriptions()
        matches = [s for s in subscriptions if s.id.startswith(webhook_id)]

        if not matches:
            return None
        if len(matches) > 1:
            console.print(f"[yellow]Multiple webhooks match '{webhook_id}':[/yellow]")
            for sub in matches:
                console.print(f"  {sub.id} - {sub.name or sub.url}")
            return None

        subscription = matches[0]
        new_active = not subscription.active

        await service.update_subscription(subscription.id, active=new_active)
        subscription.active = new_active
        return subscription

    subscription = asyncio.run(_toggle())

    if subscription is None:
        console.print(f"[red]Webhook not found: {webhook_id}[/red]")
        raise typer.Exit(1)

    status = "[green]activated[/green]" if subscription.active else "[yellow]deactivated[/yellow]"
    console.print(f"Webhook {subscription.id[:8]} {status}")
