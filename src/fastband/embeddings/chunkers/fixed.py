"""
Fixed-size chunker.

Splits files into fixed-size chunks with optional overlap.
Simple but may split mid-function.
"""

from datetime import datetime
from pathlib import Path

from fastband.embeddings.base import ChunkMetadata, ChunkType, CodeChunk
from fastband.embeddings.chunkers.base import Chunker


class FixedChunker(Chunker):
    """
    Fixed-size sliding window chunker.

    Splits code into fixed-size chunks with configurable overlap.
    Simple and fast, but doesn't respect semantic boundaries.

    Use when:
    - Semantic chunking is too slow
    - Language isn't supported by semantic chunker
    - You need consistent chunk sizes

    Example:
        chunker = FixedChunker(ChunkerConfig(
            max_chunk_size=500,
            overlap=50,
        ))
        chunks = chunker.chunk_file(Path("file.txt"), content)
    """

    def chunk_file(self, path: Path, content: str) -> list[CodeChunk]:
        """
        Split file into fixed-size chunks.

        Args:
            path: Path to the source file
            content: File content

        Returns:
            List of CodeChunk objects
        """
        chunks = []
        lines = content.split("\n")

        # Get file modification time
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except Exception:
            mtime = None

        # Calculate lines per chunk (rough estimate: ~10 words per line)
        words_per_line = 10
        lines_per_chunk = max(1, self.config.max_chunk_size // words_per_line)
        overlap_lines = max(0, self.config.overlap // words_per_line)

        if len(lines) <= lines_per_chunk:
            # File fits in one chunk
            return self._create_single_chunk(path, content, lines, mtime)

        # Slide through file
        i = 0
        chunk_num = 0
        while i < len(lines):
            end = min(i + lines_per_chunk, len(lines))
            chunk_lines = lines[i:end]
            chunk_content = "\n".join(chunk_lines)

            # Skip if too small
            if len(chunk_content.split()) >= self.config.min_chunk_size:
                metadata = ChunkMetadata(
                    file_path=str(path),
                    chunk_type=ChunkType.BLOCK,
                    start_line=i + 1,
                    end_line=end,
                    name=f"{path.stem}_chunk{chunk_num}",
                    file_type=path.suffix[1:] if path.suffix else "unknown",
                    last_modified=mtime,
                )

                chunk = CodeChunk(content=chunk_content, metadata=metadata)
                metadata.chunk_hash = chunk.compute_hash()
                chunks.append(chunk)
                chunk_num += 1

            # Move to next chunk with overlap
            if end >= len(lines):
                break
            i = end - overlap_lines

        return chunks

    def _create_single_chunk(
        self,
        path: Path,
        content: str,
        lines: list[str],
        mtime: datetime | None,
    ) -> list[CodeChunk]:
        """Create a single chunk from entire file."""
        metadata = ChunkMetadata(
            file_path=str(path),
            chunk_type=ChunkType.FILE,
            start_line=1,
            end_line=len(lines),
            name=path.stem,
            file_type=path.suffix[1:] if path.suffix else "unknown",
            last_modified=mtime,
        )

        chunk = CodeChunk(content=content, metadata=metadata)
        metadata.chunk_hash = chunk.compute_hash()

        return [chunk]
