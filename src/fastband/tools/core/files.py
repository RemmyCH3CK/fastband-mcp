"""
File operation tools - List, read, write, search files.
"""

import re
from pathlib import Path

from fastband.core.security import (
    PathSecurityError,
    PathValidator,
)
from fastband.tools.base import (
    Tool,
    ToolCategory,
    ToolDefinition,
    ToolMetadata,
    ToolParameter,
    ToolResult,
)

# Global path validator for file operations
# Allows symlinks for convenience but validates paths
_path_validator: PathValidator | None = None


def get_path_validator() -> PathValidator:
    """Get or create the path validator."""
    global _path_validator
    if _path_validator is None:
        # Default: allow current directory and home
        _path_validator = PathValidator(
            allowed_roots=[Path.cwd(), Path.home()],
            allow_symlinks=True,  # Allow symlinks but resolve them
            blocked_extensions=set(),  # Don't block extensions for read
        )
    return _path_validator


def set_allowed_roots(roots: list[Path]) -> None:
    """Set allowed root directories for file operations."""
    global _path_validator
    _path_validator = PathValidator(
        allowed_roots=roots,
        allow_symlinks=True,
        blocked_extensions=set(),
    )


class ListFilesTool(Tool):
    """List files and directories in a path."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="list_files",
                description="List files and directories in a specified path",
                category=ToolCategory.CORE,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Directory path to list (default: current directory)",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Glob pattern to filter files (e.g., '*.py', '**/*.js')",
                    required=False,
                ),
                ToolParameter(
                    name="max_depth",
                    type="integer",
                    description="Maximum directory depth to traverse (default: 1)",
                    required=False,
                    default=1,
                ),
                ToolParameter(
                    name="include_hidden",
                    type="boolean",
                    description="Include hidden files/directories (default: false)",
                    required=False,
                    default=False,
                ),
            ],
        )

    async def execute(
        self,
        path: str = ".",
        pattern: str = None,
        max_depth: int = 1,
        include_hidden: bool = False,
        **kwargs,
    ) -> ToolResult:
        """List files in directory."""
        # Validate path for security
        try:
            validator = get_path_validator()
            target = validator.validate(path)
        except PathSecurityError as e:
            return ToolResult(success=False, error=f"Path security error: {e}")

        if not target.exists():
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        if not target.is_dir():
            return ToolResult(success=False, error=f"Path is not a directory: {path}")

        files = []
        directories = []

        try:
            if pattern:
                # Use glob pattern
                matches = list(target.glob(pattern))
                for item in matches:
                    if not include_hidden and item.name.startswith("."):
                        continue
                    if item.is_file():
                        files.append(self._file_info(item, target))
                    elif item.is_dir():
                        directories.append(self._dir_info(item, target))
            else:
                # List directory contents
                self._list_recursive(
                    target, target, files, directories, max_depth, include_hidden, current_depth=0
                )

            return ToolResult(
                success=True,
                data={
                    "path": str(target),
                    "files": sorted(files, key=lambda x: x["path"]),
                    "directories": sorted(directories, key=lambda x: x["path"]),
                    "total_files": len(files),
                    "total_directories": len(directories),
                },
            )

        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _list_recursive(
        self,
        current: Path,
        base: Path,
        files: list,
        directories: list,
        max_depth: int,
        include_hidden: bool,
        current_depth: int,
    ):
        """Recursively list directory contents."""
        if current_depth >= max_depth:
            return

        try:
            for item in current.iterdir():
                if not include_hidden and item.name.startswith("."):
                    continue

                if item.is_file():
                    files.append(self._file_info(item, base))
                elif item.is_dir():
                    directories.append(self._dir_info(item, base))
                    if current_depth + 1 < max_depth:
                        self._list_recursive(
                            item,
                            base,
                            files,
                            directories,
                            max_depth,
                            include_hidden,
                            current_depth + 1,
                        )
        except PermissionError:
            pass

    def _file_info(self, path: Path, base: Path) -> dict:
        """Get file information."""
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path.relative_to(base)),
            "type": "file",
            "size": stat.st_size,
            "modified": stat.st_mtime,
        }

    def _dir_info(self, path: Path, base: Path) -> dict:
        """Get directory information."""
        return {
            "name": path.name,
            "path": str(path.relative_to(base)),
            "type": "directory",
        }


class ReadFileTool(Tool):
    """Read contents of a file."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="read_file",
                description="Read the contents of a file",
                category=ToolCategory.CORE,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file to read",
                    required=True,
                ),
                ToolParameter(
                    name="offset",
                    type="integer",
                    description="Line number to start reading from (1-indexed)",
                    required=False,
                    default=1,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of lines to read (default: 500)",
                    required=False,
                    default=500,
                ),
            ],
        )

    async def execute(self, path: str, offset: int = 1, limit: int = 500, **kwargs) -> ToolResult:
        """Read file contents."""
        # Validate path for security
        try:
            validator = get_path_validator()
            target = validator.validate(path)
        except PathSecurityError as e:
            return ToolResult(success=False, error=f"Path security error: {e}")

        if not target.exists():
            return ToolResult(success=False, error=f"File does not exist: {path}")

        if not target.is_file():
            return ToolResult(success=False, error=f"Path is not a file: {path}")

        try:
            with open(target, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            start_idx = max(0, offset - 1)
            end_idx = min(start_idx + limit, total_lines)

            selected_lines = lines[start_idx:end_idx]
            content = "".join(selected_lines)

            return ToolResult(
                success=True,
                data={
                    "path": str(target),
                    "content": content,
                    "total_lines": total_lines,
                    "lines_returned": len(selected_lines),
                    "start_line": start_idx + 1,
                    "end_line": end_idx,
                    "truncated": end_idx < total_lines,
                },
            )

        except UnicodeDecodeError:
            return ToolResult(success=False, error=f"Cannot read file as text: {path}")
        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class WriteFileTool(Tool):
    """Write contents to a file."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="write_file",
                description="Write content to a file (creates or overwrites)",
                category=ToolCategory.CORE,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file to write",
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Content to write to the file",
                    required=True,
                ),
                ToolParameter(
                    name="create_dirs",
                    type="boolean",
                    description="Create parent directories if they don't exist (default: true)",
                    required=False,
                    default=True,
                ),
            ],
        )

    async def execute(
        self, path: str, content: str, create_dirs: bool = True, **kwargs
    ) -> ToolResult:
        """Write content to file."""
        # Validate path for security
        try:
            validator = get_path_validator()
            target = validator.validate(path)
        except PathSecurityError as e:
            return ToolResult(success=False, error=f"Path security error: {e}")

        try:
            if create_dirs:
                target.parent.mkdir(parents=True, exist_ok=True)

            existed = target.exists()
            previous_size = target.stat().st_size if existed else 0

            with open(target, "w", encoding="utf-8") as f:
                f.write(content)

            new_size = target.stat().st_size

            return ToolResult(
                success=True,
                data={
                    "path": str(target),
                    "created": not existed,
                    "overwritten": existed,
                    "previous_size": previous_size,
                    "new_size": new_size,
                    "bytes_written": len(content.encode("utf-8")),
                },
            )

        except PermissionError:
            return ToolResult(success=False, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SearchCodeTool(Tool):
    """Search for patterns in code files."""

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            metadata=ToolMetadata(
                name="search_code",
                description="Search for patterns in code files using regex",
                category=ToolCategory.CORE,
                version="1.0.0",
                requires_filesystem=True,
            ),
            parameters=[
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Regex pattern to search for",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Directory to search in (default: current directory)",
                    required=False,
                    default=".",
                ),
                ToolParameter(
                    name="file_pattern",
                    type="string",
                    description="Glob pattern for files to search (default: '*.py')",
                    required=False,
                    default="*.py",
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum number of results (default: 50)",
                    required=False,
                    default=50,
                ),
                ToolParameter(
                    name="context_lines",
                    type="integer",
                    description="Number of context lines around matches (default: 2)",
                    required=False,
                    default=2,
                ),
            ],
        )

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        file_pattern: str = "*.py",
        max_results: int = 50,
        context_lines: int = 2,
        **kwargs,
    ) -> ToolResult:
        """Search for pattern in files."""
        # Validate path for security
        try:
            validator = get_path_validator()
            target = validator.validate(path)
        except PathSecurityError as e:
            return ToolResult(success=False, error=f"Path security error: {e}")

        if not target.exists():
            return ToolResult(success=False, error=f"Path does not exist: {path}")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(success=False, error=f"Invalid regex pattern: {e}")

        matches = []
        files_searched = 0
        files_matched = 0

        try:
            for file_path in target.rglob(file_pattern):
                if not file_path.is_file():
                    continue

                # Skip hidden directories
                if any(part.startswith(".") for part in file_path.parts):
                    continue

                files_searched += 1
                file_matches = self._search_file(
                    file_path, target, regex, context_lines, max_results - len(matches)
                )

                if file_matches:
                    files_matched += 1
                    matches.extend(file_matches)

                if len(matches) >= max_results:
                    break

            return ToolResult(
                success=True,
                data={
                    "pattern": pattern,
                    "path": str(target),
                    "file_pattern": file_pattern,
                    "matches": matches,
                    "total_matches": len(matches),
                    "files_searched": files_searched,
                    "files_matched": files_matched,
                    "truncated": len(matches) >= max_results,
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def _search_file(
        self,
        file_path: Path,
        base_path: Path,
        regex: re.Pattern,
        context_lines: int,
        max_results: int,
    ) -> list[dict]:
        """Search for pattern in a single file."""
        matches = []

        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception:
            return []

        for i, line in enumerate(lines):
            if regex.search(line):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)

                context = "".join(lines[start:end])

                matches.append(
                    {
                        "file": str(file_path.relative_to(base_path)),
                        "line": i + 1,
                        "match": line.rstrip(),
                        "context": context,
                        "context_start": start + 1,
                        "context_end": end,
                    }
                )

                if len(matches) >= max_results:
                    break

        return matches
