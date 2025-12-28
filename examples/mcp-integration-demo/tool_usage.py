#!/usr/bin/env python3
"""
Tool Usage Example - Direct Fastband tool execution.

This script demonstrates how to use Fastband tools programmatically
without going through an AI provider.
"""

import asyncio
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

# Fastband imports
from fastband.core.engine import FastbandEngine


console = Console()


async def main():
    """Demonstrate direct tool usage."""

    console.print(Panel.fit(
        "[bold blue]Fastband MCP - Tool Usage Demo[/bold blue]",
        border_style="blue",
    ))

    # Create and configure engine
    engine = FastbandEngine(project_path=Path.cwd())
    engine.register_core_tools()

    console.print(f"\n[green]Loaded {len(engine.registry.get_active_tools())} tools[/green]\n")

    # Example 1: List files
    console.print("[bold]Example 1: List Files[/bold]")
    console.print("-" * 40)

    result = await engine.execute_tool(
        "list_files",
        path=".",
        pattern="*.py",
        max_depth=2,
    )

    if result.success:
        files = result.data.get("files", [])
        console.print(f"Found {len(files)} Python files:")
        for f in files[:5]:
            console.print(f"  - {f['path']}")
        if len(files) > 5:
            console.print(f"  ... and {len(files) - 5} more")
    else:
        console.print(f"[red]Error: {result.error}[/red]")

    # Example 2: Read a file
    console.print("\n[bold]Example 2: Read File[/bold]")
    console.print("-" * 40)

    result = await engine.execute_tool(
        "read_file",
        path="tool_usage.py",
        limit=10,
    )

    if result.success:
        console.print(f"Read {result.data['lines_returned']} lines from tool_usage.py:")
        content = result.data["content"]
        syntax = Syntax(content, "python", line_numbers=True, start_line=1)
        console.print(syntax)
    else:
        console.print(f"[red]Error: {result.error}[/red]")

    # Example 3: Search code
    console.print("\n[bold]Example 3: Search Code[/bold]")
    console.print("-" * 40)

    result = await engine.execute_tool(
        "search_code",
        pattern="def.*main",
        path=".",
        file_pattern="*.py",
        max_results=5,
    )

    if result.success:
        matches = result.data.get("matches", [])
        console.print(f"Found {len(matches)} matches for 'def.*main':")
        for match in matches:
            console.print(f"  - {match['file']}:{match['line']}")
            console.print(f"    {match['match']}")
    else:
        console.print(f"[red]Error: {result.error}[/red]")

    # Example 4: Get tool schemas
    console.print("\n[bold]Example 4: Tool Schemas[/bold]")
    console.print("-" * 40)

    schemas = engine.get_tool_schemas()
    console.print(f"Available tools ({len(schemas)}):")
    for schema in schemas[:5]:
        console.print(f"  - {schema['name']}: {schema['description'][:50]}...")

    console.print("\n[dim]Demo complete![/dim]")


if __name__ == "__main__":
    asyncio.run(main())
