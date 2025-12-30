"""
OpenAI embedding provider.

Uses OpenAI's text-embedding models for generating embeddings.
Supports text-embedding-3-small, text-embedding-3-large, and ada-002.
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

# Model dimensions
OPENAI_MODELS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddings(EmbeddingProvider):
    """
    OpenAI embedding provider.

    Uses OpenAI's embedding API for generating high-quality embeddings.
    Supports the latest text-embedding-3 models.

    Example:
        provider = OpenAIEmbeddings(EmbeddingConfig(
            api_key="sk-...",
            model="text-embedding-3-small",
        ))

        result = await provider.embed(["Hello, world!"])
    """

    def __init__(self, config: EmbeddingConfig | None = None):
        if config is None:
            config = EmbeddingConfig()
        super().__init__(config)
        self._client = None

    def _validate_config(self) -> None:
        """Validate OpenAI-specific configuration."""
        if not self.config.api_key:
            self.config.api_key = os.getenv("OPENAI_API_KEY")

        if not self.config.api_key:
            raise ValueError(
                "OpenAI embeddings require OPENAI_API_KEY. "
                "Set it in config or OPENAI_API_KEY environment variable."
            )

        if not self.config.model:
            self.config.model = "text-embedding-3-small"

        if self.config.model not in OPENAI_MODELS:
            raise ValueError(
                f"Unknown model: {self.config.model}. Supported: {list(OPENAI_MODELS.keys())}"
            )

    @property
    def name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return "text-embedding-3-small"

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions for current model."""
        # Allow dimension reduction for text-embedding-3 models
        if self.config.dimensions:
            return self.config.dimensions
        return OPENAI_MODELS.get(self.config.model, 1536)

    @property
    def client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.config.api_key)
            except ImportError:
                raise ImportError(
                    "openai package is required for OpenAI embeddings. "
                    "Install with: pip install fastband-mcp[openai]"
                )
        return self._client

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        """
        Generate embeddings for texts using OpenAI API.

        Args:
            texts: List of text strings to embed

        Returns:
            EmbeddingResult with embedding vectors
        """
        if not texts:
            return self._empty_result()

        texts_list = list(texts)
        all_embeddings = []
        total_tokens = 0

        # Process in batches
        batch_size = self.config.batch_size
        for i in range(0, len(texts_list), batch_size):
            batch = texts_list[i : i + batch_size]

            kwargs = {
                "model": self.config.model,
                "input": batch,
            }

            # text-embedding-3 models support dimension reduction
            if self.config.dimensions and "text-embedding-3" in self.config.model:
                kwargs["dimensions"] = self.config.dimensions

            response = await self.client.embeddings.create(**kwargs)

            # Extract embeddings in order
            batch_embeddings = [None] * len(batch)
            for data in response.data:
                batch_embeddings[data.index] = data.embedding

            all_embeddings.extend(batch_embeddings)
            total_tokens += response.usage.total_tokens

        return EmbeddingResult(
            embeddings=all_embeddings,
            model=response.model,
            provider=self.name,
            dimensions=len(all_embeddings[0]) if all_embeddings else self.dimensions,
            usage={
                "prompt_tokens": total_tokens,
                "total_tokens": total_tokens,
            },
        )
