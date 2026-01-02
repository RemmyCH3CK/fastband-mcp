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
    ProjectType,
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)

logger = logging.getLogger(__name__)

# Check if Playwright is available
try:
    from playwright.async_api import Browser, BrowserContext, Page, async_playwright

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
    _browser: Any | None = None  # Browser type when Playwright available
    _context: Any | None = None  # BrowserContext when Playwright available
    _playwright: Any | None = None
    _headless: bool = True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_browser(self, headless: bool = True) -> Any | None:
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

    async def get_context(self, headless: bool = True, viewport: dict | None = None) -> Any | None:
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
_browser_manager: BrowserManager | None = None


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
        **kwargs,
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
                headless=headless, viewport={"width": width, "height": height}
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
                ToolParameter(
                    name="verify_ssl",
                    type="boolean",
                    description="Verify SSL certificates (default: true). Set to false only for local development with self-signed certs.",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] = None,
        body: str = None,
        json_body: dict[str, Any] = None,
        timeout: int = 30,
        follow_redirects: bool = True,
        verify_ssl: bool = True,
        **kwargs,
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
                verify=verify_ssl,
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
        attributes: list[str] = None,
        include_text: bool = True,
        include_html: bool = False,
        max_elements: int = 100,
        wait_for: str = "load",
        wait_timeout: int = 30000,
        headless: bool = True,
        **kwargs,
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


