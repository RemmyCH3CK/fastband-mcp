"""
Smart Caching Layer for Codebase Context.

Provides intelligent caching with:
- LRU eviction for memory management
- TTL-based expiration
- File modification detection
- Warm-up capabilities
- Persistence for cold starts
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Generic, List, Optional, Set, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """A single cache entry with metadata."""

    key: str
    value: T
    created_at: datetime
    expires_at: Optional[datetime]
    last_accessed: datetime
    access_count: int = 0
    file_mtime: Optional[float] = None  # For file-based cache invalidation

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def is_stale(self, file_path: Optional[str] = None) -> bool:
        """Check if entry is stale (file modified since caching)."""
        if file_path and self.file_mtime:
            try:
                current_mtime = os.path.getmtime(file_path)
                return current_mtime > self.file_mtime
            except OSError:
                return True  # File doesn't exist or error - consider stale
        return False


class LRUCache(Generic[T]):
    """
    Thread-safe LRU cache with TTL support.

    Features:
    - Configurable max size
    - TTL-based expiration
    - File modification tracking
    - Access statistics
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl_seconds: int = 300,
    ):
        self.max_size = max_size
        self.default_ttl = timedelta(seconds=default_ttl_seconds)
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = CacheStats()

    def get(
        self,
        key: str,
        file_path: Optional[str] = None,
    ) -> Optional[T]:
        """
        Get value from cache.

        Args:
            key: Cache key
            file_path: Optional file path for staleness check

        Returns:
            Cached value or None if not found/expired/stale
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats.misses += 1
                return None

            # Check expiration
            if entry.is_expired():
                del self._cache[key]
                self._stats.expirations += 1
                self._stats.misses += 1
                return None

            # Check staleness
            if entry.is_stale(file_path):
                del self._cache[key]
                self._stats.stale_evictions += 1
                self._stats.misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)

            # Update access stats
            entry.last_accessed = datetime.now(timezone.utc)
            entry.access_count += 1
            self._stats.hits += 1

            return entry.value

    def set(
        self,
        key: str,
        value: T,
        ttl_seconds: Optional[int] = None,
        file_path: Optional[str] = None,
    ) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional custom TTL
            file_path: Optional file path for modification tracking
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            ttl = timedelta(seconds=ttl_seconds) if ttl_seconds else self.default_ttl

            # Get file mtime if tracking file
            file_mtime = None
            if file_path:
                try:
                    file_mtime = os.path.getmtime(file_path)
                except OSError:
                    pass

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + ttl if ttl else None,
                last_accessed=now,
                file_mtime=file_mtime,
            )

            # Remove if exists (to update position)
            if key in self._cache:
                del self._cache[key]

            self._cache[key] = entry

            # Evict LRU entries if over capacity
            while len(self._cache) > self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats.evictions += 1

    def invalidate(self, key: str) -> bool:
        """
        Invalidate a specific cache entry.

        Returns:
            True if entry was found and removed
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all entries matching a pattern.

        Args:
            pattern: Glob-style pattern to match keys

        Returns:
            Number of entries invalidated
        """
        from fnmatch import fnmatch

        with self._lock:
            keys_to_remove = [k for k in self._cache if fnmatch(k, pattern)]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)

    def invalidate_for_file(self, file_path: str) -> int:
        """
        Invalidate all entries related to a file.

        Returns:
            Number of entries invalidated
        """
        count = 0
        # Invalidate by key pattern
        count += self.invalidate_pattern(f"*{file_path}*")
        # Also check file_path in entries
        with self._lock:
            keys_to_remove = []
            for key, entry in self._cache.items():
                if entry.is_stale(file_path):
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._cache[key]
                count += 1
        return count

    def clear(self) -> int:
        """Clear all entries. Returns count cleared."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    def get_stats(self) -> "CacheStats":
        """Get cache statistics."""
        with self._lock:
            self._stats.size = len(self._cache)
            self._stats.max_size = self.max_size
            return self._stats

    def warm_up(
        self,
        keys: List[str],
        loader: Callable[[str], T],
        file_paths: Optional[Dict[str, str]] = None,
    ) -> int:
        """
        Warm up cache with multiple keys.

        Args:
            keys: Keys to warm up
            loader: Function to load value for a key
            file_paths: Optional mapping of keys to file paths

        Returns:
            Number of entries warmed
        """
        warmed = 0
        file_paths = file_paths or {}

        for key in keys:
            # Skip if already cached and valid
            existing = self.get(key, file_paths.get(key))
            if existing is not None:
                continue

            try:
                value = loader(key)
                if value is not None:
                    self.set(key, value, file_path=file_paths.get(key))
                    warmed += 1
            except Exception as e:
                logger.warning(f"Failed to warm cache for {key}: {e}")

        return warmed


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    stale_evictions: int = 0
    size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.1%}",
            "evictions": self.evictions,
            "expirations": self.expirations,
            "stale_evictions": self.stale_evictions,
            "size": self.size,
            "max_size": self.max_size,
        }


