"""
Fastband Testing Tools - E2E Testing and Validation.

Provides comprehensive testing capabilities for AI agents:
- AgentTesterTool: Full E2E testing with proof-of-work reports
- ScreenshotValidatorTool: AI-powered screenshot validation

Ported from:
- MLB_dev/tests/agent_test_runner.py
- MLB_dev/scripts/validators/screenshot_validator.py
"""

import asyncio
import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
    ProjectType,
)

logger = logging.getLogger(__name__)

# Check for Playwright
try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def _playwright_not_installed_error() -> ToolResult:
    return ToolResult(
        success=False,
        error="Playwright is not installed. Install with: pip install playwright && playwright install chromium",
    )


class AgentTesterTool(Tool):
    """
    Comprehensive E2E testing framework for AI agents.

    Provides a complete testing workflow:
    - Page load testing with element verification
    - Form submission testing
    - Multi-step navigation flow testing
    - Screenshot capture at key steps
    - Proof-of-work report generation for ticket updates

    Essential for agents to verify their work and generate
    evidence for ticket completion.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="agent_tester",
                description=(
                    "Comprehensive E2E testing framework for AI agents. "
                    "Test page loads, form submissions, navigation flows, "
                    "and generate proof-of-work reports for ticket updates."
                ),
                category=ToolCategory.TESTING,
                version="1.0.0",
                project_types=[ProjectType.WEB_APP],
                tech_stack_hints=["web", "testing", "qa", "e2e", "proof-of-work"],
                network_required=True,
            ),
            parameters=[
                ToolParameter(
                    name="base_url",
                    type="string",
                    description="Base URL of the application to test (e.g., 'http://localhost:3000')",
                    required=True,
                ),
                ToolParameter(
                    name="tests",
                    type="array",
                    description=(
                        "List of tests to run. Each test is an object with:\n"
                        "- type: 'page_load' | 'form_submit' | 'navigation_flow'\n"
                        "- name: Test name for the report\n"
                        "- url: URL path to test (for page_load and form_submit)\n"
                        "- expected_elements: CSS selectors that should exist (for page_load)\n"
                        "- form_data: {selector: value} for form fields (for form_submit)\n"
                        "- submit_selector: Button to click (for form_submit)\n"
                        "- success_indicator: Element indicating success (for form_submit)\n"
                        "- steps: List of actions for navigation_flow (goto, click, fill, wait, assert)"
                    ),
                    required=True,
                ),
                ToolParameter(
                    name="login",
                    type="object",
                    description=(
                        "Optional login to perform before tests:\n"
                        "- url: Login page path\n"
                        "- email_selector, password_selector, submit_selector\n"
                        "- email, password: Credentials"
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="ticket_id",
                    type="string",
                    description="Ticket ID for proof-of-work report (e.g., 'FB-123')",
                    required=False,
                ),
                ToolParameter(
                    name="screenshot_dir",
                    type="string",
                    description="Directory to save screenshots (default: .fastband/screenshots)",
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
        tests: list[dict],
        login: dict = None,
        ticket_id: str = None,
        screenshot_dir: str = None,
        headless: bool = True,
        **kwargs,
    ) -> ToolResult:
        """Execute E2E tests and generate proof-of-work report."""
        if not PLAYWRIGHT_AVAILABLE:
            return _playwright_not_installed_error()

        base_url = base_url.rstrip("/")
        session_start = datetime.now(timezone.utc)
        test_results: list[dict] = []
        screenshots: list[dict] = []

        # Setup screenshot directory
        if screenshot_dir:
            ss_dir = Path(screenshot_dir)
        else:
            ss_dir = Path(".fastband/screenshots")
        ss_dir.mkdir(parents=True, exist_ok=True)

        browser = None
        context = None
        page = None

        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Fastband Agent Tester) AppleWebKit/537.36",
            )
            page = await context.new_page()
            page.set_default_timeout(10000)

            # Perform login if configured
            if login:
                try:
                    login_url = f"{base_url}{login.get('url', '/login')}"
                    await page.goto(login_url, wait_until="networkidle")

                    if login.get("email_selector") and login.get("email"):
                        await page.fill(login["email_selector"], login["email"])
                    if login.get("password_selector") and login.get("password"):
                        await page.fill(login["password_selector"], login["password"])
                    if login.get("submit_selector"):
                        await page.click(login["submit_selector"])
                        await page.wait_for_load_state("networkidle", timeout=10000)

                except Exception as e:
                    logger.warning(f"Login failed: {e}")

            # Run each test
            for test in tests:
                test_type = test.get("type", "page_load")
                test_name = test.get("name", f"test_{len(test_results)}")
                result = {
                    "test_name": test_name,
                    "test_type": test_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "passed": False,
                    "errors": [],
                    "warnings": [],
                    "timing": {},
                }

                start_time = datetime.now(timezone.utc)

                try:
                    if test_type == "page_load":
                        result = await self._test_page_load(
                            page, base_url, test, test_name, result
                        )
                    elif test_type == "form_submit":
                        result = await self._test_form_submit(
                            page, base_url, test, test_name, result
                        )
                    elif test_type == "navigation_flow":
                        result = await self._test_navigation_flow(
                            page, base_url, test, test_name, result
                        )
                    else:
                        result["errors"].append(f"Unknown test type: {test_type}")

                except Exception as e:
                    result["errors"].append(f"Exception: {str(e)}")
                    result["passed"] = False

                # Calculate timing
                end_time = datetime.now(timezone.utc)
                result["timing"]["total"] = f"{(end_time - start_time).total_seconds():.2f}s"

                test_results.append(result)

                # Capture screenshot after each test
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    if ticket_id:
                        filename = f"{ticket_id}_{test_name}_{timestamp}.png"
                    else:
                        filename = f"{test_name}_{timestamp}.png"

                    filepath = ss_dir / filename
                    await page.screenshot(path=str(filepath), full_page=True)

                    screenshots.append({
                        "filename": filename,
                        "filepath": str(filepath),
                        "test_name": test_name,
                        "url": page.url,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as e:
                    logger.warning(f"Screenshot capture failed: {e}")

            # Generate summary
            session_end = datetime.now(timezone.utc)
            session_duration = (session_end - session_start).total_seconds()
            passed_tests = sum(1 for r in test_results if r.get("passed", False))

            report = {
                "ticket_id": ticket_id,
                "base_url": base_url,
                "session_start": session_start.isoformat(),
                "session_end": session_end.isoformat(),
                "session_duration_seconds": round(session_duration, 2),
                "statistics": {
                    "total_tests": len(test_results),
                    "passed": passed_tests,
                    "failed": len(test_results) - passed_tests,
                    "pass_rate": round((passed_tests / len(test_results) * 100) if test_results else 0, 2),
                    "total_screenshots": len(screenshots),
                },
                "test_results": test_results,
                "screenshots": screenshots,
            }

            # Save report if ticket_id provided
            if ticket_id:
                report_filename = f"{ticket_id}_test_report_{session_end.strftime('%Y%m%d_%H%M%S')}.json"
                report_path = ss_dir / report_filename
                with open(report_path, "w") as f:
                    json.dump(report, f, indent=2)
                report["report_path"] = str(report_path)

            return ToolResult(
                success=True,
                data=report,
            )

        except Exception as e:
            logger.exception("Agent tester failed")
            return ToolResult(success=False, error=str(e))

        finally:
            if page:
                await page.close()
            if context:
                await context.close()
            if browser:
                await browser.close()

    async def _test_page_load(
        self, page, base_url: str, test: dict, test_name: str, result: dict
    ) -> dict:
        """Test page load with expected elements."""
        url_path = test.get("url", "/")
        full_url = f"{base_url}{url_path}"
        expected_elements = test.get("expected_elements", [])

        result["url"] = full_url
        result["elements_found"] = {}

        response = await page.goto(full_url, wait_until="domcontentloaded")

        if response and response.status >= 400:
            result["errors"].append(f"HTTP {response.status}")
            return result

        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            result["warnings"].append("Networkidle timeout, continuing...")

        # Check expected elements
        for selector in expected_elements:
            try:
                element = await page.wait_for_selector(selector, timeout=3000)
                result["elements_found"][selector] = bool(element)
            except Exception:
                result["elements_found"][selector] = False
                result["warnings"].append(f"Element not found: {selector}")

        result["page_title"] = await page.title()
        result["passed"] = len(result["errors"]) == 0

        return result

    async def _test_form_submit(
        self, page, base_url: str, test: dict, test_name: str, result: dict
    ) -> dict:
        """Test form submission."""
        url_path = test.get("url", "/")
        full_url = f"{base_url}{url_path}"
        form_data = test.get("form_data", {})
        submit_selector = test.get("submit_selector")
        success_indicator = test.get("success_indicator")

        result["url"] = full_url

        await page.goto(full_url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle", timeout=10000)

        # Fill form
        for selector, value in form_data.items():
            try:
                await page.fill(selector, value)
            except Exception as e:
                result["errors"].append(f"Failed to fill {selector}: {e}")

        # Submit
        if submit_selector:
            try:
                await page.click(submit_selector)
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception as e:
                result["errors"].append(f"Submit failed: {e}")

        # Check success
        if success_indicator:
            try:
                await page.wait_for_selector(success_indicator, timeout=5000)
                result["success_found"] = True
            except Exception:
                result["success_found"] = False
                result["warnings"].append("Success indicator not found")

        result["passed"] = len(result["errors"]) == 0
        return result

    async def _test_navigation_flow(
        self, page, base_url: str, test: dict, test_name: str, result: dict
    ) -> dict:
        """Test multi-step navigation flow."""
        steps = test.get("steps", [])
        result["steps_completed"] = 0
        result["total_steps"] = len(steps)

        for i, step in enumerate(steps):
            action = step.get("action", "")
            selector = step.get("selector")
            value = step.get("value")

            try:
                if action == "goto":
                    url = step.get("url", value or "/")
                    if not url.startswith("http"):
                        url = f"{base_url}{url}"
                    await page.goto(url, wait_until="domcontentloaded")
                    await page.wait_for_load_state("networkidle", timeout=10000)

                elif action == "click":
                    await page.click(selector)
                    await asyncio.sleep(0.5)

                elif action == "fill":
                    await page.fill(selector, value)

                elif action == "wait":
                    await page.wait_for_selector(selector, timeout=5000)

                elif action == "assert":
                    element = await page.wait_for_selector(selector, timeout=3000)
                    if "text" in step:
                        actual_text = await element.inner_text()
                        if step["text"] not in actual_text:
                            result["errors"].append(
                                f"Step {i+1}: Expected '{step['text']}' not in '{actual_text}'"
                            )
                            break

                result["steps_completed"] = i + 1

            except Exception as e:
                result["errors"].append(f"Step {i+1} ({action}): {e}")
                break

        result["passed"] = (
            result["steps_completed"] == result["total_steps"]
            and len(result["errors"]) == 0
        )
        return result


class ScreenshotValidatorTool(Tool):
    """
    AI-powered screenshot validation for proof-of-work.

    Uses Claude Vision API to validate screenshots against
    ticket requirements. Prevents fake or misleading proof
    submissions by:
    - Checking if UI matches requirements
    - Verifying specific elements are present
    - Scoring compliance (0-100%)
    - Detecting issues and providing feedback
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="screenshot_validator",
                description=(
                    "AI-powered screenshot validation using Claude Vision. "
                    "Validates screenshots against ticket requirements, "
                    "provides compliance scoring, and detects issues."
                ),
                category=ToolCategory.TESTING,
                version="1.0.0",
                project_types=[ProjectType.WEB_APP],
                tech_stack_hints=["testing", "qa", "validation", "proof-of-work"],
                network_required=True,
            ),
            parameters=[
                ToolParameter(
                    name="screenshot",
                    type="string",
                    description="Base64-encoded screenshot image OR path to image file",
                    required=True,
                ),
                ToolParameter(
                    name="requirements",
                    type="array",
                    description=(
                        "List of requirements to validate. Each item is a string "
                        "describing what should be visible or present in the screenshot. "
                        "E.g., ['Login button should be visible', 'Form has email field']"
                    ),
                    required=True,
                ),
                ToolParameter(
                    name="ticket_id",
                    type="string",
                    description="Ticket ID for context (optional)",
                    required=False,
                ),
                ToolParameter(
                    name="context",
                    type="string",
                    description="Additional context about what the screenshot should show",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        screenshot: str,
        requirements: list[str],
        ticket_id: str = None,
        context: str = None,
        **kwargs,
    ) -> ToolResult:
        """Validate screenshot against requirements using Claude Vision."""
        import os

        # Get screenshot as base64
        if screenshot.startswith("/") or screenshot.startswith("."):
            # File path - read and encode
            try:
                with open(screenshot, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                return ToolResult(success=False, error=f"Failed to read screenshot: {e}")
        else:
            # Already base64
            image_data = screenshot

        # Check for API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="ANTHROPIC_API_KEY not set. Required for vision validation.",
            )

        # Build validation prompt
        req_list = "\n".join(f"- {req}" for req in requirements)
        context_text = f"\nContext: {context}" if context else ""
        ticket_text = f"\nTicket: {ticket_id}" if ticket_id else ""

        prompt = f"""You are a QA validator. Analyze this screenshot and validate it against the following requirements.
{ticket_text}{context_text}

Requirements to validate:
{req_list}

For each requirement, provide:
1. PASS or FAIL status
2. Confidence score (0-100)
3. Evidence or reason

Then provide:
- Overall compliance score (0-100)
- List of any issues found
- Recommendation (APPROVE or REJECT)

Format your response as JSON:
{{
  "requirements": [
    {{"requirement": "...", "status": "PASS|FAIL", "confidence": 95, "evidence": "..."}}
  ],
  "overall_score": 85,
  "issues": ["issue 1", "issue 2"],
  "recommendation": "APPROVE|REJECT",
  "summary": "Brief summary of findings"
}}
"""

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 2048,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/png",
                                            "data": image_data,
                                        },
                                    },
                                    {
                                        "type": "text",
                                        "text": prompt,
                                    },
                                ],
                            }
                        ],
                    },
                    timeout=60.0,
                )

            if response.status_code != 200:
                return ToolResult(
                    success=False,
                    error=f"Claude API error: {response.status_code} - {response.text}",
                )

            result = response.json()
            content = result.get("content", [{}])[0].get("text", "")

            # Try to parse JSON from response
            try:
                # Find JSON in response
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    validation_result = json.loads(content[json_start:json_end])
                else:
                    validation_result = {"raw_response": content}
            except json.JSONDecodeError:
                validation_result = {"raw_response": content}

            return ToolResult(
                success=True,
                data={
                    "ticket_id": ticket_id,
                    "requirements_checked": len(requirements),
                    "validation": validation_result,
                    "passed": validation_result.get("recommendation") == "APPROVE",
                    "overall_score": validation_result.get("overall_score", 0),
                },
            )

        except Exception as e:
            logger.exception("Screenshot validation failed")
            return ToolResult(success=False, error=str(e))


# All testing tools
TESTING_TOOLS = [
    AgentTesterTool,
    ScreenshotValidatorTool,
]

__all__ = [
    "AgentTesterTool",
    "ScreenshotValidatorTool",
    "TESTING_TOOLS",
    "PLAYWRIGHT_AVAILABLE",
]
