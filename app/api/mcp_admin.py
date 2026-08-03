from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_admin_user
from app.core.db import get_db
from app.models.audit_log import AuditLog
from app.models.mcp import McpConnection, McpServer, ProfileMcpBinding
from app.models.profile import Profile
from app.models.user import User
from app.schemas.mcp import (
    McpDiscoveryRequest,
    McpServerCreate,
    McpServerUpdate,
    ProfileMcpBindingUpsert,
)
from app.services.mcp_connection_service import (
    McpConnectionError,
    mcp_connection_service,
    mcp_credentials,
)
from app.services.mcp_security import McpEndpointRejected, validate_mcp_url


router = APIRouter()


def _connection_payload(connection: McpConnection | None) -> dict | None:
    if connection is None:
        return None
    return {
        "id": str(connection.id),
        "owner_type": connection.owner_type,
        "user_id": str(connection.user_id) if connection.user_id else None,
        "credential_hint": connection.credential_hint,
        "status": connection.status,
        "discovered_tools": connection.discovered_tools or [],
        "tools_schema_hash": connection.tools_schema_hash,
        "last_checked_at": str(connection.last_checked_at) if connection.last_checked_at else None,
        "last_error": connection.last_error,
        "is_active": connection.is_active,
    }


def _server_payload(server: McpServer) -> dict:
    platform_connection = next(
        (item for item in (server.connections or []) if item.owner_type == "platform"),
        None,
    )
    return {
        "id": str(server.id),
        "name": server.name,
        "slug": server.slug,
        "description": server.description,
        "url": server.url,
        "auth_type": server.auth_type,
        "credential_mode": server.credential_mode,
        "api_key_header": server.api_key_header,
        "is_active": server.is_active,
        "discovered_tools": server.discovered_tools or [],
        "tools_schema_hash": server.tools_schema_hash,
        "last_checked_at": str(server.last_checked_at) if server.last_checked_at else None,
        "last_error": server.last_error,
        "platform_connection": _connection_payload(platform_connection),
        "binding_count": len(server.profile_bindings or []),
        "created_at": str(server.created_at),
        "updated_at": str(server.updated_at),
    }


def _binding_payload(binding: ProfileMcpBinding) -> dict:
    return {
        "id": str(binding.id),
        "profile_id": str(binding.profile_id),
        "server_id": str(binding.server_id),
        "server_name": binding.server.name,
        "server_slug": binding.server.slug,
        "server_active": binding.server.is_active,
        "allowed_tools": binding.allowed_tools or [],
        "approval_required_tools": binding.approval_required_tools or [],
        "is_active": binding.is_active,
        "created_at": str(binding.created_at),
        "updated_at": str(binding.updated_at),
    }


async def _server_with_relations(db: AsyncSession, server_id: UUID) -> McpServer | None:
    result = await db.execute(
        select(McpServer)
        .where(McpServer.id == server_id)
        .options(selectinload(McpServer.connections), selectinload(McpServer.profile_bindings))
    )
    return result.scalar_one_or_none()


async def _discover_server(server: McpServer, credential: str | None) -> None:
    try:
        tools, schema_hash = await mcp_connection_service.discover(server, credential)
    except (McpConnectionError, McpEndpointRejected) as exc:
        server.last_checked_at = datetime.utcnow()
        server.last_error = str(exc)
        raise
    server.discovered_tools = tools
    server.tools_schema_hash = schema_hash
    server.last_checked_at = datetime.utcnow()
    server.last_error = None


async def _sync_legacy_profile_servers(db: AsyncSession, profile: Profile) -> None:
    result = await db.execute(
        select(McpServer.slug)
        .join(ProfileMcpBinding, ProfileMcpBinding.server_id == McpServer.id)
        .where(
            ProfileMcpBinding.profile_id == profile.id,
            ProfileMcpBinding.is_active == True,
            McpServer.is_active == True,
        )
        .order_by(McpServer.slug.asc())
    )
    profile.allowed_mcp_servers = list(result.scalars().all())


@router.get("/servers")
async def list_mcp_servers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    result = await db.execute(
        select(McpServer)
        .options(selectinload(McpServer.connections), selectinload(McpServer.profile_bindings))
        .order_by(McpServer.name.asc())
    )
    servers = result.scalars().unique().all()
    return {"servers": [_server_payload(server) for server in servers], "count": len(servers)}


