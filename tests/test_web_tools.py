"""Tests for web tools - Browser automation and HTTP request tools."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastband.tools.base import (
    ToolCategory,
)

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_playwright():
    """Mock Playwright for testing without actual browser."""
    with patch("fastband.tools.web.PLAYWRIGHT_AVAILABLE", True):
        with patch("fastband.tools.web.async_playwright") as mock_pw:
            # Create mock browser hierarchy
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.screenshot = AsyncMock(return_value=b"fake_image_data")
            mock_page.query_selector = AsyncMock()
            mock_page.query_selector_all = AsyncMock(return_value=[])
            mock_page.evaluate = AsyncMock()
            mock_page.close = AsyncMock()
            mock_page.on = MagicMock()

            mock_context = AsyncMock()
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_context.close = AsyncMock()

            mock_browser = AsyncMock()
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_browser.close = AsyncMock()

            mock_chromium = AsyncMock()
            mock_chromium.launch = AsyncMock(return_value=mock_browser)

            mock_playwright_instance = AsyncMock()
            mock_playwright_instance.chromium = mock_chromium
            mock_playwright_instance.stop = AsyncMock()

            # Configure async_playwright() to return an async context manager
            mock_pw_cm = AsyncMock()
            mock_pw_cm.start = AsyncMock(return_value=mock_playwright_instance)
            mock_pw.return_value = mock_pw_cm

            yield {
                "playwright": mock_playwright_instance,
                "browser": mock_browser,
                "context": mock_context,
                "page": mock_page,
            }


@pytest.fixture
def mock_httpx():
    """Mock httpx for HTTP request testing."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {
            "Content-Type": "application/json",
            "Content-Length": "100",
        }
        mock_response.url = "https://example.com/api"
        mock_response.text = '{"message": "success"}'
        mock_response.json.return_value = {"message": "success"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_client_class.return_value = mock_client

        yield {
            "client": mock_client,
            "response": mock_response,
        }


@pytest.fixture
def reset_browser_manager():
    """Reset the browser manager singleton before each test."""
    import fastband.tools.web as web_module
    from fastband.tools.web import BrowserManager

    # Reset singleton
    BrowserManager._instance = None
    BrowserManager._browser = None
    BrowserManager._context = None
    BrowserManager._playwright = None
    web_module._browser_manager = None

    yield

    # Cleanup after test
    BrowserManager._instance = None
    BrowserManager._browser = None
    BrowserManager._context = None
    BrowserManager._playwright = None
    web_module._browser_manager = None


# =============================================================================
# SCREENSHOT TOOL TESTS
# =============================================================================


class TestScreenshotTool:
    """Tests for ScreenshotTool."""

    def test_definition(self):
        """Test tool definition is correct."""
        from fastband.tools.web import ScreenshotTool

        tool = ScreenshotTool()

        assert tool.name == "screenshot"
        assert tool.category == ToolCategory.WEB
        assert tool.definition.metadata.network_required is True

        # Check parameters
        params = {p.name: p for p in tool.definition.parameters}
        assert "url" in params
        assert params["url"].required is True
        assert "width" in params
        assert params["width"].default == 1280
        assert "height" in params
        assert params["height"].default == 720
        assert "full_page" in params
        assert "selector" in params
        assert "headless" in params

    def test_schema_generation(self):
        """Test MCP schema generation."""
        from fastband.tools.web import ScreenshotTool

        tool = ScreenshotTool()
        schema = tool.definition.to_mcp_schema()

        assert schema["name"] == "screenshot"
        assert "inputSchema" in schema
        assert "url" in schema["inputSchema"]["properties"]
        assert "url" in schema["inputSchema"]["required"]

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_playwright, reset_browser_manager):
        """Test successful screenshot capture."""
        from fastband.tools.web import ScreenshotTool

        tool = ScreenshotTool()
        result = await tool.execute(url="https://example.com")

        assert result.success is True
        assert "image_base64" in result.data
        assert result.data["format"] == "png"
        assert result.data["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_execute_with_viewport(self, mock_playwright, reset_browser_manager):
        """Test screenshot with custom viewport."""
        from fastband.tools.web import ScreenshotTool

        tool = ScreenshotTool()
        result = await tool.execute(
            url="https://example.com",
            width=1920,
            height=1080,
        )

        assert result.success is True
        assert result.data["width"] == 1920
        assert result.data["height"] == 1080

    @pytest.mark.asyncio
    async def test_execute_full_page(self, mock_playwright, reset_browser_manager):
        """Test full page screenshot."""
        from fastband.tools.web import ScreenshotTool

        tool = ScreenshotTool()
        result = await tool.execute(
            url="https://example.com",
            full_page=True,
        )

        assert result.success is True
        assert result.data["full_page"] is True

    @pytest.mark.asyncio
    async def test_execute_element_screenshot(self, mock_playwright, reset_browser_manager):
        """Test element-specific screenshot."""
        from fastband.tools.web import ScreenshotTool

        # Set up mock element
        mock_element = AsyncMock()
        mock_element.screenshot = AsyncMock(return_value=b"element_image")
        mock_playwright["page"].query_selector = AsyncMock(return_value=mock_element)

        tool = ScreenshotTool()
        result = await tool.execute(
            url="https://example.com",
            selector=".main-content",
        )

        assert result.success is True
        assert result.data["selector"] == ".main-content"

    @pytest.mark.asyncio
    async def test_execute_element_not_found(self, mock_playwright, reset_browser_manager):
        """Test screenshot with non-existent element."""
        from fastband.tools.web import ScreenshotTool

        mock_playwright["page"].query_selector = AsyncMock(return_value=None)

        tool = ScreenshotTool()
        result = await tool.execute(
            url="https://example.com",
            selector=".nonexistent",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_without_playwright(self):
        """Test graceful handling when Playwright not installed."""
        with patch("fastband.tools.web.PLAYWRIGHT_AVAILABLE", False):
            from fastband.tools.web import ScreenshotTool

            tool = ScreenshotTool()
            result = await tool.execute(url="https://example.com")

            assert result.success is False
            assert "playwright" in result.error.lower()
            assert "install" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_invalid_url(self, mock_playwright, reset_browser_manager):
        """Test handling of navigation errors."""
        from fastband.tools.web import ScreenshotTool

        mock_playwright["page"].goto = AsyncMock(side_effect=Exception("Navigation failed"))

        tool = ScreenshotTool()
        result = await tool.execute(url="https://invalid-url.example")

        assert result.success is False
        assert "navigation failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_url_normalization(self, mock_playwright, reset_browser_manager):
        """Test URL normalization (adding https://)."""
        from fastband.tools.web import ScreenshotTool

        tool = ScreenshotTool()
        result = await tool.execute(url="example.com")

        # Should have added https://
        assert result.success is True
        mock_playwright["page"].goto.assert_called()
        call_args = mock_playwright["page"].goto.call_args
        assert call_args[0][0] == "https://example.com"


# =============================================================================
# HTTP REQUEST TOOL TESTS
# =============================================================================


class TestHttpRequestTool:
    """Tests for HttpRequestTool."""

    def test_definition(self):
        """Test tool definition is correct."""
        from fastband.tools.web import HttpRequestTool

        tool = HttpRequestTool()

        assert tool.name == "http_request"
        assert tool.category == ToolCategory.WEB

        params = {p.name: p for p in tool.definition.parameters}
        assert "url" in params
        assert "method" in params
        assert params["method"].default == "GET"
        assert params["method"].enum == ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        assert "headers" in params
        assert "body" in params
        assert "json_body" in params
        assert "timeout" in params

    @pytest.mark.asyncio
    async def test_execute_get(self, mock_httpx):
        """Test GET request."""
        from fastband.tools.web import HttpRequestTool

        tool = HttpRequestTool()
        result = await tool.execute(url="https://example.com/api")

        assert result.success is True
        assert result.data["status"] == 200
        assert result.data["json"] == {"message": "success"}
        assert result.metadata["method"] == "GET"

    @pytest.mark.asyncio
    async def test_execute_post_with_json(self, mock_httpx):
        """Test POST request with JSON body."""
        from fastband.tools.web import HttpRequestTool

        tool = HttpRequestTool()
        result = await tool.execute(
            url="https://example.com/api",
            method="POST",
            json_body={"key": "value"},
        )

        assert result.success is True
        assert result.metadata["method"] == "POST"

        # Verify request was called with JSON body
        mock_httpx["client"].request.assert_called_once()
        call_kwargs = mock_httpx["client"].request.call_args[1]
        assert "application/json" in call_kwargs.get("headers", {}).get("Content-Type", "")

    @pytest.mark.asyncio
    async def test_execute_with_headers(self, mock_httpx):
        """Test request with custom headers."""
        from fastband.tools.web import HttpRequestTool

        tool = HttpRequestTool()
        result = await tool.execute(
            url="https://example.com/api",
            headers={"Authorization": "Bearer token123"},
        )

        assert result.success is True
        call_kwargs = mock_httpx["client"].request.call_args[1]
        assert "Authorization" in call_kwargs.get("headers", {})

    @pytest.mark.asyncio
    async def test_execute_timeout(self, mock_httpx):
        """Test request timeout handling."""
        import httpx

        mock_httpx["client"].request.side_effect = httpx.TimeoutException("Request timed out")

        from fastband.tools.web import HttpRequestTool

        tool = HttpRequestTool()
        result = await tool.execute(
            url="https://example.com/api",
            timeout=5,
        )

        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_network_error(self, mock_httpx):
        """Test network error handling."""
        import httpx

        mock_httpx["client"].request.side_effect = httpx.RequestError("Connection refused")

        from fastband.tools.web import HttpRequestTool

        tool = HttpRequestTool()
        result = await tool.execute(url="https://example.com/api")

        assert result.success is False
        assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_all_methods(self, mock_httpx):
        """Test all HTTP methods work."""
        from fastband.tools.web import HttpRequestTool

        tool = HttpRequestTool()

        for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
            result = await tool.execute(
                url="https://example.com/api",
                method=method,
            )

            assert result.success is True
            assert result.metadata["method"] == method

            # Reset mock for next iteration
            mock_httpx["client"].request.reset_mock()

    @pytest.mark.asyncio
    async def test_url_normalization(self, mock_httpx):
        """Test URL normalization."""
        from fastband.tools.web import HttpRequestTool

        tool = HttpRequestTool()
        result = await tool.execute(url="example.com/api")

        assert result.success is True
        call_kwargs = mock_httpx["client"].request.call_args[1]
        assert call_kwargs["url"] == "https://example.com/api"


# =============================================================================
# DOM QUERY TOOL TESTS
# =============================================================================


class TestDomQueryTool:
    """Tests for DomQueryTool."""

    def test_definition(self):
        """Test tool definition is correct."""
        from fastband.tools.web import DomQueryTool

        tool = DomQueryTool()

        assert tool.name == "dom_query"
        assert tool.category == ToolCategory.WEB

        params = {p.name: p for p in tool.definition.parameters}
        assert "url" in params
        assert "selector" in params
        assert params["selector"].required is True
        assert "include_text" in params
        assert "include_html" in params
        assert "max_elements" in params

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_playwright, reset_browser_manager):
        """Test successful DOM query."""
        from fastband.tools.web import DomQueryTool

        # Set up mock elements
        mock_element = AsyncMock()
        mock_element.evaluate = AsyncMock(
            side_effect=[
                "div",  # tag name
                {"class": "test-class", "id": "test-id"},  # attributes
            ]
        )
        mock_element.text_content = AsyncMock(return_value="Test content")
        mock_element.inner_text = AsyncMock(return_value="Test content")
        mock_element.get_attribute = AsyncMock(return_value="value")

        mock_playwright["page"].query_selector_all = AsyncMock(return_value=[mock_element])

        tool = DomQueryTool()
        result = await tool.execute(
            url="https://example.com",
            selector=".test-class",
        )

        assert result.success is True
        assert result.data["total_found"] == 1
        assert len(result.data["elements"]) == 1
        assert result.data["elements"][0]["tag"] == "div"

    @pytest.mark.asyncio
    async def test_execute_no_elements(self, mock_playwright, reset_browser_manager):
        """Test query with no matching elements."""
        from fastband.tools.web import DomQueryTool

        mock_playwright["page"].query_selector_all = AsyncMock(return_value=[])

        tool = DomQueryTool()
        result = await tool.execute(
            url="https://example.com",
            selector=".nonexistent",
        )

        assert result.success is True
        assert result.data["total_found"] == 0
        assert len(result.data["elements"]) == 0

    @pytest.mark.asyncio
    async def test_execute_with_attributes_filter(self, mock_playwright, reset_browser_manager):
        """Test query with specific attributes."""
        from fastband.tools.web import DomQueryTool

        mock_element = AsyncMock()
        mock_element.evaluate = AsyncMock(return_value="a")
        mock_element.text_content = AsyncMock(return_value="Link text")
        mock_element.inner_text = AsyncMock(return_value="Link text")
        mock_element.get_attribute = AsyncMock(
            side_effect=lambda attr: {
                "href": "https://example.com",
                "class": "link",
            }.get(attr)
        )

        mock_playwright["page"].query_selector_all = AsyncMock(return_value=[mock_element])

        tool = DomQueryTool()
        result = await tool.execute(
            url="https://example.com",
            selector="a",
            attributes=["href", "class"],
        )

        assert result.success is True
        assert "href" in result.data["elements"][0]["attributes"]
        assert "class" in result.data["elements"][0]["attributes"]

    @pytest.mark.asyncio
    async def test_execute_max_elements(self, mock_playwright, reset_browser_manager):
        """Test max_elements limit."""
        from fastband.tools.web import DomQueryTool

        # Create 10 mock elements
        mock_elements = []
        for i in range(10):
            elem = AsyncMock()
            elem.evaluate = AsyncMock(return_value="div")
            elem.text_content = AsyncMock(return_value=f"Content {i}")
            elem.inner_text = AsyncMock(return_value=f"Content {i}")
            mock_elements.append(elem)

        mock_playwright["page"].query_selector_all = AsyncMock(return_value=mock_elements)

        tool = DomQueryTool()
        result = await tool.execute(
            url="https://example.com",
            selector="div",
            max_elements=5,
        )

        assert result.success is True
        assert result.data["total_found"] == 10
        assert result.data["returned"] == 5
        assert result.data["truncated"] is True

    @pytest.mark.asyncio
    async def test_execute_without_playwright(self):
        """Test graceful handling when Playwright not installed."""
        with patch("fastband.tools.web.PLAYWRIGHT_AVAILABLE", False):
            from fastband.tools.web import DomQueryTool

            tool = DomQueryTool()
            result = await tool.execute(
                url="https://example.com",
                selector=".test",
            )

            assert result.success is False
            assert "playwright" in result.error.lower()


# =============================================================================
# BROWSER CONSOLE TOOL TESTS
# =============================================================================


class TestBrowserConsoleTool:
    """Tests for BrowserConsoleTool."""

    def test_definition(self):
        """Test tool definition is correct."""
        from fastband.tools.web import BrowserConsoleTool

        tool = BrowserConsoleTool()

        assert tool.name == "browser_console"
        assert tool.category == ToolCategory.WEB

        params = {p.name: p for p in tool.definition.parameters}
        assert "url" in params
        assert "wait_time" in params
        assert "log_types" in params
        assert "include_network_errors" in params
        assert "execute_script" in params

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_playwright, reset_browser_manager):
        """Test successful console capture."""
        from fastband.tools.web import BrowserConsoleTool

        tool = BrowserConsoleTool()

        # Simulate short wait time
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await tool.execute(
                url="https://example.com",
                wait_time=100,
            )

        assert result.success is True
        assert "console_messages" in result.data
        assert "network_errors" in result.data

    @pytest.mark.asyncio
    async def test_execute_with_script(self, mock_playwright, reset_browser_manager):
        """Test console capture with script execution."""
        from fastband.tools.web import BrowserConsoleTool

        tool = BrowserConsoleTool()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await tool.execute(
                url="https://example.com",
                execute_script="console.log('test');",
                wait_time=100,
            )

        assert result.success is True
        mock_playwright["page"].evaluate.assert_called_with("console.log('test');")

    @pytest.mark.asyncio
    async def test_execute_script_error(self, mock_playwright, reset_browser_manager):
        """Test handling of script execution errors."""
        from fastband.tools.web import BrowserConsoleTool

        mock_playwright["page"].evaluate = AsyncMock(side_effect=Exception("Script error"))

        tool = BrowserConsoleTool()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await tool.execute(
                url="https://example.com",
                execute_script="invalid_script();",
                wait_time=100,
            )

        # Should still succeed but include error in messages
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_without_playwright(self):
        """Test graceful handling when Playwright not installed."""
        with patch("fastband.tools.web.PLAYWRIGHT_AVAILABLE", False):
            from fastband.tools.web import BrowserConsoleTool

            tool = BrowserConsoleTool()
            result = await tool.execute(url="https://example.com")

            assert result.success is False
            assert "playwright" in result.error.lower()


