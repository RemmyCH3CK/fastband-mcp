#!/usr/bin/env python3
"""
AI Assistant Example - Using Fastband tools with an AI provider.

This script demonstrates how to build an AI assistant that can use
Fastband tools for file operations and code assistance.

Prerequisites:
- Set ANTHROPIC_API_KEY environment variable
"""

import asyncio
import os
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Fastband imports
from fastband.core.engine import FastbandEngine

console = Console()


async def run_assistant():
    """Run the AI assistant with Fastband tools."""

    console.print(Panel.fit(
        "[bold blue]Fastband MCP - AI Assistant Demo[/bold blue]\n"
        "[dim]An AI assistant that can read and analyze your code[/dim]",
        border_style="blue",
    ))

    # Check for API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("\n[yellow]Note: ANTHROPIC_API_KEY not set[/yellow]")
        console.print("This demo will show the tool integration pattern.")
        console.print("Set the environment variable to enable actual AI responses.\n")
        await demo_pattern()
        return

    try:
        import anthropic
    except ImportError:
        console.print("[red]anthropic package not installed[/red]")
        console.print("Run: pip install anthropic")
        return

    # Create engine and register tools
    engine = FastbandEngine(project_path=Path.cwd())
    engine.register_core_tools()

    # Get tool schemas for Claude
    tools = engine.get_tool_schemas()

    console.print(f"\n[green]Loaded {len(tools)} tools for AI assistant[/green]\n")

    # Create Anthropic client
    client = anthropic.Anthropic(api_key=api_key)

    # Example conversation
    messages = [
        {
            "role": "user",
            "content": "Please list the Python files in this directory and briefly describe what each one does."
        }
    ]

    console.print("[bold]User:[/bold] " + messages[0]["content"])
    console.print("\n[dim]Processing...[/dim]\n")

    # Call Claude with tools
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        tools=tools,
        messages=messages,
    )

    # Handle tool calls
    while response.stop_reason == "tool_use":
        # Extract tool call
        tool_use = next(
            block for block in response.content
            if block.type == "tool_use"
        )

        console.print(f"[cyan]Using tool: {tool_use.name}[/cyan]")
        console.print(f"[dim]Arguments: {tool_use.input}[/dim]")

        # Execute the tool
        result = await engine.execute_tool(tool_use.name, **tool_use.input)

        # Prepare tool result for Claude
        if result.success:
            tool_result = str(result.data)
        else:
            tool_result = f"Error: {result.error}"

        # Continue conversation with tool result
        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": tool_result,
            }]
        })

        # Get next response
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            tools=tools,
            messages=messages,
        )

    # Display final response
    final_text = "".join(
        block.text for block in response.content
        if hasattr(block, "text")
    )

    console.print("\n[bold]Assistant:[/bold]")
    console.print(Markdown(final_text))


async def demo_pattern():
    """Demonstrate the integration pattern without making API calls."""

    console.print("[bold]Integration Pattern Demo[/bold]\n")

    # Create engine
    engine = FastbandEngine(project_path=Path.cwd())
    engine.register_core_tools()

    # Get schemas
    schemas = engine.get_tool_schemas()

    console.print("1. [cyan]Get tool schemas for AI provider:[/cyan]")
    console.print(f"   Found {len(schemas)} tools")

    console.print("\n2. [cyan]AI decides to use a tool (simulated):[/cyan]")
    console.print("   Tool: list_files")
    console.print('   Args: {"path": ".", "pattern": "*.py"}')

    console.print("\n3. [cyan]Execute the tool:[/cyan]")
    result = await engine.execute_tool("list_files", path=".", pattern="*.py")
    if result.success:
        console.print(f"   Found {len(result.data.get('files', []))} Python files")
    else:
        console.print(f"   Error: {result.error}")

    console.print("\n4. [cyan]Return result to AI for response generation[/cyan]")
    console.print("   The AI would then format this into a natural response.")

    console.print("\n[dim]See the full code for the complete pattern.[/dim]")


if __name__ == "__main__":
    asyncio.run(run_assistant())
