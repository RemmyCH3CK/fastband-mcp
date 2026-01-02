"""
Lazy Bible Loader for Fastband Memory Architecture.

Loads Agent Bible sections on-demand based on tool usage.
Reduces base memory from ~3000 tokens to ~850 tokens.

"Agents don't need to memorize the Bible - they need to follow it."
"""

import hashlib
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


class PathValidator:
    """
    Validates file paths to prevent path traversal attacks.

    P0 Security: Prevents loading arbitrary files via malicious paths.
    """

    # Allowed base directories for Bible files
    ALLOWED_BASES = [
        Path.cwd(),
        Path.home() / ".fastband",
    ]

    # Required filename pattern for Bible files
    BIBLE_FILENAME_PATTERN = re.compile(r"^[A-Z_]+\.md$")

    @classmethod
    def validate_bible_path(cls, path: str | Path) -> tuple[bool, str]:
        """
        Validate that a path is safe for Bible loading.

        Returns (is_valid, error_message).
        """
        try:
            path = Path(path)

            # Resolve to absolute path (follows symlinks)
            resolved = path.resolve()

            # Check for path traversal attempts
            path_str = str(path)
            if ".." in path_str:
                return False, "Path traversal detected: '..' not allowed"

            # Verify it's under an allowed base
            is_under_allowed = False
            for base in cls.ALLOWED_BASES:
                try:
                    resolved.relative_to(base.resolve())
                    is_under_allowed = True
                    break
                except ValueError:
                    continue

            if not is_under_allowed:
                return False, f"Path not under allowed directories: {cls.ALLOWED_BASES}"

            # Verify filename matches expected pattern
            if not cls.BIBLE_FILENAME_PATTERN.match(resolved.name):
                return False, f"Invalid Bible filename: {resolved.name} (expected pattern: UPPER_CASE.md)"

            # Verify it's a file (not directory, socket, etc.)
            if resolved.exists() and not resolved.is_file():
                return False, f"Path is not a regular file: {resolved}"

            return True, ""

        except Exception as e:
            return False, f"Path validation error: {e}"

    @classmethod
    def safe_resolve(cls, path: str | Path) -> Optional[Path]:
        """
        Safely resolve a path, returning None if invalid.
        """
        is_valid, _ = cls.validate_bible_path(path)
        if is_valid:
            return Path(path).resolve()
        return None

# Token estimates (approximate)
BIBLE_SUMMARY_TOKENS = 850  # Core laws + workflow basics
FULL_BIBLE_TOKENS = 3000  # Complete bible
SECTION_TOKENS = 200  # Average per section

# Tool-to-section mappings
TOOL_SECTION_MAP = {
    # Ticket tools trigger ticket-related sections
    "claim_ticket": ["LAW 1", "LAW 2", "STEP 1", "STEP 2", "STEP 3"],
    "complete_ticket_safely": ["LAW 6", "LAW 7", "STEP 6", "STEP 7", "STEP 8"],
    "submit_review": ["LAW 5", "LAW 7", "REVIEW_PROTOCOL"],
    "escalate_ticket": ["LAW 6", "STEP 8"],
    # Git tools trigger code-related sections
    "git_commit": ["LAW 4", "LAW 9", "CODE_STANDARDS"],
    "git_push": ["LAW 4", "LAW 9"],
    # Ops log tools trigger coordination sections
    "ops_log_write": ["LAW 3", "OPS_LOG_PROTOCOL"],
    "ops_log_read": ["LAW 3", "OPS_LOG_PROTOCOL"],
    # Screenshot tools trigger verification sections
    "take_screenshot": ["LAW 8", "VERIFICATION_PROTOCOL"],
    # Error conditions trigger emergency sections
    "_on_error": ["LAW 10", "EMERGENCY_PROTOCOL"],
}

# Sections always loaded in summary
ALWAYS_LOADED = [
    "LAW_HEADERS",  # All 10 law one-liners
    "STEP 1",  # Agent naming
    "STEP 2",  # Claim ticket
    "STEP 3",  # Read requirements
    "STEP 4",  # Do work
    "STEP 5",  # Test & verify
    "OPS_LOG_BASICS",  # Core ops log protocol
]


@dataclass
class BibleSection:
    """A section of the Agent Bible."""

    section_id: str
    title: str
    content: str
    token_count: int
    priority: int = 1  # 1=always, 2=common, 3=rare

    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "content": self.content,
            "token_count": self.token_count,
            "priority": self.priority,
        }


