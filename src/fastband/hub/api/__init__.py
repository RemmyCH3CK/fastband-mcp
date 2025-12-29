"""
Fastband AI Hub - API Layer.

FastAPI-based REST API with SSE streaming for real-time chat.

Endpoints:
- POST /api/sessions - Create new session
- GET /api/sessions/{id} - Get session details
- DELETE /api/sessions/{id} - Terminate session
- POST /api/chat - Send chat message
- GET /api/chat/stream - Stream chat response (SSE)
- GET /api/conversations - List conversations
- GET /api/health - Health check
"""

from fastband.hub.api.app import create_app, get_app
from fastband.hub.api.routes import router

__all__ = [
    "create_app",
    "get_app",
    "router",
]
