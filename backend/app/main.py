import logging
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.api import brainstorms, chat, map, library, realtime, models, health, settings, export, auth, share
from app.config import (
    APP_TITLE, APP_DESCRIPTION, APP_VERSION, CORS_ORIGINS, validate_config,
)
from app.logging_config import configure_logging, set_request_id

# Initialize structured logging
configure_logging()

logger = logging.getLogger(__name__)

# Validate configuration at startup
try:
    warnings = validate_config()
    for w in warnings:
        logger.warning("Config: %s", w)
except ValueError as e:
    logger.critical("Configuration error: %s", e)
    raise

app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
)

# Request ID middleware — tags every request for log traceability
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        set_request_id(req_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

app.add_middleware(RequestIDMiddleware)

# CORS middleware — configurable via CORS_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(brainstorms.router)
app.include_router(chat.router)
app.include_router(map.router)
app.include_router(library.router)
app.include_router(realtime.router)
app.include_router(models.router)
app.include_router(health.router)
app.include_router(settings.router)
app.include_router(export.router)
app.include_router(auth.router)
app.include_router(share.router)
