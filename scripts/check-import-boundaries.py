#!/usr/bin/env python3
"""
Import Boundary Checker for Fastband Dual-Product Architecture.

Enforces the following import rules:
- packages/core must NOT import packages/dev or packages/enterprise
- packages/dev must NOT import packages/enterprise
- packages/enterprise must NOT import packages/dev

Uses Python AST parsing for accurate import detection.
Designed to run in <30 seconds.

Exit codes:
- 0: All checks pass
- 1: Boundary violations detected
- 2: Script error
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple


class Violation(NamedTuple):
    """Import boundary violation."""
    file: Path
    line: int
    module: str
    rule: str


class ImportBoundaryChecker:
    """Check import boundaries between packages."""

    # Forbidden import patterns per package
    RULES = {
        "core": {
            "forbidden": ["fastband_dev", "fastband_enterprise"],
            "description": "Core must not import Dev or Enterprise",
        },
        "dev": {
            "forbidden": ["fastband_enterprise"],
            "description": "Dev must not import Enterprise",
        },
        "enterprise": {
            "forbidden": ["fastband_dev"],
            "description": "Enterprise must not import Dev",
        },
    }

    # Directories to skip
    SKIP_DIRS = {".git", ".venv", "dist", "build", "__pycache__", "node_modules", ".pytest_cache"}

    # File prefixes to skip (macOS resource forks, etc.)
    SKIP_PREFIXES = ("._", ".DS_Store")

    def __init__(self, root: Path):
        self.root = root
        self.violations: list[Violation] = []

    def check_all(self) -> list[Violation]:
        """Check all packages for import boundary violations."""
        self.violations = []

        # Check Python packages
        self._check_python_package("core", self.root / "packages" / "core" / "src")
        self._check_python_package("dev", self.root / "packages" / "dev" / "src")

        # Check Go package (enterprise)
        self._check_go_package("enterprise", self.root / "packages" / "enterprise")

        return self.violations

    def _check_python_package(self, package_name: str, src_path: Path) -> None:
        """Check a Python package for forbidden imports."""
        if not src_path.exists():
            return

        rule = self.RULES.get(package_name)
        if not rule:
            return

        forbidden = rule["forbidden"]

        for py_file in self._iter_python_files(src_path):
            self._check_python_file(py_file, package_name, forbidden, rule["description"])

    def _check_go_package(self, package_name: str, pkg_path: Path) -> None:
        """Check a Go package for forbidden imports."""
        if not pkg_path.exists():
            return

        rule = self.RULES.get(package_name)
        if not rule:
            return

        forbidden = rule["forbidden"]

        for go_file in self._iter_go_files(pkg_path):
            self._check_go_file(go_file, package_name, forbidden, rule["description"])

    def _iter_python_files(self, path: Path):
        """Iterate over Python files, skipping excluded directories and files."""
        for item in path.rglob("*.py"):
            if any(skip in item.parts for skip in self.SKIP_DIRS):
                continue
            if item.name.startswith(self.SKIP_PREFIXES):
                continue
            yield item

    def _iter_go_files(self, path: Path):
        """Iterate over Go files, skipping excluded directories and files."""
        for item in path.rglob("*.go"):
            if any(skip in item.parts for skip in self.SKIP_DIRS):
                continue
            if item.name.startswith(self.SKIP_PREFIXES):
                continue
            yield item

    def _check_python_file(
        self, file_path: Path, package_name: str, forbidden: list[str], rule_desc: str
    ) -> None:
        """Check a Python file for forbidden imports using AST."""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._check_import_name(
                        file_path, node.lineno, alias.name, forbidden, rule_desc
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._check_import_name(
                        file_path, node.lineno, node.module, forbidden, rule_desc
                    )

    def _check_import_name(
        self,
        file_path: Path,
        line: int,
        module: str,
        forbidden: list[str],
        rule_desc: str,
    ) -> None:
        """Check if an import name violates boundaries."""
        for forbidden_module in forbidden:
            if module == forbidden_module or module.startswith(f"{forbidden_module}."):
                self.violations.append(
                    Violation(
                        file=file_path,
                        line=line,
                        module=module,
                        rule=rule_desc,
                    )
                )

    def _check_go_file(
        self, file_path: Path, package_name: str, forbidden: list[str], rule_desc: str
    ) -> None:
        """Check a Go file for forbidden imports (simple pattern matching)."""
        try:
            source = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
            return

        # Simple Go import detection
        in_import_block = False
        for line_num, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()

            # Detect import block
            if stripped.startswith("import ("):
                in_import_block = True
                continue
            if in_import_block and stripped == ")":
                in_import_block = False
                continue

            # Check single import
            if stripped.startswith("import "):
                import_path = stripped.replace("import ", "").strip().strip('"')
                self._check_go_import(file_path, line_num, import_path, forbidden, rule_desc)

            # Check imports in block
            if in_import_block and stripped.startswith('"'):
                import_path = stripped.strip('"')
                self._check_go_import(file_path, line_num, import_path, forbidden, rule_desc)

    def _check_go_import(
        self,
        file_path: Path,
        line: int,
        import_path: str,
        forbidden: list[str],
        rule_desc: str,
    ) -> None:
        """Check if a Go import path violates boundaries."""
        for forbidden_module in forbidden:
            # Check for Python package names in Go imports (cross-language reference)
            if forbidden_module in import_path:
                self.violations.append(
                    Violation(
                        file=file_path,
                        line=line,
                        module=import_path,
                        rule=rule_desc,
                    )
                )


def main() -> int:
    """Main entry point."""
    # Find repository root
    script_path = Path(__file__).resolve()
    root = script_path.parent.parent

    # Verify we're in the right place
    if not (root / "packages").exists():
        print(f"Error: packages/ directory not found in {root}", file=sys.stderr)
        return 2

    print("=" * 60)
    print("Import Boundary Checker")
    print("=" * 60)
    print(f"Repository root: {root}")
    print()

    # Run checks
    checker = ImportBoundaryChecker(root)
    violations = checker.check_all()

    # Report results
    if violations:
        print(f"FAILED: {len(violations)} violation(s) found\n")
        for v in violations:
            rel_path = v.file.relative_to(root)
            print(f"  {rel_path}:{v.line}")
            print(f"    Import: {v.module}")
            print(f"    Rule: {v.rule}")
            print()
        return 1
    else:
        print("PASSED: No import boundary violations detected")
        print()
        print("Checked packages:")
        for pkg, rule in ImportBoundaryChecker.RULES.items():
            print(f"  - {pkg}: {rule['description']}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
