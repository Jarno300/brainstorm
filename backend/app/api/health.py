from fastapi import APIRouter
from sqlalchemy import text
from app.database import SessionLocal
from app.config import (
    APP_ENV, get_startup_timestamp, REDIS_URL, APP_VERSION,
    OLLAMA_BASE_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY,
)

router = APIRouter(prefix="/health", tags=["health"])

_startup_time = get_startup_timestamp()


def _check_db():
    """Check database connectivity."""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def _check_redis():
    """Check Redis connectivity (non-fatal)."""
    try:
        import redis
        r = redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        r.ping()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unavailable", "detail": str(e)}


def _check_ollama():
    """Check Ollama is reachable and has at least one model."""
    try:
        import httpx
        r = httpx.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=5)
        r.raise_for_status()
        models = r.json().get("models", [])
        return {"status": "healthy", "model_count": len(models)}
    except Exception as e:
        return {"status": "unavailable", "detail": str(e)}


def _check_openai():
    """Check OpenAI API key is configured and reachable."""
    if not OPENAI_API_KEY:
        return {"status": "unconfigured", "detail": "OPENAI_API_KEY not set"}
    try:
        import httpx
        r = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            timeout=5,
        )
        r.raise_for_status()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unavailable", "detail": str(e)}


def _check_anthropic():
    """Check Anthropic API key is configured."""
    if not ANTHROPIC_API_KEY:
        return {"status": "unconfigured", "detail": "ANTHROPIC_API_KEY not set"}
    # Anthropic has no lightweight health endpoint, so just confirm key presence
    return {"status": "configured"}


@router.get("")
def health_check():
    return {
        "status": "healthy",
        "version": APP_VERSION,
        "environment": APP_ENV,
        "uptime": _startup_time,
        "checks": {
            "database": _check_db(),
            "redis": _check_redis(),
            "ollama": _check_ollama(),
            "openai": _check_openai(),
            "anthropic": _check_anthropic(),
        },
    }


@router.get("/ready")
def readiness_check():
    """Kubernetes-style readiness: DB must be reachable.

    Redis is optional in development mode (it powers Celery and real-time
    updates but the app can function without it).
    """
    from app.config import APP_ENV

    db = _check_db()
    if db["status"] != "healthy":
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Redis is required in production, optional in development
    redis_status = _check_redis()
    if redis_status["status"] == "unavailable" and APP_ENV not in ("development",):
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {redis_status.get('detail', 'unknown')}")

    return {"status": "ready"}