# =============================================================================
# BROWSER MANAGER TESTS
# =============================================================================


class TestBrowserManager:
    """Tests for BrowserManager singleton."""

    def test_singleton_pattern(self, reset_browser_manager):
        """Test that BrowserManager is a singleton."""
        from fastband.tools.web import BrowserManager

        manager1 = BrowserManager()
        manager2 = BrowserManager()

        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_get_browser(self, mock_playwright, reset_browser_manager):
        """Test getting browser instance."""
        from fastband.tools.web import get_browser_manager

        manager = get_browser_manager()
        browser = await manager.get_browser(headless=True)

        assert browser is not None
        mock_playwright["playwright"].chromium.launch.assert_called_with(headless=True)

    @pytest.mark.asyncio
    async def test_headless_mode_switch(self, mock_playwright, reset_browser_manager):
        """Test switching between headless and headful modes."""
        from fastband.tools.web import get_browser_manager

        manager = get_browser_manager()

        # First call with headless=True
        await manager.get_browser(headless=True)

        # Second call with headless=False should create new browser
        await manager.get_browser(headless=False)

        # Should have been called twice with different headless values
        calls = mock_playwright["playwright"].chromium.launch.call_args_list
        assert len(calls) == 2
        assert calls[0][1]["headless"] is True
        assert calls[1][1]["headless"] is False

    @pytest.mark.asyncio
    async def test_close_cleanup(self, mock_playwright, reset_browser_manager):
        """Test browser cleanup on close."""
        from fastband.tools.web import get_browser_manager

        manager = get_browser_manager()
        await manager.get_browser(headless=True)
        await manager.close()

        mock_playwright["browser"].close.assert_called_once()
        mock_playwright["playwright"].stop.assert_called_once()


