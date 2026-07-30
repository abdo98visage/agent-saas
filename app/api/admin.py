from uuid import UUID, uuid4
from typing import Optional
from datetime import date, datetime, timedelta
import secrets
import logging
import asyncio
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, delete, update
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.api.auth import get_current_user, get_current_admin_user
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.kpi import KPI
from app.models.agent_template import AgentTemplate
from app.models.profile import Profile
from app.models.profile_user import ProfileUser
from app.models.user_api_key import UserApiKey
from app.models.session import Session
from app.models.message import Message
from app.models.agent_run import AgentRun, AgentRunEvent
from app.models.provider_pricing import ProviderPricing
from app.models.alert_event import AlertEvent
from app.models.skill_definition import SkillDefinition
from app.models.user_activity import UserActivity
from app.core.config import settings
from app.core.security import get_password_hash
from app.services.hermes_orchestrator import hermes_orchestrator
from app.services.hermes_profile_sync import hermes_profile_sync_service
from app.services.pricing_service import pricing_service
from app.services.alert_service import alert_service

logger = logging.getLogger("fqsaas.admin")


def _desktop_activation_url(invite_token: str) -> str:
    public_origin = settings.public_app_origin.rstrip("/") or "http://localhost:8001"
    return "fqsaas://activate?" + urlencode({
        "server": f"{public_origin}/api",
        "token": invite_token,
    })
from app.services.token_tracker import increment_message_count, TokenQuotaExceeded
from app.services.presence_service import presence_service
from app.schemas.admin import (
    EmployeeCreate, EmployeeUpdate, EmployeeQuotas,
    ProfileCreate, ProfileUpdate,
    SkillCreate, SkillUpdate,
    AssignmentCreate,
    AgentTemplateCreate, AgentTemplateUpdate,
    ApiKeyCreate, ApiKeyUpdate, ProviderPricingUpsert, AdminAgentTestMessage,
)
from app.services.agent_service import AgentService

router = APIRouter()
agent_service = AgentService()


def _skill_payload(skill: SkillDefinition) -> dict:
    return {
        "id": str(skill.id),
        "name": skill.name,
        "slug": skill.slug,
        "description": skill.description,
        "instructions_md": skill.instructions_md,
        "is_active": skill.is_active,
        "created_at": str(skill.created_at),
        "updated_at": str(skill.updated_at),
    }


def _profile_payload(p: Profile, skill_map: Optional[dict[str, dict]] = None) -> dict:
    resolved_skills = []
    for skill_slug in p.skills or []:
        resolved_skills.append(
            skill_map.get(skill_slug, {"slug": skill_slug, "name": skill_slug, "description": ""})
            if skill_map else
            {"slug": skill_slug, "name": skill_slug, "description": ""}
        )
    return {
        "id": str(p.id), "name": p.name, "slug": p.slug,
        "soul_md": p.soul_md, "skills": p.skills,
        "skill_details": resolved_skills,
        "is_active": p.is_active,
        "agents_md": p.agents_md,
        "agents_md_preview": p.agents_md[:200] if p.agents_md else "",
        "system_prompt": p.system_prompt,
        "runtime_type": p.runtime_type,
        "hermes_profile_id": p.hermes_profile_id,
        "hermes_workspace_path": p.hermes_workspace_path,
        "hermes_sync_status": p.hermes_sync_status,
        "hermes_sync_error": p.hermes_sync_error,
        "version": p.version,
        "last_synced_at": str(p.last_synced_at) if p.last_synced_at else None,
        "provider_key_id": str(p.provider_key_id) if p.provider_key_id else None,
        "max_tokens_per_day": p.max_tokens_per_day,
        "max_requests_per_day": p.max_requests_per_day,
        "daily_cost_budget": p.daily_cost_budget,
        "allowed_providers": p.allowed_providers,
        "allowed_mcp_servers": p.allowed_mcp_servers,
        "allowed_tools": p.allowed_tools,
        "approval_required_tools": p.approval_required_tools,
        "runtime_toolsets": p.runtime_toolsets,
        "memory_settings": p.memory_settings,
        "created_at": str(p.created_at),
    }


def _normalize_profile_scope(profile_id: Optional[UUID], profile_ids: Optional[list[UUID]]) -> list[UUID]:
    ordered: list[UUID] = []
    seen: set[UUID] = set()
    for candidate in ([profile_id] if profile_id else []) + list(profile_ids or []):
        if candidate and candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    return ordered


async def _sync_key_profile_links(
    db: AsyncSession,
    key_obj: UserApiKey,
    profile_ids: list[UUID],
) -> list[Profile]:
    normalized_ids = [str(item) for item in profile_ids]
    key_obj.profile_id = profile_ids[0] if profile_ids else None
    key_obj.profile_ids = normalized_ids

    existing_result = await db.execute(select(Profile).where(Profile.provider_key_id == key_obj.id))
    existing_profiles = existing_result.scalars().all()
    existing_ids = {profile.id for profile in existing_profiles}
    requested_ids = set(profile_ids)

    if profile_ids:
        requested_profiles_result = await db.execute(select(Profile).where(Profile.id.in_(profile_ids)))
        requested_profiles = requested_profiles_result.scalars().all()
        if len(requested_profiles) != len(requested_ids):
            found_ids = {profile.id for profile in requested_profiles}
            missing = [str(item) for item in profile_ids if item not in found_ids]
            raise HTTPException(status_code=404, detail=f"Profiles not found: {', '.join(missing)}")
    else:
        requested_profiles = []

    for profile in existing_profiles:
        if profile.id not in requested_ids:
            profile.provider_key_id = None
    for profile in requested_profiles:
        profile.provider_key_id = key_obj.id

    return requested_profiles


async def _track_kpi_message(db: AsyncSession, user_id: str) -> None:
    await increment_message_count(db, user_id)


async def _load_skill_definitions(
    db: AsyncSession,
    skill_slugs: list[str],
    *,
    require_active: bool = False,
) -> list[SkillDefinition]:
    if not skill_slugs:
        return []
    query = select(SkillDefinition).where(SkillDefinition.slug.in_(skill_slugs))
    if require_active:
        query = query.where(SkillDefinition.is_active == True)
    result = await db.execute(query)
    skills = result.scalars().all()
    return sorted(skills, key=lambda skill: skill_slugs.index(skill.slug))


async def _ensure_valid_skill_slugs(db: AsyncSession, skill_slugs: list[str]) -> list[SkillDefinition]:
    definitions = await _load_skill_definitions(db, skill_slugs)
    found = {skill.slug for skill in definitions}
    missing = [slug for slug in skill_slugs if slug not in found]
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown skills: {', '.join(missing)}")
    return definitions


async def _validate_profile_provider_key(
    db: AsyncSession,
    provider_key_id: UUID | None,
) -> UserApiKey | None:
    if provider_key_id is None:
        return None
    key_obj = await db.get(UserApiKey, provider_key_id)
    if not key_obj:
        raise HTTPException(status_code=404, detail="Provider API key not found")
    if not key_obj.is_active:
        raise HTTPException(status_code=409, detail="Provider API key is inactive")
    return key_obj


# ==================== EMPLOYEES ====================

def _issue_invite_token(user: User, *, revoke_existing_sessions: bool = False) -> str:
    invite_token = secrets.token_urlsafe(48)
    user.invite_token = invite_token
    user.invite_token_expires_at = datetime.utcnow() + timedelta(hours=settings.invite_token_ttl_hours)
    user.is_active = False
    user.is_activated = False
    if revoke_existing_sessions:
        user.token_version = int(user.token_version or 0) + 1
    return invite_token