class VisionAnalysisTool(Tool):
    """
    Analyze screenshots using Claude Vision API.

    This tool enables AI-powered visual analysis of web pages, supporting:
    - UI/UX review and verification
    - Visual bug detection
    - Accessibility assessment
    - Layout and styling validation
    - Content verification

    Can accept either a URL (captures screenshot first) or existing base64 image.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="analyze_screenshot_with_vision",
                description=(
                    "Analyze a screenshot or webpage using Claude Vision API. "
                    "Supports UI verification, bug detection, accessibility review, "
                    "and visual comparison. Can capture screenshot from URL or analyze "
                    "existing base64-encoded image."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
                project_types=[ProjectType.WEB_APP, ProjectType.MOBILE_CROSS],
                tech_stack_hints=["web", "ui", "testing", "qa", "visual"],
                network_required=True,
            ),
            parameters=[
                ToolParameter(
                    name="prompt",
                    type="string",
                    description=(
                        "Analysis prompt describing what to look for. Examples:\n"
                        "- 'Check if the login form is visible and properly styled'\n"
                        "- 'Verify the error message is displayed in red'\n"
                        "- 'Assess the accessibility of this page'\n"
                        "- 'Compare this UI to the expected design'"
                    ),
                    required=True,
                ),
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL to capture and analyze (mutually exclusive with image_base64)",
                    required=False,
                ),
                ToolParameter(
                    name="image_base64",
                    type="string",
                    description="Base64-encoded image to analyze (mutually exclusive with url)",
                    required=False,
                ),
                ToolParameter(
                    name="analysis_type",
                    type="string",
                    description=(
                        "Type of analysis to perform:\n"
                        "- 'general': General UI analysis (default)\n"
                        "- 'ui_review': Detailed UI/UX review\n"
                        "- 'bug_detection': Look for visual bugs\n"
                        "- 'accessibility': Accessibility assessment\n"
                        "- 'verification': Verify specific UI elements"
                    ),
                    required=False,
                    default="general",
                    enum=["general", "ui_review", "bug_detection", "accessibility", "verification"],
                ),
                ToolParameter(
                    name="selector",
                    type="string",
                    description="CSS selector for element-specific screenshot (only with url)",
                    required=False,
                ),
                ToolParameter(
                    name="width",
                    type="integer",
                    description="Viewport width in pixels when capturing from URL (default: 1280)",
                    required=False,
                    default=1280,
                ),
                ToolParameter(
                    name="height",
                    type="integer",
                    description="Viewport height in pixels when capturing from URL (default: 720)",
                    required=False,
                    default=720,
                ),
                ToolParameter(
                    name="full_page",
                    type="boolean",
                    description="Capture full scrollable page when using URL (default: false)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="wait_for",
                    type="string",
                    description="Wait condition when capturing: 'load', 'domcontentloaded', 'networkidle'",
                    required=False,
                    default="networkidle",
                    enum=["load", "domcontentloaded", "networkidle"],
                ),
                ToolParameter(
                    name="max_tokens",
                    type="integer",
                    description="Maximum tokens for analysis response (default: 2048)",
                    required=False,
                    default=2048,
                ),
            ],
        )

    def _build_system_prompt(self, analysis_type: str) -> str:
        """Build system prompt based on analysis type."""
        base_prompt = (
            "You are a visual UI/UX analysis expert. Analyze the provided screenshot "
            "and provide detailed, actionable feedback."
        )

        type_prompts = {
            "general": (
                f"{base_prompt}\n\n"
                "Provide a comprehensive analysis covering:\n"
                "1. Overall visual appearance and layout\n"
                "2. Key UI elements visible\n"
                "3. Any obvious issues or concerns\n"
                "4. Suggestions for improvement"
            ),
            "ui_review": (
                f"{base_prompt}\n\n"
                "Perform a detailed UI/UX review covering:\n"
                "1. Visual hierarchy and layout structure\n"
                "2. Color scheme and contrast\n"
                "3. Typography and readability\n"
                "4. Spacing and alignment\n"
                "5. Interactive element visibility\n"
                "6. Consistency with modern design patterns\n"
                "7. Mobile responsiveness indicators\n"
                "8. Specific recommendations for improvement"
            ),
            "bug_detection": (
                f"{base_prompt}\n\n"
                "Focus on detecting visual bugs and issues:\n"
                "1. Layout breaks or overflow issues\n"
                "2. Missing or broken images\n"
                "3. Text truncation or overflow\n"
                "4. Z-index/layering problems\n"
                "5. Misaligned elements\n"
                "6. Inconsistent styling\n"
                "7. Loading state issues\n"
                "8. Error messages or warnings visible\n"
                "Report each issue with its location and severity."
            ),
            "accessibility": (
                f"{base_prompt}\n\n"
                "Assess accessibility from a visual perspective:\n"
                "1. Color contrast ratios (estimate)\n"
                "2. Text size and readability\n"
                "3. Interactive element sizing (touch targets)\n"
                "4. Visual focus indicators\n"
                "5. Icon clarity and labeling\n"
                "6. Error state visibility\n"
                "7. Visual hierarchy for screen readers\n"
                "8. Potential WCAG compliance issues\n"
                "Note: This is visual-only assessment, not full accessibility audit."
            ),
            "verification": (
                f"{base_prompt}\n\n"
                "Verify the UI against the user's requirements:\n"
                "1. Confirm presence/absence of requested elements\n"
                "2. Verify text content matches expectations\n"
                "3. Check styling matches specifications\n"
                "4. Validate layout and positioning\n"
                "5. Confirm interactive states\n"
                "Be specific about what matches and what doesn't."
            ),
        }

        return type_prompts.get(analysis_type, type_prompts["general"])

    async def _capture_screenshot(
        self,
        url: str,
        width: int,
        height: int,
        full_page: bool,
        selector: str | None,
        wait_for: str,
    ) -> tuple[bytes | None, str | None]:
        """Capture screenshot from URL. Returns (image_bytes, error)."""
        if not PLAYWRIGHT_AVAILABLE:
            return None, (
                "Playwright is not installed. Install it with:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )

        context = None
        page = None

        try:
            manager = get_browser_manager()
            context = await manager.get_context(
                headless=True, viewport={"width": width, "height": height}
            )

            if context is None:
                return None, "Failed to create browser context"

            page = await context.new_page()
            await page.goto(url, wait_until=wait_for, timeout=30000)

            screenshot_options = {"full_page": full_page, "type": "png"}

            if selector:
                element = await page.query_selector(selector)
                if element is None:
                    return None, f"Element not found: {selector}"
                screenshot_bytes = await element.screenshot(**screenshot_options)
            else:
                screenshot_bytes = await page.screenshot(**screenshot_options)

            return screenshot_bytes, None

        except Exception as e:
            logger.exception(f"Screenshot capture failed for {url}")
            return None, str(e)
        finally:
            if page:
                await page.close()
            if context:
                await context.close()

    async def execute(
        self,
        prompt: str,
        url: str = None,
        image_base64: str = None,
        analysis_type: str = "general",
        selector: str = None,
        width: int = 1280,
        height: int = 720,
        full_page: bool = False,
        wait_for: str = "networkidle",
        max_tokens: int = 2048,
        **kwargs,
    ) -> ToolResult:
        """Analyze screenshot with Claude Vision API."""
        import time

        start_time = time.perf_counter()

        # Validate inputs - need either url or image_base64
        if not url and not image_base64:
            return ToolResult(
                success=False,
                error="Either 'url' or 'image_base64' must be provided",
            )

        if url and image_base64:
            return ToolResult(
                success=False,
                error="Provide either 'url' or 'image_base64', not both",
            )

        # Get image bytes
        image_bytes: bytes | None = None
        source_info = {}

        if url:
            # Validate and normalize URL
            try:
                parsed = urlparse(url)
                if not parsed.scheme:
                    url = f"https://{url}"
            except Exception as e:
                return ToolResult(success=False, error=f"Invalid URL: {e}")

            # Capture screenshot
            image_bytes, error = await self._capture_screenshot(
                url=url,
                width=width,
                height=height,
                full_page=full_page,
                selector=selector,
                wait_for=wait_for,
            )

            if error:
                return ToolResult(success=False, error=f"Screenshot capture failed: {error}")

            source_info = {
                "source": "url",
                "url": url,
                "viewport": {"width": width, "height": height},
                "full_page": full_page,
                "selector": selector,
            }
        else:
            # Decode base64 image
            try:
                image_bytes = base64.b64decode(image_base64)
                source_info = {
                    "source": "base64",
                    "size_bytes": len(image_bytes),
                }
            except Exception as e:
                return ToolResult(success=False, error=f"Invalid base64 image: {e}")

        # Import and configure Claude provider
        try:
            from fastband.providers.base import Capability
            from fastband.providers.registry import ProviderRegistry

            # Get Claude provider (supports vision)
            provider = ProviderRegistry.get("claude")

            if Capability.VISION not in provider.capabilities:
                return ToolResult(
                    success=False,
                    error="Selected provider does not support vision capability",
                )

        except ImportError:
            return ToolResult(
                success=False,
                error=(
                    "Claude provider requires anthropic package. Install with:\n"
                    "  pip install anthropic\n"
                    "Or: pip install fastband[claude]"
                ),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to initialize AI provider: {e}",
            )

        # Build the analysis prompt
        system_prompt = self._build_system_prompt(analysis_type)
        full_prompt = f"{system_prompt}\n\nUser Request:\n{prompt}"

        # Call Claude Vision API
        try:
            response = await provider.analyze_image(
                image_data=image_bytes,
                prompt=full_prompt,
                image_type="image/png",
                max_tokens=max_tokens,
            )

            execution_time = (time.perf_counter() - start_time) * 1000

            return ToolResult(
                success=True,
                data={
                    "analysis": response.content,
                    "analysis_type": analysis_type,
                    "prompt": prompt,
                    **source_info,
                },
                execution_time_ms=execution_time,
                metadata={
                    "model": response.model,
                    "provider": response.provider,
                    "usage": response.usage,
                    "finish_reason": response.finish_reason,
                },
            )

        except Exception as e:
            logger.exception("Vision analysis failed")
            return ToolResult(
                success=False,
                error=f"Vision analysis failed: {e}",
            )


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
        log_types: list[str] = None,
        include_network_errors: bool = True,
        execute_script: str = None,
        wait_for: str = "load",
        wait_timeout: int = 30000,
        headless: bool = True,
        **kwargs,
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
                    console_messages.append(
                        {
                            "type": msg_type,
                            "text": msg.text,
                            "location": {
                                "url": msg.location.get("url", ""),
                                "line": msg.location.get("lineNumber", 0),
                                "column": msg.location.get("columnNumber", 0),
                            }
                            if hasattr(msg, "location") and msg.location
                            else None,
                        }
                    )

            page.on("console", handle_console)

            # Set up network error handler
            if include_network_errors:

                def handle_request_failed(request):
                    network_errors.append(
                        {
                            "url": request.url,
                            "method": request.method,
                            "failure": request.failure,
                            "resource_type": request.resource_type,
                        }
                    )

                page.on("requestfailed", handle_request_failed)

            # Navigate to URL
            await page.goto(url, wait_until=wait_for, timeout=wait_timeout)

            # Execute custom script if provided
            if execute_script:
                try:
                    await page.evaluate(execute_script)
                except Exception as e:
                    console_messages.append(
                        {
                            "type": "error",
                            "text": f"Script execution error: {e}",
                            "location": None,
                        }
                    )

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
                        for msg_type in {m["type"] for m in console_messages}
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


class BrowserAutomationTool(Tool):
    """
    Browser automation tool for human-like interaction with web pages.

    Enables agents to:
    - Navigate to pages and perform login flows
    - Fill forms and submit them
    - Click buttons and links
    - Wait for elements to appear
    - Scroll pages
    - Execute multi-step navigation flows
    - Capture screenshots after actions

    This is essential for testing UI changes, verifying fixes,
    and generating proof-of-work for ticket completion.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="browser_automation",
                description=(
                    "Perform browser automation actions like a human user. "
                    "Supports clicking, typing, form filling, navigation, scrolling, "
                    "and waiting for elements. Essential for testing UI changes and "
                    "generating proof-of-work screenshots."
                ),
                category=ToolCategory.WEB,
                version="1.0.0",
                project_types=[ProjectType.WEB_APP],
                tech_stack_hints=["web", "testing", "qa", "e2e", "playwright"],
                network_required=True,
            ),
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="Starting URL to navigate to",
                    required=True,
                ),
                ToolParameter(
                    name="actions",
                    type="array",
                    description=(
                        "List of actions to perform. Each action is an object with:\n"
                        "- type: 'click' | 'type' | 'fill' | 'wait' | 'scroll' | 'select' | 'hover' | 'press' | 'goto'\n"
                        "- selector: CSS selector for the element (required for most actions)\n"
                        "- value: Value for type/fill/select/scroll/press actions\n"
                        "- timeout: Optional timeout in ms for wait actions (default: 5000)\n\n"
                        "Examples:\n"
                        "- {type: 'click', selector: 'button.submit'}\n"
                        "- {type: 'fill', selector: 'input[name=email]', value: 'test@example.com'}\n"
                        "- {type: 'type', selector: '#search', value: 'query'}\n"
                        "- {type: 'wait', selector: '.loading', timeout: 10000}\n"
                        "- {type: 'scroll', value: 500} (scroll down 500px)\n"
                        "- {type: 'select', selector: 'select#country', value: 'US'}\n"
                        "- {type: 'hover', selector: '.menu-item'}\n"
                        "- {type: 'press', value: 'Enter'}\n"
                        "- {type: 'goto', value: '/another-page'}"
                    ),
                    required=True,
                ),
                ToolParameter(
                    name="screenshot_after",
                    type="boolean",
                    description="Capture screenshot after all actions complete (default: true)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="screenshot_name",
                    type="string",
                    description="Name for the screenshot file (default: 'automation_result')",
                    required=False,
                    default="automation_result",
                ),
                ToolParameter(
                    name="width",
                    type="integer",
                    description="Viewport width in pixels (default: 1920)",
                    required=False,
                    default=1920,
                ),
                ToolParameter(
                    name="height",
                    type="integer",
                    description="Viewport height in pixels (default: 1080)",
                    required=False,
                    default=1080,
                ),
                ToolParameter(
                    name="headless",
                    type="boolean",
                    description="Run browser in headless mode (default: true)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="wait_after_action",
                    type="integer",
                    description="Milliseconds to wait after each action (default: 500)",
                    required=False,
                    default=500,
                ),
                ToolParameter(
                    name="collect_console",
                    type="boolean",
                    description="Collect console logs during automation (default: true)",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(
        self,
        url: str,
        actions: list[dict],
        screenshot_after: bool = True,
        screenshot_name: str = "automation_result",
        width: int = 1920,
        height: int = 1080,
        headless: bool = True,
        wait_after_action: int = 500,
        collect_console: bool = True,
        **kwargs,
    ) -> ToolResult:
        """Execute browser automation actions."""
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
        console_messages: list[dict] = []
        network_errors: list[dict] = []
        action_results: list[dict] = []

        try:
            manager = get_browser_manager()
            context = await manager.get_context(
                headless=headless, viewport={"width": width, "height": height}
            )

            if context is None:
                return _playwright_not_installed_error()

            page = await context.new_page()

            # Set up console handler if requested
            if collect_console:
                def handle_console(msg):
                    console_messages.append({
                        "type": msg.type,
                        "text": msg.text,
                    })

                def handle_request_failed(request):
                    network_errors.append({
                        "url": request.url,
                        "method": request.method,
                        "failure": str(request.failure) if request.failure else "Unknown",
                    })

                page.on("console", handle_console)
                page.on("requestfailed", handle_request_failed)

            # Navigate to initial URL
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                # Fallback if networkidle times out
                await asyncio.sleep(2)

            action_results.append({
                "action": "navigate",
                "url": url,
                "success": True,
            })

            # Execute each action
            for i, action in enumerate(actions):
                action_type = action.get("type", "").lower()
                selector = action.get("selector")
                value = action.get("value")
                timeout = action.get("timeout", 5000)

                result = {
                    "index": i,
                    "action": action_type,
                    "selector": selector,
                    "success": False,
                    "error": None,
                }

                try:
                    if action_type == "click":
                        if not selector:
                            result["error"] = "click requires 'selector'"
                        else:
                            await page.click(selector, timeout=timeout)
                            result["success"] = True

                    elif action_type in ("type", "fill"):
                        if not selector or value is None:
                            result["error"] = f"{action_type} requires 'selector' and 'value'"
                        else:
                            if action_type == "type":
                                await page.type(selector, str(value))
                            else:
                                await page.fill(selector, str(value))
                            result["success"] = True

                    elif action_type == "wait":
                        if not selector:
                            result["error"] = "wait requires 'selector'"
                        else:
                            await page.wait_for_selector(selector, timeout=timeout)
                            result["success"] = True

                    elif action_type == "scroll":
                        scroll_y = int(value) if value else 500
                        await page.evaluate(f"window.scrollBy(0, {scroll_y})")
                        result["success"] = True
                        result["scrolled"] = scroll_y

                    elif action_type == "select":
                        if not selector or value is None:
                            result["error"] = "select requires 'selector' and 'value'"
                        else:
                            await page.select_option(selector, value=str(value))
                            result["success"] = True

                    elif action_type == "hover":
                        if not selector:
                            result["error"] = "hover requires 'selector'"
                        else:
                            await page.hover(selector)
                            result["success"] = True

                    elif action_type == "press":
                        if value is None:
                            result["error"] = "press requires 'value' (key name)"
                        else:
                            await page.keyboard.press(str(value))
                            result["success"] = True

                    elif action_type == "goto":
                        if value is None:
                            result["error"] = "goto requires 'value' (URL or path)"
                        else:
                            goto_url = str(value)
                            if not goto_url.startswith("http"):
                                # Relative path - construct from current URL
                                current_parsed = urlparse(page.url)
                                goto_url = f"{current_parsed.scheme}://{current_parsed.netloc}{goto_url}"
                            await page.goto(goto_url, wait_until="domcontentloaded", timeout=30000)
                            result["success"] = True
                            result["navigated_to"] = goto_url

                    elif action_type == "wait_for_load":
                        try:
                            await page.wait_for_load_state("networkidle", timeout=timeout)
                        except Exception:
                            await asyncio.sleep(2)
                        result["success"] = True

                    elif action_type == "screenshot":
                        # Inline screenshot during automation
                        ss_name = value or f"step_{i}"
                        screenshot_bytes = await page.screenshot(type="png")
                        result["success"] = True
                        result["screenshot_size"] = len(screenshot_bytes)

                    else:
                        result["error"] = f"Unknown action type: {action_type}"

                except Exception as e:
                    result["error"] = str(e)
                    logger.warning(f"Action {i} ({action_type}) failed: {e}")

                action_results.append(result)

                # Wait between actions
                if wait_after_action > 0 and result["success"]:
                    await asyncio.sleep(wait_after_action / 1000)

            # Capture final screenshot if requested
            screenshot_base64 = None
            if screenshot_after:
                try:
                    screenshot_bytes = await page.screenshot(type="png", full_page=False)
                    screenshot_base64 = base64.b64encode(screenshot_bytes).decode("utf-8")
                except Exception as e:
                    logger.warning(f"Failed to capture screenshot: {e}")

            # Calculate success rate
            successful_actions = sum(1 for r in action_results if r.get("success", False))
            total_actions = len(action_results)

            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "final_url": page.url,
                    "actions_completed": successful_actions,
                    "actions_total": total_actions,
                    "action_results": action_results,
                    "console_messages": console_messages if collect_console else [],
                    "console_errors": [m for m in console_messages if m.get("type") == "error"],
                    "network_errors": network_errors if collect_console else [],
                    "screenshot_base64": screenshot_base64,
                    "screenshot_format": "png" if screenshot_base64 else None,
                    "page_title": await page.title(),
                },
                metadata={
                    "viewport": {"width": width, "height": height},
                    "headless": headless,
                },
            )

        except Exception as e:
            logger.exception(f"Browser automation failed for {url}")
            return ToolResult(
                success=False,
                error=str(e),
                data={
                    "url": url,
                    "action_results": action_results,
                    "console_messages": console_messages,
                    "network_errors": network_errors,
                },
            )
        finally:
            if page:
                await page.close()
            if context:
                await context.close()


