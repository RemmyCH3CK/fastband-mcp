"""
API Testing Tools - HTTP API testing and validation.

Provides MCP tools for:
- Single endpoint testing
- Batch endpoint testing
- Health checks
- Endpoint discovery from OpenAPI specs

Usage:
    # Test single endpoint
    result = await api_test("https://api.example.com/health")
    print(f"Status: {result['status_code']}")

    # Health check
    result = await api_health("https://api.example.com/health")
    print(f"Healthy: {result['healthy']}")

    # Discover endpoints
    result = await api_discover()
    print(f"Found {result['count']} endpoints")
"""

from fastband.tools.api_testing.tool import (
    APIHealthCheck,
    APITestingTool,
    APITestResult,
    api_discover,
    api_health,
    api_test,
    api_test_suite,
    check_health,
    make_request,
    validate_response,
)

__all__ = [
    # Main tool
    "APITestingTool",
    # Utility functions
    "make_request",
    "validate_response",
    "check_health",
    # MCP functions
    "api_test",
    "api_health",
    "api_discover",
    "api_test_suite",
    # Models
    "APITestResult",
    "APIHealthCheck",
]


# =========================================================================
# MCP TOOL REGISTRATION
# =========================================================================

def register_tools(mcp_server):
    """Register API testing tools with the MCP server."""

    @mcp_server.tool()
    async def api_test_endpoint(
        url: str,
        method: str = "GET",
        headers: str = "",
        body: str = "",
        expected_status: int = 0,
        path: str = "",
    ) -> dict:
        """
        Test a single API endpoint.

        Makes an HTTP request and validates the response.

        Args:
            url: Full URL to test
            method: HTTP method (GET, POST, PUT, DELETE)
            headers: Comma-separated headers (key:value,key:value)
            body: Request body (JSON string)
            expected_status: Expected status code (0 for any)
            path: Project path

        Returns:
            Test result:
            - status_code: HTTP status
            - response_time_ms: Response time
            - passed: If test passed
            - errors: Any validation errors

        Example:
            {"url": "https://api.example.com/health"}
            {"url": "https://api.example.com/users", "method": "POST", "expected_status": 201}
        """
        return await api_test(
            url=url, method=method, headers=headers,
            body=body, expected_status=expected_status, path=path
        )

    @mcp_server.tool()
    async def api_health_check(url: str, path: str = "") -> dict:
        """
        Check health of an API endpoint.

        Performs comprehensive health check including
        status code, response time, and health data parsing.

        Args:
            url: Health endpoint URL
            path: Project path

        Returns:
            Health status:
            - healthy: Overall health status
            - checks_passed: Passed health checks
            - checks_failed: Failed health checks
            - health_data: Parsed health response

        Example:
            {"url": "https://api.example.com/health"}
        """
        return await api_health(url=url, path=path)

    @mcp_server.tool()
    async def api_discover_endpoints(path: str = "") -> dict:
        """
        Discover API endpoints from project.

        Scans for OpenAPI specs, route files, and
        common API patterns.

        Args:
            path: Project path

        Returns:
            Discovered endpoints:
            - count: Number of endpoints found
            - endpoints: List of endpoint definitions

        Example:
            {}
        """
        return await api_discover(path=path)

    @mcp_server.tool()
    async def api_run_test_suite(endpoints: str, path: str = "") -> dict:
        """
        Test multiple API endpoints.

        Runs tests against multiple endpoints and
        reports aggregate results.

        Args:
            endpoints: JSON array of endpoints or comma-separated URLs
            path: Project path

        Returns:
            Test suite results:
            - total: Total tests
            - passed: Passed tests
            - failed: Failed tests
            - success_rate: Pass percentage

        Example:
            {"endpoints": "https://api.example.com/health,https://api.example.com/status"}
        """
        return await api_test_suite(endpoints=endpoints, path=path)

    return [
        "api_test_endpoint",
        "api_health_check",
        "api_discover_endpoints",
        "api_run_test_suite",
    ]
