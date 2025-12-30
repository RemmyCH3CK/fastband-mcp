"""
Fastband AI Hub - Web-based AI Chat Interface.

Provides a comprehensive AI-driven platform for:
- Conversational setup and onboarding
- Natural language CLI for all platform operations
- RAG-powered memory for unlimited conversation history
- Platform analysis and MCP workflow recommendations
- Real-time streaming chat via SSE

Performance Optimizations (Issue #38):
- Session pooling for efficient resource management
- Streaming responses to reduce latency
- Tier-based rate limiting
- Cached embeddings for RAG queries

Architecture:
- HubSession: Per-client session abstraction
- ChatManager: Orchestrates AI provider + tool execution
- SemanticMemory: RAG-based long-term memory
- PlatformAnalyzer: Codebase analysis and recommendations
"""

from fastband.hub.chat import (
    ChatManager,
    MessagePipeline,
    ToolExecutor,
)
from fastband.hub.memory import (
    MemoryStore,
    SemanticMemory,
)
from fastband.hub.models import (
    # Chat models
    ChatMessage,
    Conversation,
    ConversationStatus,
    # Session models
    HubSession,
    MemoryContext,
    # Memory models
    MemoryEntry,
    MessageRole,
    SessionConfig,
    SessionStatus,
    # Tier models
    SubscriptionTier,
    TierLimits,
    UsageStats,
)
from fastband.hub.server import (
    create_server_app,
    get_static_directory,
    mount_dashboard,
    run_server,
)
from fastband.hub.session import (
    SessionManager,
    get_session_manager,
)

__all__ = [
    # Session
    "HubSession",
    "SessionConfig",
    "SessionStatus",
    "SessionManager",
    "get_session_manager",
    # Chat
    "ChatMessage",
    "MessageRole",
    "Conversation",
    "ConversationStatus",
    "ChatManager",
    "MessagePipeline",
    "ToolExecutor",
    # Memory
    "MemoryEntry",
    "MemoryContext",
    "SemanticMemory",
    "MemoryStore",
    # Tiers
    "SubscriptionTier",
    "TierLimits",
    "UsageStats",
    # Server
    "run_server",
    "create_server_app",
    "mount_dashboard",
    "get_static_directory",
]