# =============================================================================
# WEB TOOLS COLLECTION TESTS
# =============================================================================

# =============================================================================
# VISION ANALYSIS TOOL TESTS
# =============================================================================


class TestVisionAnalysisTool:
    """Tests for VisionAnalysisTool - Claude Vision API integration."""

    def test_definition(self):
        """Test tool definition is correct."""
        from fastband.tools.base import ToolCategory
        from fastband.tools.web import VisionAnalysisTool

        tool = VisionAnalysisTool()

        assert tool.name == "analyze_screenshot_with_vision"
        assert tool.category == ToolCategory.AI
        assert tool.definition.metadata.network_required is True

        # Check parameters
        params = {p.name: p for p in tool.definition.parameters}
        assert "prompt" in params
        assert params["prompt"].required is True
        assert "url" in params
        assert params["url"].required is False
        assert "image_base64" in params
        assert params["image_base64"].required is False
        assert "analysis_type" in params
        assert params["analysis_type"].enum == [
            "general",
            "ui_review",
            "bug_detection",
            "accessibility",
            "verification",
        ]
        assert "selector" in params
        assert "width" in params
        assert "height" in params
        assert "full_page" in params
        assert "max_tokens" in params

    def test_schema_generation(self):
        """Test MCP schema generation."""
        from fastband.tools.web import VisionAnalysisTool

        tool = VisionAnalysisTool()
        schema = tool.definition.to_mcp_schema()

        assert schema["name"] == "analyze_screenshot_with_vision"
        assert "inputSchema" in schema
        assert "prompt" in schema["inputSchema"]["properties"]
        assert "prompt" in schema["inputSchema"]["required"]

    def test_build_system_prompt_general(self):
        """Test system prompt generation for general analysis."""
        from fastband.tools.web import VisionAnalysisTool

        tool = VisionAnalysisTool()
        prompt = tool._build_system_prompt("general")

        assert "visual UI/UX analysis expert" in prompt
        assert "Overall visual appearance" in prompt

    def test_build_system_prompt_ui_review(self):
        """Test system prompt generation for UI review."""
        from fastband.tools.web import VisionAnalysisTool

        tool = VisionAnalysisTool()
        prompt = tool._build_system_prompt("ui_review")

        assert "Visual hierarchy" in prompt
        assert "Color scheme" in prompt
        assert "Typography" in prompt

    def test_build_system_prompt_bug_detection(self):
        """Test system prompt generation for bug detection."""
        from fastband.tools.web import VisionAnalysisTool

        tool = VisionAnalysisTool()
        prompt = tool._build_system_prompt("bug_detection")

        assert "Layout breaks" in prompt
        assert "Missing or broken images" in prompt
        assert "severity" in prompt.lower()

    def test_build_system_prompt_accessibility(self):
        """Test system prompt generation for accessibility."""
        from fastband.tools.web import VisionAnalysisTool

        tool = VisionAnalysisTool()
        prompt = tool._build_system_prompt("accessibility")

        assert "Color contrast" in prompt
        assert "WCAG" in prompt
        assert "touch targets" in prompt.lower()

    def test_build_system_prompt_verification(self):
        """Test system prompt generation for verification."""
        from fastband.tools.web import VisionAnalysisTool

        tool = VisionAnalysisTool()
        prompt = tool._build_system_prompt("verification")

        assert "Verify the UI" in prompt
        assert "presence/absence" in prompt

    @pytest.mark.asyncio
    async def test_execute_requires_url_or_image(self):
        """Test that either url or image_base64 must be provided."""
        from fastband.tools.web import VisionAnalysisTool

        tool = VisionAnalysisTool()
        result = await tool.execute(prompt="Check the UI")

        assert result.success is False
        assert "Either 'url' or 'image_base64' must be provided" in result.error

    @pytest.mark.asyncio
    async def test_execute_rejects_both_url_and_image(self):
        """Test that providing both url and image_base64 is rejected."""
        from fastband.tools.web import VisionAnalysisTool

        tool = VisionAnalysisTool()
        result = await tool.execute(
            prompt="Check the UI",
            url="https://example.com",
            image_base64="aGVsbG8=",  # base64 for "hello"
        )

        assert result.success is False
        assert "not both" in result.error

    @pytest.mark.asyncio
    async def test_execute_invalid_base64(self):
        """Test handling of invalid base64 image."""
        from fastband.tools.web import VisionAnalysisTool

        tool = VisionAnalysisTool()
        result = await tool.execute(
            prompt="Check the UI",
            image_base64="not-valid-base64!!!",
        )

        assert result.success is False
        assert "Invalid base64" in result.error

    @pytest.mark.asyncio
    async def test_execute_with_base64_image(self, mock_playwright, reset_browser_manager):
        """Test analysis with base64 image input."""
        from fastband.providers.base import Capability, CompletionResponse
        from fastband.tools.web import VisionAnalysisTool

        # Mock the provider registry
        mock_provider = AsyncMock()
        mock_provider.capabilities = [Capability.VISION]
        mock_provider.analyze_image = AsyncMock(
            return_value=CompletionResponse(
                content="The UI looks clean with a centered login form.",
                model="claude-sonnet-4-20250514",
                provider="claude",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="end_turn",
            )
        )

        with patch("fastband.providers.registry.ProviderRegistry.get", return_value=mock_provider):
            tool = VisionAnalysisTool()
            # Valid base64 for a tiny PNG
            valid_base64 = base64.b64encode(b"fake_image_data").decode()

            result = await tool.execute(
                prompt="Check if the login form is visible",
                image_base64=valid_base64,
                analysis_type="verification",
            )

            assert result.success is True
            assert "analysis" in result.data
            assert result.data["analysis_type"] == "verification"
            assert result.data["source"] == "base64"
            assert result.metadata["provider"] == "claude"

    @pytest.mark.asyncio
    async def test_execute_with_url(self, mock_playwright, reset_browser_manager):
        """Test analysis with URL input (captures screenshot)."""
        from fastband.providers.base import Capability, CompletionResponse
        from fastband.tools.web import VisionAnalysisTool

        # Mock the provider
        mock_provider = AsyncMock()
        mock_provider.capabilities = [Capability.VISION]
        mock_provider.analyze_image = AsyncMock(
            return_value=CompletionResponse(
                content="The page shows a navigation bar and hero section.",
                model="claude-sonnet-4-20250514",
                provider="claude",
                usage={"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300},
                finish_reason="end_turn",
            )
        )

        with patch("fastband.providers.registry.ProviderRegistry.get", return_value=mock_provider):
            tool = VisionAnalysisTool()
            result = await tool.execute(
                prompt="Describe the page layout",
                url="https://example.com",
                analysis_type="ui_review",
            )

            assert result.success is True
            assert "analysis" in result.data
            assert result.data["source"] == "url"
            assert result.data["url"] == "https://example.com"
            assert "viewport" in result.data

    @pytest.mark.asyncio
    async def test_execute_with_selector(self, mock_playwright, reset_browser_manager):
        """Test analysis with element-specific screenshot."""
        from fastband.providers.base import Capability, CompletionResponse
        from fastband.tools.web import VisionAnalysisTool

        # Set up mock element
        mock_element = AsyncMock()
        mock_element.screenshot = AsyncMock(return_value=b"element_image")
        mock_playwright["page"].query_selector = AsyncMock(return_value=mock_element)

        mock_provider = AsyncMock()
        mock_provider.capabilities = [Capability.VISION]
        mock_provider.analyze_image = AsyncMock(
            return_value=CompletionResponse(
                content="The button has correct styling.",
                model="claude-sonnet-4-20250514",
                provider="claude",
                usage={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
                finish_reason="end_turn",
            )
        )

        with patch("fastband.providers.registry.ProviderRegistry.get", return_value=mock_provider):
            tool = VisionAnalysisTool()
            result = await tool.execute(
                prompt="Check button styling",
                url="https://example.com",
                selector=".submit-button",
            )

            assert result.success is True
            assert result.data["selector"] == ".submit-button"

    @pytest.mark.asyncio
    async def test_execute_element_not_found(self, mock_playwright, reset_browser_manager):
        """Test handling when selector element is not found."""
        from fastband.tools.web import VisionAnalysisTool

        mock_playwright["page"].query_selector = AsyncMock(return_value=None)

        tool = VisionAnalysisTool()
        result = await tool.execute(
            prompt="Check the element",
            url="https://example.com",
            selector=".nonexistent",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_without_playwright(self):
        """Test handling when Playwright is not installed (URL mode)."""
        with patch("fastband.tools.web.PLAYWRIGHT_AVAILABLE", False):
            from fastband.tools.web import VisionAnalysisTool

            tool = VisionAnalysisTool()
            result = await tool.execute(
                prompt="Check the UI",
                url="https://example.com",
            )

            assert result.success is False
            assert "playwright" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_provider_not_available(self, mock_playwright, reset_browser_manager):
        """Test handling when Claude provider is not available."""
        from fastband.tools.web import VisionAnalysisTool

        with patch(
            "fastband.providers.registry.ProviderRegistry.get",
            side_effect=Exception("ANTHROPIC_API_KEY not set"),
        ):
            tool = VisionAnalysisTool()
            valid_base64 = base64.b64encode(b"fake_image").decode()

            result = await tool.execute(
                prompt="Check the UI",
                image_base64=valid_base64,
            )

            assert result.success is False
            assert "Failed to initialize AI provider" in result.error

    @pytest.mark.asyncio
    async def test_execute_vision_api_error(self, mock_playwright, reset_browser_manager):
        """Test handling of Vision API errors."""
        from fastband.providers.base import Capability
        from fastband.tools.web import VisionAnalysisTool

        mock_provider = AsyncMock()
        mock_provider.capabilities = [Capability.VISION]
        mock_provider.analyze_image = AsyncMock(side_effect=Exception("API rate limit exceeded"))

        with patch("fastband.providers.registry.ProviderRegistry.get", return_value=mock_provider):
            tool = VisionAnalysisTool()
            valid_base64 = base64.b64encode(b"fake_image").decode()

            result = await tool.execute(
                prompt="Check the UI",
                image_base64=valid_base64,
            )

            assert result.success is False
            assert "Vision analysis failed" in result.error

    @pytest.mark.asyncio
    async def test_execute_url_normalization(self, mock_playwright, reset_browser_manager):
        """Test URL normalization (adding https://)."""
        from fastband.providers.base import Capability, CompletionResponse
        from fastband.tools.web import VisionAnalysisTool

        mock_provider = AsyncMock()
        mock_provider.capabilities = [Capability.VISION]
        mock_provider.analyze_image = AsyncMock(
            return_value=CompletionResponse(
                content="Analysis complete.",
                model="claude-sonnet-4-20250514",
                provider="claude",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="end_turn",
            )
        )

        with patch("fastband.providers.registry.ProviderRegistry.get", return_value=mock_provider):
            tool = VisionAnalysisTool()
            result = await tool.execute(
                prompt="Check the UI",
                url="example.com",  # No scheme
            )

            # Should have added https:// and succeeded
            assert result.success is True
            mock_playwright["page"].goto.assert_called()
            call_args = mock_playwright["page"].goto.call_args
            assert call_args[0][0] == "https://example.com"

    @pytest.mark.asyncio
    async def test_execute_records_execution_time(self, mock_playwright, reset_browser_manager):
        """Test that execution time is recorded."""
        from fastband.providers.base import Capability, CompletionResponse
        from fastband.tools.web import VisionAnalysisTool

        mock_provider = AsyncMock()
        mock_provider.capabilities = [Capability.VISION]
        mock_provider.analyze_image = AsyncMock(
            return_value=CompletionResponse(
                content="Analysis complete.",
                model="claude-sonnet-4-20250514",
                provider="claude",
                usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                finish_reason="end_turn",
            )
        )

        with patch("fastband.providers.registry.ProviderRegistry.get", return_value=mock_provider):
            tool = VisionAnalysisTool()
            valid_base64 = base64.b64encode(b"fake_image").decode()

            result = await tool.execute(
                prompt="Check the UI",
                image_base64=valid_base64,
            )

            assert result.success is True
            assert result.execution_time_ms > 0


class TestWebToolsCollection:
    """Tests for WEB_TOOLS collection."""

    def test_all_tools_exported(self):
        """Test that all web tools are properly exported."""
        from fastband.tools.web import (
            WEB_TOOLS,
            BrowserConsoleTool,
            DomQueryTool,
            HttpRequestTool,
            ScreenshotTool,
            VisionAnalysisTool,
        )

        assert len(WEB_TOOLS) == 5
        assert ScreenshotTool in WEB_TOOLS
        assert HttpRequestTool in WEB_TOOLS
        assert DomQueryTool in WEB_TOOLS
        assert BrowserConsoleTool in WEB_TOOLS
        assert VisionAnalysisTool in WEB_TOOLS

    def test_all_tools_have_valid_category(self):
        """Test that all web tools have valid categories (WEB or AI)."""
        from fastband.tools.web import WEB_TOOLS

        valid_categories = [ToolCategory.WEB, ToolCategory.AI]
        for tool_class in WEB_TOOLS:
            tool = tool_class()
            assert tool.category in valid_categories, (
                f"{tool.name} has unexpected category {tool.category}"
            )

    def test_playwright_available_exported(self):
        """Test that PLAYWRIGHT_AVAILABLE flag is exported."""
        from fastband.tools.web import PLAYWRIGHT_AVAILABLE

        assert isinstance(PLAYWRIGHT_AVAILABLE, bool)


# =============================================================================
# INTEGRATION TESTS (marked for optional running)
# =============================================================================


@pytest.mark.integration
class TestWebToolsIntegration:
    """
    Integration tests that require actual Playwright installation.

    Run with: pytest -m integration tests/test_web_tools.py
    """

    @pytest.mark.asyncio
    async def test_real_screenshot(self):
        """Test real screenshot capture (requires Playwright)."""
        from fastband.tools.web import PLAYWRIGHT_AVAILABLE, ScreenshotTool

        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        tool = ScreenshotTool()
        result = await tool.execute(
            url="https://example.com",
            width=800,
            height=600,
        )

        assert result.success is True
        assert "image_base64" in result.data

        # Verify it's valid base64 PNG
        image_data = base64.b64decode(result.data["image_base64"])
        assert image_data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes

    @pytest.mark.asyncio
    async def test_real_http_request(self):
        """Test real HTTP request (requires network)."""
        from fastband.tools.web import HttpRequestTool

        tool = HttpRequestTool()
        result = await tool.execute(url="https://httpbin.org/get")

        assert result.success is True
        assert result.data["status"] == 200

    @pytest.mark.asyncio
    async def test_real_dom_query(self):
        """Test real DOM query (requires Playwright)."""
        from fastband.tools.web import PLAYWRIGHT_AVAILABLE, DomQueryTool

        if not PLAYWRIGHT_AVAILABLE:
            pytest.skip("Playwright not installed")

        tool = DomQueryTool()
        result = await tool.execute(
            url="https://example.com",
            selector="h1",
        )

        assert result.success is True
        assert result.data["total_found"] >= 1
