"""
Embedding providers for different AI platforms.

Provides:
- OpenAIEmbeddings: OpenAI's text-embedding models
- GeminiEmbeddings: Google's embedding models
- OllamaEmbeddings: Local embeddings via Ollama
"""

from fastband.embeddings.providers.gemini import GeminiEmbeddings
from fastband.embeddings.providers.ollama import OllamaEmbeddings
from fastband.embeddings.providers.openai import OpenAIEmbeddings

__all__ = [
    "OpenAIEmbeddings",
    "GeminiEmbeddings",
    "OllamaEmbeddings",
]
