"""
Web tools - Browser automation and HTTP request tools.

These tools provide web-related functionality including:
- Screenshot capture using Playwright
- HTTP requests (GET, POST, PUT, DELETE)
- DOM querying with CSS selectors
- Browser console log capture

Playwright is an optional dependency - tools will gracefully handle
its absence by returning helpful error messages.
"""

import asyncio
import base64
import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastband.tools.base import (
    Tool,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolCategory,
    ToolResult,
    ProjectType,
)

logger = logging.getLogger(__name__)

# Check if Playwright is available
try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    Browser = None
    Page = None
    BrowserContext = None


def _playwright_not_installed_error() -> ToolResult:
    """Return a helpful error when Playwright is not installed."""
    return ToolResult(
        success=False,
        error=(
            "Playwright is not installed. Install it with:\n"
            "  pip install playwright\n"
            "  playwright install chromium\n\n"
            "Or install fastband with web extras:\n"
            "  pip install fastband[web]"
        ),
    )


class BrowserManager:
    """
    Manages browser instances for Playwright tools.

    Supports both headful and headless modes, and handles
    browser lifecycle management.
    """

    _instance: Optional["BrowserManager"] = None
    _browser: Optional[Any] = None  # Browser type when Playwright available
    _context: Optional[Any] = None  # BrowserContext when Playwright available
    _playwright: Optional[Any] = None
    _headless: bool = True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_browser(self, headless: bool = True) -> Optional[Any]:
        """Get or create a browser instance."""
        if not PLAYWRIGHT_AVAILABLE:
            return None

        # If headless mode changed or browser not initialized, create new browser
        if self._browser is None or self._headless != headless:
            await self.close()
            self._headless = headless
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=headless)

        return self._browser

    async def get_context(self, headless: bool = True, viewport: Optional[Dict] = None) -> Optional[Any]:
        """Get a browser context with optional viewport settings."""
        browser = await self.get_browser(headless=headless)
        if browser is None:
            return None

        context_options = {}
        if viewport:
            context_options["viewport"] = viewport

        return await browser.new_context(**context_options)

    async def close(self):
        """Close browser and cleanup resources."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


# Global browser manager instance
_browser_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    """Get the global browser manager instance."""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager


class ScreenshotTool(Tool):
    """Capture webpage screenshots using Playwright."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="screenshot",
                description=(
                    "Capture a screenshot of a webpage. Returns base64-encoded PNG image. "
                    "Supports custom viewport sizes, full page capture, and element-specific screenshots."
                ),
                category=ToolCategory.WEB,
                version="1.0.0",
                project_types=[ProjectType.WEB_APP, ProjectType.API_SERVICE],
                tech_stack_hints=["web", "html", "css", "javascript", "react", "vue", "angular"],
                network_required=True,
            ),
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL of the webpage to capture",
                    required=True,
                ),
                ToolParameter(
                    name="width",
                    type="integer",
                    description="Viewport width in pixels (default: 1280)",
                    required=False,
                    default=1280,
                ),
                ToolParameter(
                    name="height",
                    type="integer",
                    description="Viewport height in pixels (default: 720)",
                    required=False,
                    default=720,
                ),
                ToolParameter(
                    name="full_page",
                    type="boolean",
                    description="Capture the full scrollable page (default: false)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS selector for element-specific screenshot (optional)",
                    required=False,
                ),
                ToolParameter(
                    name="wait_for",
                    type="string",
                    description="Wait condition: 'load', 'domcontentloaded', 'networkidle' (default: 'load')",
                    required=False,
                    default="load",
                    enum=["load", "domcontentloaded", "networkidle"],
                ),
                ToolParameter(
                    name="wait_timeout",
                    type="integer",
                    description="Maximum time to wait for page in milliseconds (default: 30000)",
                    required=False,
                    default=30000,
                ),
                ToolParameter(
                    name="headless",
                    type="boolean",
                    description="Run browser in headless mode (default: true)",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(
        self,
        url: str,
        width: int = 1280,
        height: int = 720,
        full_page: bool = False,
        selector: str = None,
        wait_for: str = "load",
        wait_timeout: int = 30000,
        headless: bool = True,
        **kwargs
    ) -> ToolResult:
        """Capture webpage screenshot."""
        if not PLAYWRIGHT_AVAILABLE:
            return _playwright_not_installed_error()

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"
        except Exception as e:
            return ToolResult(success=False, error=f"Invalid URL: {e}")

        context = None
        page = None

        try:
            manager = get_browser_manager()
            context = await manager.get_context(
                headless=headless,
                viewport={"width": width, "height": height}
            )

            if context is None:
                return _playwright_not_installed_error()

            page = await context.new_page()

            # Navigate to URL
            await page.goto(url, wait_until=wait_for, timeout=wait_timeout)

            # Take screenshot
            screenshot_options = {
                "full_page": full_page,
                "type": "png",
            }

            if selector:
                # Element-specific screenshot
                element = await page.query_selector(selector)
                if element is None:
                    return ToolResult(
                        success=False,
                        error=f"Element not found: {selector}",
                    )
                screenshot_bytes = await element.screenshot(**screenshot_options)
            else:
                screenshot_bytes = await page.screenshot(**screenshot_options)

            # Encode as base64
            screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "image_base64": screenshot_base64,
                    "format": "png",
                    "width": width,
                    "height": height,
                    "full_page": full_page,
                    "selector": selector,
                    "size_bytes": len(screenshot_bytes),
                },
                metadata={
                    "content_type": "image/png",
                },
            )

        except Exception as e:
            logger.exception(f"Screenshot failed for {url}")
            return ToolResult(success=False, error=str(e))
        finally:
            if page:
                await page.close()
            if context:
                await context.close()


