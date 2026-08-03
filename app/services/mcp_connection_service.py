import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings
from app.models.mcp import McpConnection, McpServer
from app.services.mcp_security import McpEndpointRejected, validate_mcp_destination


class McpConnectionError(RuntimeError):
    pass


def _non_redirecting_http_client(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        auth=auth,
        follow_redirects=False,
    )


class McpCredentialService:
    def __init__(self) -> None:
        self._fernet: Fernet | None = None

    @property
    def fernet(self) -> Fernet:
        if self._fernet is None:
            self._fernet = Fernet(settings.fernet_key.encode())
        return self._fernet

    def encrypt(self, credential: str | None) -> str:
        value = str(credential or "")
        if not value:
            return ""
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str | None) -> str:
        if not encrypted:
            return ""
        try:
            return self.fernet.decrypt(encrypted.encode()).decode()
        except InvalidToken as exc:
            raise McpConnectionError("Stored MCP credential cannot be decrypted") from exc

    @staticmethod
    def hint(credential: str | None) -> str:
        value = str(credential or "")
        return f"...{value[-4:]}" if value else ""


def mcp_auth_headers(server: McpServer, credential: str | None) -> dict[str, str]:
    value = str(credential or "")
    if server.auth_type == "none":
        return {}
    if not value:
        raise McpConnectionError("MCP credentials are required")
    if server.auth_type == "bearer" or server.auth_type == "oauth":
        return {"Authorization": f"Bearer {value}"}
    if server.auth_type == "api_key":
        return {server.api_key_header: value}
    raise McpConnectionError("Unsupported MCP authentication type")


def _tool_payload(tool: Any) -> dict[str, Any]:
    payload = tool.model_dump(mode="json") if hasattr(tool, "model_dump") else {}
    return {
        "name": str(payload.get("name") or "")[:200],
        "description": str(payload.get("description") or "")[:4000],
        "input_schema": payload.get("inputSchema") or payload.get("input_schema") or {},
        "annotations": payload.get("annotations") or {},
    }


def tools_schema_hash(tools: list[dict[str, Any]]) -> str:
    canonical = json.dumps(tools, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


class McpConnectionService:
    async def discover(self, server: McpServer, credential: str | None = None) -> tuple[list[dict[str, Any]], str]:
        server.url = await validate_mcp_destination(server.url)
        headers = mcp_auth_headers(server, credential)
        try:
            async with streamablehttp_client(
                server.url,
                headers=headers,
                timeout=settings.mcp_connect_timeout_seconds,
                sse_read_timeout=settings.mcp_tool_timeout_seconds,
                httpx_client_factory=_non_redirecting_http_client,
            ) as (read_stream, write_stream, _):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timedelta(seconds=settings.mcp_tool_timeout_seconds),
                    sampling_capabilities=None,
                ) as session:
                    await session.initialize()
                    response = await session.list_tools()
        except Exception as exc:
            raise McpConnectionError(f"Unable to connect to MCP server: {type(exc).__name__}") from exc
        tools = [_tool_payload(tool) for tool in response.tools]
        if len(tools) > 500:
            raise McpConnectionError("MCP server exposes too many tools")
        if any(not tool["name"] for tool in tools):
            raise McpConnectionError("MCP server returned an invalid tool definition")
        names = [tool["name"] for tool in tools]
        if len(set(names)) != len(names):
            raise McpConnectionError("MCP server returned duplicate tool names")
        if len(json.dumps(tools, ensure_ascii=False).encode("utf-8")) > 2 * 1024 * 1024:
            raise McpConnectionError("MCP tool catalog is too large")
        return tools, tools_schema_hash(tools)

    async def check_connection(self, connection: McpConnection) -> tuple[list[dict[str, Any]], str]:
        credential = mcp_credentials.decrypt(connection.encrypted_credentials)
        try:
            tools, schema_hash = await self.discover(connection.server, credential)
        except (McpConnectionError, McpEndpointRejected) as exc:
            connection.status = "error"
            connection.is_active = False
            connection.last_checked_at = datetime.utcnow()
            connection.last_error = str(exc)
            raise
        connection.status = "connected"
        connection.is_active = True
        connection.discovered_tools = tools
        connection.tools_schema_hash = schema_hash
        connection.last_checked_at = datetime.utcnow()
        connection.last_error = None
        return tools, schema_hash


mcp_credentials = McpCredentialService()
mcp_connection_service = McpConnectionService()
