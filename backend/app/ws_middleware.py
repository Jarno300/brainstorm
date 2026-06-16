"""
WebSocket route rewriting middleware.

Handles legacy /api/ws/* WebSocket upgrade requests by rewriting them
to /api/v1/ws/* before the router sees them. Standard HTTP middleware
can't intercept WebSocket upgrades, so this works at the ASGI scope level.
"""


class WebSocketVersionMiddleware:
    """ASGI middleware that rewrites legacy WebSocket paths.

    WebSocket upgrade requests to /api/ws/* are rewritten to /api/v1/ws/*
    so the realtime router (mounted at /api/v1) handles them.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            path = scope.get("path", "")
            if path.startswith("/api/") and not path.startswith("/api/v1/"):
                scope["path"] = path.replace("/api/", "/api/v1/", 1)
        return await self.app(scope, receive, send)