@router.post("/servers", status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    req: McpServerCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    try:
        normalized_url = validate_mcp_url(req.url)
    except McpEndpointRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    existing = await db.execute(select(McpServer.id).where(McpServer.slug == req.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="MCP server slug already exists")
    server = McpServer(
        name=req.name,
        slug=req.slug,
        description=req.description,
        url=normalized_url,
        auth_type=req.auth_type,
        credential_mode=req.credential_mode,
        api_key_header=req.api_key_header,
        is_active=req.is_active,
    )
    db.add(server)
    await db.flush()
    platform_connection = None
    if req.credential_mode == "platform":
        platform_connection = McpConnection(
            server_id=server.id,
            owner_type="platform",
            encrypted_credentials=mcp_credentials.encrypt(req.credential),
            credential_hint=mcp_credentials.hint(req.credential),
            status="pending",
        )
        db.add(platform_connection)
    discovery_credential = req.credential if req.auth_type != "none" else None
    try:
        await _discover_server(server, discovery_credential)
        if platform_connection is not None:
            platform_connection.status = "connected"
            platform_connection.is_active = True
            platform_connection.discovered_tools = server.discovered_tools
            platform_connection.tools_schema_hash = server.tools_schema_hash
            platform_connection.last_checked_at = server.last_checked_at
    except (McpConnectionError, McpEndpointRejected):
        if platform_connection is not None:
            platform_connection.status = "error"
            platform_connection.is_active = False
            platform_connection.last_error = server.last_error
            platform_connection.last_checked_at = server.last_checked_at
    db.add(AuditLog(user_id=admin.id, action="mcp_server_created", details={"server_id": str(server.id), "slug": server.slug}))
    await db.flush()
    loaded_server = await _server_with_relations(db, server.id)
    if loaded_server is None:
        raise HTTPException(status_code=500, detail="MCP server could not be reloaded")
    return _server_payload(loaded_server)


@router.put("/servers/{server_id}")
async def update_mcp_server(
    server_id: UUID,
    req: McpServerUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    server = await _server_with_relations(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    previous_mode = server.credential_mode
    for field in ("name", "description", "auth_type", "credential_mode", "api_key_header", "is_active"):
        value = getattr(req, field)
        if value is not None:
            setattr(server, field, value)
    if req.url is not None:
        try:
            server.url = validate_mcp_url(req.url)
        except McpEndpointRejected as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if server.auth_type == "oauth":
        raise HTTPException(status_code=400, detail="OAuth MCP connections are not enabled yet")
    if previous_mode != server.credential_mode:
        incompatible_owner = "platform" if server.credential_mode == "user" else "user"
        await db.execute(
            delete(McpConnection).where(
                McpConnection.server_id == server.id,
                McpConnection.owner_type == incompatible_owner,
            )
        )
        server.connections = [item for item in server.connections if item.owner_type != incompatible_owner]
    platform_connection = next((item for item in server.connections if item.owner_type == "platform"), None)
    if server.credential_mode == "platform":
        if platform_connection is None:
            if server.auth_type != "none" and not req.credential:
                raise HTTPException(status_code=400, detail="A platform credential is required")
            platform_connection = McpConnection(server_id=server.id, owner_type="platform")
            db.add(platform_connection)
            server.connections.append(platform_connection)
        if req.credential is not None:
            platform_connection.encrypted_credentials = mcp_credentials.encrypt(req.credential)
            platform_connection.credential_hint = mcp_credentials.hint(req.credential)
        stored_credential = mcp_credentials.decrypt(platform_connection.encrypted_credentials)
        if server.auth_type != "none" and not stored_credential:
            raise HTTPException(status_code=400, detail="A platform credential is required")
    credential = req.credential
    if credential is None and platform_connection is not None:
        credential = mcp_credentials.decrypt(platform_connection.encrypted_credentials)
    if server.auth_type == "none" or credential:
        try:
            await _discover_server(server, credential)
            if platform_connection:
                platform_connection.status = "connected"
                platform_connection.is_active = True
                platform_connection.discovered_tools = server.discovered_tools
                platform_connection.tools_schema_hash = server.tools_schema_hash
                platform_connection.last_checked_at = server.last_checked_at
                platform_connection.last_error = None
        except (McpConnectionError, McpEndpointRejected):
            if platform_connection:
                platform_connection.status = "error"
                platform_connection.is_active = False
                platform_connection.last_checked_at = server.last_checked_at
                platform_connection.last_error = server.last_error
    elif server.auth_type != "none" and any(
        getattr(req, field) is not None
        for field in ("url", "auth_type", "credential_mode", "api_key_header")
    ):
        server.discovered_tools = []
        server.tools_schema_hash = ""
        server.last_error = "Tool discovery is required with a user credential"
    db.add(AuditLog(user_id=admin.id, action="mcp_server_updated", details={"server_id": str(server.id), "slug": server.slug}))
    await db.flush()
    return _server_payload(server)


@router.post("/servers/{server_id}/discover")
async def discover_mcp_server(
    server_id: UUID,
    req: McpDiscoveryRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    server = await _server_with_relations(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    credential = req.credential
    platform_connection = next((item for item in server.connections if item.owner_type == "platform"), None)
    if credential is None and platform_connection:
        credential = mcp_credentials.decrypt(platform_connection.encrypted_credentials)
    try:
        await _discover_server(server, credential)
    except (McpConnectionError, McpEndpointRejected) as exc:
        if platform_connection:
            platform_connection.status = "error"
            platform_connection.is_active = False
            platform_connection.last_error = str(exc)
            platform_connection.last_checked_at = server.last_checked_at
        return {"status": "error", "detail": str(exc), "server": _server_payload(server)}
    if platform_connection:
        platform_connection.status = "connected"
        platform_connection.is_active = True
        platform_connection.discovered_tools = server.discovered_tools
        platform_connection.tools_schema_hash = server.tools_schema_hash
        platform_connection.last_checked_at = server.last_checked_at
        platform_connection.last_error = None
    db.add(AuditLog(user_id=admin.id, action="mcp_server_discovered", details={"server_id": str(server.id), "tool_count": len(server.discovered_tools)}))
    return {"status": "connected", "server": _server_payload(server)}


@router.delete("/servers/{server_id}")
async def delete_mcp_server(
    server_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    server = await _server_with_relations(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    affected_profile_ids = {binding.profile_id for binding in server.profile_bindings}
    await db.delete(server)
    await db.flush()
    for profile_id in affected_profile_ids:
        profile = await db.get(Profile, profile_id)
        if profile:
            await _sync_legacy_profile_servers(db, profile)
    db.add(AuditLog(user_id=admin.id, action="mcp_server_deleted", details={"server_id": str(server_id), "slug": server.slug}))
    return {"message": "MCP server deleted"}


@router.get("/profiles/{profile_id}/bindings")
async def list_profile_mcp_bindings(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
):
    if not await db.get(Profile, profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    result = await db.execute(
        select(ProfileMcpBinding)
        .where(ProfileMcpBinding.profile_id == profile_id)
        .options(selectinload(ProfileMcpBinding.server))
        .order_by(ProfileMcpBinding.created_at.asc())
    )
    bindings = result.scalars().all()
    return {"bindings": [_binding_payload(binding) for binding in bindings], "count": len(bindings)}


@router.post("/profiles/{profile_id}/bindings")
async def upsert_profile_mcp_binding(
    profile_id: UUID,
    req: ProfileMcpBindingUpsert,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    profile = await db.get(Profile, profile_id)
    server = await db.get(McpServer, req.server_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    if req.is_active and not server.is_active:
        raise HTTPException(status_code=400, detail="Disabled MCP servers cannot be enabled for a profile")
    discovered = {str(tool.get("name")) for tool in (server.discovered_tools or [])}
    unknown = set(req.allowed_tools) - discovered
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown MCP tools: {', '.join(sorted(unknown))}")
    result = await db.execute(
        select(ProfileMcpBinding).where(
            ProfileMcpBinding.profile_id == profile.id,
            ProfileMcpBinding.server_id == server.id,
        )
    )
    binding = result.scalar_one_or_none()
    if binding is None:
        binding = ProfileMcpBinding(profile_id=profile.id, server_id=server.id)
        db.add(binding)
    binding.allowed_tools = req.allowed_tools
    binding.approval_required_tools = req.approval_required_tools
    binding.is_active = req.is_active
    await db.flush()
    await db.refresh(binding, attribute_names=["server"])
    await _sync_legacy_profile_servers(db, profile)
    db.add(AuditLog(user_id=admin.id, action="profile_mcp_binding_updated", details={"profile_id": str(profile.id), "server_id": str(server.id), "allowed_tools": req.allowed_tools}))
    return _binding_payload(binding)


@router.delete("/profiles/{profile_id}/bindings/{server_id}")
async def delete_profile_mcp_binding(
    profile_id: UUID,
    server_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    profile = await db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    result = await db.execute(
        select(ProfileMcpBinding).where(
            ProfileMcpBinding.profile_id == profile_id,
            ProfileMcpBinding.server_id == server_id,
        )
    )
    binding = result.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="MCP profile binding not found")
    await db.delete(binding)
    await db.flush()
    await _sync_legacy_profile_servers(db, profile)
    db.add(AuditLog(user_id=admin.id, action="profile_mcp_binding_deleted", details={"profile_id": str(profile_id), "server_id": str(server_id)}))
    return {"message": "MCP profile binding deleted"}