@dataclass
class BibleCache:
    """Caches parsed Bible sections for efficient access."""

    bible_path: str
    bible_hash: str  # For cache invalidation
    sections: dict[str, BibleSection] = field(default_factory=dict)
    summary: str = ""
    summary_tokens: int = 0
    parsed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def is_valid(self, current_hash: str) -> bool:
        """Check if cache is still valid."""
        return self.bible_hash == current_hash


class LazyBibleLoader:
    """
    Lazy-loads Agent Bible sections based on context.

    Strategy:
    1. Always load summary (850 tokens) - law headers + workflow basics
    2. Load full sections when relevant tools are invoked
    3. Cache loaded sections for session duration
    """

    def __init__(self, bible_path: Optional[str] = None):
        if bible_path:
            # P0 Security: Validate user-provided paths
            is_valid, error = PathValidator.validate_bible_path(bible_path)
            if not is_valid:
                import logging
                logging.getLogger(__name__).warning(
                    f"Invalid Bible path rejected: {bible_path}. Reason: {error}"
                )
                bible_path = None  # Fall back to auto-discovery

        self.bible_path = bible_path or self._find_bible_path()
        self._cache: Optional[BibleCache] = None
        self._loaded_sections: set[str] = set()

    def _find_bible_path(self) -> str:
        """Find the Agent Bible in common locations with path validation."""
        candidates = [
            Path.cwd() / "AGENT_BIBLE.md",
            Path.cwd() / ".fastband" / "AGENT_BIBLE.md",
            Path.home() / ".fastband" / "AGENT_BIBLE.md",
        ]
        for path in candidates:
            # P0 Security: Validate each candidate path
            is_valid, _ = PathValidator.validate_bible_path(path)
            if is_valid and path.exists():
                return str(path)
        # Return first valid candidate as default (even if doesn't exist yet)
        for path in candidates:
            is_valid, _ = PathValidator.validate_bible_path(path)
            if is_valid:
                return str(path)
        return str(candidates[0])  # Last resort fallback

    def _compute_hash(self, content: str) -> str:
        """Compute hash of bible content for cache invalidation."""
        # P2 Security: Use SHA-256 instead of MD5
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _parse_bible(self, content: str) -> BibleCache:
        """Parse Bible into sections."""
        cache = BibleCache(
            bible_path=self.bible_path,
            bible_hash=self._compute_hash(content),
        )

        # Parse LAW sections
        law_pattern = r"## (LAW \d+): ([^\n]+)\n(.*?)(?=## LAW|\Z)"
        for match in re.finditer(law_pattern, content, re.DOTALL):
            law_id = match.group(1)
            title = match.group(2).strip()
            body = match.group(3).strip()
            token_count = len(body.split()) * 1.3  # Rough estimate

            cache.sections[law_id] = BibleSection(
                section_id=law_id,
                title=title,
                content=f"## {law_id}: {title}\n\n{body}",
                token_count=int(token_count),
                priority=1 if law_id in ["LAW 1", "LAW 2", "LAW 3"] else 2,
            )

        # Parse STEP sections
        step_pattern = r"### (STEP \d+): ([^\n]+)\n(.*?)(?=### STEP|\Z)"
        for match in re.finditer(step_pattern, content, re.DOTALL):
            step_id = match.group(1)
            title = match.group(2).strip()
            body = match.group(3).strip()
            token_count = len(body.split()) * 1.3

            cache.sections[step_id] = BibleSection(
                section_id=step_id,
                title=title,
                content=f"### {step_id}: {title}\n\n{body}",
                token_count=int(token_count),
                priority=1 if step_id in ["STEP 1", "STEP 2", "STEP 3", "STEP 4", "STEP 5"] else 2,
            )

        # Build summary (law headers + priority 1 sections)
        summary_parts = ["# AGENT BIBLE SUMMARY\n"]

        # Add law headers
        summary_parts.append("## THE 10 LAWS\n")
        for i in range(1, 11):
            law_id = f"LAW {i}"
            if law_id in cache.sections:
                section = cache.sections[law_id]
                # Extract just the first line/rule
                first_line = section.content.split("\n")[0]
                summary_parts.append(f"- {first_line}")

        summary_parts.append("\n## WORKFLOW BASICS\n")
        for step_id in ["STEP 1", "STEP 2", "STEP 3", "STEP 4", "STEP 5"]:
            if step_id in cache.sections:
                section = cache.sections[step_id]
                # Abbreviated version
                summary_parts.append(f"- **{step_id}**: {section.title}")

        cache.summary = "\n".join(summary_parts)
        cache.summary_tokens = len(cache.summary.split()) * 1.3

        return cache

    def _ensure_cache(self) -> BibleCache:
        """Ensure cache is loaded and valid."""
        try:
            with open(self.bible_path, "r") as f:
                content = f.read()
        except FileNotFoundError:
            # Return empty cache if no bible
            return BibleCache(
                bible_path=self.bible_path,
                bible_hash="empty",
                summary="# No Agent Bible found\nOperating in basic mode.",
                summary_tokens=10,
            )

        current_hash = self._compute_hash(content)

        if self._cache and self._cache.is_valid(current_hash):
            return self._cache

        self._cache = self._parse_bible(content)
        return self._cache

    def get_summary(self) -> tuple[str, int]:
        """
        Get the Bible summary for initial context.

        Returns (summary_text, token_count).
        """
        cache = self._ensure_cache()
        self._loaded_sections.update(["LAW_HEADERS"] + [f"STEP {i}" for i in range(1, 6)])
        return cache.summary, int(cache.summary_tokens)

    def get_section(self, section_id: str) -> Optional[tuple[str, int]]:
        """
        Get a specific Bible section.

        Returns (section_text, token_count) or None if not found.
        """
        cache = self._ensure_cache()
        section = cache.sections.get(section_id)
        if section:
            self._loaded_sections.add(section_id)
            return section.content, section.token_count
        return None

    def get_sections_for_tool(self, tool_name: str) -> list[tuple[str, int]]:
        """
        Get all Bible sections relevant to a tool.

        Returns list of (section_text, token_count) tuples.
        Only returns sections not already loaded.
        """
        section_ids = TOOL_SECTION_MAP.get(tool_name, [])
        results = []

        for section_id in section_ids:
            if section_id not in self._loaded_sections:
                result = self.get_section(section_id)
                if result:
                    results.append(result)

        return results

    def get_full_bible(self) -> tuple[str, int]:
        """
        Get the complete Bible (for emergency or complex situations).

        Returns (full_text, token_count).
        """
        try:
            with open(self.bible_path, "r") as f:
                content = f.read()
            token_count = len(content.split()) * 1.3
            # Mark all sections as loaded
            cache = self._ensure_cache()
            self._loaded_sections.update(cache.sections.keys())
            return content, int(token_count)
        except FileNotFoundError:
            return "# No Agent Bible found", 5

    def get_loaded_sections(self) -> set[str]:
        """Get set of currently loaded section IDs."""
        return self._loaded_sections.copy()

    def get_loading_stats(self) -> dict:
        """Get statistics about Bible loading."""
        cache = self._ensure_cache()
        total_sections = len(cache.sections)
        loaded_sections = len(self._loaded_sections)
        total_tokens = sum(s.token_count for s in cache.sections.values())
        loaded_tokens = sum(
            cache.sections[sid].token_count
            for sid in self._loaded_sections
            if sid in cache.sections
        )

        return {
            "total_sections": total_sections,
            "loaded_sections": loaded_sections,
            "load_percentage": (loaded_sections / total_sections * 100) if total_sections else 0,
            "total_tokens": int(total_tokens),
            "loaded_tokens": int(loaded_tokens),
            "token_savings": int(total_tokens - loaded_tokens),
            "savings_percentage": (
                (total_tokens - loaded_tokens) / total_tokens * 100 if total_tokens else 0
            ),
        }


# Session-specific loaders (thread-safe)
_loaders: dict[str, LazyBibleLoader] = {}
_loaders_lock = threading.Lock()


def get_bible_loader(session_id: str, bible_path: Optional[str] = None) -> LazyBibleLoader:
    """Get or create a Bible loader for a session. Thread-safe."""
    with _loaders_lock:
        if session_id not in _loaders:
            _loaders[session_id] = LazyBibleLoader(bible_path)
        return _loaders[session_id]


def close_bible_loader(session_id: str) -> Optional[dict]:
    """Close a session's Bible loader and return stats. Thread-safe."""
    with _loaders_lock:
        loader = _loaders.pop(session_id, None)
    if loader:
        return loader.get_loading_stats()
    return None
