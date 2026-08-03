import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


class McpEndpointRejected(ValueError):
    pass


def validate_mcp_url(value: str) -> str:
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
    except ValueError as exc:
        raise McpEndpointRejected("Invalid MCP server URL") from exc
    if parsed.scheme.lower() != "https":
        raise McpEndpointRejected("MCP server URL must use HTTPS")
    if not parsed.hostname:
        raise McpEndpointRejected("MCP server URL must include a hostname")
    if parsed.username or parsed.password:
        raise McpEndpointRejected("Credentials are not allowed in the MCP server URL")
    if parsed.fragment:
        raise McpEndpointRejected("MCP server URL must not include a fragment")
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        raise McpEndpointRejected("Local MCP server addresses are not allowed")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise McpEndpointRejected("Private or reserved MCP server addresses are not allowed")
    try:
        port = parsed.port
    except ValueError as exc:
        raise McpEndpointRejected("MCP server URL has an invalid port") from exc
    host_for_url = f"[{hostname}]" if ":" in hostname else hostname
    netloc = host_for_url
    if port:
        netloc = f"{host_for_url}:{port}"
    return urlunsplit(("https", netloc, parsed.path or "/", parsed.query, ""))


async def validate_mcp_destination(value: str) -> str:
    normalized = validate_mcp_url(value)
    parsed = urlsplit(normalized)
    loop = asyncio.get_running_loop()
    try:
        records = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM),
            ),
            timeout=5,
        )
    except (OSError, asyncio.TimeoutError) as exc:
        raise McpEndpointRejected("MCP server hostname could not be resolved") from exc
    if not records:
        raise McpEndpointRejected("MCP server hostname could not be resolved")
    for record in records:
        address = ipaddress.ip_address(record[4][0])
        if not address.is_global:
            raise McpEndpointRejected("MCP server resolved to a private or reserved address")
    return normalized
