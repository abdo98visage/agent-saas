from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, status, Header, Cookie, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.core.config import settings

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

    token = create_access_token(str(user.id), user.role, extra_claims={"ver": int(user.token_version or 0)})
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

    access_token = create_access_token(str(user.id), user.role, extra_claims={"ver": int(user.token_version or 0)})
    _set_session_cookie(response, access_token)
    return TokenResponse(access_token=access_token)


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
    response.delete_cookie("access_token", path="/")
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
