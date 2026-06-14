"""Auth endpoints: register + login + JWT token management."""
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
import bcrypt
import jwt

from app.database import get_db
from app.models.user import User
from app.config import SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_HOURS
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        user = db.query(User).filter(User.id == user_id).first()
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

@router.post("/register", response_model=AuthResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    # Validate input
    email = data.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

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
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not bcrypt.checkpw(data.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

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
