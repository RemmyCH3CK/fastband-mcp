#!/usr/bin/env python3
"""
Custom Tool Example - Creating and registering custom Fastband tools.

This script demonstrates how to create custom tools that integrate
with the Fastband MCP ecosystem.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Fastband imports
from fastband.core.engine import FastbandEngine
from fastband.tools.base import (
    Tool,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolCategory,
    ToolResult,
)


console = Console()


# =============================================================================
# Custom Tool: Project Summary
# =============================================================================


class ProjectSummaryTool(Tool):
    """
    Custom tool that generates a project summary.

    This demonstrates how to create a custom tool with:
    - Proper definition with parameters
    - Async execution
    - Structured result handling
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="project_summary",
                description="Generate a summary of the project structure and contents",
                category=ToolCategory.PROJECT,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Project directory path",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="include_size",
                    type="boolean",
                    description="Include file sizes in summary",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(
        self,
        path: str = ".",
        include_size: bool = True,
        **kwargs
    ) -> ToolResult:
        """Execute the project summary tool."""
        target = Path(path).resolve()

        if not target.exists():
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        if not target.is_dir():
            return ToolResult(success=False, error=f"Path is not a directory: {path}")

        try:
            # Collect statistics
            stats = {
                "directories": 0,
                "files": 0,
                "total_size": 0,
                "by_extension": {},
            }

            for item in target.rglob("*"):
                # Skip hidden files and directories
                if any(part.startswith(".") for part in item.parts):
                    continue

                if item.is_dir():
                    stats["directories"] += 1
                elif item.is_file():
                    stats["files"] += 1
                    if include_size:
                        stats["total_size"] += item.stat().st_size

                    ext = item.suffix.lower() or "(no extension)"
                    if ext not in stats["by_extension"]:
                        stats["by_extension"][ext] = {"count": 0, "size": 0}
                    stats["by_extension"][ext]["count"] += 1
                    if include_size:
                        stats["by_extension"][ext]["size"] += item.stat().st_size

            # Find key project files
            key_files = []
            for name in ["README.md", "pyproject.toml", "package.json", "Cargo.toml", "go.mod"]:
                if (target / name).exists():
                    key_files.append(name)

            return ToolResult(
                success=True,
                data={
                    "path": str(target),
                    "name": target.name,
                    "directories": stats["directories"],
                    "files": stats["files"],
                    "total_size_bytes": stats["total_size"],
                    "total_size_human": self._format_size(stats["total_size"]),
                    "by_extension": stats["by_extension"],
                    "key_files": key_files,
                    "analyzed_at": datetime.now().isoformat(),
                },
            )

        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _format_size(self, size_bytes: int) -> str:
        """Format size in human-readable form."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


# =============================================================================
# Custom Tool: TODO Finder
# =============================================================================


class TodoFinderTool(Tool):
    """
    Custom tool that finds TODO comments in code.

    Demonstrates a more complex tool with multiple parameters
    and structured output.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="find_todos",
                description="Find TODO, FIXME, and NOTE comments in code",
                category=ToolCategory.PROJECT,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Directory to search",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="file_pattern",
                    type="string",
                    description="Glob pattern for files to search",
                    required=False,
                    default="*.py",
                ),
                ToolParameter(
                    name="patterns",
                    type="array",
                    description="Comment patterns to find",
                    required=False,
                    default=["TODO", "FIXME", "NOTE", "HACK"],
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum results to return",
                    required=False,
                    default=50,
                ),
            ],
        )

    async def execute(
        self,
        path: str = ".",
        file_pattern: str = "*.py",
        patterns: List[str] = None,
        max_results: int = 50,
        **kwargs
    ) -> ToolResult:
        """Find TODO-style comments in code."""
        target = Path(path).resolve()
        patterns = patterns or ["TODO", "FIXME", "NOTE", "HACK"]

        if not target.exists():
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        todos = []
        files_searched = 0

        try:
            for file_path in target.rglob(file_pattern):
                if not file_path.is_file():
                    continue

                # Skip hidden directories
                if any(part.startswith(".") for part in file_path.parts):
                    continue

                files_searched += 1

                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        for line_num, line in enumerate(f, 1):
                            for pattern in patterns:
                                if pattern in line:
                                    todos.append({
                                        "file": str(file_path.relative_to(target)),
                                        "line": line_num,
                                        "pattern": pattern,
                                        "text": line.strip(),
                                    })

                                    if len(todos) >= max_results:
                                        break

                        if len(todos) >= max_results:
                            break
                except Exception:
                    continue

                if len(todos) >= max_results:
                    break

            # Group by pattern
            by_pattern = {}
            for todo in todos:
                p = todo["pattern"]
                if p not in by_pattern:
                    by_pattern[p] = 0
                by_pattern[p] += 1

            return ToolResult(
                success=True,
                data={
                    "path": str(target),
                    "file_pattern": file_pattern,
                    "patterns_searched": patterns,
                    "files_searched": files_searched,
                    "total_found": len(todos),
                    "by_pattern": by_pattern,
                    "todos": todos,
                    "truncated": len(todos) >= max_results,
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))


