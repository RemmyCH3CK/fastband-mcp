"""
Code chunkers for splitting source files into embeddable units.

Provides:
- Chunker: Abstract base class for all chunkers
- SemanticChunker: AST-based semantic chunking
- FixedChunker: Fixed-size sliding window chunking
"""

from fastband.embeddings.chunkers.base import Chunker
from fastband.embeddings.chunkers.fixed import FixedChunker
from fastband.embeddings.chunkers.semantic import SemanticChunker

__all__ = [
    "Chunker",
    "SemanticChunker",
    "FixedChunker",
]
