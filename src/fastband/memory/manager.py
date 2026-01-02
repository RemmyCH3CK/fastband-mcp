"""
Memory Manager - Claude Memory System for Fastband.

Provides:
1. Automatic context editing (relevance-based pruning)
2. Cross-session learning (pattern extraction)
3. Self-healing storage (validation & migration)

Ported from Fastband_MCP/memory_manager.py
"""

import hashlib
import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastband.memory.models import FixPattern, SessionContext, TicketMemory

logger = logging.getLogger(__name__)

# Configuration
SCHEMA_VERSION = "1.0.0"
MAX_TICKET_MEMORIES_PER_APP = 500
MEMORY_DECAY_DAYS = 180
PRUNE_THRESHOLD = 0.1
MAX_MEMORIES_PER_QUERY = 50

# Stopwords for keyword extraction
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "not", "no", "yes",
    "when", "where", "which", "who", "whom", "whose", "why", "how",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "only", "own", "same", "so", "than", "too", "very",
    "just", "also", "now", "here", "there", "then", "once", "always",
}


class MemoryManager:
    """
    Manages Claude Memory for Fastband with:
    - Automatic context editing (relevance-based pruning)
    - Cross-session learning (pattern extraction)
    - Self-healing storage (validation & migration)
    """

    def __init__(self, base_path: Optional[Path] = None):
        """Initialize memory manager.

        Args:
            base_path: Path to memory storage. Defaults to .fastband/memory
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            # Use .fastband/memory in project root or home
            self.base_path = Path(
                os.environ.get("FASTBAND_MEMORY_PATH", ".fastband/memory")
            )

        self._ensure_structure()
        self._load_indexes()

    def _ensure_structure(self):
        """Create memory directory structure if needed."""
        dirs = [
            self.base_path / "tickets",
            self.base_path / "patterns",
            self.base_path / "sessions",
            self.base_path / "index",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        # Initialize metadata if not exists
        metadata_path = self.base_path / "index" / "metadata.json"
        if not metadata_path.exists():
            self._save_json(
                metadata_path,
                {
                    "schema_version": SCHEMA_VERSION,
                    "created_at": datetime.now().isoformat(),
                    "total_memories": 0,
                    "total_patterns": 0,
                    "last_pruned": None,
                },
            )

    def _load_indexes(self):
        """Load semantic index for fast lookups."""
        index_path = self.base_path / "index" / "semantic_index.json"
        if index_path.exists():
            self.semantic_index = self._load_json(index_path)
        else:
            self.semantic_index = {
                "keyword_to_tickets": {},
                "file_to_tickets": {},
                "type_to_tickets": {},
                "app_to_tickets": {},
            }

    def _save_indexes(self):
        """Persist semantic index."""
        index_path = self.base_path / "index" / "semantic_index.json"
        self._save_json(index_path, self.semantic_index)

    def _load_json(self, path: Path) -> Dict:
        """Load JSON with error recovery."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError, UnicodeDecodeError) as e:
            logger.warning(f"Error loading {path}: {e}")
            return {}

    def _save_json(self, path: Path, data: Dict):
        """Save JSON with atomic write."""
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp_path.replace(path)

    def _get_ticket_memory_path(self, app: str, ticket_id: str) -> Path:
        """Get path for a ticket memory file."""
        safe_app = re.sub(r"[^\w\-]", "_", app)
        return self.base_path / "tickets" / f"{safe_app}_{ticket_id}.json"

    # =========================================================================
    # TICKET MEMORY OPERATIONS
    # =========================================================================

    def save_ticket_memory(self, memory: TicketMemory) -> Dict[str, Any]:
        """Save a ticket memory and update indexes."""
        path = self._get_ticket_memory_path(memory.app, memory.ticket_id)
        self._save_json(path, memory.to_dict())

        # Update semantic index
        self._index_memory(memory)
        self._save_indexes()

        # Update metadata
        self._update_metadata(memories_delta=1)

        return {
            "success": True,
            "memory_id": memory.ticket_id,
            "app": memory.app,
            "path": str(path),
        }

    def get_ticket_memory(
        self, ticket_id: str, app: Optional[str] = None
    ) -> Optional[TicketMemory]:
        """Retrieve a specific ticket memory."""
        # Search by app if provided
        if app:
            path = self._get_ticket_memory_path(app, ticket_id)
            if path.exists():
                data = self._load_json(path)
                if data:
                    memory = TicketMemory.from_dict(data)
                    memory.access_count += 1
                    memory.last_accessed = datetime.now().isoformat()
                    self._save_json(path, memory.to_dict())
                    return memory
            return None

        # Search all tickets
        tickets_dir = self.base_path / "tickets"
        for path in tickets_dir.glob(f"*_{ticket_id}.json"):
            if path.name.startswith("._"):
                continue
            data = self._load_json(path)
            if data:
                memory = TicketMemory.from_dict(data)
                memory.access_count += 1
                memory.last_accessed = datetime.now().isoformat()
                self._save_json(path, memory.to_dict())
                return memory

        return None

    def _index_memory(self, memory: TicketMemory):
        """Add memory to semantic index for fast retrieval."""
        ticket_id = memory.ticket_id

        # Index by keywords
        for kw in memory.keywords:
            kw_lower = kw.lower()
            if kw_lower not in self.semantic_index["keyword_to_tickets"]:
                self.semantic_index["keyword_to_tickets"][kw_lower] = []
            if ticket_id not in self.semantic_index["keyword_to_tickets"][kw_lower]:
                self.semantic_index["keyword_to_tickets"][kw_lower].append(ticket_id)

        # Index by files
        for f in memory.files_modified:
            f_key = f.lower()
            if f_key not in self.semantic_index["file_to_tickets"]:
                self.semantic_index["file_to_tickets"][f_key] = []
            if ticket_id not in self.semantic_index["file_to_tickets"][f_key]:
                self.semantic_index["file_to_tickets"][f_key].append(ticket_id)

        # Index by type
        t_key = memory.ticket_type.lower()
        if t_key not in self.semantic_index["type_to_tickets"]:
            self.semantic_index["type_to_tickets"][t_key] = []
        if ticket_id not in self.semantic_index["type_to_tickets"][t_key]:
            self.semantic_index["type_to_tickets"][t_key].append(ticket_id)

        # Index by app
        app_key = memory.app.lower()
        if app_key not in self.semantic_index["app_to_tickets"]:
            self.semantic_index["app_to_tickets"][app_key] = []
        if ticket_id not in self.semantic_index["app_to_tickets"][app_key]:
            self.semantic_index["app_to_tickets"][app_key].append(ticket_id)

    # =========================================================================
    # AUTOMATIC CONTEXT EDITING (Relevance-Based Retrieval)
    # =========================================================================

    def query_memories(
        self,
        query: str,
        app: Optional[str] = None,
        ticket_type: Optional[str] = None,
        files: Optional[List[str]] = None,
        session: Optional[SessionContext] = None,
        max_results: int = MAX_MEMORIES_PER_QUERY,
    ) -> List[Tuple[TicketMemory, float]]:
        """
        Query memories with automatic relevance scoring.

        Returns: List of (memory, relevance_score) tuples
        """
        candidates = []
        query_lower = query.lower()
        query_words = set(re.findall(r"\w+", query_lower))

        # Gather candidate ticket IDs from index
        candidate_ids: Set[str] = set()

        # Match keywords
        for word in query_words:
            if word in self.semantic_index["keyword_to_tickets"]:
                candidate_ids.update(self.semantic_index["keyword_to_tickets"][word])

        # Match files
        if files:
            for f in files:
                f_key = f.lower()
                if f_key in self.semantic_index["file_to_tickets"]:
                    candidate_ids.update(self.semantic_index["file_to_tickets"][f_key])

        # Match type
        if ticket_type:
            t_key = ticket_type.lower()
            if t_key in self.semantic_index["type_to_tickets"]:
                candidate_ids.update(self.semantic_index["type_to_tickets"][t_key])

        # Match app
        if app:
            app_key = app.lower()
            if app_key in self.semantic_index["app_to_tickets"]:
                candidate_ids.update(self.semantic_index["app_to_tickets"][app_key])

        # If no index matches, do full scan
        if not candidate_ids:
            candidate_ids = self._get_all_ticket_ids()

        # Score each candidate
        for ticket_id in candidate_ids:
            memory = self.get_ticket_memory(ticket_id)
            if not memory:
                continue

            # Filter by app if specified
            if app and memory.app.lower() != app.lower():
                continue

            # Skip already-loaded memories in this session
            if session and ticket_id in session.loaded_memories:
                continue

            # Calculate relevance score
            score = self._calculate_relevance(memory, query_words, files, ticket_type)

            if score > PRUNE_THRESHOLD:
                candidates.append((memory, score))

        # Sort by relevance and return top N
        candidates.sort(key=lambda x: -x[1])
        results = candidates[:max_results]

        # Mark as loaded in session
        if session:
            for memory, _ in results:
                session.loaded_memories.add(memory.ticket_id)

        return results

    def _calculate_relevance(
        self,
        memory: TicketMemory,
        query_words: Set[str],
        files: Optional[List[str]],
        ticket_type: Optional[str],
    ) -> float:
        """Calculate relevance score for a memory."""
        score = 0.0

        # Keyword match
        memory_keywords = set(kw.lower() for kw in memory.keywords)
        memory_text = (
            f"{memory.title} {memory.problem_summary} {memory.solution_summary}".lower()
        )
        memory_words = set(re.findall(r"\w+", memory_text))

        keyword_overlap = len(query_words & memory_keywords)
        text_overlap = len(query_words & memory_words)

        if memory_keywords and query_words:
            score += 0.3 * (keyword_overlap / len(query_words))
        score += 0.1 * min(text_overlap / 5, 1.0)

        # File match
        if files:
            memory_files = set(f.lower() for f in memory.files_modified)
            query_files = set(f.lower() for f in files)
            file_overlap = len(query_files & memory_files)
            if query_files:
                score += 0.3 * (file_overlap / len(query_files))

        # Type match
        if ticket_type and memory.ticket_type.lower() == ticket_type.lower():
            score += 0.1

        # Recency bonus
        try:
            resolved = datetime.fromisoformat(memory.resolved_date)
            days_old = (datetime.now() - resolved).days
            recency = max(0, 1 - (days_old / MEMORY_DECAY_DAYS))
            score += 0.1 * recency
        except Exception:
            pass

        # Access frequency bonus
        access_bonus = min(memory.access_count / 10, 1.0)
        score += 0.1 * access_bonus

        return score

    def _get_all_ticket_ids(self) -> Set[str]:
        """Get all ticket IDs."""
        ids = set()
        tickets_dir = self.base_path / "tickets"
        if tickets_dir.exists():
            for f in tickets_dir.glob("*.json"):
                if f.name.startswith("._"):
                    continue
                # Extract ticket_id from filename (app_ticketid.json)
                parts = f.stem.rsplit("_", 1)
                if len(parts) == 2:
                    ids.add(parts[1])
        return ids

    # =========================================================================
    # CROSS-SESSION LEARNING (Pattern Extraction)
    # =========================================================================

    def extract_fix_patterns(self) -> Dict[str, Any]:
        """Analyze resolved tickets to extract common fix patterns."""
        patterns_found = []

        # Group memories by common characteristics
        file_groups = defaultdict(list)
        keyword_groups = defaultdict(list)

        for ticket_id in self._get_all_ticket_ids():
            memory = self.get_ticket_memory(ticket_id)
            if not memory:
                continue

            for f in memory.files_modified:
                file_groups[f].append(memory)
            for kw in memory.keywords:
                keyword_groups[kw.lower()].append(memory)

        # Find patterns in file groups
        for file_path, memories in file_groups.items():
            if len(memories) >= 3:
                solution_words = defaultdict(int)
                for m in memories:
                    for word in re.findall(r"\w+", m.solution_summary.lower()):
                        solution_words[word] += 1

                common_words = [
                    w for w, c in solution_words.items() if c >= len(memories) * 0.5
                ]

                if common_words:
                    pattern_id = hashlib.md5(file_path.encode()).hexdigest()[:8]
                    pattern = FixPattern(
                        pattern_id=pattern_id,
                        name=f"Common fixes for {Path(file_path).name}",
                        description=f"Pattern from {len(memories)} tickets",
                        error_signatures=[],
                        file_patterns=[file_path],
                        keyword_triggers=common_words[:5],
                        solution_template=self._generate_solution_template(memories),
                        common_files_to_check=[file_path],
                        example_ticket_ids=[m.ticket_id for m in memories[:3]],
                        occurrence_count=len(memories),
                    )
                    patterns_found.append(pattern)

        # Save patterns
        patterns_path = self.base_path / "patterns" / "fix_patterns.json"
        existing = (
            self._load_json(patterns_path) if patterns_path.exists() else {"patterns": []}
        )

        pattern_map = {p["pattern_id"]: p for p in existing.get("patterns", [])}
        for p in patterns_found:
            if p.pattern_id in pattern_map:
                pattern_map[p.pattern_id]["occurrence_count"] = p.occurrence_count
            else:
                pattern_map[p.pattern_id] = p.to_dict()

        existing["patterns"] = list(pattern_map.values())
        existing["last_extracted"] = datetime.now().isoformat()
        self._save_json(patterns_path, existing)

        return {
            "success": True,
            "patterns_found": len(patterns_found),
            "total_patterns": len(pattern_map),
        }

    def _generate_solution_template(self, memories: List[TicketMemory]) -> str:
        """Generate a solution template from similar ticket solutions."""
        phrases = [m.solution_summary for m in memories[:5]]
        if not phrases:
            return "Check similar resolved tickets for solution approach."
        return max(phrases, key=len)

    def get_relevant_patterns(
        self,
        query: str,
        files: Optional[List[str]] = None,
        session: Optional[SessionContext] = None,
    ) -> List[FixPattern]:
        """Get fix patterns relevant to current problem."""
        patterns_path = self.base_path / "patterns" / "fix_patterns.json"
        if not patterns_path.exists():
            return []

        data = self._load_json(patterns_path)
        patterns = [FixPattern.from_dict(p) for p in data.get("patterns", [])]

        query_words = set(re.findall(r"\w+", query.lower()))
        query_files = set(f.lower() for f in (files or []))

        relevant = []
        for p in patterns:
            if session and p.pattern_id in session.loaded_patterns:
                continue

            pattern_keywords = set(kw.lower() for kw in p.keyword_triggers)
            if query_words & pattern_keywords:
                relevant.append(p)
                continue

            pattern_files = set(f.lower() for f in p.file_patterns)
            if query_files & pattern_files:
                relevant.append(p)

        if session:
            for p in relevant:
                session.loaded_patterns.add(p.pattern_id)

        return relevant

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    def create_session(
        self, agent_name: str, session_id: Optional[str] = None
    ) -> SessionContext:
        """Create a new session context."""
        if not session_id:
            session_id = hashlib.md5(
                f"{agent_name}-{datetime.now().isoformat()}".encode()
            ).hexdigest()[:12]

        session = SessionContext(
            session_id=session_id,
            agent_name=agent_name,
            started_at=datetime.now().isoformat(),
        )

        path = self.base_path / "sessions" / f"{session_id}.json"
        self._save_json(path, session.to_dict())

        return session

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """Retrieve an existing session."""
        path = self.base_path / "sessions" / f"{session_id}.json"
        if path.exists():
            data = self._load_json(path)
            return SessionContext.from_dict(data)
        return None

    def save_session(self, session: SessionContext):
        """Persist session state."""
        path = self.base_path / "sessions" / f"{session.session_id}.json"
        self._save_json(path, session.to_dict())

    def add_session_discovery(
        self, session: SessionContext, discovery: str, category: str = "general"
    ):
        """Add a discovery made during this session."""
        session.session_discoveries.append(
            {
                "discovery": discovery,
                "category": category,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.save_session(session)

    # =========================================================================
    # MAINTENANCE & SELF-HEALING
    # =========================================================================

    def prune_stale_memories(self, dry_run: bool = True) -> Dict[str, Any]:
        """Remove memories below relevance threshold."""
        pruned = []
        kept = 0

        for ticket_id in self._get_all_ticket_ids():
            memory = self.get_ticket_memory(ticket_id)
            if not memory:
                continue

            try:
                resolved = datetime.fromisoformat(memory.resolved_date)
                days_old = (datetime.now() - resolved).days
                decay = max(0.1, 1 - (days_old / MEMORY_DECAY_DAYS))
            except Exception:
                decay = 0.5
                days_old = None

            adjusted_relevance = memory.relevance_score * decay

            if adjusted_relevance < PRUNE_THRESHOLD:
                pruned.append(
                    {
                        "ticket_id": ticket_id,
                        "app": memory.app,
                        "relevance": adjusted_relevance,
                        "days_old": days_old,
                    }
                )
                if not dry_run:
                    path = self._get_ticket_memory_path(memory.app, ticket_id)
                    path.unlink(missing_ok=True)
            else:
                kept += 1

        if not dry_run:
            self._update_metadata(last_pruned=datetime.now().isoformat())

        return {
            "success": True,
            "dry_run": dry_run,
            "pruned_count": len(pruned),
            "kept_count": kept,
            "pruned_memories": pruned[:20],
        }

    def _update_metadata(
        self,
        memories_delta: int = 0,
        patterns_delta: int = 0,
        last_pruned: Optional[str] = None,
    ):
        """Update global metadata."""
        path = self.base_path / "index" / "metadata.json"
        meta = self._load_json(path)
        meta["total_memories"] = meta.get("total_memories", 0) + memories_delta
        meta["total_patterns"] = meta.get("total_patterns", 0) + patterns_delta
        if last_pruned:
            meta["last_pruned"] = last_pruned
        meta["last_updated"] = datetime.now().isoformat()
        self._save_json(path, meta)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        meta_path = self.base_path / "index" / "metadata.json"
        meta = self._load_json(meta_path) if meta_path.exists() else {}

        tickets_dir = self.base_path / "tickets"
        total_memories = (
            len(list(tickets_dir.glob("*.json"))) if tickets_dir.exists() else 0
        )

        patterns_path = self.base_path / "patterns" / "fix_patterns.json"
        pattern_count = 0
        if patterns_path.exists():
            data = self._load_json(patterns_path)
            pattern_count = len(data.get("patterns", []))

        sessions_dir = self.base_path / "sessions"
        session_count = (
            len(list(sessions_dir.glob("*.json"))) if sessions_dir.exists() else 0
        )

        return {
            "schema_version": SCHEMA_VERSION,
            "total_memories": total_memories,
            "total_patterns": pattern_count,
            "total_sessions": session_count,
            "index_keywords": len(self.semantic_index.get("keyword_to_tickets", {})),
            "index_files": len(self.semantic_index.get("file_to_tickets", {})),
            "last_pruned": meta.get("last_pruned"),
            "last_updated": meta.get("last_updated"),
        }

    # =========================================================================
    # TICKET RESOLUTION INTEGRATION
    # =========================================================================

    def create_memory_from_ticket(
        self, ticket: Dict[str, Any]
    ) -> Optional[TicketMemory]:
        """Create a memory from a resolved ticket."""
        status = ticket.get("status", "")
        if "Resolved" not in status and "Closed" not in status:
            return None

        text = f"{ticket.get('title', '')} {ticket.get('description', '')}"
        keywords = self._extract_keywords(text)

        problem = ticket.get("problem_summary") or ticket.get("description", "")[:200]
        solution = ticket.get("solution_summary") or ticket.get("resolution", "")[:300]

        if not problem or not solution:
            return None

        return TicketMemory(
            ticket_id=str(ticket.get("ticket_id")),
            app=ticket.get("app", "unknown"),
            app_version=ticket.get("app_version"),
            title=ticket.get("title", ""),
            problem_summary=problem,
            solution_summary=solution,
            files_modified=ticket.get("files_modified", []),
            keywords=keywords,
            ticket_type=ticket.get("ticket_type", "Unknown"),
            resolved_date=ticket.get("end_date") or datetime.now().strftime("%Y-%m-%d"),
        )

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text."""
        words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", text.lower())
        word_counts = defaultdict(int)
        for w in words:
            if len(w) >= 3 and w not in STOPWORDS:
                word_counts[w] += 1

        sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
        return [w for w, _ in sorted_words[:15]]


# Singleton instance
_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get singleton memory manager instance."""
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
