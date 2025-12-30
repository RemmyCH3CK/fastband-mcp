"""
Ollama embedding provider.

Uses Ollama for local embedding generation.
Supports nomic-embed-text, all-minilm, mxbai-embed-large, and other models.
"""

import logging
import os
from collections.abc import Sequence

from fastband.embeddings.base import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
)

logger = logging.getLogger(__name__)

# Model dimensions (approximate, varies by model)
OLLAMA_MODELS = {
    "nomic-embed-text": 768,
    "all-minilm": 384,
    "mxbai-embed-large": 1024,
    "snowflake-arctic-embed": 1024,
}


class OllamaEmbeddings(EmbeddingProvider):
    """
    Ollama embedding provider for local embeddings.

    Uses Ollama's embedding API for fully local, private embeddings.
    No data leaves your machine.

    Example:
        provider = OllamaEmbeddings(EmbeddingConfig(
            base_url="http://localhost:11434",
            model="nomic-embed-text",
        ))

        result = await provider.embed(["Hello, world!"])
    """

    def __init__(self, config: EmbeddingConfig | None = None):
        if config is None:
            config = EmbeddingConfig()
        super().__init__(config)
        self._client = None

    def _validate_config(self) -> None:
        """Validate Ollama-specific configuration."""
        if not self.config.base_url:
            self.config.base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")

        if not self.config.model:
            self.config.model = "nomic-embed-text"

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def default_model(self) -> str:
        return "nomic-embed-text"

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions for current model."""
        return OLLAMA_MODELS.get(self.config.model, 768)

    @property
    def client(self):
        """Lazy-load the Ollama client."""
        if self._client is None:
            try:
                from ollama import AsyncClient

                self._client = AsyncClient(host=self.config.base_url)
            except ImportError:
                raise ImportError(
                    "ollama package is required for Ollama embeddings. "
                    "Install with: pip install fastband-mcp[ollama]"
                )
        return self._client

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        """
        Generate embeddings for texts using Ollama.

        Args:
            texts: List of text strings to embed

        Returns:
            EmbeddingResult with embedding vectors
        """
        if not texts:
            return self._empty_result()

        texts_list = list(texts)
        all_embeddings = []

        # Ollama processes one at a time (as of current version)
        for text in texts_list:
            response = await self.client.embeddings(
                model=self.config.model,
                prompt=text,
            )
            all_embeddings.append(response["embedding"])

        estimated_tokens = self._estimate_tokens(texts_list)
        return EmbeddingResult(
            embeddings=all_embeddings,
            model=self.config.model,
            provider=self.name,
            dimensions=len(all_embeddings[0]) if all_embeddings else self.dimensions,
            usage={
                "prompt_tokens": estimated_tokens,
                "total_tokens": estimated_tokens,
            },
        )
