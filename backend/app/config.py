import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pathlib import Path

# Load .env file if present.
# config.py is at: backend/app/config.py (2 levels deep)
# .env is at:      backend/.env or project-root/.env
# Docker Compose injects vars directly — this matters for local dev only.
_config_dir = Path(__file__).resolve().parent  # backend/app/
_backend_dir = _config_dir.parent               # backend/
_root_dir = _backend_dir.parent                 # project root/

for _candidate in (_backend_dir / ".env", _root_dir / ".env"):
    if _candidate.exists():
        load_dotenv(_candidate)
        break
else:
    load_dotenv()  # fallback: CWD

# ─── App Metadata ─────────────────────────────────────────────
APP_TITLE = os.getenv("APP_TITLE", "Brainstorm API")
APP_DESCRIPTION = os.getenv("APP_DESCRIPTION", "AI Chat Platform with Knowledge Mapping")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

# ─── Database ─────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://raguser:ragpassword@localhost:5432/ragdb")

# ─── AI Providers ─────────────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_API_VERSION = os.getenv("ANTHROPIC_API_VERSION", "2024-02-15")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "2048"))      # max tokens to generate
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))              # context window size
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")              # keep model loaded in RAM
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "deepseek/deepseek-chat")
CLASSIFICATION_MODEL = os.getenv("CLASSIFICATION_MODEL", "")           # optional smaller model for classification tasks

# ─── CORS ─────────────────────────────────────────────────────
_CORS_DEFAULT = "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174,http://frontend:5173"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", _CORS_DEFAULT).split(",")

# ─── Redis / Celery ──────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# ─── Auth ─────────────────────────────────────────────────────
# In development, auto-generate a random key so there's never a
# hardcoded default that could accidentally reach production.
_SECRET_ENV = os.getenv("SECRET_KEY", "")
if _SECRET_ENV:
    SECRET_KEY = _SECRET_ENV
elif os.getenv("APP_ENV", "development") == "development":
    import secrets
    SECRET_KEY = secrets.token_hex(32)
else:
    raise RuntimeError(
        "SECRET_KEY is required in production/staging. "
        "Generate one with:  openssl rand -hex 32"
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "72"))

# Account lockout
ACCOUNT_LOCKOUT_MAX_ATTEMPTS = int(os.getenv("ACCOUNT_LOCKOUT_MAX_ATTEMPTS", "5"))
ACCOUNT_LOCKOUT_WINDOW_MINUTES = int(os.getenv("ACCOUNT_LOCKOUT_WINDOW_MINUTES", "15"))
ACCOUNT_LOCKOUT_DURATION_MINUTES = int(os.getenv("ACCOUNT_LOCKOUT_DURATION_MINUTES", "15"))

# ─── Server ───────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
APP_ENV = os.getenv("APP_ENV", "development")
APP_LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO")

# ─── Error Tracking (Sentry) ──────────────────────────────────
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
# Sample rate for performance tracing: 1.0 = all requests, 0.1 = 10%
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

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
    if not DEEPSEEK_API_KEY:
        warnings.append("DEEPSEEK_API_KEY not set — DeepSeek models will fail")
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
