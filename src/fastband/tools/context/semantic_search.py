"""
Semantic Search Tool.

MCP tool for searching indexed code using natural language queries.
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


class SemanticSearchTool(Tool):
    """
    Search indexed code using natural language.

    Finds code chunks that are semantically similar to the query,
    even if they don't contain exact keyword matches.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="semantic_search",
                description=(
                    "Search indexed code using natural language. "
                    "Finds relevant functions, classes, and code blocks "
                    "based on semantic similarity to your query."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Natural language search query (e.g., 'authentication logic', 'database connection handling')",
                    required=True,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of results to return (default: 5)",
                    required=False,
                    default=5,
                ),
                ToolParameter(
                    name="file_type",
                    type="string",
                    description="Filter by file type (e.g., 'py', 'js', 'ts')",
                    required=False,
                ),
                ToolParameter(
                    name="file_pattern",
                    type="string",
                    description="Filter by file path pattern (e.g., 'src/auth')",
                    required=False,
                ),
                ToolParameter(
                    name="directory",
                    type="string",
                    description="Directory containing the index. Defaults to current directory.",
                    required=False,
                ),
                ToolParameter(
                    name="provider",
                    type="string",
                    description="Embedding provider (must match the one used for indexing)",
                    required=False,
                    default="openai",
                    enum=["openai", "gemini", "ollama"],
                ),
            ],
        )

    async def execute(
        self,
        query: str,
        limit: int = 5,
        file_type: str | None = None,
        file_pattern: str | None = None,
        directory: str | None = None,
        provider: str = "openai",
        **kwargs,
    ) -> ToolResult:
        """Execute the semantic search."""
        try:
            from fastband.embeddings.index import create_index

            # Resolve directory
            if directory:
                dir_path = Path(directory).resolve()
            else:
                dir_path = Path.cwd()

            # Check for index
            storage_path = dir_path / ".fastband" / "semantic.db"
            if not storage_path.exists():
                return ToolResult(
                    success=False,
                    error=(
                        f"No index found at {storage_path}. "
                        "Run index_codebase first to create an index."
                    ),
                )

            # Build provider kwargs
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
                base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
                provider_kwargs["base_url"] = base_url

            # Create index instance
            index = create_index(
                provider_name=provider,
                storage_path=storage_path,
                **provider_kwargs,
            )

            try:
                # Perform search
                results = await index.search(
                    query=query,
                    limit=limit,
                    file_type=file_type,
                    file_path_pattern=file_pattern,
                )

                # Format results
                formatted_results = []
                for result in results:
                    formatted_results.append(
                        {
                            "file": result.metadata.file_path,
                            "name": result.metadata.name,
                            "type": result.metadata.chunk_type.value,
                            "lines": f"{result.metadata.start_line}-{result.metadata.end_line}",
                            "score": round(result.score, 4),
                            "docstring": result.metadata.docstring[:200]
                            if result.metadata.docstring
                            else None,
                            "content_preview": result.content[:500] + "..."
                            if len(result.content) > 500
                            else result.content,
                        }
                    )

                return ToolResult(
                    success=True,
                    data={
                        "query": query,
                        "total_results": len(formatted_results),
                        "results": formatted_results,
                    },
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
                error=f"Search failed: {e}",
            )
