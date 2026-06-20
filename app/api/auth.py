from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends, status, Header, Cookie, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.core.db import get_db
from app.core.security import (
    create_access_token, decode_access_token,
    verify_password, get_password_hash,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.core.config import settings

router = APIRouter()


# --- Dependencies ---

async def get_current_user(
    auth_header: str | None = Header(None, alias="Authorization"),
    access_token: str | None = Cookie(None, alias="access_token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract user from an HttpOnly browser cookie or Authorization Bearer token."""
    token = access_token
    if auth_header:
        try:
            scheme, bearer_token = auth_header.split()
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid auth scheme")
            token = bearer_token
        except ValueError:
            raise HTTPException(status_code=401, detail="Missing or malformed token")

    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")

    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


async def get_current_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """Ensure current user is admin."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# --- Endpoints ---

def _set_session_cookie(response: Response, token: str) -> None:
    """Set the web admin session cookie while keeping token responses for desktop clients."""
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.environment.lower() == "production",
        samesite="lax",
        path="/",
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Login and get JWT access token."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    if not user.is_activated:
        raise HTTPException(status_code=403, detail="Account not activated. Please activate first.")

    # SECURITY: Audit login action
    from app.models.audit_log import AuditLog
    audit = AuditLog(user_id=user.id, action="login", details={"email": user.email})
    db.add(audit)
    await db.flush()

    token = create_access_token(str(user.id), user.role)
    _set_session_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register endpoint — DISABLED for production. Only admin can create employees."""
    raise HTTPException(
        status_code=403,
        detail="Self-registration is disabled. Contact your administrator for an invite token."
    )


@router.post("/activate", response_model=TokenResponse)
async def activate_account(
    request: dict,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Activate an employee account using invite token + set password."""
    token = request.get("token", "")
    password = request.get("password", "")

    if not token or not password:
        raise HTTPException(status_code=400, detail="Token and password required")

    # SECURITY: Password policy - minimum 8 chars, must have letter + number
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one letter and one number"
        )

    result = await db.execute(select(User).where(User.invite_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Invalid invite token")
    if user.is_activated:
        raise HTTPException(status_code=409, detail="Account already activated")

    user.hashed_password = get_password_hash(password)
    user.is_activated = True
    user.is_active = True
    user.invite_token = None
    await db.flush()

    # SECURITY: Audit account activation
    from app.models.audit_log import AuditLog
    audit = AuditLog(user_id=user.id, action="account_activated", details={"email": user.email})
    db.add(audit)

    access_token = create_access_token(str(user.id), user.role)
    _set_session_cookie(response, access_token)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return user


@router.post("/logout")
async def logout(response: Response):
    """Clear the browser session cookie."""
    response.delete_cookie("access_token", path="/")
    return {"message": "Logged out"}


@router.post("/ws-token")
async def create_websocket_token(user: User = Depends(get_current_user)):
    """Create a short-lived token intended for WebSocket connection URLs."""
    token = create_access_token(
        str(user.id),
        user.role,
        expires_delta=timedelta(minutes=5),
    )
    return {"access_token": token, "expires_in": 300, "token_type": "bearer"}
