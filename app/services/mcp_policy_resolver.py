import hashlib
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.mcp import McpConnection, McpServer, ProfileMcpBinding
from app.services.mcp_connection_service import McpConnectionError, mcp_credentials


class McpPolicyError(RuntimeError):
    pass


def _tool_names(tools: list[dict[str, Any]] | None) -> set[str]:
    return {str(tool.get("name") or "").strip() for tool in (tools or []) if str(tool.get("name") or "").strip()}


def effective_mcp_tools(
    binding_allowed: list[str] | None,
    server_tools: list[dict[str, Any]] | None,
    connection_tools: list[dict[str, Any]] | None,
) -> list[str]:
    server_names = _tool_names(server_tools)
    connection_names = _tool_names(connection_tools)
    return [
        name
        for name in dict.fromkeys(str(item).strip() for item in (binding_allowed or []) if str(item).strip())
        if name in server_names and name in connection_names
    ]


def _credential_env_name(server: McpServer) -> str:
    safe_slug = re.sub(r"[^A-Z0-9]+", "_", server.slug.upper()).strip("_")[:32] or "SERVER"
    suffix = hashlib.sha256(str(server.id).encode()).hexdigest()[:8].upper()
    return f"MCP_{safe_slug}_{suffix}_TOKEN"


class McpPolicyResolver:
    async def resolve(
        self,
        db: AsyncSession,
        user_id: UUID,
        profile_id: UUID | None,
    ) -> list[dict[str, Any]]:
        if not settings.mcp_enabled or profile_id is None:
            return []
        bindings_result = await db.execute(
            select(ProfileMcpBinding)
            .where(
                ProfileMcpBinding.profile_id == profile_id,
                ProfileMcpBinding.is_active == True,
            )
            .options(selectinload(ProfileMcpBinding.server))
            .order_by(ProfileMcpBinding.created_at.asc())
        )
        bindings = bindings_result.scalars().all()
        if not bindings:
            return []
        server_ids = [binding.server_id for binding in bindings]
        connections_result = await db.execute(
            select(McpConnection).where(
                McpConnection.server_id.in_(server_ids),
                McpConnection.is_active == True,
                McpConnection.status == "connected",
                (McpConnection.user_id == user_id) | (McpConnection.owner_type == "platform"),
            )
        )
        connections = connections_result.scalars().all()
        user_connections = {
            item.server_id: item for item in connections if item.owner_type == "user" and item.user_id == user_id
        }
        platform_connections = {
            item.server_id: item for item in connections if item.owner_type == "platform"
        }
        resolved: list[dict[str, Any]] = []
        for binding in bindings:
            server = binding.server
            if not server.is_active:
                continue
            opt_in_connection = user_connections.get(server.id)
            if opt_in_connection is None:
                continue
            credential_connection = (
                platform_connections.get(server.id)
                if server.credential_mode == "platform"
                else opt_in_connection
            )
            if credential_connection is None:
                continue
            allowed_tools = effective_mcp_tools(
                binding.allowed_tools,
                server.discovered_tools,
                opt_in_connection.discovered_tools,
            )
            if not allowed_tools:
                continue
            approvals = [
                tool for tool in (binding.approval_required_tools or []) if tool in set(allowed_tools)
            ]
            try:
                credential = mcp_credentials.decrypt(credential_connection.encrypted_credentials)
            except McpConnectionError:
                continue
            if server.auth_type != "none" and not credential:
                continue
            resolved.append({
                "id": str(server.id),
                "slug": server.slug,
                "name": server.name,
                "url": server.url,
                "auth_type": server.auth_type,
                "api_key_header": server.api_key_header,
                "credential_env": _credential_env_name(server),
                "credential": credential,
                "allowed_tools": allowed_tools,
                "approval_required_tools": approvals,
            })
        return resolved


mcp_policy_resolver = McpPolicyResolver()
