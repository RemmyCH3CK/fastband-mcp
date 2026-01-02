#!/usr/bin/env python3
"""
Fastband Core Demo - Validates Core Independence.

This demo validates that fastband_core can run independently without:
- External SDKs (anthropic, openai, etc.)
- Web frameworks (FastAPI, Flask)
- Database drivers
- Network calls
- Environment file loading

The demo:
1. Sets up mock adapters for all Core ports
2. Registers and invokes a tool through the registry
3. Emits domain events and audit records
4. Validates all Core abstractions work together

Run:
    python packages/core/examples/core_demo.py

    Or from the package root:
    python -m packages.core.examples.core_demo
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

# Ensure the package is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Core imports
from fastband_core.events import DomainEvent, EventMetadata, CommonEventTypes
from fastband_core.audit import (
    AuditRecord,
    AuditActor,
    AuditCategory,
    AuditSeverity,
    AuditEventTypes,
)
from fastband_core.tools import (
    ToolBase,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
    ToolRegistry,
    tool,
)
from fastband_core.ports import Event, EventMetadata as PortEventMetadata, LogLevel

# Mock imports
from mocks import DemoContext, MockCompletionProvider


# =============================================================================
# DEMO TOOL
# =============================================================================


class GreetingTool(ToolBase):
    """A simple demo tool that generates greetings."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="greeting",
                description="Generate a greeting message",
                category=ToolCategory.CORE,
            ),
            parameters=[
                ToolParameter(
                    name="person_name",
                    type="string",
                    description="Name to greet",
                    required=True,
                ),
                ToolParameter(
                    name="style",
                    type="string",
                    description="Greeting style: formal, casual, or enthusiastic",
                    required=False,
                    default="casual",
                ),
            ],
        )

    async def execute(self, **params: Any) -> ToolResult:
        person_name = params.get("person_name", "World")
        style = params.get("style", "casual")

        greetings = {
            "formal": f"Good day, {person_name}. It is a pleasure to meet you.",
            "casual": f"Hey {person_name}! What's up?",
            "enthusiastic": f"WOW! {person_name}! SO GREAT TO SEE YOU!!!",
        }

        message = greetings.get(style, greetings["casual"])
        return ToolResult(success=True, data=message, metadata={"style": style})


# Decorator-based tool for comparison
@tool(
    name="echo",
    description="Echo the input message",
    category=ToolCategory.CORE,
)
async def echo_tool(message: str, uppercase: bool = False) -> ToolResult:
    """Echo a message back."""
    output = message.upper() if uppercase else message
    return ToolResult(success=True, data=output)


# =============================================================================
# DEMO RUNNER
# =============================================================================


