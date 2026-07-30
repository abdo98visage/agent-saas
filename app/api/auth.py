from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from fastapi import APIRouter, HTTPException, Depends, status, Header, Cookie, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from uuid import UUID, uuid4

from app.core.db import get_db
from app.core.security import (
    create_access_token, decode_access_token,
    verify_password, get_password_hash,
)
from app.models.user import User
from app.models.agent_template import AgentTemplate
from app.models.profile import Profile
from app.models.profile_user import ProfileUser
from app.schemas.auth import BrowserSessionResponse, LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.core.config import settings
from app.models.auth_session import AuthSession

router = APIRouter()
_ws_ticket_fallback: dict[str, datetime] = {}


def _ws_ticket_key(ticket_id: str) -> str:
    return f"ws-ticket:{ticket_id}"


async def _store_ws_ticket(app, ticket_id: str, ttl_seconds: int) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    redis_client = getattr(app.state, "redis", None)
    if redis_client:
        await redis_client.set(_ws_ticket_key(ticket_id), "1", ex=ttl_seconds)
        return
    _ws_ticket_fallback[ticket_id] = expires_at


async def consume_ws_ticket(app, ticket_id: str) -> bool:
    redis_client = getattr(app.state, "redis", None)
    if redis_client:
        value = await redis_client.getdel(_ws_ticket_key(ticket_id))
        return bool(value)

    expires_at = _ws_ticket_fallback.pop(ticket_id, None)
    return bool(expires_at and expires_at > datetime.now(timezone.utc))


# --- Dependencies ---

