import logging
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Route
from app.api import brainstorms, chat, map, library, realtime, models, health, settings, export, auth, share, search, upload, research, organizations, api_keys, flashcards
from app.config import (
    APP_TITLE, APP_DESCRIPTION, APP_VERSION, CORS_ORIGINS, validate_config,
)
from app.database import wait_for_db
from app.logging_config import configure_logging, set_request_id
from app.metrics import MetricsMiddleware, metrics_endpoint
from app.rate_limit import RateLimitMiddleware
from app.ws_middleware import WebSocketVersionMiddleware

# Initialize structured logging
configure_logging()

logger = logging.getLogger(__name__)

# ── Error tracking (Sentry) ───────────────────────────────
# Initialize before the app so middleware captures startup errors.
from app.config import SENTRY_DSN, SENTRY_TRACES_SAMPLE_RATE, APP_ENV

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=APP_ENV,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        send_default_pii=False,
        integrations=[
            StarletteIntegration(transaction_style="url"),
            FastApiIntegration(transaction_style="url"),
        ],
    )
    logger.info("Sentry initialized | env=%s traces_rate=%.2f", APP_ENV, SENTRY_TRACES_SAMPLE_RATE)
else:
    logger.info("Sentry disabled — set SENTRY_DSN to enable error tracking")

# Validate configuration at startup
try:
    warnings = validate_config()
    for w in warnings:
        logger.warning("Config: %s", w)
except ValueError as e:
    logger.critical("Configuration error: %s", e)
    raise

# Wait for database with exponential backoff (handles Docker startup ordering)
wait_for_db()

app = FastAPI(
    title=APP_TITLE,
    description="""
Brainstorm is an AI-powered knowledge mapping platform that transforms topics
into interactive visual knowledge maps.

## Key Features

- **AI Research** — One-call deep topic research with structured knowledge extraction
- **Visual Canvas** — Drag-and-drop knowledge maps with parent/child/related taxonomy
- **Real-time WebSocket** — Live updates across the canvas
- **Library** — Auto-generated research summaries per topic
- **Multi-provider** — DeepSeek, OpenAI, Anthropic, and local Ollama models

## Authentication

Most endpoints require a JWT token. Obtain one via `POST /api/v1/auth/login`.
Include it as `Authorization: Bearer <token>` in request headers.
""",
    version=APP_VERSION,
    contact={
        "name": "Brainstorm Team",
    },
    license_info={
        "name": "MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "auth",
            "description": "User registration, login, and token management.",
        },
        {
            "name": "brainstorms",
            "description": "Create, list, update, and delete brainstorm sessions.",
        },
        {
            "name": "chat",
            "description": "Real-time AI chat (streaming) and synchronous messaging.",
        },
        {
            "name": "research",
            "description": "Deep topic research — single LLM call builds a complete knowledge map.",
        },
        {
            "name": "map",
            "description": "Knowledge map operations — topics, edges, and suggestion management.",
        },
        {
            "name": "library",
            "description": "Research library — AI-generated content organized by topic.",
        },
        {
            "name": "export",
            "description": "Export brainstorms as structured JSON, Markdown, or SVG.",
        },
        {
            "name": "search",
            "description": "Full-text search across brainstorms, topics, and library.",
        },
        {
            "name": "share",
            "description": "Generate and manage shareable links for brainstorms.",
        },
        {
            "name": "upload",
            "description": "Upload files (PDF, text) for context injection into brainstorms.",
        },
        {
            "name": "models",
            "description": "List available AI models across all configured providers.",
        },
        {
            "name": "settings",
            "description": "User and provider settings management.",
        },
        {
            "name": "health",
            "description": "Health check endpoints for monitoring and readiness probes.",
        },
    ],
)

# ── WebSocket legacy path rewrite (ASGI-level, before HTTP middleware) ──
# Must be added directly to the app, not via add_middleware, because
# it handles WebSocket scopes which BaseHTTPMiddleware ignores.
app.add_middleware(WebSocketVersionMiddleware)
# Reject requests with bodies larger than 1 MB before any
# processing to prevent memory exhaustion from oversized payloads.
_MAX_BODY_BYTES = 1_048_576  # 1 MB

class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit():
            if int(content_length) > _MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large. Maximum is {_MAX_BODY_BYTES // 1_048_576} MB."},
                )
        return await call_next(request)

app.add_middleware(BodySizeLimitMiddleware)

# Request ID middleware — tags every request for log traceability
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        set_request_id(req_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

app.add_middleware(RequestIDMiddleware)

# ── Version redirect: /api/* → /api/v1/* ─────────────────
# Must run before rate limiter and metrics so they see the canonical path.
class _VersionRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect legacy /api/* to /api/v1/* with deprecation notice."""
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            request.scope["path"] = path.replace("/api/", "/api/v1/", 1)
            request.scope["raw_path"] = request.scope["path"].encode()
            response = await call_next(request)
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "Sat, 01 Aug 2026 00:00:00 GMT"
            return response
        return await call_next(request)

app.add_middleware(_VersionRedirectMiddleware)

# Prometheus metrics — request count, latency, in-flight gauge
app.add_middleware(MetricsMiddleware)

# Rate limiting — Redis-backed sliding window per client IP + route
app.add_middleware(RateLimitMiddleware)

# CORS middleware — configurable via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers at /api/v1 ─────────────────────────
API_PREFIX = "/api/v1"

_routers = [
    brainstorms.router,
    chat.router,
    map.router,
    library.router,
    realtime.router,
    models.router,
    health.router,
    settings.router,
    export.router,
    auth.router,
    share.router,
    search.router,
    upload.router,
    research.router,
    organizations.router,
    api_keys.router,
    flashcards.router,
]

for r in _routers:
    app.include_router(r, prefix=API_PREFIX)

# ── Prometheus /metrics endpoint ─────────────────────────────
app.routes.append(Route("/metrics", metrics_endpoint, methods=["GET"]))

# ── Root redirect to API docs ────────────────────────────────
@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect root to API documentation."""
    return RedirectResponse("/docs")

# ── Global exception handler ─────────────────────────────────
# Sentry's FastAPI integration captures most exceptions, but this
# ensures any unhandled ones are logged and reported.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s %s", request.method, request.url.path)
    if SENTRY_DSN:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
