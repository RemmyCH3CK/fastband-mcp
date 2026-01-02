"""
Dependency Graph Builder - Analyzes import relationships across the codebase.

Supports multiple languages with extensible parsers:
- Python: import/from statements
- JavaScript/TypeScript: import/require/export
- Go: import statements
- More can be added

The graph enables:
- Impact analysis ("what breaks if I change this?")
- Test discovery ("what tests cover this?")
- Critical path detection ("is this core infrastructure?")
"""

import ast
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from fastband.context.models import (
    FileType,
    ImpactGraph,
    ImpactLevel,
    ImportRelation,
)

logger = logging.getLogger(__name__)


# =============================================================================
# LANGUAGE PARSERS
# =============================================================================


class ImportParser(ABC):
    """Base class for language-specific import parsers."""

    @abstractmethod
    def parse_imports(self, content: str, file_path: str) -> List[ImportRelation]:
        """Parse imports from file content."""
        pass

    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """File extensions this parser handles."""
        pass


class PythonImportParser(ImportParser):
    """Parse Python import statements."""

    def supported_extensions(self) -> List[str]:
        return [".py", ".pyi"]

    def parse_imports(self, content: str, file_path: str) -> List[ImportRelation]:
        imports = []

        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Fall back to regex for files with syntax errors
            return self._parse_with_regex(content, file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(
                        ImportRelation(
                            source_file=file_path,
                            target_file=self._module_to_path(alias.name),
                            import_type="direct",
                            symbols=[alias.asname or alias.name],
                        )
                    )

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    target = self._module_to_path(node.module)
                    symbols = [alias.name for alias in node.names]
                    imports.append(
                        ImportRelation(
                            source_file=file_path,
                            target_file=target,
                            import_type="from",
                            symbols=symbols,
                        )
                    )

        return imports

    def _parse_with_regex(self, content: str, file_path: str) -> List[ImportRelation]:
        """Fallback regex parsing for files with syntax errors."""
        imports = []

        # Match: import foo, import foo.bar
        for match in re.finditer(r"^import\s+([\w.]+)", content, re.MULTILINE):
            imports.append(
                ImportRelation(
                    source_file=file_path,
                    target_file=self._module_to_path(match.group(1)),
                    import_type="direct",
                    symbols=[match.group(1).split(".")[-1]],
                )
            )

        # Match: from foo import bar, from foo.bar import baz
        for match in re.finditer(
            r"^from\s+([\w.]+)\s+import\s+(.+?)(?:\n|$)", content, re.MULTILINE
        ):
            module = match.group(1)
            symbols = [s.strip().split(" as ")[0] for s in match.group(2).split(",")]
            imports.append(
                ImportRelation(
                    source_file=file_path,
                    target_file=self._module_to_path(module),
                    import_type="from",
                    symbols=symbols,
                )
            )

        return imports

    def _module_to_path(self, module: str) -> str:
        """Convert module name to relative path."""
        # This is a simplified conversion - full resolution requires
        # knowledge of the project structure
        return module.replace(".", "/")


class JavaScriptImportParser(ImportParser):
    """Parse JavaScript/TypeScript import statements."""

    def supported_extensions(self) -> List[str]:
        return [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]

    def parse_imports(self, content: str, file_path: str) -> List[ImportRelation]:
        imports = []

        # ES6 imports: import { foo } from 'bar'
        es6_pattern = r"""
            import\s+
            (?:
                (\w+)\s*,?\s*          # Default import
                |
                \{([^}]+)\}\s*         # Named imports
                |
                \*\s+as\s+(\w+)\s*     # Namespace import
            )*
            \s*from\s+['"]([^'"]+)['"]
        """
        for match in re.finditer(es6_pattern, content, re.VERBOSE):
            target = match.group(4)
            symbols = []

            if match.group(1):  # Default import
                symbols.append(match.group(1))
            if match.group(2):  # Named imports
                symbols.extend(s.strip().split(" as ")[0] for s in match.group(2).split(","))
            if match.group(3):  # Namespace import
                symbols.append(f"* as {match.group(3)}")

            imports.append(
                ImportRelation(
                    source_file=file_path,
                    target_file=self._resolve_path(target, file_path),
                    import_type="es6",
                    symbols=symbols,
                )
            )

        # CommonJS: require('foo')
        for match in re.finditer(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content):
            imports.append(
                ImportRelation(
                    source_file=file_path,
                    target_file=self._resolve_path(match.group(1), file_path),
                    import_type="require",
                    symbols=["*"],
                )
            )

        # Dynamic imports: import('foo')
        for match in re.finditer(r"import\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", content):
            imports.append(
                ImportRelation(
                    source_file=file_path,
                    target_file=self._resolve_path(match.group(1), file_path),
                    import_type="dynamic",
                    symbols=["*"],
                )
            )

        return imports

    def _resolve_path(self, import_path: str, source_file: str) -> str:
        """Resolve import path relative to source file."""
        if import_path.startswith("."):
            # Relative import
            source_dir = os.path.dirname(source_file)
            return os.path.normpath(os.path.join(source_dir, import_path))
        else:
            # Package import - return as-is
            return import_path


class GoImportParser(ImportParser):
    """Parse Go import statements."""

    def supported_extensions(self) -> List[str]:
        return [".go"]

    def parse_imports(self, content: str, file_path: str) -> List[ImportRelation]:
        imports = []

        # Single import: import "fmt"
        for match in re.finditer(r'import\s+"([^"]+)"', content):
            imports.append(
                ImportRelation(
                    source_file=file_path,
                    target_file=match.group(1),
                    import_type="direct",
                    symbols=["*"],
                )
            )

        # Block import: import ( "fmt" "os" )
        block_match = re.search(r"import\s*\((.*?)\)", content, re.DOTALL)
        if block_match:
            block = block_match.group(1)
            for match in re.finditer(r'"([^"]+)"', block):
                imports.append(
                    ImportRelation(
                        source_file=file_path,
                        target_file=match.group(1),
                        import_type="direct",
                        symbols=["*"],
                    )
                )

        return imports


# =============================================================================
# GRAPH BUILDER
# =============================================================================


@dataclass
class DependencyNode:
    """A node in the dependency graph."""

    file_path: str
    imports: Set[str] = field(default_factory=set)
    imported_by: Set[str] = field(default_factory=set)
    import_details: List[ImportRelation] = field(default_factory=list)


class DependencyGraph:
    """
    Full dependency graph for a codebase.

    Builds and maintains relationships between files,
    enabling impact analysis and test discovery.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.nodes: Dict[str, DependencyNode] = {}
        self._parsers: Dict[str, ImportParser] = {}
        self._file_type_map: Dict[str, FileType] = {}

        # Register default parsers
        self._register_parser(PythonImportParser())
        self._register_parser(JavaScriptImportParser())
        self._register_parser(GoImportParser())

        # Build extension to file type mapping
        self._extension_map = {
            ".py": FileType.PYTHON,
            ".pyi": FileType.PYTHON,
            ".js": FileType.JAVASCRIPT,
            ".jsx": FileType.JAVASCRIPT,
            ".mjs": FileType.JAVASCRIPT,
            ".cjs": FileType.JAVASCRIPT,
            ".ts": FileType.TYPESCRIPT,
            ".tsx": FileType.TYPESCRIPT,
            ".go": FileType.GO,
            ".rs": FileType.RUST,
            ".java": FileType.JAVA,
            ".css": FileType.CSS,
            ".scss": FileType.CSS,
            ".html": FileType.HTML,
            ".json": FileType.JSON,
            ".yaml": FileType.YAML,
            ".yml": FileType.YAML,
            ".md": FileType.MARKDOWN,
            ".sql": FileType.SQL,
            ".sh": FileType.SHELL,
            ".bash": FileType.SHELL,
        }

    def _register_parser(self, parser: ImportParser) -> None:
        """Register an import parser for its supported extensions."""
        for ext in parser.supported_extensions():
            self._parsers[ext] = parser

    def get_file_type(self, file_path: str) -> FileType:
        """Determine file type from extension."""
        ext = Path(file_path).suffix.lower()
        return self._extension_map.get(ext, FileType.UNKNOWN)

    def scan_directory(
        self,
        directory: Optional[str] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> int:
        """
        Scan a directory and build the dependency graph.

        Args:
            directory: Directory to scan (default: project root)
            exclude_patterns: Glob patterns to exclude

        Returns:
            Number of files scanned
        """
        scan_dir = Path(directory) if directory else self.project_root
        exclude_patterns = exclude_patterns or [
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
            "**/venv/**",
            "**/.venv/**",
            "**/dist/**",
            "**/build/**",
            "**/*.min.js",
        ]

        files_scanned = 0

        for file_path in scan_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Check exclusions
            rel_path = str(file_path.relative_to(self.project_root))
            if self._should_exclude(rel_path, exclude_patterns):
                continue

            # Check if we have a parser for this file type
            ext = file_path.suffix.lower()
            if ext not in self._parsers:
                continue

            try:
                self._scan_file(str(file_path))
                files_scanned += 1
            except Exception as e:
                logger.warning(f"Error scanning {file_path}: {e}")

        return files_scanned

    def _should_exclude(self, path: str, patterns: List[str]) -> bool:
        """Check if path matches any exclusion pattern."""
        from fnmatch import fnmatch

        for pattern in patterns:
            if fnmatch(path, pattern):
                return True
        return False

    def _scan_file(self, file_path: str) -> None:
        """Scan a single file and add to graph."""
        ext = Path(file_path).suffix.lower()
        parser = self._parsers.get(ext)
        if not parser:
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return

        # Get relative path for graph
        try:
            rel_path = str(Path(file_path).relative_to(self.project_root))
        except ValueError:
            rel_path = file_path

        # Ensure node exists
        if rel_path not in self.nodes:
            self.nodes[rel_path] = DependencyNode(file_path=rel_path)

        # Parse imports
        imports = parser.parse_imports(content, rel_path)

        for imp in imports:
            # Normalize target path
            target = self._normalize_import_path(imp.target_file, rel_path)

            # Add to source node's imports
            self.nodes[rel_path].imports.add(target)
            self.nodes[rel_path].import_details.append(imp)

            # Ensure target node exists and add reverse reference
            if target not in self.nodes:
                self.nodes[target] = DependencyNode(file_path=target)
            self.nodes[target].imported_by.add(rel_path)

    def _normalize_import_path(self, import_path: str, source_file: str) -> str:
        """Normalize an import path to a consistent format."""
        # Handle relative imports
        if import_path.startswith("."):
            source_dir = os.path.dirname(source_file)
            normalized = os.path.normpath(os.path.join(source_dir, import_path))
            return normalized

        # Handle Python-style module paths
        if "/" not in import_path and "." in import_path:
            # Could be a.b.c style - convert to path
            return import_path.replace(".", "/")

        return import_path

    def get_impact_graph(self, file_path: str, max_depth: int = 3) -> ImpactGraph:
        """
        Build impact graph for a file.

        Args:
            file_path: File to analyze
            max_depth: Maximum depth for transitive dependencies

        Returns:
            ImpactGraph with full impact analysis
        """
        # Normalize path
        try:
            rel_path = str(Path(file_path).relative_to(self.project_root))
        except ValueError:
            rel_path = file_path

        node = self.nodes.get(rel_path)

        if not node:
            # File not in graph - return minimal impact
            return ImpactGraph(
                file_path=rel_path,
                impact_level=ImpactLevel.ISOLATED,
            )

        # Build transitive dependents
        transitive = self._get_transitive_dependents(rel_path, max_depth)

        # Identify test files
        test_files = []
        tests_to_run = []
        for dep in list(node.imported_by) + transitive:
            if self._is_test_file(dep):
                test_files.append(dep)
                tests_to_run.append(dep)

        # Calculate impact level
        impact_level = self._calculate_impact_level(node, transitive)

        # Calculate impact score (0-100)
        impact_score = min(
            100,
            len(node.imported_by) * 10
            + len(transitive) * 5
            + (20 if self._is_on_critical_path(rel_path) else 0),
        )

        return ImpactGraph(
            file_path=rel_path,
            imports_from=list(node.imports),
            imported_by=list(node.imported_by),
            import_details=node.import_details,
            transitive_dependents=transitive,
            transitive_depth=max_depth,
            impact_level=impact_level,
            impact_score=impact_score,
            is_on_critical_path=self._is_on_critical_path(rel_path),
            critical_path_reason=self._get_critical_path_reason(rel_path),
            test_files=test_files,
            tests_to_run=tests_to_run,
        )

    def _get_transitive_dependents(
        self, file_path: str, max_depth: int
    ) -> List[str]:
        """Get all files transitively depending on this file."""
        visited = set()
        result = []

        def visit(path: str, depth: int):
            if depth > max_depth or path in visited:
                return
            visited.add(path)

            node = self.nodes.get(path)
            if not node:
                return

            for dependent in node.imported_by:
                if dependent not in visited and dependent != file_path:
                    result.append(dependent)
                    visit(dependent, depth + 1)

        node = self.nodes.get(file_path)
        if node:
            for dependent in node.imported_by:
                visit(dependent, 1)

        return result

    def _calculate_impact_level(
        self, node: DependencyNode, transitive: List[str]
    ) -> ImpactLevel:
        """Calculate the impact level for a file."""
        total_dependents = len(node.imported_by) + len(transitive)

        if total_dependents == 0 and len(node.imports) == 0:
            return ImpactLevel.ISOLATED
        elif total_dependents > 20:
            return ImpactLevel.CRITICAL
        elif total_dependents > 10:
            return ImpactLevel.HIGH
        elif total_dependents > 3:
            return ImpactLevel.MEDIUM
        else:
            return ImpactLevel.LOW

    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file."""
        path_lower = file_path.lower()
        return (
            "test" in path_lower
            or "spec" in path_lower
            or path_lower.startswith("tests/")
            or "/tests/" in path_lower
        )

    def _is_on_critical_path(self, file_path: str) -> bool:
        """Check if file is on a critical application path."""
        critical_patterns = [
            "auth",
            "login",
            "security",
            "payment",
            "checkout",
            "database",
            "db",
            "config",
            "settings",
            "middleware",
            "core",
            "main",
            "app",
            "index",
            "server",
        ]

        path_lower = file_path.lower()
        return any(pattern in path_lower for pattern in critical_patterns)

    def _get_critical_path_reason(self, file_path: str) -> Optional[str]:
        """Get reason why file is on critical path."""
        if not self._is_on_critical_path(file_path):
            return None

        path_lower = file_path.lower()
        if "auth" in path_lower or "login" in path_lower:
            return "Authentication/authorization logic"
        if "payment" in path_lower or "checkout" in path_lower:
            return "Payment processing logic"
        if "database" in path_lower or "db" in path_lower:
            return "Database access layer"
        if "config" in path_lower or "settings" in path_lower:
            return "Application configuration"
        if "middleware" in path_lower:
            return "Request middleware"
        if "core" in path_lower:
            return "Core application logic"

        return "Core application file"

    def get_most_depended_files(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get files with most dependents."""
        counts = [
            (path, len(node.imported_by))
            for path, node in self.nodes.items()
        ]
        counts.sort(key=lambda x: x[1], reverse=True)
        return counts[:limit]

    def get_orphan_files(self) -> List[str]:
        """Get files with no imports or dependents (orphans)."""
        orphans = []
        for path, node in self.nodes.items():
            if len(node.imports) == 0 and len(node.imported_by) == 0:
                orphans.append(path)
        return orphans

    def to_dict(self) -> Dict:
        """Serialize graph to dictionary."""
        return {
            "project_root": str(self.project_root),
            "nodes": {
                path: {
                    "imports": list(node.imports),
                    "imported_by": list(node.imported_by),
                }
                for path, node in self.nodes.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "DependencyGraph":
        """Deserialize graph from dictionary."""
        graph = cls(data["project_root"])
        for path, node_data in data.get("nodes", {}).items():
            graph.nodes[path] = DependencyNode(
                file_path=path,
                imports=set(node_data.get("imports", [])),
                imported_by=set(node_data.get("imported_by", [])),
            )
        return graph