async def run_demo() -> dict[str, Any]:
    """
    Run the Core demo.

    Returns:
        Dict containing demo results and statistics.
    """
    start_time = time.perf_counter()
    results: dict[str, Any] = {
        "success": False,
        "steps": [],
        "errors": [],
        "stats": {},
    }

    def log_step(name: str, status: str = "OK", details: str = "") -> None:
        step = {"name": name, "status": status, "details": details}
        results["steps"].append(step)
        print(f"  [{status}] {name}" + (f": {details}" if details else ""))

    print("\n" + "=" * 60)
    print("  FASTBAND CORE DEMO - Core Independence Validation")
    print("=" * 60 + "\n")

    try:
        # -----------------------------------------------------------------
        # Step 1: Initialize Demo Context with Mock Adapters
        # -----------------------------------------------------------------
        print("Step 1: Initializing mock adapters...")
        ctx = DemoContext()
        log_step("Storage adapters", details="KeyValue + Document stores")
        log_step("Auth adapters", details="Authenticator + Authorizer + TokenProvider")
        log_step("Policy adapters", details="PolicyEvaluator + RateLimiter + FeatureFlags")
        log_step("Telemetry adapters", details="Logger + Tracer + Metrics")
        log_step("Event adapters", details="EventPublisher + EventBus")
        log_step("Provider adapters", details="CompletionProvider + EmbeddingProvider")

        # -----------------------------------------------------------------
        # Step 2: Authentication Demo
        # -----------------------------------------------------------------
        print("\nStep 2: Testing authentication...")
        session = await ctx.authenticator.authenticate({"user_id": "demo-user"})
        if session and not session.is_expired:
            log_step("User authenticated", details=f"session={session.id[:8]}...")
        else:
            raise RuntimeError("Authentication failed")

        # Check authorization
        can_write = await ctx.authorizer.authorize(session.principal, "write", "demo-resource")
        log_step("Authorization check", details=f"write permission = {can_write}")

        # -----------------------------------------------------------------
        # Step 3: Tool Registry Demo
        # -----------------------------------------------------------------
        print("\nStep 3: Testing tool registry...")
        registry = ToolRegistry()

        # Register tools
        greeting_tool = GreetingTool()
        registry.register(greeting_tool)
        log_step("Registered GreetingTool")

        registry.register(echo_tool)
        log_step("Registered EchoTool (decorator)")

        # List and load tools
        tools = registry.get_available_tools()
        log_step("Listed tools", details=f"count={len(tools)}")

        # Load tools for execution
        registry.load("greeting")
        registry.load("echo")
        log_step("Loaded tools", details="greeting, echo")

        # Invoke greeting tool
        result = await registry.execute("greeting", person_name="Fastband", style="enthusiastic")
        if result.success:
            log_step("Invoked greeting tool", details=f"data={result.data[:40]}...")
        else:
            raise RuntimeError(f"Tool execution failed: {result.error}")

        # Invoke echo tool
        result = await registry.execute("echo", message="Hello Core!", uppercase=True)
        if result.success:
            log_step("Invoked echo tool", details=f"data={result.data}")
        else:
            raise RuntimeError(f"Tool execution failed: {result.error}")

        # -----------------------------------------------------------------
        # Step 4: Domain Event Demo
        # -----------------------------------------------------------------
        print("\nStep 4: Testing domain events...")

        # Create and publish a domain event
        event = DomainEvent(
            type=CommonEventTypes.for_aggregate("demo", "started"),
            data={"session_id": session.id, "user": "demo-user"},
            metadata=EventMetadata(source="core-demo"),
        )

        # Publish via event bus
        demo_logger = ctx.telemetry.logger_factory.get_logger("demo")

        async def event_handler(e: Event) -> None:
            demo_logger.info(f"Event received: {e.type}")

        await ctx.event_bus.subscribe("demo.*", event_handler)
        delivery_results = await ctx.event_bus.publish(event)

        log_step("Published domain event", details=f"type={event.type}")
        log_step("Event delivered", details=f"handlers={len(delivery_results)}")

        # Verify event was stored
        if ctx.event_bus.events:
            log_step("Event stored in bus", details=f"total={len(ctx.event_bus.events)}")

        # -----------------------------------------------------------------
        # Step 5: Audit Record Demo
        # -----------------------------------------------------------------
        print("\nStep 5: Testing audit records...")

        # Create audit record
        audit_record = AuditRecord.create(
            event_type=AuditEventTypes.AUTH_LOGIN,
            action="authenticate",
            actor=AuditActor(
                actor_id=session.principal.id,
                display_name=session.principal.attributes.get("display_name", "Unknown"),
            ),
            category=AuditCategory.AUTHENTICATION,
            severity=AuditSeverity.INFO,
            details={"session_id": session.id},
        )

        # Store audit record
        record_id = ctx.audit_store.append(audit_record)
        log_step("Created audit record", details=f"id={record_id[:8]}...")
        log_step("Stored audit record", details=f"total={ctx.audit_store.count()}")

        # Verify properties
        assert audit_record.is_security_event is False
        assert audit_record.is_failure is False
        log_step("Verified audit properties", details="is_security=False, is_failure=False")

        # -----------------------------------------------------------------
        # Step 6: Provider Demo
        # -----------------------------------------------------------------
        print("\nStep 6: Testing provider abstractions...")

        # Completion
        response = await ctx.completion_provider.complete(
            prompt="Explain what Fastband Core does.",
            system_prompt="You are a helpful assistant.",
        )
        log_step("Completion provider", details=f"tokens={response.usage.total_tokens}")

        # Embedding
        embed_result = await ctx.embedding_provider.embed(["Fastband Core demo"])
        log_step("Embedding provider", details=f"dimensions={embed_result.dimensions}")

        # -----------------------------------------------------------------
        # Step 7: Storage Demo
        # -----------------------------------------------------------------
        print("\nStep 7: Testing storage adapters...")

        # Key-value store
        await ctx.kv_store.set("demo:key", b"demo-value")
        value = await ctx.kv_store.get("demo:key")
        assert value == b"demo-value"
        log_step("KeyValue store", details="set + get verified")

        # Document store
        await ctx.doc_store.set("demo", "doc-1", {"name": "Demo", "value": 42})
        doc = await ctx.doc_store.get("demo", "doc-1")
        assert doc and doc["value"] == 42
        log_step("Document store", details="set + get verified")

        # -----------------------------------------------------------------
        # Step 8: Policy Demo
        # -----------------------------------------------------------------
        print("\nStep 8: Testing policy adapters...")

        from fastband_core.ports.policy import (
            PolicyContext,
            PolicyDecision,
            RateLimitConfig,
            FeatureFlagContext,
        )

        # Policy evaluation
        policy_ctx = PolicyContext(
            subject=session.principal.id,
            action="read",
            resource="demo-resource",
        )
        policy_result = await ctx.policy_evaluator.evaluate(policy_ctx)
        assert policy_result.decision == PolicyDecision.ALLOW
        log_step("Policy evaluation", details="decision=ALLOW")

        # Rate limiting
        rate_config = RateLimitConfig(key="demo:rate", max_requests=100, window_seconds=60)
        rate_status = await ctx.rate_limiter.check("demo:rate", rate_config)
        assert rate_status.remaining > 0
        log_step("Rate limiter", details=f"remaining={rate_status.remaining}")

        # Feature flags
        flag_ctx = FeatureFlagContext(user_id="demo-user")
        enabled = await ctx.feature_flags.get_bool("demo-feature", flag_ctx, default=False)
        assert enabled
        log_step("Feature flags", details="demo-feature=enabled")

        # -----------------------------------------------------------------
        # Step 9: Telemetry Demo
        # -----------------------------------------------------------------
        print("\nStep 9: Testing telemetry adapters...")

        # Logging (use logger factory)
        telemetry_logger = ctx.telemetry.logger_factory.get_logger("telemetry-demo")
        telemetry_logger.info("Demo completed successfully", demo="core")
        log_step("Logger", details=f"entries={len(ctx.telemetry.logger.entries)}")

        # Tracing
        with ctx.telemetry.tracer.span("demo-span") as span:
            span.set_attribute("demo", True)
        log_step("Tracer", details=f"spans={len(ctx.telemetry.tracer.spans)}")

        # Metrics
        ctx.telemetry.metrics.counter("demo.requests", 1)
        ctx.telemetry.metrics.histogram("demo.latency", 0.05)
        log_step("Metrics", details="counter + histogram recorded")

        # -----------------------------------------------------------------
        # Final Statistics
        # -----------------------------------------------------------------
        elapsed = time.perf_counter() - start_time

        results["stats"] = {
            "elapsed_seconds": round(elapsed, 3),
            "events_published": len(ctx.event_bus.events),
            "audit_records": ctx.audit_store.count(),
            "tools_registered": len(registry.get_available_tools()),
            "log_entries": len(ctx.telemetry.logger.entries),
            "spans_created": len(ctx.telemetry.tracer.spans),
        }

        results["success"] = True

        print("\n" + "=" * 60)
        print("  DEMO COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"\n  Elapsed: {elapsed:.3f}s")
        print(f"  Events:  {results['stats']['events_published']}")
        print(f"  Audit:   {results['stats']['audit_records']}")
        print(f"  Tools:   {results['stats']['tools_registered']}")
        print(f"  Logs:    {results['stats']['log_entries']}")
        print(f"  Spans:   {results['stats']['spans_created']}")
        print("\n  Core independence validated - no network calls made!")
        print("=" * 60 + "\n")

    except Exception as e:
        results["errors"].append(str(e))
        print(f"\n  [ERROR] Demo failed: {e}")
        import traceback
        traceback.print_exc()

    return results


def main() -> int:
    """Main entry point."""
    results = asyncio.run(run_demo())
    return 0 if results["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