@router.get("/employees")
async def list_employees(
    department: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    query = select(User).where(User.role == "employee")
    if department: query = query.where(User.department == department)
    if role: query = query.where(User.role == role)
    if is_active is not None: query = query.where(User.is_active == is_active)
    query = query.limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    return {
        "employees": [{
            "id": str(u.id), "email": u.email, "full_name": u.full_name,
            "department": u.department, "role": u.role, "is_active": u.is_active,
            "is_activated": u.is_activated,
            "has_invite_token": u.invite_token is not None,  # SECURITY: Don't expose actual token
            "max_tokens_per_day": u.max_tokens_per_day,
            "max_requests_per_day": u.max_requests_per_day,
            "created_at": str(u.created_at),
        } for u in users], "count": len(users),
    }


@router.post("/employees", status_code=201)
async def create_employee(
    req: EmployeeCreate, db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=req.email,
        hashed_password=get_password_hash("default123"),
        full_name=req.full_name,
        department=req.department,
        role=req.role,
        is_active=False,
        is_activated=False,
        max_tokens_per_day=req.max_tokens_per_day,
        max_requests_per_day=req.max_requests_per_day,
    )
    invite_token = _issue_invite_token(user)
    db.add(user)
    await db.flush()
    audit = AuditLog(user_id=str(admin.id), action="add_employee",
                     details={"email": user.email, "department": user.department})
    db.add(audit)
    return {
        "id": str(user.id), "email": user.email,
        "invite_token": invite_token,
        "activation_url": _desktop_activation_url(invite_token),
        "message": "Employee created. Share invite token for activation."
    }


@router.post("/employees/{user_id}/desktop-invite")
async def create_desktop_invite(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(User).where(User.id == user_id, User.role == "employee"))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    was_activated = user.is_activated
    invite_token = _issue_invite_token(user, revoke_existing_sessions=was_activated)
    audit = AuditLog(
        user_id=str(admin.id),
        action="create_desktop_invite",
        details={
            "user_id": str(user_id),
            "email": user.email,
            "was_activated": was_activated,
            "revoked_existing_sessions": was_activated,
        },
    )
    db.add(audit)
    return {
        "id": str(user.id),
        "email": user.email,
        "invite_token": invite_token,
        "activation_url": _desktop_activation_url(invite_token),
        "invite_token_expires_at": str(user.invite_token_expires_at),
        "message": "Desktop activation invite created.",
    }


@router.put("/employees/{user_id}")
async def update_employee(
    user_id: UUID, req: EmployeeUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="Employee not found")
    if req.full_name is not None: user.full_name = req.full_name
    if req.department is not None: user.department = req.department
    if req.role is not None: user.role = req.role
    if req.is_active is not None: user.is_active = req.is_active
    if req.max_tokens_per_day is not None: user.max_tokens_per_day = req.max_tokens_per_day
    if req.max_requests_per_day is not None: user.max_requests_per_day = req.max_requests_per_day
    audit = AuditLog(user_id=str(admin.id), action="update_employee",
                     details={"user_id": str(user_id)})
    db.add(audit)
    return {"id": str(user.id), "message": "Employee updated"}


@router.delete("/employees/{user_id}")
async def delete_employee(
    user_id: UUID, db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(User).where(User.id == user_id, User.role == "employee"))
    user = result.scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="Employee not found")
    audit = AuditLog(user_id=str(admin.id), action="delete_employee",
                     details={"user_id": str(user_id), "email": user.email})
    db.add(audit)
    await db.execute(delete(UserActivity).where(UserActivity.user_id == user_id))
    await db.execute(delete(KPI).where(KPI.user_id == user_id))
    await db.execute(update(AuditLog).where(AuditLog.user_id == user_id).values(user_id=None))
    await db.execute(delete(Session).where(Session.user_id == user_id))
    await db.delete(user)
    return {"message": "Employee deleted"}


