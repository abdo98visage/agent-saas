from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.core.db import get_db
from app.models.audit_log import AuditLog
from app.models.mcp import McpConnection, McpServer, ProfileMcpBinding
from app.models.profile import Profile
from app.models.profile_user import ProfileUser
from app.models.user import User
from app.schemas.mcp import McpUserConnectRequest
from app.services.mcp_connection_service import McpConnectionError, mcp_connection_service, mcp_credentials
from app.services.mcp_security import McpEndpointRejected


router = APIRouter()


async def _available_rows(db: AsyncSession, user_id: UUID, profile_name: str | None = None):
    query = (
        select(Profile, ProfileMcpBinding, McpServer)
        .join(ProfileUser, ProfileUser.profile_id == Profile.id)
        .join(ProfileMcpBinding, ProfileMcpBinding.profile_id == Profile.id)
        .join(McpServer, McpServer.id == ProfileMcpBinding.server_id)
        .where(
            ProfileUser.user_id == user_id,
            Profile.is_active == True,
            ProfileMcpBinding.is_active == True,
            McpServer.is_active == True,
        )
        .order_by(ProfileUser.priority.asc(), McpServer.name.asc())
    )
    if profile_name:
        query = query.where(Profile.name == profile_name)
    return (await db.execute(query)).all()


async def _user_connection(db: AsyncSession, user_id: UUID, server_id: UUID) -> McpConnection | None:
    result = await db.execute(
        select(McpConnection)
        .where(
            McpConnection.user_id == user_id,
            McpConnection.server_id == server_id,
            McpConnection.owner_type == "user",
        )
        .options(selectinload(McpConnection.server))
    )
    return result.scalar_one_or_none()


def _connection_payload(
    server: McpServer,
    connection: McpConnection | None,
    platform_connection: McpConnection | None,
) -> dict | None:
    if connection is None:
        return None
    status = connection.status
    last_error = connection.last_error
    last_checked_at = connection.last_checked_at
    if server.credential_mode == "platform" and (
        platform_connection is None
        or not platform_connection.is_active
        or platform_connection.status != "connected"
    ):
        status = "error"
        last_error = (
            platform_connection.last_error
            if platform_connection and platform_connection.last_error
            else "The administrator connection is not ready"
        )
        if platform_connection and platform_connection.last_checked_at:
            last_checked_at = platform_connection.last_checked_at
    return {
        "id": str(connection.id),
        "status": status,
        "credential_hint": connection.credential_hint,
        "last_checked_at": str(last_checked_at) if last_checked_at else None,
        "last_error": last_error,
    }


def _available_payload(
    profile: Profile,
    binding: ProfileMcpBinding,
    server: McpServer,
    connection: McpConnection | None,
    platform_connection: McpConnection | None = None,
) -> dict:
    return {
        "profile_id": str(profile.id),
        "profile_name": profile.name,
        "server_id": str(server.id),
        "name": server.name,
        "slug": server.slug,
        "description": server.description,
        "auth_type": server.auth_type,
        "credential_mode": server.credential_mode,
        "allowed_tools": binding.allowed_tools or [],
        "approval_required_tools": binding.approval_required_tools or [],
        "connection": _connection_payload(server, connection, platform_connection),
    }


@router.get("/available")
async def list_available_mcp_servers(
    profile_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = await _available_rows(db, user.id, profile_name)
    connections_result = await db.execute(
        select(McpConnection).where(
            McpConnection.user_id == user.id,
            McpConnection.owner_type == "user",
        )
    )
    connections = {item.server_id: item for item in connections_result.scalars().all()}
    server_ids = {server.id for _, _, server in rows if server.credential_mode == "platform"}
    platform_connections = {}
    if server_ids:
        platform_result = await db.execute(
            select(McpConnection).where(
                McpConnection.server_id.in_(server_ids),
                McpConnection.owner_type == "platform",
            )
        )
        platform_connections = {item.server_id: item for item in platform_result.scalars().all()}
    payload = [
        _available_payload(
            profile,
            binding,
            server,
            connections.get(server.id),
            platform_connections.get(server.id),
        )
        for profile, binding, server in rows
    ]
    return {"servers": payload, "count": len(payload)}


@router.post("/connections/{server_id}")
async def connect_mcp_server(
    server_id: UUID,
    req: McpUserConnectRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    available = [row for row in await _available_rows(db, user.id) if row[2].id == server_id]
    if not available:
        raise HTTPException(status_code=403, detail="This MCP server is not available to your assigned profiles")
    server = available[0][2]
    connection = await _user_connection(db, user.id, server.id)
    if connection is None:
        connection = McpConnection(server_id=server.id, owner_type="user", user_id=user.id)
        connection.server = server
        db.add(connection)
    if server.credential_mode == "platform":
        platform_result = await db.execute(
            select(McpConnection).where(
                McpConnection.server_id == server.id,
                McpConnection.owner_type == "platform",
                McpConnection.is_active == True,
                McpConnection.status == "connected",
            )
        )
        platform_connection = platform_result.scalar_one_or_none()
        if not platform_connection:
            connection.status = "error"
            connection.last_error = "The administrator connection is not ready"
        else:
            connection.status = "connected"
            connection.last_error = None
            connection.discovered_tools = server.discovered_tools or []
            connection.tools_schema_hash = server.tools_schema_hash
            connection.last_checked_at = datetime.utcnow()
    else:
        if server.auth_type != "none" and not req.credential:
            raise HTTPException(status_code=400, detail="A credential is required for this MCP server")
        connection.encrypted_credentials = mcp_credentials.encrypt(req.credential)
        connection.credential_hint = mcp_credentials.hint(req.credential)
        try:
            await mcp_connection_service.check_connection(connection)
        except (McpConnectionError, McpEndpointRejected):
            pass
    connection.is_active = connection.status == "connected"
    db.add(AuditLog(user_id=user.id, action="mcp_user_connection_changed", details={"server_id": str(server.id), "status": connection.status}))
    await db.flush()
    return {
        "server_id": str(server.id),
        "status": connection.status,
        "credential_hint": connection.credential_hint,
        "last_error": connection.last_error,
    }


@router.delete("/connections/{server_id}")
async def disconnect_mcp_server(
    server_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    connection = await _user_connection(db, user.id, server_id)
    if not connection:
        raise HTTPException(status_code=404, detail="MCP connection not found")
    await db.delete(connection)
    db.add(AuditLog(user_id=user.id, action="mcp_user_disconnected", details={"server_id": str(server_id)}))
    return {"message": "MCP server disconnected"}
