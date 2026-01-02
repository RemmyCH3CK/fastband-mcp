#!/usr/bin/env python3
"""
Artifact Hygiene Checker for Fastband Dual-Product Architecture.

Ensures no forbidden artifacts are tracked in git:
- Environment files (.env.local, .env.*.local)
- Local config directories (.fastband/)
- Database files (*.db, *.sqlite, *.sqlite3)
- Build artifacts (dist/, build/, *.egg-info/)
- Secrets and credentials (.secret*, *.key, *.pem, etc.)
- Python bytecode (__pycache__/, *.pyc)

Exit codes:
- 0: No forbidden files tracked
- 1: Forbidden files detected
- 2: Script error
"""

import re
import subprocess
import sys
from pathlib import Path


# Patterns that must NEVER be tracked in git
FORBIDDEN_PATTERNS = [
    # Environment files
    r"\.env\.local$",
    r"\.env\.[^/]+\.local$",
    # Local config
    r"\.fastband/",
    # Databases
    r"\.db$",
    r"\.sqlite$",
    r"\.sqlite3$",
    # Secrets and credentials
    r"\.secret",
    r"\.key$",
    r"\.pem$",
    r"\.p12$",
    r"\.pfx$",
    r"credentials\.json$",
    r"service-account.*\.json$",
    # Build artifacts in packages
    r"packages/[^/]+/dist/",
    r"packages/[^/]+/build/",
    r"packages/[^/]+/.*\.egg-info/",
    # Python bytecode
    r"__pycache__/",
    r"\.pyc$",
    # Go binaries in enterprise
    r"packages/enterprise/bin/",
    r"packages/enterprise/.*\.(exe|dll|so|dylib)$",
]

# Compile patterns for performance
COMPILED_PATTERNS = [re.compile(p) for p in FORBIDDEN_PATTERNS]


def get_tracked_files() -> list[str]:
    """Get list of all files tracked by git."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    except subprocess.CalledProcessError as e:
        print(f"Error running git ls-files: {e}", file=sys.stderr)
        sys.exit(2)


def check_file(filepath: str) -> str | None:
    """Check if a file matches any forbidden pattern. Returns matched pattern or None."""
    for i, pattern in enumerate(COMPILED_PATTERNS):
        if pattern.search(filepath):
            return FORBIDDEN_PATTERNS[i]
    return None


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("Artifact Hygiene Checker")
    print("=" * 60)
    print()

    tracked_files = get_tracked_files()
    print(f"Checking {len(tracked_files)} tracked files...")
    print()

    violations: list[tuple[str, str]] = []

    for filepath in tracked_files:
        matched_pattern = check_file(filepath)
        if matched_pattern:
            violations.append((filepath, matched_pattern))

    if violations:
        print(f"FAILED: {len(violations)} forbidden file(s) tracked\n")
        for filepath, pattern in violations:
            print(f"  {filepath}")
            print(f"    Pattern: {pattern}")
            print()
        print("To fix: Remove these files from git tracking:")
        print("  git rm --cached <file>")
        print()
        return 1
    else:
        print("PASSED: No forbidden artifacts tracked")
        print()
        print("Checked patterns:")
        for pattern in FORBIDDEN_PATTERNS[:5]:
            print(f"  - {pattern}")
        print(f"  ... and {len(FORBIDDEN_PATTERNS) - 5} more")
        return 0


if __name__ == "__main__":
    sys.exit(main())
