"""
API Testing Tool - HTTP API testing and validation.

Provides MCP tools for:
- HTTP request testing
- Response validation
- API health checks
- Contract testing
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class APITestResult:
    """Result of an API test."""

    url: str
    method: str = "GET"

    # Response
    status_code: int = 0
    response_time_ms: float = 0
    response_body: str = ""
    response_headers: dict[str, str] = field(default_factory=dict)

    # Validation
    passed: bool = True
    errors: list[str] = field(default_factory=list)

    # Expected
    expected_status: int | None = None
    expected_content_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "method": self.method,
            "status_code": self.status_code,
            "response_time_ms": round(self.response_time_ms, 2),
            "passed": self.passed,
            "errors": self.errors if not self.passed else None,
            "content_type": self.response_headers.get("Content-Type"),
        }


@dataclass
class APIHealthCheck:
    """Health check result for an API endpoint."""

    url: str
    healthy: bool = False

    # Details
    status_code: int = 0
    response_time_ms: float = 0

    # Health data (if JSON response)
    health_data: dict[str, Any] = field(default_factory=dict)

    # Checks
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)

    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "healthy": self.healthy,
            "status_code": self.status_code,
            "response_time_ms": round(self.response_time_ms, 2),
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "health_data": self.health_data if self.health_data else None,
            "checked_at": self.checked_at.isoformat(),
        }


def make_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout: int = 30,
) -> APITestResult:
    """Make an HTTP request and return the result."""
    result = APITestResult(url=url, method=method)

    try:
        req = urllib.request.Request(url, method=method)
        req.add_header("User-Agent", "Fastband-API-Test/1.0")

        if headers:
            for key, value in headers.items():
                req.add_header(key, value)

        if body:
            req.data = body.encode("utf-8")
            if "Content-Type" not in (headers or {}):
                req.add_header("Content-Type", "application/json")

        start_time = time.time()

        with urllib.request.urlopen(req, timeout=timeout) as response:
            result.status_code = response.status
            result.response_body = response.read().decode("utf-8", errors="replace")
            result.response_headers = dict(response.headers)

        result.response_time_ms = (time.time() - start_time) * 1000

    except urllib.error.HTTPError as e:
        result.status_code = e.code
        result.response_time_ms = (time.time() - start_time) * 1000
        try:
            result.response_body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        result.errors.append(f"HTTP {e.code}: {e.reason}")
        result.passed = False

    except urllib.error.URLError as e:
        result.errors.append(f"Connection error: {e.reason}")
        result.passed = False

    except Exception as e:
        result.errors.append(f"Request failed: {str(e)}")
        result.passed = False

    return result


def validate_response(
    result: APITestResult,
    expected_status: int | None = None,
    expected_content_type: str | None = None,
    expected_json_keys: list[str] | None = None,
    expected_body_contains: str | None = None,
) -> APITestResult:
    """Validate an API response against expectations."""
    result.expected_status = expected_status
    result.expected_content_type = expected_content_type

    # Status code check
    if expected_status and result.status_code != expected_status:
        result.errors.append(f"Expected status {expected_status}, got {result.status_code}")
        result.passed = False

    # Content type check
    if expected_content_type:
        content_type = result.response_headers.get("Content-Type", "")
        if expected_content_type not in content_type:
            result.errors.append(f"Expected content-type {expected_content_type}, got {content_type}")
            result.passed = False

    # JSON keys check
    if expected_json_keys and result.response_body:
        try:
            data = json.loads(result.response_body)
            for key in expected_json_keys:
                if key not in data:
                    result.errors.append(f"Missing expected key: {key}")
                    result.passed = False
        except json.JSONDecodeError:
            result.errors.append("Response is not valid JSON")
            result.passed = False

    # Body contains check
    if expected_body_contains:
        if expected_body_contains not in result.response_body:
            result.errors.append(f"Response body missing: {expected_body_contains[:50]}")
            result.passed = False

    return result


def check_health(url: str, timeout: int = 10) -> APIHealthCheck:
    """Check health of an API endpoint."""
    health = APIHealthCheck(url=url)

    result = make_request(url, timeout=timeout)
    health.status_code = result.status_code
    health.response_time_ms = result.response_time_ms

    # Basic checks
    if 200 <= result.status_code < 300:
        health.checks_passed.append("status_2xx")
    else:
        health.checks_failed.append(f"status_{result.status_code}")

    if result.response_time_ms < 1000:
        health.checks_passed.append("response_under_1s")
    elif result.response_time_ms < 3000:
        health.checks_passed.append("response_under_3s")
    else:
        health.checks_failed.append("response_over_3s")

    # Try to parse health data
    if result.response_body:
        try:
            data = json.loads(result.response_body)
            health.health_data = data

            # Check for common health indicators
            if data.get("status") == "ok" or data.get("healthy") is True:
                health.checks_passed.append("health_status_ok")
            elif data.get("status") == "error" or data.get("healthy") is False:
                health.checks_failed.append("health_status_error")

        except json.JSONDecodeError:
            pass

    health.healthy = len(health.checks_failed) == 0

    return health


class APITestingTool:
    """Unified API testing tool."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

    async def test_endpoint(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str = "",
        expected_status: int | None = None,
    ) -> dict[str, Any]:
        """Test a single API endpoint."""
        result = make_request(url, method=method, headers=headers, body=body if body else None)

        if expected_status:
            result = validate_response(result, expected_status=expected_status)

        return {
            "type": "api_test",
            **result.to_dict(),
        }

    async def health_check(self, url: str) -> dict[str, Any]:
        """Check API health."""
        health = check_health(url)
        return {
            "type": "api_health",
            **health.to_dict(),
        }

    async def test_endpoints(self, endpoints: list[dict[str, Any]]) -> dict[str, Any]:
        """Test multiple endpoints."""
        results = []
        passed = 0
        failed = 0

        for endpoint in endpoints:
            url = endpoint.get("url", "")
            method = endpoint.get("method", "GET")
            expected = endpoint.get("expected_status", 200)

            result = make_request(url, method=method)
            result = validate_response(result, expected_status=expected)

            if result.passed:
                passed += 1
            else:
                failed += 1

            results.append(result.to_dict())

        return {
            "type": "api_test_suite",
            "total": len(endpoints),
            "passed": passed,
            "failed": failed,
            "success_rate": f"{(passed / len(endpoints) * 100):.1f}%" if endpoints else "0%",
            "results": results,
        }

    async def discover_endpoints(self) -> dict[str, Any]:
        """Discover API endpoints from common sources."""
        endpoints = []

        # Check for OpenAPI/Swagger spec
        openapi_paths = [
            "openapi.json", "openapi.yaml", "swagger.json", "swagger.yaml",
            "api/openapi.json", "docs/openapi.json",
        ]

        for api_path in openapi_paths:
            full_path = self.project_root / api_path
            if full_path.exists():
                try:
                    with open(full_path) as f:
                        if api_path.endswith(".json"):
                            spec = json.load(f)
                        else:
                            # Basic YAML parsing
                            content = f.read()
                            # Simple extraction of paths
                            for line in content.split("\n"):
                                if line.strip().startswith("/"):
                                    path = line.strip().rstrip(":")
                                    endpoints.append({"path": path, "source": api_path})
                            continue

                        # Parse OpenAPI spec
                        paths = spec.get("paths", {})
                        for path, methods in paths.items():
                            for method in methods.keys():
                                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                                    endpoints.append({
                                        "path": path,
                                        "method": method.upper(),
                                        "source": api_path,
                                    })
                except Exception:
                    pass

        # Check for route files (common patterns)
        route_patterns = [
            "**/routes.py", "**/urls.py", "**/router.ts", "**/routes.ts",
            "**/api/**/*.ts", "**/api/**/*.py",
        ]

        for pattern in route_patterns:
            for file_path in self.project_root.glob(pattern):
                if any(skip in str(file_path) for skip in ["node_modules", "venv", "__pycache__"]):
                    continue

                try:
                    with open(file_path) as f:
                        content = f.read()

                    # Look for route definitions
                    # Express/Fastify style
                    for match in re.finditer(r"(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]", content, re.I):
                        endpoints.append({
                            "path": match.group(2),
                            "method": match.group(1).upper(),
                            "source": str(file_path.relative_to(self.project_root)),
                        })

                    # Flask/Django style
                    for match in re.finditer(r"@.*route\s*\(\s*['\"]([^'\"]+)['\"]", content, re.I):
                        endpoints.append({
                            "path": match.group(1),
                            "source": str(file_path.relative_to(self.project_root)),
                        })

                except Exception:
                    pass

        return {
            "type": "endpoint_discovery",
            "count": len(endpoints),
            "endpoints": endpoints[:50],  # Limit results
        }


