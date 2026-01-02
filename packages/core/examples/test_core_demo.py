#!/usr/bin/env python3
"""
Tests for the Core Demo.

Validates that the Core demo runs successfully and produces expected results.
"""

import asyncio
import pytest
import sys
from pathlib import Path

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestCoreDemoRuns:
    """Test that the Core demo runs successfully."""

    def test_demo_runs_and_succeeds(self):
        """Test that the demo runs without errors."""
        from core_demo import run_demo

        results = asyncio.run(run_demo())

        assert results["success"] is True
        assert len(results["errors"]) == 0

    def test_demo_produces_expected_stats(self):
        """Test that the demo produces expected statistics."""
        from core_demo import run_demo

        results = asyncio.run(run_demo())

        stats = results["stats"]
        assert stats["events_published"] >= 1
        assert stats["audit_records"] >= 1
        assert stats["tools_registered"] >= 2
        assert stats["log_entries"] >= 1
        assert stats["spans_created"] >= 1
        assert stats["elapsed_seconds"] < 3.0  # Should complete in <3s

    def test_demo_produces_expected_steps(self):
        """Test that all expected steps are completed."""
        from core_demo import run_demo

        results = asyncio.run(run_demo())

        step_names = [s["name"] for s in results["steps"]]
        assert "User authenticated" in step_names
        assert "Authorization check" in step_names
        assert "Registered GreetingTool" in step_names
        assert "Invoked greeting tool" in step_names
        assert "Published domain event" in step_names
        assert "Created audit record" in step_names
        assert "Completion provider" in step_names
        assert "KeyValue store" in step_names
        assert "Policy evaluation" in step_names
        assert "Logger" in step_names


class TestMockAdapters:
    """Test mock adapter implementations."""

    def test_mock_kv_store(self):
        """Test MockKeyValueStore basic operations."""
        from mocks import MockKeyValueStore

        store = MockKeyValueStore()

        async def test():
            await store.set("key1", b"value1")
            value = await store.get("key1")
            assert value == b"value1"

            exists = await store.exists("key1")
            assert exists is True

            deleted = await store.delete("key1")
            assert deleted is True

            value = await store.get("key1")
            assert value is None

        asyncio.run(test())

    def test_mock_document_store(self):
        """Test MockDocumentStore basic operations."""
        from mocks import MockDocumentStore

        store = MockDocumentStore()

        async def test():
            await store.set("users", "user1", {"name": "Test", "age": 30})
            doc = await store.get("users", "user1")
            assert doc is not None
            assert doc["name"] == "Test"
            assert doc["age"] == 30

            # Query
            await store.set("users", "user2", {"name": "Test2", "age": 25})
            results = await store.query("users")
            assert len(results) == 2

        asyncio.run(test())

    def test_mock_authenticator(self):
        """Test MockAuthenticator."""
        from mocks import MockAuthenticator

        auth = MockAuthenticator()

        async def test():
            session = await auth.authenticate({"user_id": "demo-user"})
            assert session is not None
            assert session.principal.id == "demo-user"
            assert not session.is_expired

            # Validate session
            validated = await auth.validate_session(session.id)
            assert validated is not None

            # Invalidate
            result = await auth.invalidate_session(session.id)
            assert result is True

        asyncio.run(test())

    def test_mock_policy_evaluator(self):
        """Test MockPolicyEvaluator."""
        from mocks import MockPolicyEvaluator
        from fastband_core.ports.policy import PolicyContext, PolicyDecision

        evaluator = MockPolicyEvaluator()

        async def test():
            ctx = PolicyContext(
                subject="test-user",
                action="read",
                resource="test-resource",
            )
            result = await evaluator.evaluate(ctx)
            assert result.decision == PolicyDecision.ALLOW

        asyncio.run(test())

    def test_mock_event_bus(self):
        """Test MockEventBus."""
        from mocks import MockEventBus
        from fastband_core.events import DomainEvent, EventMetadata

        bus = MockEventBus()
        received_events = []

        async def handler(event):
            received_events.append(event)

        async def test():
            await bus.subscribe("test.*", handler)

            event = DomainEvent(
                type="test.created",
                data={"key": "value"},
                metadata=EventMetadata(source="test"),
            )
            await bus.publish(event)

            assert len(received_events) == 1
            assert received_events[0].type == "test.created"

        asyncio.run(test())


class TestMockProviders:
    """Test mock provider implementations."""

    def test_mock_completion_provider(self):
        """Test MockCompletionProvider."""
        from mocks import MockCompletionProvider
        from fastband_core.providers import ProviderConfig

        provider = MockCompletionProvider(
            ProviderConfig(name="test", model="test-model")
        )

        async def test():
            response = await provider.complete(
                prompt="Hello",
                system_prompt="Be helpful",
            )
            assert response.content is not None
            assert response.provider == "mock"
            assert response.usage.total_tokens > 0

        asyncio.run(test())

    def test_mock_embedding_provider(self):
        """Test MockEmbeddingProvider."""
        from mocks import MockEmbeddingProvider
        from fastband_core.providers import EmbeddingConfig

        provider = MockEmbeddingProvider(EmbeddingConfig(model="test-embed"))

        async def test():
            result = await provider.embed(["Hello world"])
            assert result.embeddings is not None
            assert len(result.embeddings) == 1
            assert result.dimensions == 384

        asyncio.run(test())


class TestDemoContext:
    """Test DemoContext initialization."""

    def test_demo_context_creates_all_adapters(self):
        """Test that DemoContext initializes all adapters."""
        from mocks import DemoContext

        ctx = DemoContext()

        # Storage
        assert ctx.kv_store is not None
        assert ctx.doc_store is not None

        # Auth
        assert ctx.authenticator is not None
        assert ctx.authorizer is not None
        assert ctx.token_provider is not None

        # Policy
        assert ctx.policy_evaluator is not None
        assert ctx.rate_limiter is not None
        assert ctx.feature_flags is not None

        # Telemetry
        assert ctx.telemetry is not None
        assert ctx.telemetry.logger_factory is not None
        assert ctx.telemetry.tracer is not None
        assert ctx.telemetry.metrics is not None

        # Events
        assert ctx.event_publisher is not None
        assert ctx.event_bus is not None

        # Audit
        assert ctx.audit_store is not None

        # Providers
        assert ctx.completion_provider is not None
        assert ctx.embedding_provider is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