async def get_current_user(
    request: Request,
    auth_header: str | None = Header(None, alias="Authorization"),
    access_token: str | None = Cookie(None, alias="access_token"),
    csrf_cookie: str | None = Cookie(None, alias="csrf_token"),
    csrf_header: str | None = Header(None, alias="X-CSRF-Token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract user from an HttpOnly browser cookie or Authorization Bearer token."""
    token = access_token
    uses_browser_cookie = bool(access_token and not auth_header)
    if (
        uses_browser_cookie
        and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}
        and (
            not csrf_cookie
            or not csrf_header
            or not secrets.compare_digest(csrf_cookie, csrf_header)
        )
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
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
    if int(payload.get("ver", 0)) != int(user.token_version or 0):
        raise HTTPException(status_code=401, detail="Token has been revoked")
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
    response.set_cookie(
        key="csrf_token",
        value=secrets.token_urlsafe(32),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=False,
        secure=settings.environment.lower() == "production",
        samesite="strict",
        path="/",
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.environment.lower() == "production",
        samesite="strict",
        path="/api/auth",
    )


def _refresh_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _normalize_client_type(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"browser", "desktop"} else "api"


async def _issue_token_pair(
    db: AsyncSession,
    user: User,
    response: Response,
    client_type: str,
) -> TokenResponse | BrowserSessionResponse:
    access_token = create_access_token(
        str(user.id),
        user.role,
        extra_claims={"ver": int(user.token_version or 0)},
    )
    raw_refresh_token = secrets.token_urlsafe(48)
    now = datetime.utcnow()
    db.add(
        AuthSession(
            user_id=user.id,
            refresh_token_hash=_refresh_token_hash(raw_refresh_token),
            token_version=int(user.token_version or 0),
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            client_type=client_type,
        )
    )
    await db.flush()
    _set_session_cookie(response, access_token)
    _set_refresh_cookie(response, raw_refresh_token)
    if client_type == "browser":
        return BrowserSessionResponse(expires_in=settings.access_token_expire_minutes * 60)
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh_token if client_type == "desktop" else None,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse | BrowserSessionResponse)
async def login(
    request: LoginRequest,
    response: Response,
    client_type_header: str | None = Header(None, alias="X-Client-Type"),
    db: AsyncSession = Depends(get_db),
):
    """Login and get JWT access token."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()
    now = datetime.utcnow()
    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user or not verify_password(request.password, user.hashed_password):
        if user:
            user.failed_login_attempts = int(user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= settings.auth_lockout_attempts:
                user.locked_until = now + timedelta(minutes=settings.auth_lockout_minutes)
                user.failed_login_attempts = 0
            await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    if not user.is_activated:
        raise HTTPException(status_code=403, detail="Account not activated. Please activate first.")
    user.failed_login_attempts = 0
    user.locked_until = None

    # SECURITY: Audit login action
    from app.models.audit_log import AuditLog
    audit = AuditLog(user_id=user.id, action="login", details={"email": user.email})
    db.add(audit)
    await db.flush()

    return await _issue_token_pair(db, user, response, _normalize_client_type(client_type_header))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register endpoint — DISABLED for production. Only admin can create employees."""
    raise HTTPException(
        status_code=403,
        detail="Self-registration is disabled. Contact your administrator for an invite token."
    )


@router.post("/activate", response_model=TokenResponse | BrowserSessionResponse)
async def activate_account(
    request: dict,
    response: Response,
    client_type_header: str | None = Header(None, alias="X-Client-Type"),
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
    if user.invite_token_expires_at and user.invite_token_expires_at < datetime.utcnow():
        user.invite_token = None
        user.invite_token_expires_at = None
        raise HTTPException(status_code=410, detail="Invite token expired. Contact your administrator for a new invite.")

    user.hashed_password = get_password_hash(password)
    user.is_activated = True
    user.is_active = True
    user.invite_token = None
    user.invite_token_expires_at = None
    await db.flush()

    # SECURITY: Audit account activation
    from app.models.audit_log import AuditLog
    audit = AuditLog(user_id=user.id, action="account_activated", details={"email": user.email})
    db.add(audit)

    return await _issue_token_pair(db, user, response, _normalize_client_type(client_type_header))


@router.post("/refresh", response_model=TokenResponse | BrowserSessionResponse)
async def refresh_session(
    request: RefreshRequest,
    response: Response,
    refresh_cookie: str | None = Cookie(None, alias="refresh_token"),
    client_type_header: str | None = Header(None, alias="X-Client-Type"),
    db: AsyncSession = Depends(get_db),
):
    """Rotate a refresh token and issue a new access token."""
    raw_refresh_token = request.refresh_token or refresh_cookie
    if not raw_refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    result = await db.execute(
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == _refresh_token_hash(raw_refresh_token))
        .with_for_update()
    )
    auth_session = result.scalar_one_or_none()
    now = datetime.utcnow()
    if not auth_session or auth_session.revoked_at or auth_session.expires_at <= now:
        response.delete_cookie("refresh_token", path="/api/auth")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = await db.get(User, auth_session.user_id)
    if (
        not user
        or not user.is_active
        or not user.is_activated
        or auth_session.token_version != int(user.token_version or 0)
    ):
        auth_session.revoked_at = now
        response.delete_cookie("refresh_token", path="/api/auth")
        raise HTTPException(status_code=401, detail="Refresh session has been revoked")

    auth_session.revoked_at = now
    auth_session.last_used_at = now
    return await _issue_token_pair(
        db,
        user,
        response,
        _normalize_client_type(client_type_header or auth_session.client_type),
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return user


@router.post("/logout")
async def logout(
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear the browser session cookie."""
    user.token_version = int(user.token_version or 0) + 1
    await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow())
    )
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/auth")
    response.delete_cookie("csrf_token", path="/")
    return {"message": "Logged out"}


@router.post("/ws-token")
async def create_websocket_token(request: Request, user: User = Depends(get_current_user)):
    """Create a short-lived token intended for WebSocket connection URLs."""
    ticket_id = str(uuid4())
    ttl_seconds = 300
    await _store_ws_ticket(request.app, ticket_id, ttl_seconds)
    token = create_access_token(
        str(user.id),
        user.role,
        expires_delta=timedelta(minutes=5),
        extra_claims={"ver": int(user.token_version or 0), "purpose": "ws", "jti": ticket_id},
    )
    return {"access_token": token, "expires_in": ttl_seconds, "token_type": "bearer"}


@router.get("/assigned-profiles")
async def get_assigned_profiles(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List active smart-agent profiles assigned to the current employee."""
    result = await db.execute(
        select(ProfileUser, Profile)
        .join(Profile, Profile.id == ProfileUser.profile_id)
        .where(
            ProfileUser.user_id == user.id,
            Profile.is_active == True,
        )
        .order_by(ProfileUser.priority.asc(), Profile.name.asc())
    )
    rows = result.all()
    return {
        "profiles": [
            {
                "id": str(profile.id),
                "name": profile.name,
                "slug": profile.slug,
                "priority": assignment.priority,
                "runtime_type": profile.runtime_type,
            }
            for assignment, profile in rows
        ],
        "count": len(rows),
    }


@router.get("/agent-templates")
async def get_agent_templates(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List agent templates available to authenticated desktop users."""
    result = await db.execute(select(AgentTemplate).order_by(AgentTemplate.name.asc()))
    templates = result.scalars().all()
    return {
        "templates": [
            {
                "name": template.name,
                "department": template.department,
                "model_name": template.model_name,
                "temperature": template.temperature,
                "max_tokens_per_request": template.max_tokens_per_request,
                "tools": template.tools,
            }
            for template in templates
        ],
        "count": len(templates),
    }