class HttpRequestTool(Tool):
    """Make HTTP requests (GET, POST, PUT, DELETE)."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="http_request",
                description=(
                    "Make HTTP requests to APIs and web endpoints. "
                    "Supports GET, POST, PUT, DELETE, PATCH methods with headers and body."
                ),
                category=ToolCategory.WEB,
                version="1.0.0",
                project_types=[ProjectType.WEB_APP, ProjectType.API_SERVICE],
                tech_stack_hints=["api", "rest", "http", "web"],
                network_required=True,
            ),
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL to send the request to",
                    required=True,
                ),
                ToolParameter(
                    name="method",
                    type="string",
                    description="HTTP method (default: GET)",
                    required=False,
                    default="GET",
                    enum=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
                ),
                ToolParameter(
                    name="headers",
                    type="object",
                    description="Request headers as key-value pairs",
                    required=False,
                ),
                ToolParameter(
                    name="body",
                    type="string",
                    description="Request body (for POST, PUT, PATCH)",
                    required=False,
                ),
                ToolParameter(
                    name="json_body",
                    type="object",
                    description="JSON body (will be serialized and Content-Type set to application/json)",
                    required=False,
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Request timeout in seconds (default: 30)",
                    required=False,
                    default=30,
                ),
                ToolParameter(
                    name="follow_redirects",
                    type="boolean",
                    description="Follow HTTP redirects (default: true)",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: Dict[str, str] = None,
        body: str = None,
        json_body: Dict[str, Any] = None,
        timeout: int = 30,
        follow_redirects: bool = True,
        **kwargs
    ) -> ToolResult:
        """Make HTTP request."""
        import httpx

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"
        except Exception as e:
            return ToolResult(success=False, error=f"Invalid URL: {e}")

        # Prepare headers
        request_headers = headers or {}

        # Prepare body
        request_body = None
        if json_body is not None:
            request_body = json.dumps(json_body)
            request_headers.setdefault("Content-Type", "application/json")
        elif body is not None:
            request_body = body

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=follow_redirects,
                verify=False,  # Equivalent to ssl=False
            ) as client:
                response = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=request_headers,
                    content=request_body,
                )

                # Get response body
                response_text = response.text

                # Try to parse as JSON
                response_json = None
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    try:
                        response_json = response.json()
                    except json.JSONDecodeError:
                        pass

                return ToolResult(
                    success=True,
                    data={
                        "url": str(response.url),
                        "status": response.status_code,
                        "status_text": response.reason_phrase,
                        "headers": dict(response.headers),
                        "body": response_text,
                        "json": response_json,
                        "content_type": content_type,
                        "content_length": response.headers.get("Content-Length"),
                    },
                    metadata={
                        "method": method.upper(),
                        "redirected": str(response.url) != url,
                    },
                )

        except httpx.TimeoutException:
            return ToolResult(success=False, error=f"Request timed out after {timeout} seconds")
        except httpx.RequestError as e:
            return ToolResult(success=False, error=f"HTTP request failed: {e}")
        except Exception as e:
            logger.exception(f"HTTP request failed for {url}")
            return ToolResult(success=False, error=str(e))


class DomQueryTool(Tool):
    """Query DOM elements with CSS selectors."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="dom_query",
                description=(
                    "Query DOM elements on a webpage using CSS selectors. "
                    "Returns element text, attributes, and structure."
                ),
                category=ToolCategory.WEB,
                version="1.0.0",
                project_types=[ProjectType.WEB_APP],
                tech_stack_hints=["web", "html", "css", "scraping"],
                network_required=True,
            ),
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL of the webpage to query",
                    required=True,
                ),
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS selector to query elements",
                    required=True,
                ),
                ToolParameter(
                    name="attributes",
                    type="array",
                    description="List of attributes to extract (default: all)",
                    required=False,
                ),
                ToolParameter(
                    name="include_text",
                    type="boolean",
                    description="Include element text content (default: true)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="include_html",
                    type="boolean",
                    description="Include element inner HTML (default: false)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="max_elements",
                    type="integer",
                    description="Maximum number of elements to return (default: 100)",
                    required=False,
                    default=100,
                ),
                ToolParameter(
                    name="wait_for",
                    type="string",
                    description="Wait condition: 'load', 'domcontentloaded', 'networkidle' (default: 'load')",
                    required=False,
                    default="load",
                    enum=["load", "domcontentloaded", "networkidle"],
                ),
                ToolParameter(
                    name="wait_timeout",
                    type="integer",
                    description="Maximum time to wait for page in milliseconds (default: 30000)",
                    required=False,
                    default=30000,
                ),
                ToolParameter(
                    name="headless",
                    type="boolean",
                    description="Run browser in headless mode (default: true)",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(
        self,
        url: str,
        selector: str,
        attributes: List[str] = None,
        include_text: bool = True,
        include_html: bool = False,
        max_elements: int = 100,
        wait_for: str = "load",
        wait_timeout: int = 30000,
        headless: bool = True,
        **kwargs
    ) -> ToolResult:
        """Query DOM elements."""
        if not PLAYWRIGHT_AVAILABLE:
            return _playwright_not_installed_error()

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"
        except Exception as e:
            return ToolResult(success=False, error=f"Invalid URL: {e}")

        context = None
        page = None

        try:
            manager = get_browser_manager()
            context = await manager.get_context(headless=headless)

            if context is None:
                return _playwright_not_installed_error()

            page = await context.new_page()

            # Navigate to URL
            await page.goto(url, wait_until=wait_for, timeout=wait_timeout)

            # Query elements
            elements = await page.query_selector_all(selector)

            results = []
            for i, element in enumerate(elements[:max_elements]):
                element_data = {
                    "index": i,
                    "tag": await element.evaluate("el => el.tagName.toLowerCase()"),
                }

                # Get text content
                if include_text:
                    element_data["text"] = await element.text_content()
                    element_data["inner_text"] = await element.inner_text()

                # Get inner HTML
                if include_html:
                    element_data["inner_html"] = await element.inner_html()

                # Get attributes
                if attributes:
                    element_data["attributes"] = {}
                    for attr in attributes:
                        value = await element.get_attribute(attr)
                        if value is not None:
                            element_data["attributes"][attr] = value
                else:
                    # Get all attributes
                    element_data["attributes"] = await element.evaluate(
                        """el => {
                            const attrs = {};
                            for (const attr of el.attributes) {
                                attrs[attr.name] = attr.value;
                            }
                            return attrs;
                        }"""
                    )

                results.append(element_data)

            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "selector": selector,
                    "elements": results,
                    "total_found": len(elements),
                    "returned": len(results),
                    "truncated": len(elements) > max_elements,
                },
            )

        except Exception as e:
            logger.exception(f"DOM query failed for {url}")
            return ToolResult(success=False, error=str(e))
        finally:
            if page:
                await page.close()
            if context:
                await context.close()


