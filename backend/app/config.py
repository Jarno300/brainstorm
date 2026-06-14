import os
from datetime import datetime, timezone

# ─── App Metadata ─────────────────────────────────────────────
APP_TITLE = os.getenv("APP_TITLE", "Brainstorm API")
APP_DESCRIPTION = os.getenv("APP_DESCRIPTION", "AI Chat Platform with Knowledge Mapping")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

# ─── Database ─────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://raguser:ragpassword@localhost:5432/ragdb")

# ─── AI Providers ─────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "ollama/llama3.2:1b")

# ─── CORS ─────────────────────────────────────────────────────
_CORS_DEFAULT = "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174,http://frontend:5173"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", _CORS_DEFAULT).split(",")

# ─── Redis / Celery ──────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# ─── Auth ─────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "brainstorm-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "72"))

# ─── Server ───────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
APP_ENV = os.getenv("APP_ENV", "development")
APP_LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO")

# ─── Startup Validation ───────────────────────────────────────

def validate_config():
    """Called at app startup. Raises ValueError with clear message if critical config is missing."""
    errors = []

    if not DATABASE_URL:
        errors.append("DATABASE_URL is required")
    elif APP_ENV != "development" and DATABASE_URL.startswith("sqlite"):
        errors.append(f"Cannot use SQLite in {APP_ENV} environment — set DATABASE_URL to a PostgreSQL connection string")

    # Warn about missing API keys (non-fatal)
    warnings = []
    if not OPENAI_API_KEY:
        warnings.append("OPENAI_API_KEY not set — OpenAI models will fail")
    if not ANTHROPIC_API_KEY:
        warnings.append("ANTHROPIC_API_KEY not set — Anthropic models will fail")

    if errors:
        raise ValueError(
            "Configuration errors:\n  - " + "\n  - ".join(errors)
        )

    return warnings


def get_startup_timestamp():
    return datetime.now(timezone.utc).isoformat()