# =============================================================================
# Demo
# =============================================================================


async def main():
    """Demonstrate custom tool creation and usage."""

    console.print(Panel.fit(
        "[bold blue]Fastband MCP - Custom Tool Demo[/bold blue]\n"
        "[dim]Creating and using custom tools[/dim]",
        border_style="blue",
    ))

    # Create engine
    engine = FastbandEngine(project_path=Path.cwd())
    engine.register_core_tools()

    # Register custom tools
    console.print("\n[bold]Registering custom tools...[/bold]")

    project_summary_tool = ProjectSummaryTool()
    todo_finder_tool = TodoFinderTool()

    engine.register_tool(project_summary_tool)
    engine.register_tool(todo_finder_tool)

    console.print(f"[green]Registered: {project_summary_tool.name}[/green]")
    console.print(f"[green]Registered: {todo_finder_tool.name}[/green]")

    # Use project_summary tool
    console.print("\n[bold]Using project_summary tool:[/bold]")
    console.print("-" * 40)

    result = await engine.execute_tool("project_summary", path=".")

    if result.success:
        data = result.data
        table = Table(show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Project", data["name"])
        table.add_row("Directories", str(data["directories"]))
        table.add_row("Files", str(data["files"]))
        table.add_row("Total Size", data["total_size_human"])

        if data["key_files"]:
            table.add_row("Key Files", ", ".join(data["key_files"]))

        console.print(table)

        # Top extensions
        if data["by_extension"]:
            console.print("\n[bold]Top file types:[/bold]")
            sorted_exts = sorted(
                data["by_extension"].items(),
                key=lambda x: x[1]["count"],
                reverse=True,
            )[:5]
            for ext, info in sorted_exts:
                console.print(f"  {ext}: {info['count']} files")
    else:
        console.print(f"[red]Error: {result.error}[/red]")

    # Use find_todos tool
    console.print("\n[bold]Using find_todos tool:[/bold]")
    console.print("-" * 40)

    result = await engine.execute_tool(
        "find_todos",
        path=".",
        file_pattern="*.py",
        max_results=10,
    )

    if result.success:
        data = result.data
        console.print(f"Searched {data['files_searched']} files")
        console.print(f"Found {data['total_found']} TODOs/FIXMEs\n")

        if data["todos"]:
            for todo in data["todos"][:5]:
                console.print(f"[cyan]{todo['file']}:{todo['line']}[/cyan]")
                console.print(f"  [{todo['pattern']}] {todo['text'][:60]}...")
                console.print()
    else:
        console.print(f"[red]Error: {result.error}[/red]")

    # Show that custom tools are available in schemas
    console.print("[bold]Custom tools in MCP schema:[/bold]")
    console.print("-" * 40)

    schemas = engine.get_tool_schemas()
    custom_names = ["project_summary", "find_todos"]

    for schema in schemas:
        if schema["name"] in custom_names:
            console.print(f"[green]{schema['name']}[/green]: {schema['description']}")

    console.print("\n[dim]Custom tools are now available for AI clients![/dim]")


if __name__ == "__main__":
    asyncio.run(main())
