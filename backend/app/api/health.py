from fastapi import APIRouter
from sqlalchemy import text
from app.database import SessionLocal
from app.config import APP_ENV, get_startup_timestamp, REDIS_URL, APP_VERSION

router = APIRouter(prefix="/api/health", tags=["health"])

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
        r = redis.from_url(REDIS_URL)
        r.ping()
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unavailable", "detail": str(e)}


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
        },
    }


@router.get("/ready")
def readiness_check():
    """Kubernetes-style readiness: DB must be reachable."""
    db = _check_db()
    if db["status"] != "healthy":
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ready"}
