"""
Tests for auto-port selection feature.

Tests the Hub server's ability to automatically find
available ports when the preferred port is busy.
"""

import socket
from unittest.mock import patch

import pytest

from fastband.hub.server import (
    DEFAULT_PORT,
    MAX_PORT,
    find_available_port,
    is_port_available,
)


class TestIsPortAvailable:
    """Tests for is_port_available function."""

    def test_available_port(self):
        """Test that an unused port is detected as available."""
        # Use a high port that's unlikely to be in use
        result = is_port_available("127.0.0.1", 59999)
        assert result is True

    def test_busy_port(self):
        """Test that a port in use is detected as busy."""
        # Bind to a port to make it busy
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 59998))
            s.listen(1)

            # Now check if the port is available (it shouldn't be)
            result = is_port_available("127.0.0.1", 59998)
            assert result is False

    def test_port_zero_zero_zero_zero_host(self):
        """Test port availability check with 0.0.0.0 host."""
        # 0.0.0.0 should be converted to 127.0.0.1 for checking
        result = is_port_available("0.0.0.0", 59997)
        assert result is True


class TestFindAvailablePort:
    """Tests for find_available_port function."""

    def test_finds_preferred_port_when_available(self):
        """Test that preferred port is returned when available."""
        # Use a port within the valid range (8080-8099)
        # Port 8095 is unlikely to be in use during tests
        port = find_available_port("127.0.0.1", 8095)
        assert port == 8095

    def test_finds_next_port_when_preferred_busy(self):
        """Test that next port is found when preferred is busy."""
        # Bind to a port to make it busy (use high port in range)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 8096))
            s.listen(1)

            # Should find the next available port (8097)
            port = find_available_port("127.0.0.1", 8096)
            assert port == 8097

    def test_finds_port_skipping_multiple_busy(self):
        """Test finding port when multiple ports are busy."""
        sockets = []
        try:
            # Bind to 3 consecutive ports at end of range
            for p in range(8094, 8097):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", p))
                s.listen(1)
                sockets.append(s)

            # Should find port 8097
            port = find_available_port("127.0.0.1", 8094)
            assert port == 8097
        finally:
            for s in sockets:
                s.close()

    def test_returns_none_when_all_ports_busy(self):
        """Test that None is returned when no ports available."""
        # Mock is_port_available to always return False
        with patch("fastband.hub.server.is_port_available", return_value=False):
            port = find_available_port("127.0.0.1", DEFAULT_PORT)
            assert port is None

    def test_respects_max_port_limit(self):
        """Test that search stops at MAX_PORT."""
        # Start from MAX_PORT, should only check that one port
        port = find_available_port("127.0.0.1", MAX_PORT)
        assert port == MAX_PORT

    def test_returns_none_when_starting_above_max(self):
        """Test returns None when starting above MAX_PORT."""
        port = find_available_port("127.0.0.1", MAX_PORT + 1)
        assert port is None


class TestDefaultPortConstants:
    """Tests for port constant definitions."""

    def test_default_port_value(self):
        """Test DEFAULT_PORT is 8080."""
        assert DEFAULT_PORT == 8080

    def test_max_port_value(self):
        """Test MAX_PORT allows reasonable range."""
        assert MAX_PORT > DEFAULT_PORT
        assert MAX_PORT == 8099  # 20 ports should be enough


class TestAutoPortIntegration:
    """Integration tests for auto-port in run_server."""

    @pytest.mark.asyncio
    async def test_run_server_uses_auto_port(self):
        """Test that run_server can find available port."""
        # This is more of a smoke test - we just verify imports work
        # Verify the function signature includes auto_port
        import inspect

        from fastband.hub.server import run_server

        sig = inspect.signature(run_server)
        params = sig.parameters

        assert "auto_port" in params
        assert params["auto_port"].default is True

    def test_cli_imports_port_functions(self):
        """Test that CLI can import port functions."""
        # Verify the imports work
        from fastband.hub.server import find_available_port, is_port_available

        assert callable(find_available_port)
        assert callable(is_port_available)