class ContextCache:
    """
    Specialized cache for codebase context.

    Manages multiple cache layers:
    - File context cache
    - Impact graph cache
    - Pattern cache
    - Metrics cache

    With intelligent invalidation based on file changes.
    """

    def __init__(
        self,
        project_root: str,
        max_file_contexts: int = 500,
        max_impact_graphs: int = 500,
        max_patterns: int = 200,
        context_ttl_seconds: int = 300,
        graph_ttl_seconds: int = 600,
    ):
        self.project_root = Path(project_root)

        # Separate caches for different data types
        self.file_contexts = LRUCache(
            max_size=max_file_contexts,
            default_ttl_seconds=context_ttl_seconds,
        )
        self.impact_graphs = LRUCache(
            max_size=max_impact_graphs,
            default_ttl_seconds=graph_ttl_seconds,
        )
        self.patterns = LRUCache(
            max_size=max_patterns,
            default_ttl_seconds=graph_ttl_seconds,
        )
        self.metrics = LRUCache(
            max_size=max_file_contexts,
            default_ttl_seconds=context_ttl_seconds,
        )

        # Track which files affect which cache entries
        self._dependency_map: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()

        # Persistence
        self._cache_dir = self.project_root / ".fastband" / "cache"

    def _get_file_path(self, key: str) -> Optional[str]:
        """Extract file path from cache key."""
        # Keys are typically like "context:path/to/file.py"
        if ":" in key:
            return key.split(":", 1)[1]
        return key

    def _full_path(self, rel_path: str) -> str:
        """Get full path from relative path."""
        return str(self.project_root / rel_path)

    # =========================================================================
    # FILE CONTEXT CACHE
    # =========================================================================

    def get_file_context(self, file_path: str) -> Optional[Any]:
        """Get cached file context."""
        key = f"context:{file_path}"
        return self.file_contexts.get(key, self._full_path(file_path))

    def set_file_context(
        self,
        file_path: str,
        context: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Cache file context."""
        key = f"context:{file_path}"
        self.file_contexts.set(
            key,
            context,
            ttl_seconds=ttl_seconds,
            file_path=self._full_path(file_path),
        )

    # =========================================================================
    # IMPACT GRAPH CACHE
    # =========================================================================

    def get_impact_graph(self, file_path: str) -> Optional[Any]:
        """Get cached impact graph."""
        key = f"impact:{file_path}"
        return self.impact_graphs.get(key, self._full_path(file_path))

    def set_impact_graph(
        self,
        file_path: str,
        graph: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Cache impact graph."""
        key = f"impact:{file_path}"
        self.impact_graphs.set(
            key,
            graph,
            ttl_seconds=ttl_seconds,
            file_path=self._full_path(file_path),
        )

    # =========================================================================
    # PATTERNS CACHE
    # =========================================================================

    def get_patterns(self, query: str) -> Optional[Any]:
        """Get cached patterns for a query."""
        key = f"patterns:{self._hash_query(query)}"
        return self.patterns.get(key)

    def set_patterns(
        self,
        query: str,
        patterns: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Cache patterns for a query."""
        key = f"patterns:{self._hash_query(query)}"
        self.patterns.set(key, patterns, ttl_seconds=ttl_seconds)

    def _hash_query(self, query: str) -> str:
        """Hash a query string for cache key."""
        return hashlib.md5(query.encode()).hexdigest()[:12]

    # =========================================================================
    # METRICS CACHE
    # =========================================================================

    def get_metrics(self, file_path: str) -> Optional[Any]:
        """Get cached file metrics."""
        key = f"metrics:{file_path}"
        return self.metrics.get(key, self._full_path(file_path))

    def set_metrics(
        self,
        file_path: str,
        metrics: Any,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Cache file metrics."""
        key = f"metrics:{file_path}"
        self.metrics.set(
            key,
            metrics,
            ttl_seconds=ttl_seconds,
            file_path=self._full_path(file_path),
        )

    # =========================================================================
    # INVALIDATION
    # =========================================================================

    def invalidate_file(self, file_path: str) -> int:
        """
        Invalidate all cache entries for a file.

        Returns:
            Total number of entries invalidated
        """
        count = 0
        count += self.file_contexts.invalidate(f"context:{file_path}")
        count += self.impact_graphs.invalidate(f"impact:{file_path}")
        count += self.metrics.invalidate(f"metrics:{file_path}")

        # Also invalidate entries that depend on this file
        with self._lock:
            dependents = self._dependency_map.get(file_path, set())
            for dep in dependents:
                count += self.invalidate_file(dep)

        return count

    def invalidate_directory(self, directory: str) -> int:
        """Invalidate all cache entries for files in a directory."""
        count = 0
        pattern = f"*:{directory}/*"
        count += self.file_contexts.invalidate_pattern(pattern)
        count += self.impact_graphs.invalidate_pattern(pattern)
        count += self.metrics.invalidate_pattern(pattern)
        return count

    def register_dependency(self, file_path: str, depends_on: str) -> None:
        """
        Register that file_path depends on depends_on.

        When depends_on is invalidated, file_path will also be invalidated.
        """
        with self._lock:
            if depends_on not in self._dependency_map:
                self._dependency_map[depends_on] = set()
            self._dependency_map[depends_on].add(file_path)

    # =========================================================================
    # WARM-UP & PERSISTENCE
    # =========================================================================

    def warm_up_files(
        self,
        file_paths: List[str],
        context_loader: Callable[[str], Any],
    ) -> int:
        """
        Warm up cache for multiple files.

        Args:
            file_paths: Files to warm up
            context_loader: Function to load context for a file

        Returns:
            Number of entries warmed
        """
        keys = [f"context:{fp}" for fp in file_paths]
        file_map = {f"context:{fp}": self._full_path(fp) for fp in file_paths}

        def loader(key: str) -> Any:
            file_path = key.split(":", 1)[1]
            return context_loader(file_path)

        return self.file_contexts.warm_up(keys, loader, file_map)

    def save_to_disk(self) -> None:
        """Save cache state to disk for persistence."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # For now, just save stats - full persistence can be added later
        stats = self.get_stats()
        stats_file = self._cache_dir / "stats.json"

        try:
            with open(stats_file, "w") as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache stats: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all cache layers."""
        return {
            "file_contexts": self.file_contexts.get_stats().to_dict(),
            "impact_graphs": self.impact_graphs.get_stats().to_dict(),
            "patterns": self.patterns.get_stats().to_dict(),
            "metrics": self.metrics.get_stats().to_dict(),
        }

    def clear_all(self) -> int:
        """Clear all caches. Returns total count cleared."""
        count = 0
        count += self.file_contexts.clear()
        count += self.impact_graphs.clear()
        count += self.patterns.clear()
        count += self.metrics.clear()

        with self._lock:
            self._dependency_map.clear()

        return count
