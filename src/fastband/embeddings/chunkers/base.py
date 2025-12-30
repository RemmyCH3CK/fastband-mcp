"""
Base chunker interface.

Defines the abstract interface for code chunkers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from fastband.embeddings.base import CodeChunk


@dataclass
class ChunkerConfig:
    """Configuration for chunkers."""

    max_chunk_size: int = 2000  # Max tokens per chunk
    min_chunk_size: int = 50  # Min tokens per chunk
    overlap: int = 100  # Overlap between chunks
    include_imports: bool = True
    include_docstrings: bool = True
    exclude_patterns: set[str] = field(
        default_factory=lambda: {
            "__pycache__",
            ".git",
            ".venv",
            "node_modules",
            ".pytest_cache",
            "*.pyc",
            "*.pyo",
            "*.egg-info",
            "dist",
            "build",
        }
    )
    include_extensions: set[str] = field(
        default_factory=lambda: {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".md",
            ".rst",
            ".txt",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
        }
    )


class Chunker(ABC):
    """
    Abstract base class for code chunkers.

    Chunkers split source code files into smaller pieces suitable
    for embedding. Different strategies balance semantic coherence
    against token limits.

    Example:
        class MyChunker(Chunker):
            def chunk_file(self, path: Path, content: str) -> List[CodeChunk]:
                # Split content into chunks
                return [CodeChunk(...), ...]
    """

    def __init__(self, config: ChunkerConfig | None = None):
        self.config = config or ChunkerConfig()

    @abstractmethod
    def chunk_file(self, path: Path, content: str) -> list[CodeChunk]:
        """
        Split a single file into chunks.

        Args:
            path: Path to the source file
            content: File content

        Returns:
            List of CodeChunk objects
        """
        pass

    def chunk_directory(
        self,
        directory: Path,
        recursive: bool = True,
    ) -> list[CodeChunk]:
        """
        Chunk all files in a directory.

        Args:
            directory: Directory to process
            recursive: Whether to process subdirectories

        Returns:
            List of all CodeChunk objects from all files
        """
        chunks = []
        directory = Path(directory)

        if recursive:
            files = directory.rglob("*")
        else:
            files = directory.glob("*")

        for file_path in files:
            if not file_path.is_file():
                continue

            # Check exclusions
            if self._should_exclude(file_path):
                continue

            # Check extensions
            if file_path.suffix not in self.config.include_extensions:
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                file_chunks = self.chunk_file(file_path, content)
                chunks.extend(file_chunks)
            except Exception as e:
                # Log and skip problematic files
                import logging

                logging.getLogger(__name__).warning(f"Failed to chunk {file_path}: {e}")

        return chunks

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded."""
        path_str = str(path)
        for pattern in self.config.exclude_patterns:
            if pattern.startswith("*"):
                # Wildcard pattern
                if path_str.endswith(pattern[1:]):
                    return True
            else:
                # Directory/name pattern
                if pattern in path.parts:
                    return True
        return False
