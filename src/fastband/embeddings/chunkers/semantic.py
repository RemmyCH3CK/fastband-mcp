"""
Semantic code chunker.

Uses AST parsing for Python and regex patterns for other languages
to split code into semantically meaningful chunks (functions, classes, etc.).
"""

import ast
import re
from datetime import datetime
from pathlib import Path

from fastband.embeddings.base import ChunkMetadata, ChunkType, CodeChunk
from fastband.embeddings.chunkers.base import Chunker


class SemanticChunker(Chunker):
    """
    Semantic code chunker using AST/regex parsing.

    Splits code into meaningful semantic units:
    - Functions and methods
    - Classes
    - Module-level code blocks
    - Documentation blocks

    Python files use AST parsing for accurate splitting.
    Other languages use regex patterns.

    Example:
        chunker = SemanticChunker()
        chunks = chunker.chunk_file(Path("src/main.py"), content)
    """

    # Regex patterns for non-Python languages
    PATTERNS = {
        ".js": {
            "function": r"(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{",
            "class": r"class\s+(\w+)(?:\s+extends\s+\w+)?\s*\{",
            "arrow": r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>",
        },
        ".ts": {
            "function": r"(?:async\s+)?function\s+(\w+)\s*(?:<[^>]+>)?\([^)]*\)(?:\s*:\s*[^{]+)?\s*\{",
            "class": r"class\s+(\w+)(?:<[^>]+>)?(?:\s+(?:extends|implements)\s+[^{]+)?\s*\{",
            "arrow": r"(?:const|let|var)\s+(\w+)\s*(?::\s*[^=]+)?\s*=\s*(?:async\s+)?\([^)]*\)\s*(?::\s*[^=]+)?\s*=>",
        },
        ".go": {
            "function": r"func\s+(?:\([^)]+\)\s+)?(\w+)\s*\([^)]*\)",
            "type": r"type\s+(\w+)\s+(?:struct|interface)\s*\{",
        },
        ".java": {
            "method": r"(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*(?:throws\s+[^{]+)?\s*\{",
            "class": r"(?:public|private)?\s*(?:abstract\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+\w+)?(?:\s+implements\s+[^{]+)?\s*\{",
        },
        ".rs": {
            "function": r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)(?:<[^>]+>)?\s*\([^)]*\)",
            "impl": r"impl(?:<[^>]+>)?\s+(\w+)",
            "struct": r"(?:pub\s+)?struct\s+(\w+)",
        },
    }

    def chunk_file(self, path: Path, content: str) -> list[CodeChunk]:
        """
        Split a file into semantic chunks.

        Args:
            path: Path to the source file
            content: File content

        Returns:
            List of CodeChunk objects
        """
        suffix = path.suffix.lower()

        # Get file modification time
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except Exception:
            mtime = None

        # Extract imports for context
        imports = self._extract_imports(content, suffix)

        if suffix == ".py":
            return self._chunk_python(path, content, imports, mtime)
        elif suffix in self.PATTERNS:
            return self._chunk_with_regex(path, content, suffix, imports, mtime)
        else:
            # Fall back to file-level chunking for unknown types
            return self._chunk_as_file(path, content, imports, mtime)

    def _chunk_python(
        self,
        path: Path,
        content: str,
        imports: list[str],
        mtime: datetime | None,
    ) -> list[CodeChunk]:
        """Chunk Python file using AST.

        Uses efficient single-pass traversal to avoid O(N²) re-parsing.
        """
        chunks = []
        lines = content.split("\n")

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Fall back to file-level chunk on parse error
            return self._chunk_as_file(path, content, imports, mtime)

        # Single-pass traversal maintaining parent context
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                # Create class chunk
                chunk = self._create_chunk_from_node(
                    path, lines, node, ChunkType.CLASS, imports, mtime
                )
                if chunk:
                    chunks.append(chunk)

                # Create method chunks with parent context
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        chunk = self._create_chunk_from_node(
                            path,
                            lines,
                            child,
                            ChunkType.METHOD,
                            imports,
                            mtime,
                            parent_name=node.name,
                        )
                        if chunk:
                            chunks.append(chunk)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Top-level function
                chunk = self._create_chunk_from_node(
                    path, lines, node, ChunkType.FUNCTION, imports, mtime
                )
                if chunk:
                    chunks.append(chunk)

        # If no chunks extracted, chunk as file
        if not chunks:
            return self._chunk_as_file(path, content, imports, mtime)

        return chunks

    def _create_chunk_from_node(
        self,
        path: Path,
        lines: list[str],
        node: ast.AST,
        chunk_type: ChunkType,
        imports: list[str],
        mtime: datetime | None,
        parent_name: str | None = None,
    ) -> CodeChunk | None:
        """Create a CodeChunk from an AST node.

        Args:
            path: File path
            lines: File content split into lines
            node: AST node to create chunk from
            chunk_type: Type of chunk (CLASS, FUNCTION, METHOD)
            imports: Extracted imports for context
            mtime: File modification time
            parent_name: Name of parent class (for methods)

        Returns:
            CodeChunk or None if chunk is too small
        """
        start_line = node.lineno
        end_line = node.end_lineno or start_line

        # Get the source lines
        chunk_lines = lines[start_line - 1 : end_line]
        content = "\n".join(chunk_lines)

        # Skip if too small (min_chunk_size is in characters)
        if len(content) < self.config.min_chunk_size:
            return None

        # Extract docstring
        docstring = None
        if hasattr(node, "body") and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                if isinstance(first.value.value, str):
                    docstring = first.value.value

        metadata = ChunkMetadata(
            file_path=str(path),
            chunk_type=chunk_type,
            start_line=start_line,
            end_line=end_line,
            name=node.name if hasattr(node, "name") else None,
            docstring=docstring,
            imports=imports if self.config.include_imports else [],
            parent_name=parent_name,
            file_type="python",
            last_modified=mtime,
        )

        chunk = CodeChunk(content=content, metadata=metadata)
        metadata.chunk_hash = chunk.compute_hash()

        return chunk

    def _chunk_with_regex(
        self,
        path: Path,
        content: str,
        suffix: str,
        imports: list[str],
        mtime: datetime | None,
    ) -> list[CodeChunk]:
        """Chunk non-Python file using regex patterns."""
        chunks = []
        lines = content.split("\n")
        patterns = self.PATTERNS.get(suffix, {})

        # Find all function/class definitions
        positions = []
        for pattern_type, pattern in patterns.items():
            for match in re.finditer(pattern, content, re.MULTILINE):
                name = match.group(1) if match.lastindex else None
                start_pos = match.start()
                # Convert position to line number
                start_line = content[:start_pos].count("\n") + 1
                positions.append((start_line, name, pattern_type))

        # Sort by line number
        positions.sort(key=lambda x: x[0])

        # Create chunks between definitions
        for i, (start_line, name, ptype) in enumerate(positions):
            # End at next definition or end of file
            if i + 1 < len(positions):
                end_line = positions[i + 1][0] - 1
            else:
                end_line = len(lines)

            chunk_content = "\n".join(lines[start_line - 1 : end_line])

            # Determine chunk type
            if ptype in ("class", "type", "struct", "impl"):
                chunk_type = ChunkType.CLASS
            else:
                chunk_type = ChunkType.FUNCTION

            metadata = ChunkMetadata(
                file_path=str(path),
                chunk_type=chunk_type,
                start_line=start_line,
                end_line=end_line,
                name=name,
                imports=imports if self.config.include_imports else [],
                file_type=suffix[1:],  # Remove dot
                last_modified=mtime,
            )

            chunk = CodeChunk(content=chunk_content, metadata=metadata)
            metadata.chunk_hash = chunk.compute_hash()
            chunks.append(chunk)

        # If no chunks found, chunk as file
        if not chunks:
            return self._chunk_as_file(path, content, imports, mtime)

        return chunks

    def _chunk_as_file(
        self,
        path: Path,
        content: str,
        imports: list[str],
        mtime: datetime | None,
    ) -> list[CodeChunk]:
        """Create a single chunk from entire file."""
        lines = content.split("\n")

        # If file is too large, split into blocks
        if len(content.split()) > self.config.max_chunk_size:
            return self._split_large_file(path, content, imports, mtime)

        metadata = ChunkMetadata(
            file_path=str(path),
            chunk_type=ChunkType.FILE,
            start_line=1,
            end_line=len(lines),
            name=path.stem,
            imports=imports if self.config.include_imports else [],
            file_type=path.suffix[1:] if path.suffix else "unknown",
            last_modified=mtime,
        )

        chunk = CodeChunk(content=content, metadata=metadata)
        metadata.chunk_hash = chunk.compute_hash()

        return [chunk]

    def _split_large_file(
        self,
        path: Path,
        content: str,
        imports: list[str],
        mtime: datetime | None,
    ) -> list[CodeChunk]:
        """Split a large file into smaller chunks."""
        chunks = []
        lines = content.split("\n")

        # Split into roughly equal chunks
        max_lines = self.config.max_chunk_size // 10  # Rough estimate
        overlap_lines = self.config.overlap // 10

        i = 0
        chunk_num = 0
        while i < len(lines):
            end = min(i + max_lines, len(lines))
            chunk_lines = lines[i:end]
            chunk_content = "\n".join(chunk_lines)

            metadata = ChunkMetadata(
                file_path=str(path),
                chunk_type=ChunkType.BLOCK,
                start_line=i + 1,
                end_line=end,
                name=f"{path.stem}_part{chunk_num}",
                imports=imports if self.config.include_imports and chunk_num == 0 else [],
                file_type=path.suffix[1:] if path.suffix else "unknown",
                last_modified=mtime,
            )

            chunk = CodeChunk(content=chunk_content, metadata=metadata)
            metadata.chunk_hash = chunk.compute_hash()
            chunks.append(chunk)

            i = end - overlap_lines if end < len(lines) else end
            chunk_num += 1

        return chunks

    def _extract_imports(self, content: str, suffix: str) -> list[str]:
        """Extract import statements from file."""
        imports = []

        if suffix == ".py":
            # Python imports
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    imports.append(line)
                elif line and not line.startswith("#") and not line.startswith('"""'):
                    # Stop at first non-import, non-comment line
                    if imports:
                        break

        elif suffix in (".js", ".ts", ".jsx", ".tsx"):
            # JavaScript/TypeScript imports
            import_pattern = r'^(?:import|export)\s+.+?(?:from\s+[\'"][^\'"]+[\'"])?;?$'
            for match in re.finditer(import_pattern, content, re.MULTILINE):
                imports.append(match.group(0))

        elif suffix == ".go":
            # Go imports
            import_pattern = r'import\s+(?:\(\s*([\s\S]*?)\s*\)|"[^"]+")'
            for match in re.finditer(import_pattern, content):
                imports.append(match.group(0))

        return imports[:20]  # Limit to 20 imports
