"""
Index Codebase Tool.

MCP tool for indexing a codebase for semantic search.
"""

import os
from pathlib import Path

from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)


class IndexCodebaseTool(Tool):
    """
    Index a codebase for semantic search.

    Creates semantic embeddings of code chunks and stores them
    in a vector database for fast similarity search.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="index_codebase",
                description=(
                    "Index a directory of code files for semantic search. "
                    "Creates embeddings of functions, classes, and code blocks "
                    "that can be searched using natural language queries."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="directory",
                    type="string",
                    description="Path to the directory to index. Defaults to current directory.",
                    required=False,
                ),
                ToolParameter(
                    name="provider",
                    type="string",
                    description="Embedding provider to use: openai, gemini, or ollama",
                    required=False,
                    default="openai",
                    enum=["openai", "gemini", "ollama"],
                ),
                ToolParameter(
                    name="incremental",
                    type="boolean",
                    description="Only re-index changed files (default: true)",
                    required=False,
                    default=True,
                ),
                ToolParameter(
                    name="clear",
                    type="boolean",
                    description="Clear existing index before indexing",
                    required=False,
                    default=False,
                ),
            ],
        )

    async def execute(
        self,
        directory: str | None = None,
        provider: str = "openai",
        incremental: bool = True,
        clear: bool = False,
        **kwargs,
    ) -> ToolResult:
        """Execute the indexing operation."""
        try:
            from fastband.embeddings.index import create_index

            # Resolve directory
            if directory:
                dir_path = Path(directory).resolve()
            else:
                dir_path = Path.cwd()

            if not dir_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {dir_path}",
                )

            if not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Not a directory: {dir_path}",
                )

            # Create storage path in .fastband
            storage_path = dir_path / ".fastband" / "semantic.db"
            storage_path.parent.mkdir(parents=True, exist_ok=True)

            # Build provider kwargs based on environment
            provider_kwargs = {}
            if provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return ToolResult(
                        success=False,
                        error="OPENAI_API_KEY environment variable not set",
                    )
                provider_kwargs["api_key"] = api_key

            elif provider == "gemini":
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
                if not api_key:
                    return ToolResult(
                        success=False,
                        error="GOOGLE_API_KEY or GEMINI_API_KEY environment variable not set",
                    )
                provider_kwargs["api_key"] = api_key

            elif provider == "ollama":
                # Ollama doesn't require API key
                base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
                provider_kwargs["base_url"] = base_url

            # Create index
            index = create_index(
                provider_name=provider,
                storage_path=storage_path,
                **provider_kwargs,
            )

            try:
                # Clear if requested
                if clear:
                    index.clear()

                # Index directory
                result = await index.index_directory(
                    directory=dir_path,
                    incremental=incremental,
                )

                return ToolResult(
                    success=result.success,
                    data={
                        "directory": str(dir_path),
                        "provider": provider,
                        "chunks_indexed": result.chunks_indexed,
                        "files_processed": result.files_processed,
                        "files_skipped": result.files_skipped,
                        "duration_seconds": result.duration_seconds,
                        "incremental": incremental,
                        "storage_path": str(storage_path),
                        "errors": result.errors if result.errors else None,
                    },
                    error=result.errors[0] if result.errors and not result.success else None,
                )

            finally:
                index.close()

        except ImportError as e:
            return ToolResult(
                success=False,
                error=f"Missing dependency: {e}. Install with: pip install fastband-mcp[{provider}]",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Indexing failed: {e}",
            )