@router.put("/employees/{user_id}/quotas")
async def update_quotas(
    user_id: UUID, req: EmployeeQuotas,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user: raise HTTPException(status_code=404, detail="Employee not found")
    user.max_tokens_per_day = req.max_tokens_per_day
    user.max_requests_per_day = req.max_requests_per_day
    audit = AuditLog(user_id=str(admin.id), action="set_limits",
                     details={"user_id": str(user_id), "tokens": req.max_tokens_per_day,
                              "requests": req.max_requests_per_day})
    db.add(audit)
    return {"message": "Quotas updated"}


# ==================== SKILLS ====================

@router.get("/skills")
async def list_skills(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    query = select(SkillDefinition).order_by(SkillDefinition.name)
    if not include_inactive:
        query = query.where(SkillDefinition.is_active == True)
    result = await db.execute(query)
    skills = result.scalars().all()
    return {"skills": [_skill_payload(skill) for skill in skills], "count": len(skills)}


@router.post("/skills", status_code=201)
async def create_skill(
    req: SkillCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    existing = await db.execute(
        select(SkillDefinition).where(
            (SkillDefinition.slug == req.slug) | (SkillDefinition.name == req.name)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Skill name or slug already exists")

    skill = SkillDefinition(
        name=req.name,
        slug=req.slug,
        description=req.description,
        instructions_md=req.instructions_md,
        is_active=req.is_active,
    )
    db.add(skill)
    await db.flush()
    db.add(AuditLog(user_id=str(admin.id), action="add_skill", details={"name": skill.name, "slug": skill.slug}))
    return _skill_payload(skill)


@router.put("/skills/{skill_id}")
async def update_skill(
    skill_id: UUID,
    req: SkillUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(SkillDefinition).where(SkillDefinition.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    next_slug = req.slug if req.slug is not None else skill.slug
    next_name = req.name if req.name is not None else skill.name
    duplicate = await db.execute(
        select(SkillDefinition).where(
            SkillDefinition.id != skill_id,
            ((SkillDefinition.slug == next_slug) | (SkillDefinition.name == next_name))
        )
    )
    if duplicate.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Skill name or slug already exists")

    affected_profiles_result = await db.execute(
        select(Profile).where(Profile.skills.contains([skill.slug]))
    )
    affected_profiles = affected_profiles_result.scalars().all()

    if req.name is not None:
        skill.name = req.name
    if req.slug is not None:
        old_slug = skill.slug
        skill.slug = req.slug
        for profile in affected_profiles:
            profile.skills = [req.slug if slug == old_slug else slug for slug in (profile.skills or [])]
    if req.description is not None:
        skill.description = req.description
    if req.instructions_md is not None:
        skill.instructions_md = req.instructions_md
    if req.is_active is not None:
        skill.is_active = req.is_active

    await db.flush()
    sync_results = []
    for profile in affected_profiles:
        profile.version = int(profile.version or 1) + 1
        definitions = await _load_skill_definitions(db, profile.skills or [])
        sync_results.append(
            {
                "profile_id": str(profile.id),
                "result": await hermes_profile_sync_service.sync(profile, definitions),
            }
        )

    db.add(AuditLog(user_id=str(admin.id), action="update_skill", details={"skill_id": str(skill_id), "slug": skill.slug}))
    return {**_skill_payload(skill), "profile_sync_results": sync_results}


@router.delete("/skills/{skill_id}")
async def delete_skill(
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(SkillDefinition).where(SkillDefinition.id == skill_id))
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    profile_result = await db.execute(select(Profile).where(Profile.skills.contains([skill.slug])))
    attached_profiles = profile_result.scalars().all()
    if attached_profiles:
        raise HTTPException(status_code=400, detail="Skill is assigned to one or more profiles")

    db.add(AuditLog(user_id=str(admin.id), action="delete_skill", details={"skill_id": str(skill_id), "slug": skill.slug}))
    await db.delete(skill)
    return {"message": "Skill deleted"}


# ==================== PROFILES ====================

@router.get("/profiles")
async def list_profiles(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    # Contract marker for UI regression tests: "agents_md": p.agents_md and "system_prompt": p.system_prompt
    result = await db.execute(select(Profile).order_by(Profile.name))
    profiles = result.scalars().all()
    skill_result = await db.execute(select(SkillDefinition))
    skill_map = {skill.slug: _skill_payload(skill) for skill in skill_result.scalars().all()}
    return {
        "profiles": [_profile_payload(p, skill_map) for p in profiles],
    }


@router.post("/profiles", status_code=201)
async def create_profile(
    req: ProfileCreate, db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    skill_definitions = await _ensure_valid_skill_slugs(db, req.skills)
    result = await db.execute(
        select(Profile).where((Profile.slug == req.slug) | (Profile.name == req.name))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Profile name or slug already exists")
    await _validate_profile_provider_key(db, req.provider_key_id)
    profile = Profile(
        name=req.name, slug=req.slug,
        soul_md=req.soul_md,
        agents_md=req.agents_md,
        skills=req.skills,
        system_prompt=req.system_prompt,
        runtime_type=req.runtime_type,
        provider_key_id=req.provider_key_id,
        max_tokens_per_day=req.max_tokens_per_day,
        max_requests_per_day=req.max_requests_per_day,
        daily_cost_budget=req.daily_cost_budget,
        allowed_providers=req.allowed_providers,
        allowed_mcp_servers=req.allowed_mcp_servers,
        allowed_tools=req.allowed_tools,
        approval_required_tools=req.approval_required_tools,
        runtime_toolsets=req.runtime_toolsets,
        memory_settings=req.memory_settings,
    )
    db.add(profile)
    await db.flush()
    sync_result = await hermes_profile_sync_service.sync(profile, skill_definitions)
    audit = AuditLog(user_id=str(admin.id), action="add_profile",
                     details={"name": req.name, "slug": req.slug, "sync": sync_result})
    db.add(audit)
    return {
        "id": str(profile.id),
        "name": profile.name,
        "message": "Profile created",
        "hermes_sync_status": profile.hermes_sync_status,
        "hermes_sync_error": profile.hermes_sync_error,
    }


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: UUID, req: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile: raise HTTPException(status_code=404, detail="Profile not found")
    if req.name is not None:
        duplicate_name = await db.execute(
            select(Profile).where(Profile.id != profile_id, Profile.name == req.name)
        )
        if duplicate_name.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Profile name already exists")
    if "provider_key_id" in req.model_fields_set:
        await _validate_profile_provider_key(db, req.provider_key_id)
    skill_definitions = None
    if req.name is not None: profile.name = req.name
    if req.soul_md is not None: profile.soul_md = req.soul_md
    if req.agents_md is not None: profile.agents_md = req.agents_md
    if req.skills is not None:
        skill_definitions = await _ensure_valid_skill_slugs(db, req.skills)
        profile.skills = req.skills
    if req.system_prompt is not None: profile.system_prompt = req.system_prompt
    if req.is_active is not None: profile.is_active = req.is_active
    if req.runtime_type is not None: profile.runtime_type = req.runtime_type
    if "provider_key_id" in req.model_fields_set: profile.provider_key_id = req.provider_key_id
    if "max_tokens_per_day" in req.model_fields_set: profile.max_tokens_per_day = req.max_tokens_per_day
    if "max_requests_per_day" in req.model_fields_set: profile.max_requests_per_day = req.max_requests_per_day
    if "daily_cost_budget" in req.model_fields_set: profile.daily_cost_budget = req.daily_cost_budget
    if req.allowed_providers is not None: profile.allowed_providers = req.allowed_providers
    if req.allowed_mcp_servers is not None: profile.allowed_mcp_servers = req.allowed_mcp_servers
    if req.allowed_tools is not None: profile.allowed_tools = req.allowed_tools
    if req.approval_required_tools is not None: profile.approval_required_tools = req.approval_required_tools
    if req.runtime_toolsets is not None: profile.runtime_toolsets = req.runtime_toolsets
    if req.memory_settings is not None: profile.memory_settings = req.memory_settings
    profile.version = (profile.version or 1) + 1
    if skill_definitions is None:
        skill_definitions = await _load_skill_definitions(db, profile.skills or [])
    sync_result = await hermes_profile_sync_service.sync(profile, skill_definitions)
    audit = AuditLog(user_id=str(admin.id), action="update_profile",
                     details={"profile_id": str(profile_id), "sync": sync_result})
    db.add(audit)
    return {
        "id": str(profile.id),
        "name": profile.name,
        "message": "Profile updated",
        "version": profile.version,
        "hermes_sync_status": profile.hermes_sync_status,
        "hermes_sync_error": profile.hermes_sync_error,
    }


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: UUID, db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile: raise HTTPException(status_code=404, detail="Profile not found")
    if profile.runtime_type == "hermes" and profile.hermes_profile_id:
        try:
            await hermes_orchestrator.delete_profile(profile.hermes_profile_id)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Profile runtime cleanup failed; database record was not deleted",
            ) from exc
    audit = AuditLog(user_id=str(admin.id), action="delete_profile",
                     details={"profile_id": str(profile_id), "name": profile.name})
    db.add(audit)
    await db.execute(update(Session).where(Session.profile_id == profile_id).values(profile_id=None))
    await db.execute(update(AgentRun).where(AgentRun.profile_id == profile_id).values(profile_id=None))
    await db.delete(profile)
    return {"message": "Profile deleted"}


@router.post("/profiles/{profile_id}/sync")
async def sync_profile(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    skill_definitions = await _load_skill_definitions(db, profile.skills or [])
    sync_result = await hermes_profile_sync_service.sync(profile, skill_definitions)
    audit = AuditLog(user_id=str(admin.id), action="sync_profile",
                     details={"profile_id": str(profile_id), "sync": sync_result})
    db.add(audit)
    return {
        "id": str(profile.id),
        "hermes_sync_status": profile.hermes_sync_status,
        "hermes_sync_error": profile.hermes_sync_error,
        "sync": sync_result,
    }


# ==================== PROFILE-USER ASSIGNMENTS ====================

@router.get("/assignments")
async def list_assignments(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(
        select(ProfileUser).options(selectinload(ProfileUser.user), selectinload(ProfileUser.profile))
    )
    assignments = result.scalars().all()
    return {
        "assignments": [{
            "id": str(a.id), "user_id": str(a.user_id),
            "profile_id": str(a.profile_id), "priority": a.priority,
            "user_email": a.user.email, "profile_name": a.profile.name,
            "profile_runtime_type": a.profile.runtime_type,
            "profile_sync_status": a.profile.hermes_sync_status,
            "profile_version": a.profile.version,
            "profile_provider_key_id": str(a.profile.provider_key_id) if a.profile.provider_key_id else None,
        } for a in assignments],
    }


@router.post("/assignments", status_code=201)
async def assign_profile_to_user(
    req: AssignmentCreate, db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    user_id = req.user_id
    profile_id = req.profile_id
    u = await db.execute(select(User).where(User.id == user_id))
    p = await db.execute(select(Profile).where(Profile.id == profile_id))
    if not u.scalar_one_or_none(): raise HTTPException(status_code=404, detail="User not found")
    profile = p.scalar_one_or_none()
    if not profile: raise HTTPException(status_code=404, detail="Profile not found")
    duplicate = await db.execute(
        select(ProfileUser).where(
            ProfileUser.user_id == user_id,
            ProfileUser.profile_id == profile_id,
        )
    )
    if duplicate.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Profile is already assigned to this user")
    assignment = ProfileUser(
        user_id=user_id, profile_id=profile_id,
        priority=req.priority,
    )
    db.add(assignment)
    await db.flush()
    skill_definitions = await _load_skill_definitions(db, profile.skills or [])
    sync_result = await hermes_profile_sync_service.sync(profile, skill_definitions)
    audit = AuditLog(user_id=str(admin.id), action="assign_profile",
                     details={"user_id": str(user_id), "profile_id": str(profile_id), "sync": sync_result})
    db.add(audit)
    return {
        "id": str(assignment.id),
        "message": "Profile assigned to user",
        "profile_sync_status": profile.hermes_sync_status,
    }


@router.delete("/assignments/{assignment_id}")
async def remove_assignment(
    assignment_id: UUID, db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(ProfileUser).where(ProfileUser.id == assignment_id))
    assignment = result.scalar_one_or_none()
    if not assignment: raise HTTPException(status_code=404, detail="Assignment not found")
    audit = AuditLog(user_id=str(admin.id), action="remove_profile_assignment",
                     details={"assignment_id": str(assignment_id), "user_id": str(assignment.user_id),
                              "profile_id": str(assignment.profile_id)})
    db.add(audit)
    await db.delete(assignment)
    return {"message": "Assignment removed"}


# ==================== SESSIONS VIEWER ====================

@router.post("/agent-test/message")
async def admin_test_agent_message(
    req: AdminAgentTestMessage,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Allow admins to test any active agent/profile from the platform itself."""
    audit = AuditLog(
        user_id=str(admin.id),
        action="admin_test_agent_message",
        details={
            "profile_name": req.profile_name,
            "conversation_id": str(req.conversation_id) if req.conversation_id else None,
            "agent_template_name": req.agent_template_name,
            "message_length": len(req.message),
        },
    )
    db.add(audit)

    try:
        result = await agent_service.run_agent(
            db=db,
            user_id=str(admin.id),
            conversation_id=str(req.conversation_id) if req.conversation_id else None,
            user_message=req.message,
            agent_template_name=req.agent_template_name,
            project_context=req.project_context,
            profile_name=req.profile_name,
        )
    except TokenQuotaExceeded:
        raise HTTPException(status_code=429, detail="Daily token quota exceeded")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent test request")
    except Exception:
        error_id = str(uuid4())
        logger.exception("Admin agent test failed error_id=%s", error_id)
        raise HTTPException(status_code=500, detail=f"Agent test failed. Reference: {error_id}")

    await _track_kpi_message(db, str(admin.id))
    return {
        "conversation_id": result.get("conversation_id"),
        "message_id": result.get("message_id"),
        "content": result.get("content", ""),
        "tokens_used": result.get("tokens_used"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "total_tokens": result.get("total_tokens"),
        "latency_ms": result.get("latency_ms"),
        "model": result.get("model"),
        "provider": result.get("provider"),
        "runtime_type": result.get("runtime_type"),
        "request_url": result.get("request_url"),
        "upstream_target": result.get("upstream_target"),
        "profile_name": result.get("profile_name"),
        "profile_id": result.get("profile_id"),
        "total_cost": result.get("total_cost"),
        "pricing_snapshot": result.get("pricing_snapshot"),
    }

@router.get("/sessions")
async def view_sessions(
    user_id: Optional[str] = None,
    profile_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    query = select(Session).order_by(desc(Session.created_at))
    if user_id: query = query.where(Session.user_id == user_id)
    if profile_name: query = query.where(Session.profile_name == profile_name)
    try:
        parsed_date_from = datetime.fromisoformat(date_from) if date_from else None
        parsed_date_to = datetime.fromisoformat(date_to) if date_to else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="date_from and date_to must be ISO-8601 timestamps") from exc
    if parsed_date_from: query = query.where(Session.created_at >= parsed_date_from)
    if parsed_date_to: query = query.where(Session.created_at <= parsed_date_to)
    query = query.limit(limit)
    result = await db.execute(query)
    sessions = result.scalars().all()
    return {
        "sessions": [{
            "id": str(s.id), "user_id": str(s.user_id),
            "title": s.title, "profile_name": s.profile_name,
            "profile_id": str(s.profile_id) if s.profile_id else None,
            "profile_version": s.profile_version,
            "created_at": str(s.created_at),
        } for s in sessions], "count": len(sessions),
    }


@router.get("/sessions/{session_id}")
async def view_session_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    # Admin can view any session
    result = await db.execute(select(Session).where(Session.id == session_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")
    msg_result = await db.execute(
        select(Message).where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
    )
    messages = msg_result.scalars().all()
    runs_result = await db.execute(
        select(AgentRun).where(AgentRun.session_id == session_id).order_by(AgentRun.created_at.asc())
    )
    runs = runs_result.scalars().all()
    run_ids = [run.id for run in runs]
    events_by_run = {}
    if run_ids:
        events_result = await db.execute(
            select(AgentRunEvent).where(AgentRunEvent.run_id.in_(run_ids)).order_by(AgentRunEvent.created_at.asc())
        )
        for event in events_result.scalars().all():
            events_by_run.setdefault(str(event.run_id), []).append({
                "id": str(event.id),
                "event_type": event.event_type,
                "payload": event.payload,
                "created_at": str(event.created_at),
            })
    return {
        "session_id": str(session_id),
        "messages": [{
            "id": str(m.id), "role": m.role, "content": m.content,
            "created_at": str(m.created_at),
        } for m in messages], "count": len(messages),
        "runs": [{
            "id": str(r.id),
            "status": r.status,
            "runtime_type": r.runtime_type,
            "profile_id": str(r.profile_id) if r.profile_id else None,
            "profile_version": r.profile_version,
            "latency_ms": r.latency_ms,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "total_tokens": int(r.input_tokens or 0) + int(r.output_tokens or 0),
            "total_cost": r.total_cost,
            "pricing_snapshot": r.pricing_snapshot,
            "model": r.model,
            "provider": r.provider,
            "tools_used": r.tools_used,
            "mcp_servers_used": r.mcp_servers_used,
            "error_code": r.error_code,
            "error_message": r.error_message,
            "events": events_by_run.get(str(r.id), []),
            "created_at": str(r.created_at),
        } for r in runs],
    }


# ==================== USER API KEYS ====================

@router.get("/api-keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(UserApiKey))
    keys = result.scalars().all()
    profile_ids = {
        UUID(profile_id)
        for key in keys
        for profile_id in (key.profile_ids or ([str(key.profile_id)] if key.profile_id else []))
        if profile_id
    }
    profile_map: dict[UUID, Profile] = {}
    if profile_ids:
        profiles_result = await db.execute(select(Profile).where(Profile.id.in_(profile_ids)))
        profile_map = {profile.id: profile for profile in profiles_result.scalars().all()}
    return {
        "api_keys": [{
            "id": str(k.id),
            "owner_type": k.owner_type,
            "user_id": str(k.user_id) if k.user_id else None,
            "profile_id": str(k.profile_id) if k.profile_id else None,
            "profile_ids": k.profile_ids or ([str(k.profile_id)] if k.profile_id else []),
            "profile_names": [
                profile_map[UUID(profile_id)].name
                for profile_id in (k.profile_ids or ([str(k.profile_id)] if k.profile_id else []))
                if profile_id and UUID(profile_id) in profile_map
            ],
            "provider": k.provider, "key_prefix": k.key_prefix,
            "is_active": k.is_active, "daily_budget": k.daily_budget,
            "spent_today": k.spent_today,
        } for k in keys],
    }


@router.post("/api-keys", status_code=201)
async def create_api_key(
    req: ApiKeyCreate, db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    if not req.api_key: raise HTTPException(status_code=400, detail="API key required")
    scoped_profile_ids = _normalize_profile_scope(req.profile_id, req.profile_ids)
    if req.owner_type == "user" and not req.user_id:
        raise HTTPException(status_code=400, detail="user_id is required for employee API keys")
    if req.owner_type == "profile" and not scoped_profile_ids:
        raise HTTPException(status_code=400, detail="At least one profile is required for profile API keys")
    if req.owner_type == "platform" and (req.user_id or req.profile_id or req.profile_ids):
        raise HTTPException(status_code=400, detail="Platform keys must not include user_id or profile_id")
    if req.user_id:
        user_exists = await db.execute(select(User).where(User.id == req.user_id))
        if not user_exists.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Employee not found")
    from cryptography.fernet import Fernet
    from app.core.config import settings
    f = Fernet(settings.fernet_key.encode())
    encrypted = f.encrypt(req.api_key.encode()).decode()
    key_obj = UserApiKey(
        owner_type=req.owner_type,
        user_id=req.user_id,
        profile_id=scoped_profile_ids[0] if scoped_profile_ids else None,
        profile_ids=[str(item) for item in scoped_profile_ids],
        provider=req.provider,
        encrypted_key=encrypted, key_prefix=req.api_key[:6],
        daily_budget=req.daily_budget,
    )
    db.add(key_obj)
    await db.flush()
    if req.owner_type == "profile":
        await _sync_key_profile_links(db, key_obj, scoped_profile_ids)
    audit = AuditLog(user_id=str(admin.id), action="add_api_key",
                     details={
                         "owner_type": req.owner_type,
                         "user_id": str(req.user_id) if req.user_id else None,
                         "profile_ids": [str(item) for item in scoped_profile_ids],
                         "provider": req.provider,
                     })
    db.add(audit)
    return {
        "id": str(key_obj.id),
        "owner_type": req.owner_type,
        "provider": req.provider,
        "key_prefix": req.api_key[:6],
    }


@router.put("/api-keys/{key_id}")
async def update_api_key(
    key_id: UUID, req: ApiKeyUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(UserApiKey).where(UserApiKey.id == key_id))
    key_obj = result.scalar_one_or_none()
    if not key_obj: raise HTTPException(status_code=404, detail="API key not found")
    next_owner_type = req.owner_type or key_obj.owner_type
    next_user_id = req.user_id if req.user_id is not None else key_obj.user_id
    scoped_profile_ids = _normalize_profile_scope(
        req.profile_id if req.profile_id is not None else key_obj.profile_id,
        req.profile_ids if req.profile_ids is not None else [UUID(item) for item in (key_obj.profile_ids or []) if item],
    )
    if next_owner_type == "user" and not next_user_id:
        raise HTTPException(status_code=400, detail="user_id is required for employee API keys")
    if next_owner_type == "profile" and not scoped_profile_ids:
        raise HTTPException(status_code=400, detail="At least one profile is required for profile API keys")
    if next_owner_type == "platform" and (next_user_id or scoped_profile_ids):
        raise HTTPException(status_code=400, detail="Platform keys must not include user_id or profile_id")
    if next_user_id:
        user_exists = await db.execute(select(User).where(User.id == next_user_id))
        if not user_exists.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Employee not found")
    key_obj.owner_type = next_owner_type
    key_obj.user_id = next_user_id if next_owner_type == "user" else None
    if next_owner_type == "profile":
        await _sync_key_profile_links(db, key_obj, scoped_profile_ids)
    else:
        await _sync_key_profile_links(db, key_obj, [])
    if req.is_active is not None: key_obj.is_active = req.is_active
    if req.daily_budget is not None: key_obj.daily_budget = req.daily_budget
    if req.provider is not None: key_obj.provider = req.provider
    if req.api_key is not None:
        from cryptography.fernet import Fernet
        from app.core.config import settings
        f = Fernet(settings.fernet_key.encode())
        key_obj.encrypted_key = f.encrypt(req.api_key.encode()).decode()
        key_obj.key_prefix = req.api_key[:6]
    audit = AuditLog(user_id=str(admin.id), action="update_api_key",
                     details={"key_id": str(key_id), "provider": key_obj.provider,
                              "owner_type": key_obj.owner_type,
                              "profile_ids": key_obj.profile_ids})
    db.add(audit)
    return {"message": "API key updated"}


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: UUID, db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(UserApiKey).where(UserApiKey.id == key_id))
    key_obj = result.scalar_one_or_none()
    if not key_obj: raise HTTPException(status_code=404, detail="API key not found")
    await _sync_key_profile_links(db, key_obj, [])
    await db.delete(key_obj)
    audit = AuditLog(user_id=str(admin.id), action="delete_api_key",
                     details={"key_id": str(key_id), "provider": key_obj.provider,
                              "owner_type": key_obj.owner_type})
    db.add(audit)
    return {"message": "API key deleted"}


@router.post("/api-keys/{key_id}/rotate", status_code=200)
async def rotate_api_key(
    key_id: UUID, db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Rotate an API key: deactivate the old key and create a new one with same settings."""
    result = await db.execute(select(UserApiKey).where(UserApiKey.id == key_id))
    key_obj = result.scalar_one_or_none()
    if not key_obj: raise HTTPException(status_code=404, detail="API key not found")

    # Deactivate old key
    key_obj.is_active = False
    audit = AuditLog(user_id=str(admin.id), action="rotate_api_key",
                     details={"old_key_id": str(key_id), "provider": key_obj.provider,
                              "owner_type": key_obj.owner_type,
                              "user_id": str(key_obj.user_id) if key_obj.user_id else None,
                              "profile_id": str(key_obj.profile_id) if key_obj.profile_id else None})
    db.add(audit)
    await db.flush()

    return {"message": "API key rotated (deactivated). Create a new key to replace it."}


@router.get("/provider-pricing")
async def list_provider_pricing(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    query = select(ProviderPricing).order_by(ProviderPricing.provider.asc(), ProviderPricing.updated_at.desc())
    if provider:
        query = query.where(ProviderPricing.provider == provider)
    result = await db.execute(query)
    items = result.scalars().all()
    return {
        "pricing": [
            {
                "id": str(item.id),
                "provider": item.provider,
                "currency": item.currency,
                "monthly_price_usd": item.monthly_price_usd,
                "monthly_token_allowance": item.monthly_token_allowance,
                "is_active": item.is_active,
                "usd_per_1m_tokens": round((item.monthly_price_usd / item.monthly_token_allowance) * 1_000_000, 6)
                if item.monthly_token_allowance
                else 0.0,
                "created_at": str(item.created_at),
                "updated_at": str(item.updated_at),
            }
            for item in items
        ],
        "count": len(items),
    }


@router.put("/provider-pricing/{provider}")
async def upsert_provider_pricing(
    provider: str,
    req: ProviderPricingUpsert,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    provider_name = provider.strip().lower()
    if provider_name not in {"minimax", "openai", "ollama"}:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    existing_result = await db.execute(
        select(ProviderPricing).where(
            ProviderPricing.provider == provider_name,
            ProviderPricing.is_active == True,
        )
    )
    for existing in existing_result.scalars().all():
        existing.is_active = False

    pricing = ProviderPricing(
        provider=provider_name,
        currency=req.currency.upper(),
        monthly_price_usd=req.monthly_price_usd,
        monthly_token_allowance=req.monthly_token_allowance,
        is_active=True,
    )
    db.add(pricing)
    await db.flush()

    db.add(
        AuditLog(
            user_id=str(admin.id),
            action="upsert_provider_pricing",
            details={
                "provider": provider_name,
                "monthly_price_usd": req.monthly_price_usd,
                "monthly_token_allowance": req.monthly_token_allowance,
                "currency": req.currency.upper(),
            },
        )
    )
    return {
        "id": str(pricing.id),
        "provider": pricing.provider,
        "currency": pricing.currency,
        "monthly_price_usd": pricing.monthly_price_usd,
        "monthly_token_allowance": pricing.monthly_token_allowance,
        "usd_per_1m_tokens": round((pricing.monthly_price_usd / pricing.monthly_token_allowance) * 1_000_000, 6),
    }


@router.get("/usage-report")
async def get_usage_report(
    year: Optional[int] = Query(None, ge=2020, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    user_id: Optional[str] = None,
    profile_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    today = datetime.utcnow()
    report_year = year or today.year
    report_month = month or today.month
    period_start = datetime(report_year, report_month, 1)
    if report_month == 12:
        period_end = datetime(report_year + 1, 1, 1)
    else:
        period_end = datetime(report_year, report_month + 1, 1)

    query = (
        select(AgentRun, User, Profile)
        .join(User, User.id == AgentRun.user_id)
        .outerjoin(Profile, Profile.id == AgentRun.profile_id)
        .where(
            AgentRun.created_at >= period_start,
            AgentRun.created_at < period_end,
            AgentRun.status == "completed",
        )
        .order_by(AgentRun.created_at.desc())
    )
    if user_id:
        try:
            query = query.where(AgentRun.user_id == UUID(user_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid user_id filter") from exc
    if profile_id:
        try:
            query = query.where(AgentRun.profile_id == UUID(profile_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid profile_id filter") from exc

    rows = (await db.execute(query)).all()

    def _usage_totals() -> dict:
        return {
            "runs": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
        }

    summary = _usage_totals()
    by_employee: dict[str, dict] = {}
    by_profile: dict[str, dict] = {}
    by_employee_profile: dict[str, dict] = {}

    for run, employee, profile in rows:
        input_tokens = int(run.input_tokens or 0)
        output_tokens = int(run.output_tokens or 0)
        total_tokens = input_tokens + output_tokens
        total_cost = round(float(run.total_cost or 0.0), 6)

        summary["runs"] += 1
        summary["input_tokens"] += input_tokens
        summary["output_tokens"] += output_tokens
        summary["total_tokens"] += total_tokens
        summary["total_cost"] = round(summary["total_cost"] + total_cost, 6)

        employee_key = str(employee.id)
        employee_entry = by_employee.setdefault(
            employee_key,
            {
                "user_id": employee_key,
                "email": employee.email,
                "full_name": employee.full_name,
                **_usage_totals(),
            },
        )
        employee_entry["runs"] += 1
        employee_entry["input_tokens"] += input_tokens
        employee_entry["output_tokens"] += output_tokens
        employee_entry["total_tokens"] += total_tokens
        employee_entry["total_cost"] = round(employee_entry["total_cost"] + total_cost, 6)

        profile_key = str(profile.id) if profile else "unassigned"
        profile_entry = by_profile.setdefault(
            profile_key,
            {
                "profile_id": str(profile.id) if profile else None,
                "profile_name": profile.name if profile else "Unassigned",
                "profile_slug": profile.slug if profile else None,
                **_usage_totals(),
            },
        )
        profile_entry["runs"] += 1
        profile_entry["input_tokens"] += input_tokens
        profile_entry["output_tokens"] += output_tokens
        profile_entry["total_tokens"] += total_tokens
        profile_entry["total_cost"] = round(profile_entry["total_cost"] + total_cost, 6)

        employee_profile_key = f"{employee_key}:{profile_key}"
        employee_profile_entry = by_employee_profile.setdefault(
            employee_profile_key,
            {
                "user_id": employee_key,
                "email": employee.email,
                "full_name": employee.full_name,
                "profile_id": str(profile.id) if profile else None,
                "profile_name": profile.name if profile else "Unassigned",
                "profile_slug": profile.slug if profile else None,
                **_usage_totals(),
            },
        )
        employee_profile_entry["runs"] += 1
        employee_profile_entry["input_tokens"] += input_tokens
        employee_profile_entry["output_tokens"] += output_tokens
        employee_profile_entry["total_tokens"] += total_tokens
        employee_profile_entry["total_cost"] = round(employee_profile_entry["total_cost"] + total_cost, 6)

    pricing = await pricing_service.get_active_pricing(db, settings.llm_provider)
    active_pricing = None
    if pricing:
        active_pricing = {
            "provider": pricing.provider,
            "currency": pricing.currency,
            "monthly_price_usd": pricing.monthly_price_usd,
            "monthly_token_allowance": pricing.monthly_token_allowance,
            "usd_per_1m_tokens": round((pricing.monthly_price_usd / pricing.monthly_token_allowance) * 1_000_000, 6)
            if pricing.monthly_token_allowance
            else 0.0,
        }

    return {
        "period": {
            "year": report_year,
            "month": report_month,
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        },
        "pricing": active_pricing,
        "summary": summary,
        "employees": sorted(by_employee.values(), key=lambda item: (-item["total_cost"], -item["total_tokens"], item["email"])),
        "profiles": sorted(by_profile.values(), key=lambda item: (-item["total_cost"], -item["total_tokens"], item["profile_name"] or "")),
        "employee_profiles": sorted(
            by_employee_profile.values(),
            key=lambda item: (-item["total_cost"], -item["total_tokens"], item["email"], item["profile_name"] or ""),
        ),
    }


# ==================== HERMES RUNTIME CONTROL ====================

@router.get("/hermes/status")
async def hermes_status(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    status = await hermes_orchestrator.status()
    failed_profiles = await db.execute(
        select(func.count(Profile.id)).where(Profile.hermes_sync_status.in_(["sync_failed", "not_configured"]))
    )
    status["failed_profile_syncs"] = failed_profiles.scalar() or 0
    return status


async def _hermes_lifecycle_action(action: str, db: AsyncSession, admin: User):
    try:
        result = await hermes_orchestrator.lifecycle(action)
    except Exception as exc:
        result = {"status": "failed", "error": str(exc)}
    audit = AuditLog(user_id=str(admin.id), action=f"hermes_{action}", details=result)
    db.add(audit)
    return result


@router.post("/hermes/install")
async def hermes_install(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    return await _hermes_lifecycle_action("install", db, admin)


@router.post("/hermes/start")
async def hermes_start(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    return await _hermes_lifecycle_action("start", db, admin)


@router.post("/hermes/restart")
async def hermes_restart(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    return await _hermes_lifecycle_action("restart", db, admin)


@router.post("/hermes/stop")
async def hermes_stop(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    return await _hermes_lifecycle_action("stop", db, admin)


@router.post("/hermes/repair-sync")
async def hermes_repair_sync(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await _hermes_lifecycle_action("repair-sync", db, admin)
    profiles = (await db.execute(select(Profile).where(Profile.runtime_type == "hermes"))).scalars().all()
    sync_results = []
    for profile in profiles:
        definitions = await _load_skill_definitions(db, profile.skills or [])
        sync_results.append(
            {
                "profile_id": str(profile.id),
                "result": await hermes_profile_sync_service.sync(profile, definitions),
            }
        )
    return {"runtime": result, "profiles": sync_results}


@router.get("/hermes/logs")
async def hermes_logs(
    limit: int = Query(200, le=1000),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    return await hermes_orchestrator.logs(limit=limit)


@router.get("/monitoring/alerts")
async def get_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    alerts = await alert_service.list_alerts(db, status=status, severity=severity, limit=limit)
    payload = [
        {
            "id": str(alert.id),
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "status": alert.status,
            "title": alert.title,
            "message": alert.message,
            "context": alert.context,
            "first_seen_at": str(alert.first_seen_at),
            "last_seen_at": str(alert.last_seen_at),
            "last_notified_at": str(alert.last_notified_at) if alert.last_notified_at else None,
            "is_acknowledged": alert.is_acknowledged,
            "created_at": str(alert.created_at),
        }
        for alert in alerts
    ]
    return {
        "alerts": payload,
        "items": payload,
        "count": len(alerts),
    }


@router.post("/monitoring/alerts/run")
async def run_alert_evaluation(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    candidates = await alert_service.collect_candidates(db)
    result = await alert_service.sync_candidates(db, candidates)
    result["generated"] = result.get("activated", 0)
    db.add(
        AuditLog(
            user_id=str(admin.id),
            action="run_alert_evaluation",
            details=result,
        )
    )
    return result


@router.post("/monitoring/alerts/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    alert = await alert_service.acknowledge(db, str(alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.add(
        AuditLog(
            user_id=str(admin.id),
            action="acknowledge_alert",
            details={"alert_id": str(alert_id), "alert_type": alert.alert_type},
        )
    )
    return {"message": "Alert acknowledged", "alert_id": str(alert_id)}


# ==================== EXISTING ENDPOINTS ====================

@router.get("/kpis")
async def get_kpis(
    user_id: Optional[str] = None, date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    query = select(KPI)
    if user_id: query = query.where(KPI.user_id == user_id)
    if date: query = query.where(KPI.date == date)
    result = await db.execute(query)
    kpis = result.scalars().all()
    # Cost monitoring: include cost_alert and cost data
    return {
        "kpis": [{
            "user_id": k.user_id,
            "date": k.date,
            "tasks_completed": k.tasks_completed,
            "messages_sent": k.messages_sent,
            "avg_response_quality": k.avg_response_quality,
            "active_minutes": k.active_minutes,
            "tools_used": k.tools_used,
            "tokens_used": k.tokens_used,
            "total_cost": k.total_cost,
            "models_used": k.models_used,
            "cost_alert": k.cost_alert if hasattr(k, "cost_alert") else False,
        } for k in kpis],
        "count": len(kpis),
    }


@router.get("/audit-log")
async def get_audit_log(
    action: Optional[str] = None, user_id: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action: query = query.where(AuditLog.action == action)
    if user_id: query = query.where(AuditLog.user_id == user_id)
    query = query.limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()
    return {"audit_log": [{
        "id": l.id, "user_id": l.user_id, "action": l.action,
        "details": l.details, "ip_address": l.ip_address,
        "created_at": str(l.created_at),
    } for l in logs], "count": len(logs)}


@router.get("/agent-templates")
async def list_templates(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(AgentTemplate))
    templates = result.scalars().all()
    return {"templates": [{
        "name": t.name, "department": t.department, "model_name": t.model_name,
        "tools": t.tools, "temperature": t.temperature,
    } for t in templates]}


@router.post("/agent-templates", status_code=201)
async def create_agent_template(
    req: AgentTemplateCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    existing = await db.execute(select(AgentTemplate).where(AgentTemplate.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agent template already exists")
    template = AgentTemplate(
        name=req.name,
        department=req.department,
        system_prompt=req.system_prompt,
        tools=req.tools,
        model_name=req.model_name,
        max_tokens_per_request=req.max_tokens_per_request,
        temperature=req.temperature,
    )
    db.add(template)
    await db.flush()
    audit = AuditLog(user_id=str(admin.id), action="add_agent_template",
                     details={"name": req.name, "department": template.department})
    db.add(audit)
    return {
        "name": template.name, "department": template.department,
        "model_name": template.model_name, "message": "Agent template created",
    }


@router.put("/agent-templates/{name}")
async def update_agent_template(
    name: str,
    req: AgentTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    result = await db.execute(select(AgentTemplate).where(AgentTemplate.name == name))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Agent template not found")
    if req.department is not None: template.department = req.department
    if req.system_prompt is not None: template.system_prompt = req.system_prompt
    if req.tools is not None: template.tools = req.tools
    if req.model_name is not None: template.model_name = req.model_name
    if req.max_tokens_per_request is not None: template.max_tokens_per_request = req.max_tokens_per_request
    if req.temperature is not None: template.temperature = req.temperature
    audit = AuditLog(user_id=str(admin.id), action="update_agent_template",
                     details={"name": name})
    db.add(audit)
    return {"name": template.name, "message": "Agent template updated"}


@router.delete("/agent-templates/{name}")
async def delete_agent_template(
    name: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Delete an agent template."""
    result = await db.execute(select(AgentTemplate).where(AgentTemplate.name == name))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Agent template not found")
    await db.delete(template)
    audit = AuditLog(user_id=str(admin.id), action="delete_agent_template",
                     details={"name": name})
    db.add(audit)
    return {"message": "Agent template deleted"}


# ==================== SESSION DELETE ====================

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Delete a session and all its associated messages."""
    # Delete messages first (FK constraint)
    from sqlalchemy import delete
    await db.execute(delete(Message).where(Message.session_id == session_id))
    # Delete the session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    audit = AuditLog(user_id=str(admin.id), action="delete_session",
                     details={"session_id": str(session_id), "user_id": str(session.user_id)})
    db.add(audit)
    return {"message": "Session and messages deleted"}


# ==================== MONITORING & DASHBOARD ====================

@router.get("/monitoring/online-users")
async def get_online_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Get employees with an active desktop websocket connection."""
    active_user_ids = await presence_service.get_active_user_ids()
    if not active_user_ids:
        return {"online_count": 0, "online_users": []}

    result = await db.execute(
        select(User)
        .where(
            User.id.in_(active_user_ids),
            User.is_active == True,
            User.is_activated == True,
            User.role == "employee",
        )
    )
    online_users = result.scalars().all()
    
    return {
        "online_count": len(online_users),
        "online_users": [{
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "department": u.department,
            "role": u.role,
            "last_seen": str(u.last_seen_at) if u.last_seen_at else None,
        } for u in online_users],
    }


@router.get("/monitoring/activity-feed")
async def get_activity_feed(
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Get real-time activity feed for monitoring."""
    from app.models.user_activity import UserActivity
    
    query = (
        select(UserActivity)
        .join(User)
        .options(selectinload(UserActivity.user))
        .order_by(desc(UserActivity.created_at))
    )
    
    if user_id:
        query = query.where(UserActivity.user_id == user_id)
    if action:
        query = query.where(UserActivity.action == action)
    
    query = query.limit(limit)
    result = await db.execute(query)
    activities = result.scalars().all()
    
    return {
        "activities": [{
            "id": a.id,
            "user_id": str(a.user_id),
            "user_email": a.user.email,
            "user_name": a.user.full_name or a.user.email,
            "action": a.action,
            "details": a.details,
            "session_id": str(a.session_id) if a.session_id else None,
            "created_at": str(a.created_at),
        } for a in activities],
        "count": len(activities),
    }


@router.get("/monitoring/dashboard-stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Get comprehensive dashboard statistics for the admin panel."""
    from datetime import timedelta, date
    from app.models.user_activity import UserActivity
    from app.core.config import settings
    
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    # Total employees
    total_employees = await db.execute(
        select(func.count(User.id)).where(User.role == "employee")
    )
    total_employees = total_employees.scalar() or 0
    
    # Active employees
    active_employees = await db.execute(
        select(func.count(User.id)).where(
            User.role == "employee",
            User.is_active == True,
            User.is_activated == True,
        )
    )
    active_employees = active_employees.scalar() or 0
    
    # Online now (real-time desktop websocket presence)
    active_user_ids = await presence_service.get_active_user_ids()
    if active_user_ids:
        online_now_query = await db.execute(
            select(func.count(User.id)).where(
                User.id.in_(active_user_ids),
                User.role == "employee",
                User.is_active == True,
                User.is_activated == True,
            )
        )
        online_now = online_now_query.scalar() or 0
    else:
        online_now = 0
    
    # Messages today
    kpi_today = await db.execute(
        select(func.coalesce(func.sum(KPI.messages_sent), 0)).where(KPI.date == today)
    )
    messages_today = kpi_today.scalar() or 0
    
    # Messages yesterday
    kpi_yesterday = await db.execute(
        select(func.coalesce(func.sum(KPI.messages_sent), 0)).where(KPI.date == yesterday)
    )
    messages_yesterday = kpi_yesterday.scalar() or 0
    
    # Total sessions
    total_sessions = await db.execute(select(func.count(Session.id)))
    total_sessions = total_sessions.scalar() or 0
    
    # Sessions today
    today_start_dt = datetime.combine(date.today(), datetime.min.time())
    week_start_dt = datetime.combine(date.today() - timedelta(days=7), datetime.min.time())
    sessions_today = await db.execute(
        select(func.count(Session.id)).where(Session.created_at >= today_start_dt)
    )
    sessions_today = sessions_today.scalar() or 0
    
    # Token usage today
    tokens_today = await db.execute(
        select(func.coalesce(func.sum(KPI.tokens_used), 0)).where(KPI.date == today)
    )
    tokens_today = tokens_today.scalar() or 0

    cost_today = await db.execute(
        select(func.coalesce(func.sum(AgentRun.total_cost), 0)).where(AgentRun.created_at >= today_start_dt)
    )
    cost_today = float(cost_today.scalar() or 0.0)

    active_profiles = await db.execute(
        select(func.count(Profile.id)).where(Profile.is_active == True)
    )
    active_profiles = active_profiles.scalar() or 0

    failed_profile_syncs = await db.execute(
        select(func.count(Profile.id)).where(Profile.hermes_sync_status.in_(["sync_failed", "not_configured"]))
    )
    failed_profile_syncs = failed_profile_syncs.scalar() or 0

    failed_runs_today = await db.execute(
        select(func.count(AgentRun.id)).where(AgentRun.created_at >= today_start_dt, AgentRun.status == "failed")
    )
    failed_runs_today = failed_runs_today.scalar() or 0

    total_runs_today = await db.execute(
        select(func.count(AgentRun.id)).where(AgentRun.created_at >= today_start_dt)
    )
    total_runs_today = total_runs_today.scalar() or 0

    avg_latency_today = await db.execute(
        select(func.coalesce(func.avg(AgentRun.latency_ms), 0)).where(
            AgentRun.created_at >= today_start_dt,
            AgentRun.latency_ms.is_not(None),
        )
    )
    avg_latency_today = round(float(avg_latency_today.scalar() or 0.0), 1)

    run_failure_rate_today = (
        round((failed_runs_today / total_runs_today) * 100, 2)
        if total_runs_today
        else 0.0
    )

    key_pressure_result = await db.execute(
        select(UserApiKey).where(UserApiKey.is_active == True)
    )
    key_budget_pressure = []
    for key in key_pressure_result.scalars().all():
        percent_used = round((key.spent_today / key.daily_budget) * 100, 2) if key.daily_budget else 0.0
        if percent_used >= 70:
            key_budget_pressure.append({
                "id": str(key.id),
                "owner_type": key.owner_type,
                "user_id": str(key.user_id) if key.user_id else None,
                "profile_id": str(key.profile_id) if key.profile_id else None,
                "provider": key.provider,
                "spent_today": key.spent_today,
                "daily_budget": key.daily_budget,
                "percent_used": percent_used,
                "alert_level": "critical" if percent_used >= 90 else "warning",
            })

    profile_budget_result = await db.execute(
        select(
            Profile.id,
            Profile.name,
            Profile.daily_cost_budget,
            func.coalesce(func.sum(AgentRun.total_cost), 0),
        )
        .outerjoin(
            AgentRun,
            (AgentRun.profile_id == Profile.id) & (AgentRun.created_at >= today_start_dt),
        )
        .where(Profile.is_active == True, Profile.daily_cost_budget.is_not(None))
        .group_by(Profile.id, Profile.name, Profile.daily_cost_budget)
    )
    profile_budget_pressure = []
    for row in profile_budget_result.all():
        profile_budget = float(row[2] or 0.0)
        spent_today = float(row[3] or 0.0)
        percent_used = round((spent_today / profile_budget) * 100, 2) if profile_budget else 0.0
        if percent_used >= 70:
            profile_budget_pressure.append({
                "profile_id": str(row[0]),
                "profile_name": row[1],
                "daily_cost_budget": profile_budget,
                "spent_today": spent_today,
                "percent_used": percent_used,
                "alert_level": "critical" if percent_used >= 90 else "warning",
            })

    kpi_alert_result = await db.execute(
        select(User.email, User.full_name, KPI.tokens_used, KPI.total_cost)
        .join(KPI, KPI.user_id == User.id)
        .where(
            KPI.date == today,
            (KPI.tokens_used > settings.kpi_token_alert_threshold) | (KPI.total_cost > settings.kpi_cost_alert_threshold),
        )
        .order_by(desc(KPI.total_cost), desc(KPI.tokens_used))
        .limit(10)
    )
    kpi_alerts = [
        {
            "email": row[0],
            "full_name": row[1],
            "tokens_used": int(row[2] or 0),
            "total_cost": float(row[3] or 0.0),
            "alert_level": "critical" if float(row[3] or 0.0) > settings.kpi_cost_alert_threshold else "warning",
        }
        for row in kpi_alert_result.all()
    ]
    
    # Messages this week
    week_messages = await db.execute(
        select(func.coalesce(func.sum(KPI.messages_sent), 0)).where(KPI.date >= week_ago)
    )
    week_messages = week_messages.scalar() or 0
    
    # Calculate percentage change
    messages_change = 0
    if messages_yesterday > 0:
        messages_change = round(((messages_today - messages_yesterday) / messages_yesterday) * 100, 1)
    
    # Top 5 most active users today
    top_users_result = await db.execute(
        select(User, KPI)
        .join(KPI, User.id == KPI.user_id)
        .where(KPI.date == today)
        .order_by(desc(KPI.messages_sent))
        .limit(5)
    )
    top_users = top_users_result.all()
    
    # Activity counts by type today
    activity_counts = await db.execute(
        select(UserActivity.action, func.count(UserActivity.id))
        .where(UserActivity.created_at >= today_start_dt)
        .group_by(UserActivity.action)
    )
    activity_counts = {row[0]: row[1] for row in activity_counts.all()}
    
    daily_usage_result = await db.execute(
        select(
            KPI.date,
            func.coalesce(func.sum(KPI.messages_sent), 0),
            func.coalesce(func.sum(KPI.tokens_used), 0),
        )
        .where(KPI.date >= week_ago)
        .group_by(KPI.date)
    )
    daily_usage = {
        row[0]: {"messages": int(row[1] or 0), "tokens": int(row[2] or 0)}
        for row in daily_usage_result.all()
    }
    chart_days = [
        (date.today() - timedelta(days=i)).isoformat()
        for i in range(6, -1, -1)
    ]
    messages_per_day = [
        {"date": day, "messages": daily_usage.get(day, {}).get("messages", 0)}
        for day in chart_days
    ]
    tokens_per_day = [
        {"date": day, "tokens": daily_usage.get(day, {}).get("tokens", 0)}
        for day in chart_days
    ]

    profile_usage_result = await db.execute(
        select(Profile.name, func.count(AgentRun.id), func.coalesce(func.sum(AgentRun.total_cost), 0))
        .join(AgentRun, AgentRun.profile_id == Profile.id)
        .where(AgentRun.created_at >= week_start_dt)
        .group_by(Profile.name)
        .order_by(desc(func.count(AgentRun.id)))
        .limit(10)
    )
    profile_usage = [
        {"profile_name": row[0], "runs": row[1], "total_cost": float(row[2] or 0.0)}
        for row in profile_usage_result.all()
    ]

    employee_cost_result = await db.execute(
        select(
            User.email,
            User.full_name,
            func.count(AgentRun.id),
            func.coalesce(func.sum(AgentRun.total_cost), 0),
            func.coalesce(func.sum(AgentRun.output_tokens), 0),
        )
        .join(AgentRun, AgentRun.user_id == User.id)
        .where(AgentRun.created_at >= week_start_dt)
        .group_by(User.email, User.full_name)
        .order_by(desc(func.coalesce(func.sum(AgentRun.total_cost), 0)))
        .limit(10)
    )
    employee_cost = [
        {
            "email": row[0],
            "full_name": row[1],
            "runs": row[2],
            "total_cost": float(row[3] or 0.0),
            "output_tokens": int(row[4] or 0),
        }
        for row in employee_cost_result.all()
    ]

    try:
        async with asyncio.timeout(settings.dependency_health_timeout_seconds):
            hermes = await hermes_orchestrator.status()
    except Exception:
        hermes = {"status": "error", "message": "Agent runtime unavailable"}

    alerts = []
    if hermes.get("run_health") == "unhealthy" or hermes.get("status") in {"error", "unhealthy"}:
        alerts.append({
            "type": "hermes_runtime",
            "level": "critical",
            "message": "Agent runtime is unhealthy or unreachable.",
        })
    if failed_profile_syncs:
        alerts.append({
            "type": "profile_sync",
            "level": "warning",
            "message": f"{failed_profile_syncs} profile syncs require attention.",
        })
    if failed_runs_today:
        alerts.append({
            "type": "agent_runs",
            "level": "warning" if failed_runs_today < 5 else "critical",
            "message": f"{failed_runs_today} agent runs failed today.",
        })
    alerts.extend(
        {
            "type": "api_key_budget",
            "level": item["alert_level"],
            "message": f"API key budget usage is {item['percent_used']}% for {item['provider']} ({item['owner_type']}).",
            "context": item,
        }
        for item in key_budget_pressure[:10]
    )
    alerts.extend(
        {
            "type": "profile_budget",
            "level": item["alert_level"],
            "message": f"Profile {item['profile_name']} used {item['percent_used']}% of its daily budget.",
            "context": item,
        }
        for item in profile_budget_pressure[:10]
    )
    alerts.extend(
        {
            "type": "user_kpi",
            "level": item["alert_level"],
            "message": f"User {item['email']} exceeded KPI alert thresholds.",
            "context": item,
        }
        for item in kpi_alerts
    )
    
    return {
        "summary": {
            "total_employees": total_employees,
            "active_employees": active_employees,
            "online_now": online_now,
            "messages_today": messages_today,
            "messages_yesterday": messages_yesterday,
            "messages_change_pct": messages_change,
            "sessions_today": sessions_today,
            "total_sessions": total_sessions,
            "tokens_today": tokens_today,
            "week_messages": week_messages,
            "cost_today": cost_today,
            "active_profiles": active_profiles,
            "failed_profile_syncs": failed_profile_syncs,
            "failed_runs_today": failed_runs_today,
            "total_runs_today": total_runs_today,
            "run_failure_rate_today": run_failure_rate_today,
            "avg_latency_ms_today": avg_latency_today,
            "api_keys_over_70pct_budget": len(key_budget_pressure),
            "profiles_over_70pct_budget": len(profile_budget_pressure),
            "users_over_kpi_alert_threshold": len(kpi_alerts),
            "active_alerts": len(alerts),
        },
        "top_users": [{
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "messages_sent": kpi.messages_sent,
            "tokens_used": kpi.tokens_used if hasattr(kpi, 'tokens_used') else 0,
        } for u, kpi in top_users],
        "activity_counts": activity_counts,
        "messages_per_day": messages_per_day,
        "tokens_per_day": tokens_per_day,
        "profile_usage": profile_usage,
        "employee_cost": employee_cost,
        "key_budget_pressure": key_budget_pressure,
        "profile_budget_pressure": profile_budget_pressure,
        "kpi_alerts": kpi_alerts,
        "alerts": alerts,
        "observability": {
            "sentry_configured": bool(settings.sentry_dsn),
            "sentry_environment": settings.sentry_environment or settings.environment,
            "sentry_traces_sample_rate": settings.sentry_traces_sample_rate,
        },
        "hermes": hermes,
    }
