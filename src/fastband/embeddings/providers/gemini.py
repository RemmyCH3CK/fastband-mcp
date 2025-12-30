"""
Google Gemini embedding provider.

Uses Google's embedding models for generating embeddings.
Supports embedding-001 and text-embedding-004.
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
GEMINI_MODELS = {
    "embedding-001": 768,
    "text-embedding-004": 768,
}


class GeminiEmbeddings(EmbeddingProvider):
    """
    Google Gemini embedding provider.

    Uses Google's generative AI API for generating embeddings.
    Supports embedding-001 and text-embedding-004 models.

    Example:
        provider = GeminiEmbeddings(EmbeddingConfig(
            api_key="...",
            model="text-embedding-004",
        ))

        result = await provider.embed(["Hello, world!"])
    """

    def __init__(self, config: EmbeddingConfig | None = None):
        if config is None:
            config = EmbeddingConfig()
        super().__init__(config)
        self._client = None

    def _validate_config(self) -> None:
        """Validate Gemini-specific configuration."""
        if not self.config.api_key:
            self.config.api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        if not self.config.api_key:
            raise ValueError(
                "Gemini embeddings require GOOGLE_API_KEY or GEMINI_API_KEY. "
                "Set it in config or environment variable."
            )

        if not self.config.model:
            self.config.model = "text-embedding-004"

        if self.config.model not in GEMINI_MODELS:
            raise ValueError(
                f"Unknown model: {self.config.model}. Supported: {list(GEMINI_MODELS.keys())}"
            )

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return "text-embedding-004"

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions for current model."""
        return GEMINI_MODELS.get(self.config.model, 768)

    def _get_client(self):
        """Lazy-load the Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.config.api_key)
                self._client = genai
            except ImportError:
                raise ImportError(
                    "google-generativeai package is required for Gemini embeddings. "
                    "Install with: pip install fastband-mcp[gemini]"
                )
        return self._client

    async def embed(self, texts: Sequence[str]) -> EmbeddingResult:
        """
        Generate embeddings for texts using Gemini API.

        Args:
            texts: List of text strings to embed

        Returns:
            EmbeddingResult with embedding vectors
        """
        if not texts:
            return self._empty_result()

        genai = self._get_client()
        texts_list = list(texts)
        all_embeddings = []

        # Process in batches
        batch_size = self.config.batch_size
        for i in range(0, len(texts_list), batch_size):
            batch = texts_list[i : i + batch_size]

            # Gemini embed_content supports batch embedding
            result = genai.embed_content(
                model=f"models/{self.config.model}",
                content=batch,
                task_type="retrieval_document",
            )

            # Extract embeddings
            if isinstance(result["embedding"], list) and len(result["embedding"]) > 0:
                if isinstance(result["embedding"][0], list):
                    # Batch result
                    all_embeddings.extend(result["embedding"])
                else:
                    # Single result wrapped in list
                    all_embeddings.append(result["embedding"])

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