# =============================================================================
# MCP-FACING FUNCTIONS
# =============================================================================

async def api_test(
    url: str,
    method: str = "GET",
    headers: str = "",
    body: str = "",
    expected_status: int = 0,
    path: str = "",
) -> dict[str, Any]:
    """Test a single API endpoint."""
    project_path = path or os.getcwd()
    tool = APITestingTool(project_path)

    header_dict = None
    if headers:
        header_dict = dict(h.split(":") for h in headers.split(",") if ":" in h)

    return await tool.test_endpoint(
        url=url,
        method=method,
        headers=header_dict,
        body=body,
        expected_status=expected_status if expected_status > 0 else None,
    )


async def api_health(url: str, path: str = "") -> dict[str, Any]:
    """Check API health."""
    project_path = path or os.getcwd()
    tool = APITestingTool(project_path)
    return await tool.health_check(url)


async def api_discover(path: str = "") -> dict[str, Any]:
    """Discover API endpoints."""
    project_path = path or os.getcwd()
    tool = APITestingTool(project_path)
    return await tool.discover_endpoints()


async def api_test_suite(endpoints: str, path: str = "") -> dict[str, Any]:
    """Test multiple endpoints."""
    project_path = path or os.getcwd()
    tool = APITestingTool(project_path)

    # Parse endpoints string (format: "url1,url2" or JSON array)
    try:
        endpoint_list = json.loads(endpoints)
    except json.JSONDecodeError:
        endpoint_list = [{"url": u.strip(), "method": "GET"} for u in endpoints.split(",")]

    return await tool.test_endpoints(endpoint_list)
