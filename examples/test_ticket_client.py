#!/usr/bin/env python3
"""
Test client for the Custom Ticket Server.

Run the server first:
    python custom_ticket_server.py

Then in another terminal:
    python test_ticket_client.py
"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    print("🔌 Connecting to Custom Ticket Server...\n")

    import os
    import sys

    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, "custom_ticket_server.py")
    src_path = os.path.join(os.path.dirname(script_dir), "src")

    # Build environment with PYTHONPATH
    env = os.environ.copy()
    env["PYTHONPATH"] = src_path

    server_params = StdioServerParameters(
        command=sys.executable,  # Use the same Python as the test
        args=[server_script],
        env=env,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()

            # List tools
            tools = await session.list_tools()
            print(f"📦 Available tools: {len(tools.tools)}")
            for tool in tools.tools:
                print(f"   - {tool.name}")
            print()

            # Create some tickets
            print("📝 Creating tickets...\n")

            result = await session.call_tool(
                "create_ticket",
                arguments={
                    "title": "Implement user authentication",
                    "description": "Add JWT-based auth to the API",
                    "priority": "high",
                    "labels": ["backend", "security"]
                }
            )
            print(result.content[0].text)
            print()

            result = await session.call_tool(
                "create_ticket",
                arguments={
                    "title": "Fix login page CSS",
                    "description": "Button alignment is broken on mobile",
                    "priority": "medium",
                    "labels": ["frontend", "bug"]
                }
            )
            print(result.content[0].text)
            print()

            result = await session.call_tool(
                "create_ticket",
                arguments={
                    "title": "Update dependencies",
                    "priority": "low"
                }
            )
            print(result.content[0].text)
            print()

            # List all tickets
            print("📋 Listing all tickets...\n")
            result = await session.call_tool("list_tickets", arguments={})
            print(result.content[0].text)
            print()

            # Get stats
            print("📊 Getting statistics...\n")
            result = await session.call_tool("ticket_stats", arguments={})
            print(result.content[0].text)
            print()

            # Bulk create
            print("📦 Bulk creating tickets...\n")
            result = await session.call_tool(
                "bulk_create",
                arguments={
                    "tickets": [
                        {"title": "Write unit tests", "priority": "high"},
                        {"title": "Update README", "priority": "low"},
                        {"title": "Code review", "priority": "medium"},
                    ]
                }
            )
            print(result.content[0].text)
            print()

            # Final list
            print("📋 Final ticket list...\n")
            result = await session.call_tool("list_tickets", arguments={})
            print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
