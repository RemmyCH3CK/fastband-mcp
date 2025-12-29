"""
Fastband AI Hub - Custom Exceptions.

Provides domain-specific exception classes for better error handling
and consistency with the rest of the Fastband codebase.
"""


class HubError(Exception):
    """Base exception for all hub-related errors."""

    def __init__(self, message: str, code: str = "HUB_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class SessionError(HubError):
    """Session-related errors."""

    def __init__(self, message: str, session_id: str = None):
        super().__init__(message, code="SESSION_ERROR")
        self.session_id = session_id


class SessionNotFoundError(SessionError):
    """Session not found."""

    def __init__(self, session_id: str):
        super().__init__(f"Session not found: {session_id}", session_id)
        self.code = "SESSION_NOT_FOUND"


class SessionLimitError(SessionError):
    """Maximum sessions reached."""

    def __init__(self, max_sessions: int):
        super().__init__(
            f"Maximum sessions ({max_sessions}) reached",
            session_id=None,
        )
        self.code = "SESSION_LIMIT_EXCEEDED"
        self.max_sessions = max_sessions


class ChatError(HubError):
    """Chat-related errors."""

    def __init__(self, message: str, conversation_id: str = None):
        super().__init__(message, code="CHAT_ERROR")
        self.conversation_id = conversation_id


class ToolExecutionError(ChatError):
    """Tool execution failed."""

    def __init__(self, tool_name: str, message: str):
        super().__init__(f"Tool '{tool_name}' failed: {message}")
        self.code = "TOOL_EXECUTION_ERROR"
        self.tool_name = tool_name


class RateLimitError(HubError):
    """Rate limit exceeded."""

    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message, code="RATE_LIMIT_EXCEEDED")
        self.retry_after = retry_after


class MemoryError(HubError):
    """Memory/RAG-related errors."""

    def __init__(self, message: str):
        super().__init__(message, code="MEMORY_ERROR")


class EmbeddingError(MemoryError):
    """Embedding generation failed."""

    def __init__(self, message: str, provider: str = None):
        super().__init__(f"Embedding failed: {message}")
        self.code = "EMBEDDING_ERROR"
        self.provider = provider


class BillingError(HubError):
    """Billing-related errors."""

    def __init__(self, message: str, customer_id: str = None):
        super().__init__(message, code="BILLING_ERROR")
        self.customer_id = customer_id


class SubscriptionError(BillingError):
    """Subscription-related errors."""

    def __init__(self, message: str, subscription_id: str = None):
        super().__init__(message)
        self.code = "SUBSCRIPTION_ERROR"
        self.subscription_id = subscription_id


class AuthenticationError(HubError):
    """Authentication-related errors."""

    def __init__(self, message: str):
        super().__init__(message, code="AUTHENTICATION_ERROR")


class AuthorizationError(HubError):
    """Authorization-related errors."""

    def __init__(self, message: str, required_tier: str = None):
        super().__init__(message, code="AUTHORIZATION_ERROR")
        self.required_tier = required_tier
