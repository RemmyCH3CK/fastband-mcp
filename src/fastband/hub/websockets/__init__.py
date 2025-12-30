"""
WebSocket management for real-time Control Plane updates.

Provides:
- WebSocketManager: Connection pool and broadcast management
- SubscriptionType: Event subscription categories
- Event types and message formats
"""

from fastband.hub.websockets.manager import (
    SubscriptionType,
    WebSocketManager,
    WSEventType,
    WSMessage,
    get_websocket_manager,
)

__all__ = [
    "WebSocketManager",
    "SubscriptionType",
    "WSMessage",
    "WSEventType",
    "get_websocket_manager",
]
