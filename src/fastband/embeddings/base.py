"""
Base classes for the embeddings module.

Provides abstract interfaces and data classes used across the embeddings system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
import hashlib


class ChunkType(Enum):
    """Type of code chunk."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    BLOCK = "block"
    FILE = "file"


@dataclass(slots=True)
class ChunkMetadata:
    """
    Metadata for a code chunk.

    Contains all the rich context about a chunk needed for
    filtering and display in search results.
    """
    file_path: str
    chunk_type: ChunkType
    start_line: int
    end_line: int
    name: Optional[str] = None  # Function/class name
    docstring: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    parent_name: Optional[str] = None  # e.g., class name for methods
    file_type: str = "unknown"
    last_modified: Optional[datetime] = None
    chunk_hash: Optional[str] = None  # For change detection

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "chunk_type": self.chunk_type.value,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "name": self.name,
            "docstring": self.docstring,
            "imports": self.imports,
            "parent_name": self.parent_name,
            "file_type": self.file_type,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "chunk_hash": self.chunk_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkMetadata":
        """Create from dictionary."""
        return cls(
            file_path=data["file_path"],
            chunk_type=ChunkType(data["chunk_type"]),
            start_line=data["start_line"],
            end_line=data["end_line"],
            name=data.get("name"),
            docstring=data.get("docstring"),
            imports=data.get("imports", []),
            parent_name=data.get("parent_name"),
            file_type=data.get("file_type", "unknown"),
            last_modified=datetime.fromisoformat(data["last_modified"]) if data.get("last_modified") else None,
            chunk_hash=data.get("chunk_hash"),
        )


@dataclass(slots=True)
class CodeChunk:
    """
    A chunk of code ready for embedding.

    Contains both the content to embed and its metadata.
    """
    content: str
    metadata: ChunkMetadata

    @property
    def chunk_id(self) -> str:
        """Generate a unique ID for this chunk."""
        # Combine file path and line range for uniqueness
        key = f"{self.metadata.file_path}:{self.metadata.start_line}-{self.metadata.end_line}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def compute_hash(self) -> str:
        """Compute content hash for change detection."""
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]


@dataclass(slots=True)
class EmbeddingConfig:
    """Configuration for an embedding provider."""
    api_key: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    dimensions: Optional[int] = None  # Output dimensions (for providers that support it)
    batch_size: int = 100  # Max texts per API call
    timeout: int = 60
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingResult:
    """Result from an embedding operation."""
    embeddings: List[List[float]]
    model: str
    provider: str
    dimensions: int
    usage: Dict[str, int]  # token counts


class EmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.

    All embedding providers (OpenAI, Gemini, Ollama) implement this interface
    for consistent embedding generation across the platform.

    Example:
        class MyProvider(EmbeddingProvider):
            async def embed(self, texts: List[str]) -> EmbeddingResult:
                # Call embedding API
                return EmbeddingResult(...)
    """

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self._validate_config()

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider-specific configuration."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return provider name (openai, gemini, ollama)."""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default embedding model for this provider."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions for the current model."""
        pass

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            EmbeddingResult with embedding vectors and metadata

        Note:
            Implementations should handle batching internally if the
            provider has limits on texts per request.
        """
        pass

    async def embed_single(self, text: str) -> List[float]:
        """
        Embed a single text string.

        Convenience method that wraps embed() for single texts.

        Args:
            text: Text string to embed

        Returns:
            Single embedding vector
        """
        result = await self.embed([text])
        return result.embeddings[0]