class BrowserConsoleTool(Tool):
    """Capture browser console logs."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="browser_console",
                description=(
                    "Navigate to a webpage and capture browser console logs. "
                    "Useful for debugging JavaScript errors and monitoring network activity."
                ),
                category=ToolCategory.WEB,
                version="1.0.0",
                project_types=[ProjectType.WEB_APP],
                tech_stack_hints=["web", "javascript", "debugging"],
                network_required=True,
            ),
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL of the webpage to capture console from",
                    required=True,
                ),
                ToolParameter(
                    name="wait_time",
                    type="integer",
                    description="Time to wait for console messages in milliseconds (default: 5000)",
                    required=False,
                    default=5000,
                ),
                ToolParameter(
                    name="log_types",
                    type="array",
                    description="Types of logs to capture: 'log', 'error', 'warning', 'info' (default: all)",
                    required=False,
                ),
                ToolParameter(
                    name="include_network_errors",
                    type="boolean",
                    description="Include network request failures (default: true)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="execute_script",
                    type="string",
                    description="Optional JavaScript to execute before capturing logs",
                    required=False,
                ),
                ToolParameter(
                    name="wait_for",
                    type="string",
                    description="Wait condition: 'load', 'domcontentloaded', 'networkidle' (default: 'load')",
                    required=False,
                    default="load",
                    enum=["load", "domcontentloaded", "networkidle"],
                ),
                ToolParameter(
                    name="wait_timeout",
                    type="integer",
                    description="Maximum time to wait for page in milliseconds (default: 30000)",
                    required=False,
                    default=30000,
                ),
                ToolParameter(
                    name="headless",
                    type="boolean",
                    description="Run browser in headless mode (default: true)",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(
        self,
        url: str,
        wait_time: int = 5000,
        log_types: List[str] = None,
        include_network_errors: bool = True,
        execute_script: str = None,
        wait_for: str = "load",
        wait_timeout: int = 30000,
        headless: bool = True,
        **kwargs
    ) -> ToolResult:
        """Capture browser console logs."""
        if not PLAYWRIGHT_AVAILABLE:
            return _playwright_not_installed_error()

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"https://{url}"
        except Exception as e:
            return ToolResult(success=False, error=f"Invalid URL: {e}")

        # Default log types
        if log_types is None:
            log_types = ["log", "error", "warning", "info", "debug"]

        context = None
        page = None
        console_messages = []
        network_errors = []

        try:
            manager = get_browser_manager()
            context = await manager.get_context(headless=headless)

            if context is None:
                return _playwright_not_installed_error()

            page = await context.new_page()

            # Set up console message handler
            def handle_console(msg):
                msg_type = msg.type
                if msg_type in log_types:
                    console_messages.append({
                        "type": msg_type,
                        "text": msg.text,
                        "location": {
                            "url": msg.location.get("url", ""),
                            "line": msg.location.get("lineNumber", 0),
                            "column": msg.location.get("columnNumber", 0),
                        } if hasattr(msg, "location") and msg.location else None,
                    })

            page.on("console", handle_console)

            # Set up network error handler
            if include_network_errors:
                def handle_request_failed(request):
                    network_errors.append({
                        "url": request.url,
                        "method": request.method,
                        "failure": request.failure,
                        "resource_type": request.resource_type,
                    })

                page.on("requestfailed", handle_request_failed)

            # Navigate to URL
            await page.goto(url, wait_until=wait_for, timeout=wait_timeout)

            # Execute custom script if provided
            if execute_script:
                try:
                    await page.evaluate(execute_script)
                except Exception as e:
                    console_messages.append({
                        "type": "error",
                        "text": f"Script execution error: {e}",
                        "location": None,
                    })

            # Wait for additional messages
            await asyncio.sleep(wait_time / 1000)

            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "console_messages": console_messages,
                    "network_errors": network_errors if include_network_errors else [],
                    "total_messages": len(console_messages),
                    "total_network_errors": len(network_errors),
                    "message_counts": {
                        msg_type: len([m for m in console_messages if m["type"] == msg_type])
                        for msg_type in set(m["type"] for m in console_messages)
                    },
                },
            )

        except Exception as e:
            logger.exception(f"Browser console capture failed for {url}")
            return ToolResult(success=False, error=str(e))
        finally:
            if page:
                await page.close()
            if context:
                await context.close()


# All web tools
WEB_TOOLS = [
    ScreenshotTool,
    HttpRequestTool,
    DomQueryTool,
    BrowserConsoleTool,
]

__all__ = [
    "ScreenshotTool",
    "HttpRequestTool",
    "DomQueryTool",
    "BrowserConsoleTool",
    "WEB_TOOLS",
    "PLAYWRIGHT_AVAILABLE",
    "get_browser_manager",
    "BrowserManager",
]
