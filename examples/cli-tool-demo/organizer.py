#!/usr/bin/env python3
"""
File Organizer CLI - Demo application for Fastband MCP.

A simple command-line tool that organizes files by extension.
This demonstrates how to structure a CLI tool that can be developed
with Fastband MCP ticket management.
"""

import typer
from pathlib import Path
from typing import Optional
from collections import defaultdict
import shutil

from rich.console import Console
from rich.table import Table
from rich import box

app = typer.Typer(
    name="organizer",
    help="File organizer CLI - organize files by extension",
    no_args_is_help=True,
)

console = Console()


# =============================================================================
# File Type Categories
# =============================================================================

FILE_CATEGORIES = {
    "documents": [".txt", ".pdf", ".doc", ".docx", ".md", ".rst", ".odt"],
    "images": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"],
    "code": [".py", ".js", ".ts", ".java", ".cpp", ".c", ".go", ".rs", ".rb"],
    "data": [".json", ".yaml", ".yml", ".xml", ".csv", ".toml"],
    "archives": [".zip", ".tar", ".gz", ".rar", ".7z"],
    "audio": [".mp3", ".wav", ".flac", ".ogg", ".m4a"],
    "video": [".mp4", ".mkv", ".avi", ".mov", ".webm"],
}


def get_category(extension: str) -> str:
    """Get the category for a file extension."""
    ext_lower = extension.lower()
    for category, extensions in FILE_CATEGORIES.items():
        if ext_lower in extensions:
            return category
    return "other"


# =============================================================================
# Commands
# =============================================================================


@app.command()
def list(
    directory: Path = typer.Argument(
        ...,
        help="Directory to list files from",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Include subdirectories",
    ),
    show_hidden: bool = typer.Option(
        False,
        "--hidden",
        "-a",
        help="Show hidden files",
    ),
):
    """
    List files in a directory.

    Shows files grouped by their extension category.
    """
    files = _collect_files(directory, recursive, show_hidden)

    if not files:
        console.print(f"[yellow]No files found in {directory}[/yellow]")
        return

    # Group by category
    by_category = defaultdict(list)
    for file in files:
        category = get_category(file.suffix)
        by_category[category].append(file)

    # Display table
    table = Table(
        title=f"Files in {directory}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Files")

    for category in sorted(by_category.keys()):
        files_in_cat = by_category[category]
        file_names = ", ".join(f.name for f in files_in_cat[:5])
        if len(files_in_cat) > 5:
            file_names += f" (+{len(files_in_cat) - 5} more)"
        table.add_row(category, str(len(files_in_cat)), file_names)

    console.print(table)
    console.print(f"\n[dim]Total: {len(files)} files[/dim]")


@app.command()
def organize(
    directory: Path = typer.Argument(
        ...,
        help="Directory to organize",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: organized/ in source directory)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without moving files",
    ),
    copy: bool = typer.Option(
        False,
        "--copy",
        "-c",
        help="Copy files instead of moving them",
    ),
):
    """
    Organize files by extension category.

    Creates subdirectories for each category and moves/copies files.
    """
    files = _collect_files(directory, recursive=False, include_hidden=False)

    if not files:
        console.print(f"[yellow]No files to organize in {directory}[/yellow]")
        return

    output_dir = output or (directory / "organized")

    # Group by category
    by_category = defaultdict(list)
    for file in files:
        category = get_category(file.suffix)
        by_category[category].append(file)

    action = "copy" if copy else "move"

    if dry_run:
        console.print(f"[bold]Dry run - would {action}:[/bold]\n")

    for category, cat_files in sorted(by_category.items()):
        category_dir = output_dir / category

        if dry_run:
            console.print(f"[cyan]{category}/[/cyan] ({len(cat_files)} files)")
            for f in cat_files:
                console.print(f"  - {f.name}")
        else:
            category_dir.mkdir(parents=True, exist_ok=True)
            for f in cat_files:
                dest = category_dir / f.name
                if copy:
                    shutil.copy2(f, dest)
                else:
                    shutil.move(str(f), dest)

    if not dry_run:
        total = sum(len(f) for f in by_category.values())
        console.print(f"[green]Organized {total} files into {len(by_category)} categories[/green]")


@app.command()
def stats(
    directory: Path = typer.Argument(
        ...,
        help="Directory to analyze",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="Include subdirectories",
    ),
):
    """
    Show file statistics for a directory.

    Displays size, count, and extension breakdown.
    """
    files = _collect_files(directory, recursive, include_hidden=False)

    if not files:
        console.print(f"[yellow]No files found in {directory}[/yellow]")
        return

    # Calculate statistics
    total_size = sum(f.stat().st_size for f in files)
    by_extension = defaultdict(lambda: {"count": 0, "size": 0})

    for file in files:
        ext = file.suffix.lower() or "(no extension)"
        by_extension[ext]["count"] += 1
        by_extension[ext]["size"] += file.stat().st_size

    # Display stats
    console.print(f"\n[bold]Directory Statistics: {directory}[/bold]\n")

    # Summary
    console.print(f"Total files: [green]{len(files)}[/green]")
    console.print(f"Total size: [green]{_format_size(total_size)}[/green]")
    console.print(f"Extensions: [green]{len(by_extension)}[/green]")

    # Extension breakdown
    table = Table(
        title="\nBy Extension",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Extension", style="cyan")
    table.add_column("Count", style="green", justify="right")
    table.add_column("Size", style="yellow", justify="right")
    table.add_column("% of Total", justify="right")

    sorted_exts = sorted(
        by_extension.items(),
        key=lambda x: x[1]["size"],
        reverse=True,
    )

    for ext, data in sorted_exts[:15]:  # Top 15 extensions
        pct = (data["size"] / total_size * 100) if total_size > 0 else 0
        table.add_row(
            ext,
            str(data["count"]),
            _format_size(data["size"]),
            f"{pct:.1f}%",
        )

    if len(by_extension) > 15:
        table.add_row(
            f"... +{len(by_extension) - 15} more",
            "",
            "",
            "",
        )

    console.print(table)


# =============================================================================
# Helper Functions
# =============================================================================


def _collect_files(
    directory: Path,
    recursive: bool,
    include_hidden: bool,
) -> list[Path]:
    """Collect files from a directory."""
    files = []

    if recursive:
        iterator = directory.rglob("*")
    else:
        iterator = directory.iterdir()

    for item in iterator:
        if not item.is_file():
            continue
        if not include_hidden and item.name.startswith("."):
            continue
        files.append(item)

    return files


def _format_size(size_bytes: int) -> str:
    """Format size in human-readable form."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


# =============================================================================
# Entry Point
# =============================================================================


if __name__ == "__main__":
    app()
