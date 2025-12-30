"""
Index Status Tool.

MCP tool for checking the status of the semantic index.
"""

from pathlib import Path

from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)


class IndexStatusTool(Tool):
    """
    Get the status of the semantic code index.

    Shows statistics about indexed files, chunks, and storage.
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="index_status",
                description=(
                    "Get the status of the semantic code index. "
                    "Shows statistics about indexed files, chunks, embedding provider, and storage size."
                ),
                category=ToolCategory.AI,
                version="1.0.0",
            ),
            parameters=[
                ToolParameter(
                    name="directory",
                    type="string",
                    description="Directory containing the index. Defaults to current directory.",
                    required=False,
                ),
            ],
        )

    async def execute(
        self,
        directory: str | None = None,
        **kwargs,
    ) -> ToolResult:
        """Get index status."""
        try:
            from fastband.embeddings.storage.sqlite import SQLiteVectorStore

            # Resolve directory
            if directory:
                dir_path = Path(directory).resolve()
            else:
                dir_path = Path.cwd()

            # Check for index
            storage_path = dir_path / ".fastband" / "semantic.db"
            if not storage_path.exists():
                return ToolResult(
                    success=True,
                    data={
                        "indexed": False,
                        "message": f"No index found at {storage_path}",
                        "directory": str(dir_path),
                    },
                )

            # Get stats from store
            store = SQLiteVectorStore(path=storage_path)

            try:
                stats = store.get_stats()

                # Format size
                if stats.size_bytes < 1024:
                    size_str = f"{stats.size_bytes} B"
                elif stats.size_bytes < 1024 * 1024:
                    size_str = f"{stats.size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{stats.size_bytes / (1024 * 1024):.1f} MB"

                return ToolResult(
                    success=True,
                    data={
                        "indexed": True,
                        "directory": str(dir_path),
                        "storage_path": str(storage_path),
                        "total_chunks": stats.total_chunks,
                        "total_files": stats.total_files,
                        "dimensions": stats.dimensions,
                        "provider": stats.provider,
                        "model": stats.model,
                        "last_updated": stats.last_updated,
                        "storage_size": size_str,
                        "storage_size_bytes": stats.size_bytes,
                    },
                )

            finally:
                store.close()

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get index status: {e}",
            )
