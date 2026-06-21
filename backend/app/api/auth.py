"""Auth endpoints: register + login + JWT token management."""
import re
import uuid
import logging
import time as _time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
import bcrypt
import jwt

from app.database import get_db
from app.models.user import User
from app.config import (
    SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_HOURS,
    ACCOUNT_LOCKOUT_MAX_ATTEMPTS, ACCOUNT_LOCKOUT_WINDOW_MINUTES, ACCOUNT_LOCKOUT_DURATION_MINUTES,
    REDIS_URL,
)
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Schemas ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    tier: str


class UserInfoResponse(BaseModel):
    id: str
    email: str
    tier: str


# ─── Helpers ──────────────────────────────────────────────────

def _create_token(user: User) -> str:
    """Create a JWT token for the given user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "tier": user.tier,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: extract Bearer token, decode, return current user.

    Usage:
        @router.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            ...
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # API Key auth: tokens starting with "bsk_"
        if token.startswith("bsk_"):
            from app.models.api_key import ApiKey
            keys = db.query(ApiKey).filter(
                ApiKey.is_active == True,
            ).all()
            for key in keys:
                if ApiKey.verify(token, key.key_hash):
                    # Update last used
                    key.last_used_at = datetime.now(timezone.utc)
                    db.commit()
                    user = db.query(User).filter(User.id == key.user_id).first()
                    if not user:
                        raise HTTPException(status_code=401, detail="User not found")
                    return user
            raise HTTPException(status_code=401, detail="Invalid or revoked API key")

        # JWT auth
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        # Convert string from JWT to UUID for cross-database compatibility
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        user = db.query(User).filter(User.id == user_uuid).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Endpoints ────────────────────────────────────────────────

_SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;':\",.<>/?~`"


def _validate_password(password: str, email: str) -> str | None:
    """Validate password strength. Returns an error message or None if valid.

    Requirements:
      - At least 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit
      - At least one special character
      - Must not contain the email
    """
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return "Password must contain at least one digit"
    if not any(ch in _SPECIAL_CHARS for ch in password):
        return "Password must contain at least one special character"
    if email and email.lower() in password.lower():
        return "Password must not contain your email address"
    return None


# ─── In-memory login attempt tracking (fallback when Redis unavailable) ───
# Keys: email → list of (timestamp, success) tuples within the lockout window
_login_attempts: dict[str, list[tuple[float, bool]]] = defaultdict(list)


def _get_redis_client():
    """Lazily create a Redis client for lockout tracking."""
    try:
        import redis as _redis
        return _redis.Redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        return None


def _check_account_lockout(email: str) -> str | None:
    """Check if the account is locked out. Returns error message or None."""
    now = _time.time()
    window_start = now - (ACCOUNT_LOCKOUT_WINDOW_MINUTES * 60)
    lockout_start = now - (ACCOUNT_LOCKOUT_DURATION_MINUTES * 60)

    r = _get_redis_client()
    if r:
        try:
            key = f"lockout:login:{email}"
            # Count failed attempts within the window
            failed = int(r.zcount(key, window_start, "+inf") or 0)
            if failed >= ACCOUNT_LOCKOUT_MAX_ATTEMPTS:
                newest = r.zrange(key, -1, -1, withscores=True)
                if newest:
                    last_failure = newest[0][1]
                    remaining = int(lockout_start + (ACCOUNT_LOCKOUT_DURATION_MINUTES * 60) - now)
                    if remaining > 0:
                        return f"Account temporarily locked. Try again in {max(remaining // 60, 1)} minute(s)."
            r.close()
            return None
        except Exception:
            r.close()

    # Fallback: in-memory tracking
    attempts = _login_attempts[email]
    # Prune old entries
    _login_attempts[email] = [(ts, ok) for ts, ok in attempts if ts > window_start]
    failures_in_window = sum(1 for ts, ok in _login_attempts[email] if not ok and ts > window_start)
    if failures_in_window >= ACCOUNT_LOCKOUT_MAX_ATTEMPTS:
        last_failure = max((ts for ts, ok in _login_attempts[email] if not ok), default=0)
        remaining = int(last_failure + (ACCOUNT_LOCKOUT_DURATION_MINUTES * 60) - now)
        if remaining > 0:
            return f"Account temporarily locked. Try again in {max(remaining // 60, 1)} minute(s)."
    return None


def _record_login_attempt(email: str, success: bool) -> None:
    """Record a login attempt for lockout tracking."""
    now = _time.time()

    r = _get_redis_client()
    if r:
        try:
            key = f"lockout:login:{email}"
            r.zadd(key, {str(now): now})
            r.expire(key, ACCOUNT_LOCKOUT_WINDOW_MINUTES * 60 + 60)
            r.close()
            return
        except Exception:
            r.close()

    # Fallback: in-memory
    _login_attempts[email].append((now, success))


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    # Validate input
    email = data.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")

    pw_error = _validate_password(data.password, email)
    if pw_error:
        raise HTTPException(status_code=400, detail=pw_error)

    # Check for existing user
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    # Create user
    password_bytes = data.password.encode()
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode()
    user = User(
        email=email,
        password_hash=hashed,
        tier="free",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info("New user registered: %s", email)

    return AuthResponse(
        token=_create_token(user),
        user_id=str(user.id),
        email=user.email,
        tier=user.tier,
    )


@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate and return a JWT token."""
    email = data.email.strip().lower()

    # Check account lockout before any credential validation
    lockout_error = _check_account_lockout(email)
    if lockout_error:
        raise HTTPException(status_code=429, detail=lockout_error)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        _record_login_attempt(email, success=False)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not bcrypt.checkpw(data.password.encode(), user.password_hash.encode()):
        _record_login_attempt(email, success=False)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    _record_login_attempt(email, success=True)
    logger.info("User logged in: %s", email)

    return AuthResponse(
        token=_create_token(user),
        user_id=str(user.id),
        email=user.email,
        tier=user.tier,
    )


@router.get("/me", response_model=UserInfoResponse)
def me(current_user: User = Depends(get_current_user)):
    """Return the current user's info based on the Bearer token."""
    return UserInfoResponse(
        id=str(current_user.id),
        email=current_user.email,
        tier=current_user.tier,
    )