class QAConsoleSweepTool(Tool):
    """
    Multi-page console error detection tool.

    Sweeps multiple pages of a web application to detect:
    - JavaScript console errors and warnings
    - Network failures (4xx, 5xx responses)
    - Page load failures
    - Uncaught exceptions

    Essential for QA verification after deployments or migrations.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="qa_console_sweep",
                description=(
                    "Sweep multiple pages of a web application checking for console errors, "
                    "network failures, and JavaScript exceptions. Returns a comprehensive "
                    "QA report with pass/fail status for each page."
                ),
                category=ToolCategory.WEB,
                version="1.0.0",
                project_types=[ProjectType.WEB_APP],
                tech_stack_hints=["web", "testing", "qa", "debugging"],
                network_required=True,
            ),
            parameters=[
                ToolParameter(
                    name="base_url",
                    type="string",
                    description="Base URL of the application (e.g., 'http://localhost:3000')",
                    required=True,
                ),
                ToolParameter(
                    name="pages",
                    type="array",
                    description=(
                        "List of pages to check. Each item can be:\n"
                        "- A string path (e.g., '/dashboard')\n"
                        "- An object with 'path' and 'name' (e.g., {path: '/dashboard', name: 'Dashboard'})"
                    ),
                    required=True,
                ),
                ToolParameter(
                    name="login",
                    type="object",
                    description=(
                        "Optional login configuration for authenticated pages:\n"
                        "- url: Login page URL path (e.g., '/login')\n"
                        "- email_selector: CSS selector for email input\n"
                        "- password_selector: CSS selector for password input\n"
                        "- submit_selector: CSS selector for submit button\n"
                        "- email: Email to use\n"
                        "- password: Password to use"
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="wait_time",
                    type="integer",
                    description="Milliseconds to wait on each page for async operations (default: 3000)",
                    required=False,
                    default=3000,
                ),
                ToolParameter(
                    name="ignore_patterns",
                    type="array",
                    description="Patterns to ignore in error messages (e.g., ['favicon.ico', 'chrome-extension'])",
                    required=False,
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
        base_url: str,
        pages: list,
        login: dict = None,
        wait_time: int = 3000,
        ignore_patterns: list[str] = None,
        headless: bool = True,
        **kwargs,
    ) -> ToolResult:
        """Execute QA console sweep across multiple pages."""
        if not PLAYWRIGHT_AVAILABLE:
            return _playwright_not_installed_error()

        # Normalize base URL
        base_url = base_url.rstrip("/")

        # Default ignore patterns
        default_ignores = ["favicon.ico", "chrome-extension", "extensions::"]
        ignore_patterns = (ignore_patterns or []) + default_ignores

        context = None
        page = None
        results: list[dict] = []

        try:
            manager = get_browser_manager()
            context = await manager.get_context(
                headless=headless, viewport={"width": 1920, "height": 1080}
            )

            if context is None:
                return _playwright_not_installed_error()

            page = await context.new_page()

            # Handle login if provided
            if login:
                try:
                    login_url = f"{base_url}{login.get('url', '/login')}"
                    await page.goto(login_url, wait_until="networkidle", timeout=30000)

                    if login.get("email_selector") and login.get("email"):
                        await page.fill(login["email_selector"], login["email"])
                    if login.get("password_selector") and login.get("password"):
                        await page.fill(login["password_selector"], login["password"])
                    if login.get("submit_selector"):
                        await page.click(login["submit_selector"])
                        await page.wait_for_load_state("networkidle", timeout=10000)

                except Exception as e:
                    logger.warning(f"Login failed: {e}")

            # Check each page
            for page_config in pages:
                if isinstance(page_config, str):
                    path = page_config
                    name = page_config.strip("/").replace("/", "_") or "home"
                else:
                    path = page_config.get("path", "/")
                    name = page_config.get("name", path)

                full_url = f"{base_url}{path}"

                page_result = {
                    "name": name,
                    "path": path,
                    "url": full_url,
                    "status": "PASS",
                    "page_loaded": False,
                    "console_errors": [],
                    "console_warnings": [],
                    "network_failures": [],
                    "js_errors": [],
                }

                # Collectors
                console_messages = []
                network_failures = []
                page_errors = []

                def handle_console(msg):
                    console_messages.append({"type": msg.type, "text": msg.text})

                def handle_response(response):
                    if response.status >= 400:
                        network_failures.append({
                            "url": response.url,
                            "status": response.status,
                            "method": response.request.method,
                        })

                def handle_page_error(exc):
                    page_errors.append(str(exc))

                page.on("console", handle_console)
                page.on("response", handle_response)
                page.on("pageerror", handle_page_error)

                try:
                    response = await page.goto(full_url, wait_until="domcontentloaded", timeout=30000)

                    if response and response.status >= 400:
                        page_result["status"] = "FAIL"
                        page_result["http_status"] = response.status
                    else:
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass

                        await asyncio.sleep(wait_time / 1000)
                        page_result["page_loaded"] = True

                except Exception as e:
                    page_result["status"] = "ERROR"
                    page_result["error"] = str(e)

                # Remove listeners
                page.remove_listener("console", handle_console)
                page.remove_listener("response", handle_response)
                page.remove_listener("pageerror", handle_page_error)

                # Process collected data
                for msg in console_messages:
                    text = msg.get("text", "")
                    # Check ignore patterns
                    if any(pattern.lower() in text.lower() for pattern in ignore_patterns):
                        continue

                    if msg["type"] == "error":
                        page_result["console_errors"].append(text)
                    elif msg["type"] == "warning":
                        page_result["console_warnings"].append(text)

                page_result["network_failures"] = network_failures
                page_result["js_errors"] = page_errors

                # Determine status
                has_500_error = any(f["status"] >= 500 for f in network_failures)
                has_console_errors = len(page_result["console_errors"]) > 0
                has_js_errors = len(page_errors) > 0

                if page_result["status"] != "ERROR":
                    if has_500_error or has_console_errors or has_js_errors:
                        page_result["status"] = "FAIL"
                    elif any(f["status"] == 404 for f in network_failures):
                        page_result["status"] = "WARNING"

                results.append(page_result)

            # Calculate summary
            passed = sum(1 for r in results if r["status"] == "PASS")
            warnings = sum(1 for r in results if r["status"] == "WARNING")
            failed = sum(1 for r in results if r["status"] == "FAIL")
            errors = sum(1 for r in results if r["status"] == "ERROR")

            return ToolResult(
                success=True,
                data={
                    "base_url": base_url,
                    "pages_checked": len(results),
                    "summary": {
                        "passed": passed,
                        "warnings": warnings,
                        "failed": failed,
                        "errors": errors,
                        "pass_rate": round((passed / len(results) * 100) if results else 0, 2),
                    },
                    "overall_status": "PASS" if (failed == 0 and errors == 0) else "FAIL",
                    "results": results,
                    "failed_pages": [r for r in results if r["status"] in ("FAIL", "ERROR")],
                },
            )

        except Exception as e:
            logger.exception(f"QA console sweep failed")
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
    VisionAnalysisTool,
    BrowserAutomationTool,
    QAConsoleSweepTool,
]

__all__ = [
    "ScreenshotTool",
    "HttpRequestTool",
    "DomQueryTool",
    "BrowserConsoleTool",
    "VisionAnalysisTool",
    "BrowserAutomationTool",
    "QAConsoleSweepTool",
    "WEB_TOOLS",
    "PLAYWRIGHT_AVAILABLE",
    "get_browser_manager",
    "BrowserManager",
]
