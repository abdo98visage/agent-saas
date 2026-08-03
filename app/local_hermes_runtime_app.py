"""
Hermes CLI bridge runtime.

This service keeps the existing AgentSaaS HTTP contract while delegating each
run to a real hermes-agent profile stored under /data/hermes/profiles/<slug>.
"""
import asyncio
import base64
import json
import os
import re
import secrets
import signal
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
import websockets
from app.core.config import settings
from app.core.runtime_policy import ALL_RUNTIME_TOOLSETS, SAFE_RUNTIME_TOOLSETS, normalize_runtime_toolsets
from app.services.attachments import normalize_image_attachments
from app.services.mcp_security import McpEndpointRejected, validate_mcp_destination


HERMES_PROFILES_ROOT = Path(os.getenv("HERMES_PROFILES_ROOT", "/data/hermes/profiles"))
OPENAI_COMPAT_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "")
MCP_PROXY_BASE_URL = os.getenv("MCP_PROXY_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen3-14b")
RUNTIME_SECRET = os.getenv("HERMES_RUNTIME_SECRET", "")
RUNTIME_REQUIRE_SECRET = os.getenv("HERMES_RUNTIME_REQUIRE_SECRET", "true").lower() == "true"
INLINE_TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".css",
    ".js", ".ts", ".py", ".sql", ".toml", ".ini", ".cfg", ".conf",
}

_pending_approvals: dict[tuple[str, str], asyncio.Future[str]] = {}
_mcp_proxy_runs: dict[str, dict[str, Any]] = {}


def _hermes_mcp_tool_name(server_slug: str, tool_name: str) -> str:
    normalize = lambda value: re.sub(r"[^a-zA-Z0-9_]", "_", value)
    return f"mcp__{normalize(server_slug)}__{normalize(tool_name)}"


def _mcp_tool_identity(tool_name: str, servers: list[dict[str, Any]]) -> tuple[str, str] | None:
    matches: list[tuple[int, str, str]] = []
    for server in servers:
        slug = str(server.get("slug") or "")
        for original in server.get("allowed_tools") or []:
            registered = _hermes_mcp_tool_name(slug, str(original))
            if registered == tool_name:
                matches.append((len(registered), slug, str(original)))
    if not matches:
        return None
    _, slug, original = max(matches)
    return slug, original


def _mcp_approval_tool_names(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for server in payload.get("mcp_servers") or []:
        for tool in server.get("approval_required_tools") or []:
            names.append(_hermes_mcp_tool_name(str(server.get("slug") or ""), str(tool)))
    return names


def _register_mcp_proxy(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    servers = payload.get("mcp_servers") or []
    if not servers:
        return payload, None
    token = uuid4().hex
    proxy_servers: list[dict[str, Any]] = []
    server_map: dict[str, dict[str, Any]] = {}
    for server in servers:
        slug = str(server.get("slug") or "").strip()
        if not slug:
            continue
        server_map[slug] = dict(server)
        proxy_servers.append({
            **server,
            "url": f"{MCP_PROXY_BASE_URL}/internal/mcp/{slug}",
            "auth_type": "none",
            "credential": "",
            "credential_env": "",
            "proxy_token": token,
        })
    if not server_map:
        return {**payload, "mcp_servers": []}, None
    _mcp_proxy_runs[token] = {
        "servers": server_map,
        "approval_queue": asyncio.Queue(),
        "interactive": bool(payload.get("interactive_approvals")),
        "run_id": str(payload.get("run_id") or ""),
    }
    return {**payload, "mcp_servers": proxy_servers}, token

app = FastAPI(title="AgentSaaS Agent Runtime", version="0.2.0")


def _authorize_runtime(secret: str | None) -> None:
    if RUNTIME_REQUIRE_SECRET and not RUNTIME_SECRET:
        raise HTTPException(status_code=503, detail="Agent runtime secret is not configured")
    if RUNTIME_SECRET and not secrets.compare_digest(secret or "", RUNTIME_SECRET):
        raise HTTPException(status_code=403, detail="Invalid agent runtime secret")


def _proxy_auth_headers(server: dict[str, Any]) -> dict[str, str]:
    auth_type = str(server.get("auth_type") or "none")
    credential = str(server.get("credential") or "")
    if auth_type == "none":
        return {}
    if not credential:
        raise HTTPException(status_code=503, detail="MCP credential is unavailable")
    if auth_type in {"bearer", "oauth"}:
        return {"Authorization": f"Bearer {credential}"}
    if auth_type == "api_key":
        return {str(server.get("api_key_header") or "X-API-Key"): credential}
    raise HTTPException(status_code=503, detail="Unsupported MCP authentication type")


def _denied_mcp_response(request_id: Any) -> JSONResponse:
    return JSONResponse({
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": "MCP tool execution was denied by the user."}],
            "isError": True,
        },
    })


@app.api_route("/internal/mcp/{server_slug}", methods=["GET", "POST", "DELETE"])
async def proxy_mcp_request(server_slug: str, request: Request):
    run_token = request.headers.get("x-agentsaas-mcp-run", "")
    run = _mcp_proxy_runs.get(run_token)
    server = (run or {}).get("servers", {}).get(server_slug)
    if run is None or server is None:
        raise HTTPException(status_code=404, detail="MCP run proxy is unavailable")
    body = await request.body()
    if len(body) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="MCP request is too large")

    if request.method == "POST" and body:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid MCP JSON-RPC request")
        messages = parsed if isinstance(parsed, list) else [parsed]
        approval_tools = set(server.get("approval_required_tools") or [])
        for message in messages:
            if not isinstance(message, dict) or message.get("method") != "tools/call":
                continue
            params = message.get("params") or {}
            tool_name = str(params.get("name") or "")
            if tool_name not in approval_tools:
                continue
            if not run.get("interactive") or not run.get("run_id"):
                return _denied_mcp_response(message.get("id"))
            approval_id = uuid4().hex
            future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            await run["approval_queue"].put({
                "approval_id": approval_id,
                "run_id": run["run_id"],
                "server": server_slug,
                "tool": tool_name,
                "description": f"Allow {server_slug}.{tool_name} to run once?",
                "future": future,
            })
            try:
                decision = await asyncio.wait_for(
                    asyncio.shield(future),
                    timeout=settings.mcp_approval_timeout_seconds,
                )
            except asyncio.TimeoutError:
                decision = "deny"
                if not future.done():
                    future.set_result(decision)
            if decision != "approve":
                return _denied_mcp_response(message.get("id"))

    forwarded_headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() in {"accept", "content-type", "mcp-session-id", "mcp-protocol-version", "last-event-id"}
    }
    forwarded_headers.update(_proxy_auth_headers(server))
    timeout = httpx.Timeout(
        connect=settings.mcp_connect_timeout_seconds,
        read=None,
        write=settings.mcp_tool_timeout_seconds,
        pool=settings.mcp_connect_timeout_seconds,
    )
    client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
    try:
        upstream_url = await validate_mcp_destination(str(server.get("url") or ""))
        upstream_request = client.build_request(
            request.method,
            upstream_url,
            headers=forwarded_headers,
            content=body,
        )
        upstream = await client.send(upstream_request, stream=True)
    except McpEndpointRejected:
        await client.aclose()
        raise HTTPException(status_code=502, detail="MCP upstream destination was rejected")
    except Exception:
        await client.aclose()
        raise HTTPException(status_code=502, detail="MCP upstream request failed")

    response_headers = {
        name: value
        for name, value in upstream.headers.items()
        if name.lower() in {"content-type", "mcp-session-id", "cache-control"}
    }

    async def response_body():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        response_body(),
        status_code=upstream.status_code,
        headers=response_headers,
    )


@app.get("/health")
async def health():
    binary = shutil.which("hermes")
    profiles_ready = HERMES_PROFILES_ROOT.exists() and os.access(HERMES_PROFILES_ROOT, os.R_OK)
    if not binary or not profiles_ready:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "runtime": "hermes-agent-cli",
                "binary": "available" if binary else "missing",
                "profiles": "readable" if profiles_ready else "unavailable",
            },
        )
    return {
        "status": "healthy",
        "runtime": "hermes-agent-cli",
        "binary": "available",
        "profiles": "readable",
    }


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug or "default"


def _profile_home(payload: dict[str, Any]) -> Path:
    profile = payload.get("profile") or {}
    slug = _slugify(profile.get("slug") or profile.get("hermes_profile_id") or "default")
    profile_home = HERMES_PROFILES_ROOT / slug
    profile_home.mkdir(parents=True, exist_ok=True)
    return profile_home


def _profile_skill_names(profile_home: Path) -> list[str]:
    skills_dir = profile_home / "skills"
    if not skills_dir.exists():
        return []
    return sorted(entry.name for entry in skills_dir.iterdir() if entry.is_dir() and (entry / "SKILL.md").exists())


def _mock_runtime_response(payload: dict[str, Any]) -> str:
    profile = payload.get("profile") or {}
    employee = payload.get("employee") or {}
    profile_name = profile.get("name") or profile.get("slug") or "default"
    employee_name = employee.get("full_name") or employee.get("email") or "employee"
    user_message = (payload.get("message") or "").strip()
    if not user_message:
        content = f"Mock agent ready for {employee_name} on profile {profile_name}."
    else:
        content = (
            f"Mock agent for {profile_name} received your request. "
            f"Employee: {employee_name}. "
            f"Summary: {user_message[:160]}"
        )
    cowork = payload.get("cowork") or {}
    if cowork.get("protocol") == "cowork_v1":
        return json.dumps({"type": "assistant_final", "content": content}, ensure_ascii=False)
    return content


def _provider_name(provider: str) -> str:
    if provider == "openai":
        return "custom"
    return provider


def _config_yaml(payload: dict[str, Any], profile_home: Path, runtime_workspace: Path) -> str:
    provider = payload.get("provider") or "custom"
    model = payload.get("model") or DEFAULT_MODEL
    provider_name = _provider_name(provider)
    provider_base_url = str(payload.get("provider_base_url") or "").strip()
    mcp_servers = payload.get("mcp_servers") or []
    lines = [
        "model:",
        f"  provider: {provider_name}",
        f"  default: {json.dumps(model)}",
    ]
    if provider_name == "custom" and (provider_base_url or OPENAI_COMPAT_BASE_URL):
        base_url = provider_base_url or OPENAI_COMPAT_BASE_URL
        lines.append(f"  base_url: {json.dumps(base_url.rsplit('/chat/completions', 1)[0])}")
        lines.append("  api_key: ${OPENAI_API_KEY}")
    elif provider_name == "minimax" and (provider_base_url or MINIMAX_BASE_URL):
        lines.append(f"  base_url: {json.dumps(provider_base_url or MINIMAX_BASE_URL)}")
    elif provider_name == "ollama" and OLLAMA_BASE_URL:
        lines.append(f"  base_url: {json.dumps(OLLAMA_BASE_URL)}")
    lines.append(f"mcp_discovery_timeout: {float(settings.mcp_connect_timeout_seconds) + 2.0}")
    configured_toolsets = normalize_runtime_toolsets(
        (payload.get("profile") or {}).get("runtime_toolsets", list(SAFE_RUNTIME_TOOLSETS))
    )
    platform_toolsets = configured_toolsets + [
        str(server.get("slug") or "").strip()
        for server in mcp_servers
        if str(server.get("slug") or "").strip()
    ]
    disabled_toolsets = sorted(ALL_RUNTIME_TOOLSETS - set(configured_toolsets))
    lines.append("platform_toolsets:")
    if platform_toolsets:
        lines.append("  cli:")
        lines.extend(f"    - {item}" for item in platform_toolsets)
    else:
        lines.append("  cli: []")
    lines.extend(["agent:", "  disabled_toolsets:"])
    lines.extend(f"    - {item}" for item in disabled_toolsets)
    if mcp_servers:
        lines.append("mcp_servers:")
        for server in mcp_servers:
            slug = str(server.get("slug") or "").strip()
            url = str(server.get("url") or "").strip()
            allowed_tools = [str(item).strip() for item in (server.get("allowed_tools") or []) if str(item).strip()]
            if not slug or not url or not allowed_tools:
                raise ValueError("Invalid MCP runtime configuration")
            lines.extend([
                f"  {json.dumps(slug)}:",
                f"    url: {json.dumps(url)}",
                f"    timeout: {float(settings.mcp_tool_timeout_seconds)}",
                f"    connect_timeout: {float(settings.mcp_connect_timeout_seconds)}",
            ])
            credential_env = str(server.get("credential_env") or "").strip()
            auth_type = str(server.get("auth_type") or "none")
            if auth_type != "none":
                if not credential_env:
                    raise ValueError("Invalid MCP credential configuration")
                header_name = "Authorization" if auth_type in {"bearer", "oauth"} else str(server.get("api_key_header") or "X-API-Key")
                header_value = f"Bearer ${{{credential_env}}}" if auth_type in {"bearer", "oauth"} else f"${{{credential_env}}}"
                lines.extend([
                    "    headers:",
                    f"      {json.dumps(header_name)}: {json.dumps(header_value)}",
                ])
            proxy_token = str(server.get("proxy_token") or "")
            if proxy_token:
                lines.extend([
                    "    headers:",
                    f"      \"X-AgentSaaS-MCP-Run\": {json.dumps(proxy_token)}",
                ])
            lines.extend([
                "    tools:",
                "      include:",
            ])
            lines.extend(f"        - {json.dumps(item)}" for item in allowed_tools)
            lines.extend([
                "      prompts: false",
                "      resources: false",
                "    sampling:",
                "      enabled: false",
                "    supports_parallel_tool_calls: false",
            ])
    return "\n".join(lines) + "\n"


def _runtime_env(payload: dict[str, Any], profile_home: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {
            "PATH",
            "LANG",
            "LC_ALL",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
        }
    }
    env["HOME"] = str(profile_home)
    env["HERMES_HOME"] = str(profile_home)
    configured_toolsets = normalize_runtime_toolsets(
        (payload.get("profile") or {}).get("runtime_toolsets", list(SAFE_RUNTIME_TOOLSETS))
    )
    mcp_toolsets = [
        str(server.get("slug") or "").strip()
        for server in payload.get("mcp_servers") or []
        if str(server.get("slug") or "").strip()
    ]
    env["HERMES_TUI_TOOLSETS"] = ",".join(configured_toolsets + mcp_toolsets)
    api_key = payload.get("api_key") or ""
    provider = payload.get("provider") or ""
    if provider == "openai":
        if OPENAI_COMPAT_BASE_URL:
            env["OPENAI_BASE_URL"] = OPENAI_COMPAT_BASE_URL
        if api_key:
            env["OPENAI_API_KEY"] = api_key
    elif provider == "minimax":
        if MINIMAX_BASE_URL:
            env["MINIMAX_BASE_URL"] = MINIMAX_BASE_URL
        if api_key:
            env["MINIMAX_API_KEY"] = api_key
    elif provider == "ollama" and OLLAMA_BASE_URL:
        env["OLLAMA_BASE_URL"] = OLLAMA_BASE_URL
    for server in payload.get("mcp_servers") or []:
        credential_env = str(server.get("credential_env") or "").strip()
        credential = str(server.get("credential") or "")
        if credential_env and credential:
            env[credential_env] = credential
    return env


def _upstream_target(payload: dict[str, Any]) -> str:
    provider = (payload.get("provider") or "").strip().lower()
    if provider == "openai":
        return OPENAI_COMPAT_BASE_URL or "openai-compatible"
    if provider == "minimax":
        return MINIMAX_BASE_URL or "https://api.minimax.io/v1/chat/completions"
    if provider == "ollama":
        return OLLAMA_BASE_URL or "ollama"
    return provider or "unknown"


def _stage_runtime_profile(source_profile_home: Path, runtime_profile_home: Path) -> Path:
    runtime_profile_home.mkdir(parents=True, exist_ok=True)
    runtime_workspace = runtime_profile_home / "workspace"
    runtime_workspace.mkdir(parents=True, exist_ok=True)

    for name in ("SOUL.md", "system_prompt.md", "profile.json"):
        source = source_profile_home / name
        if source.exists():
            shutil.copy2(source, runtime_profile_home / name)

    source_skills = source_profile_home / "skills"
    if source_skills.exists():
        shutil.copytree(source_skills, runtime_profile_home / "skills", dirs_exist_ok=True)

    source_agents = source_profile_home / "workspace" / "AGENTS.md"
    if source_agents.exists():
        shutil.copy2(source_agents, runtime_workspace / "AGENTS.md")

    return runtime_workspace


def _stage_attachments(payload: dict[str, Any], runtime_workspace: Path) -> list[str]:
    attachments = normalize_image_attachments(payload.get("attachments") or [])
    if not attachments:
        return []
    attachment_dir = runtime_workspace / ".attachments"
    attachment_dir.mkdir(parents=True, exist_ok=True)
    extensions = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
    }
    paths: list[str] = []
    for index, item in enumerate(attachments, start=1):
        target = attachment_dir / f"attachment-{index}{extensions[item['mime_type']]}"
        target.write_bytes(base64.b64decode(item["data_url"].split(",", 1)[1], validate=True))
        paths.append(str(target))
    return paths


def _build_prompt(payload: dict[str, Any]) -> str:
    profile_home = _profile_home(payload)
    employee = payload.get("employee") or {}
    user_request = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    parts = [
        "Conversation continuity rule:",
        "Use the conversation history below to resolve short follow-up replies such as Arabic yes/no/continue confirmations, English yes/no/continue, or do it.",
        "If the latest message is a short confirmation, treat it as an answer to the immediately preceding assistant question in the same session.",
        "Do not restart the conversation or introduce yourself again when history is available.",
        "Primary user request (verbatim; may be Arabic or English):",
        user_request or "[empty request]",
        "Interpret the user request literally.",
        "Do not claim encoding or readability problems unless the user request itself visibly contains broken replacement characters such as �.",
        f"Employee: {employee.get('full_name') or employee.get('email') or 'Unknown'}",
        f"Employee email: {employee.get('email') or 'Unknown'}",
    ]
    if history:
        safe_history = []
        for item in history[-20:]:
            role = str(item.get("role") or "").strip()
            content = str(item.get("content") or "").strip()
            if role in {"user", "assistant", "system"} and content:
                safe_history.append({"role": role, "content": content[:4000]})
        if safe_history:
            parts.append(
                "Conversation history before the latest user request:\n"
                f"{json.dumps(safe_history, ensure_ascii=False, indent=2)}"
            )
    system_prompt_path = profile_home / "system_prompt.md"
    if system_prompt_path.exists():
        system_prompt = system_prompt_path.read_text(encoding="utf-8", errors="ignore").strip()
        if system_prompt:
            parts.append(f"Profile system instructions:\n{system_prompt}")
    if employee.get("department"):
        parts.append(f"Department: {employee['department']}")
    if payload.get("project_context"):
        parts.append(f"Project context:\n{payload['project_context']}")
    attachment_paths = payload.get("runtime_attachment_paths") or []
    if attachment_paths:
        parts.append(
            "Image attachments for the latest request:\n"
            + "\n".join(f"- {path}" for path in attachment_paths)
            + "\nInspect these image files when answering. Do not ignore them."
        )
    cowork = payload.get("cowork") or {}
    workspace = payload.get("workspace") or {}
    if workspace.get("root_name"):
        workspace_lines = [
            f"Desktop active project root: {workspace['root_name']}",
            "Treat that desktop project as the employee's current project reference.",
            "Do not inspect or describe Hermes runtime folders, profile folders, or internal working directories as if they were the employee's project.",
        ]
        if workspace.get("root_path"):
            workspace_lines.insert(1, f"Desktop active project path: {workspace['root_path']}")
        parts.append("\n".join(workspace_lines))
    else:
        parts.append(
            "\n".join(
                [
                    "No desktop project is currently attached to this request.",
                    "Do not create or save files into Hermes runtime folders for the employee.",
                    "Do not claim that you saved a file locally when no desktop project is attached.",
                    "If the employee asks for a new file or document without an attached desktop project, return the deliverable inline with a clear filename so the desktop client can present it in the conversation.",
                ]
            )
        )
    if cowork.get("protocol") == "cowork_v1":
        parts.append(_cowork_protocol_block(workspace, cowork))
    return "\n\n".join(parts)


def _log_runtime_prompt(payload: dict[str, Any], prompt: str) -> None:
    profile = payload.get("profile") or {}
    employee = payload.get("employee") or {}
    cowork = payload.get("cowork") or {}
    workspace = payload.get("workspace") or {}
    print(
        json.dumps(
            {
                "debug_event": "runtime_prompt",
                "profile_slug": profile.get("slug"),
                "profile_name": profile.get("name"),
                "employee_id": employee.get("id"),
                "provider": payload.get("provider"),
                "model": payload.get("model"),
                "cowork_protocol": cowork.get("protocol"),
                "workspace_root": workspace.get("root_name"),
                "message_length": len(str(payload.get("message") or "")),
                "project_context_length": len(str(payload.get("project_context") or "")),
                "prompt_length": len(prompt),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def _cowork_protocol_block(workspace: dict[str, Any], cowork: dict[str, Any]) -> str:
    transcript = cowork.get("transcript") or []
    transcript_lines = []
    for item in transcript[-12:]:
        item_type = item.get("type", "event")
        if item_type == "tool_request":
            transcript_lines.append(
                f"- tool_request {item.get('tool')}: {json.dumps(item.get('args') or {}, ensure_ascii=False)}"
            )
        elif item_type in {"tool_result", "apply_result"}:
            transcript_lines.append(
                f"- {item_type} ok={item.get('ok')}: {json.dumps(item.get('result') or item.get('error') or {}, ensure_ascii=False)}"
            )
        else:
            transcript_lines.append(f"- {item_type}: {json.dumps(item, ensure_ascii=False)}")

    selected_files = workspace.get("selected_files") or []
    root_name = workspace.get("root_name") or "workspace"
    root_path = workspace.get("root_path") or ""
    file_paths = workspace.get("file_paths") or []
    return "\n".join(
        [
            "Cowork protocol mode is enabled.",
            "You must reply with exactly one JSON object and no markdown fences.",
            'Allowed response types: {"type":"assistant_final","content":"..."}, {"type":"tool_request","tool":"list_files|search_files|read_file|read_multiple_files","args":{...}}, {"type":"apply_request","summary":"...","changes":[...]}',
            "The employee's latest message is authoritative and may be Arabic or English.",
            "Do not say the employee message has encoding, garbling, or readability issues unless you literally see broken replacement characters such as � or obvious mojibake inside the employee message itself.",
            "If the employee asks a general question about the open project, your role, or what help you can provide, answer directly with assistant_final instead of inventing an encoding problem.",
            "The desktop app, not your own runtime filesystem, is the authority for project files.",
            "Never say the workspace path is inaccessible, unavailable, on WSL, or that the user must apply edits manually.",
            "If the employee asks to create, edit, append, rewrite, rename, or delete a file in the open desktop project, you must respond with apply_request.",
            "If you need file contents or filenames before editing, respond with tool_request first, then continue with apply_request.",
            "Do not answer a file-edit request with assistant_final unless the user explicitly asked for explanation only and no file change.",
            "For apply_request, each change must use one of these shapes:",
            '{"action":"update","path":"relative/path","content":"full new file content"}',
            '{"action":"create","path":"relative/path","content":"full file content"}',
            '{"action":"rename","path":"old/path","new_path":"new/path"}',
            '{"action":"delete","path":"relative/path"}',
            "Do not ask for arbitrary shell commands.",
            "Do not write files directly inside your own runtime working directory.",
            "Never treat Hermes profile directories or the runtime working directory as the employee's project.",
            f"Workspace root name: {root_name}",
            f"Workspace root path: {root_path}" if root_path else "Workspace root path: unavailable",
            f"Selected files: {json.dumps(selected_files, ensure_ascii=False)}",
            f"Visible desktop file snapshot: {json.dumps(file_paths, ensure_ascii=False)}",
            "If the employee asks what files or folders exist in the open desktop project, do not answer from Hermes runtime folders.",
            "Use the desktop workspace snapshot above if it already answers the question exactly; otherwise emit a tool_request for list_files before answering.",
            "Prior cowork events:",
            "\n".join(transcript_lines) if transcript_lines else "- none",
        ]
    )


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def _workspace_generated_files(runtime_workspace: Path) -> list[Path]:
    generated: list[Path] = []
    for path in runtime_workspace.rglob("*"):
        if not path.is_file():
            continue
        if path.name == "AGENTS.md":
            continue
        generated.append(path)
    return sorted(generated)


def _render_inline_artifact_response(runtime_workspace: Path, generated_files: list[Path], fallback_text: str) -> str:
    if not generated_files:
        return fallback_text

    rendered_parts: list[str] = []
    for file_path in generated_files[:5]:
        relative_name = file_path.relative_to(runtime_workspace).as_posix()
        suffix = file_path.suffix.lower()
        if suffix in INLINE_TEXT_EXTENSIONS:
            try:
                content = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = None
            if content is not None:
                rendered_parts.append(
                    f"Filename: {relative_name}\n\n```{suffix.lstrip('.') or 'txt'}\n{content}\n```"
                )
                continue
        rendered_parts.append(f"Filename: {relative_name}")

    return "\n\n".join(rendered_parts)


def _sanitize_internal_paths(text: str) -> str:
    sanitized = re.sub(r"/tmp/hermes-run-[^\s`]+", "[ephemeral-runtime-file]", text)
    sanitized = re.sub(r"/data/hermes/profiles/[^\s`]+", "[internal-runtime-path]", sanitized)
    return sanitized


def _extract_response_text(stdout: str) -> str:
    cleaned = _strip_ansi(stdout or "").replace("\r", "")
    lines = [line for line in cleaned.splitlines()]
    prefixes = (
        "Detected:",
        "Checking Node.js",
        "Node.js not found",
        "Could not find Node.js",
        "Install manually:",
        "✓ Detected:",
        "→ Checking Node.js",
        "→ Node.js not found",
        "→ Install manually:",
        "⚠ Could not find Node.js",
    )
    while lines and (not lines[0].strip() or lines[0].strip().startswith(prefixes)):
        lines.pop(0)
    return "\n".join(lines).strip()


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", cleaned, flags=re.IGNORECASE)
    candidates = fenced + [cleaned]
    decoder = json.JSONDecoder()

    for candidate in candidates:
        candidate = candidate.strip()
        for start in range(len(candidate)):
            if candidate[start] != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(candidate[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return None


def _is_safe_relative_workspace_path(value: Any) -> bool:
    path_value = str(value or "").strip().replace("\\", "/")
    if not path_value:
        return False
    if path_value.startswith(("/", "../")) or path_value == "..":
        return False
    if re.match(r"^[A-Za-z]:/", path_value):
        return False
    parts = [part for part in path_value.split("/") if part not in {"", "."}]
    return all(part != ".." for part in parts)


def _normalize_tool_request_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(parsed.get("tool") or "").strip()
    args = parsed.get("args") or {}
    if not isinstance(args, dict):
        args = {}

    normalized_args: dict[str, Any] = {}
    if tool_name == "list_files":
        normalized_args["query"] = str(args.get("query") or "")[:500]
        normalized_args["limit"] = min(max(int(args.get("limit") or 50), 1), 200)
    elif tool_name == "search_files":
        normalized_args["query"] = str(args.get("query") or "")[:500]
        normalized_args["limit"] = min(max(int(args.get("limit") or 20), 1), 100)
    elif tool_name == "read_file":
        candidate_path = args.get("path")
        if not _is_safe_relative_workspace_path(candidate_path):
            raise ValueError("Invalid read_file path")
        normalized_args["path"] = str(candidate_path)
    elif tool_name == "read_multiple_files":
        paths = args.get("paths") or []
        if not isinstance(paths, list):
            raise ValueError("Invalid read_multiple_files paths")
        safe_paths = []
        for path_value in paths[:20]:
            if not _is_safe_relative_workspace_path(path_value):
                raise ValueError("Invalid read_multiple_files path")
            safe_paths.append(str(path_value))
        normalized_args["paths"] = safe_paths
    else:
        raise ValueError(f"Unsupported cowork tool: {tool_name}")

    return {
        "type": "tool_request",
        "request_id": parsed.get("request_id") or str(uuid4()),
        "tool": tool_name,
        "args": normalized_args,
    }


def _normalize_apply_request_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    normalized_changes: list[dict[str, Any]] = []
    for raw_change in (parsed.get("changes") or [])[:50]:
        if not isinstance(raw_change, dict):
            raise ValueError("Invalid apply_request change entry")
        action = str(raw_change.get("action") or "update").strip()
        if action not in {"update", "create", "rename", "delete"}:
            raise ValueError(f"Unsupported apply_request action: {action}")
        if not _is_safe_relative_workspace_path(raw_change.get("path")):
            raise ValueError("Invalid apply_request path")
        change: dict[str, Any] = {
            "action": action,
            "path": str(raw_change.get("path")),
        }
        if action == "rename":
            if not _is_safe_relative_workspace_path(raw_change.get("new_path")):
                raise ValueError("Invalid apply_request rename target")
            change["new_path"] = str(raw_change.get("new_path"))
        elif action in {"update", "create"}:
            change["content"] = str(raw_change.get("content") or "")
        normalized_changes.append(change)

    return {
        "type": "apply_request",
        "request_id": parsed.get("request_id") or str(uuid4()),
        "mode": parsed.get("mode") or "workspace_changes",
        "summary": parsed.get("summary") or "Apply requested workspace changes",
        "changes": normalized_changes,
    }


def _normalize_cowork_response(raw_text: str) -> dict[str, Any]:
    parsed = _extract_first_json_object(raw_text)
    if not parsed:
        return {"type": "assistant_final", "content": raw_text.strip()}

    event_type = parsed.get("type")
    try:
        if event_type == "tool_request":
            return _normalize_tool_request_payload(parsed)
        if event_type == "apply_request":
            return _normalize_apply_request_payload(parsed)
    except (TypeError, ValueError):
        return {
            "type": "assistant_final",
            "content": "Unable to continue because the agent returned an invalid workspace operation payload.",
        }
    content = parsed.get("content")
    if isinstance(content, str) and content.strip():
        return {"type": "assistant_final", "content": content.strip()}
    return {"type": "assistant_final", "content": raw_text.strip()}


async def _run_hermes(payload: dict[str, Any]) -> str:
    result = await _run_hermes_result(payload)
    return result["content"]


async def _run_hermes_result(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"content": "", "usage": {}}
    async for event in _run_hermes_server_events(payload):
        if event.get("type") == "complete":
            result = {
                "content": event.get("content", ""),
                "usage": event.get("usage") or {},
            }
    return result


async def _drain_process_stream(stream, sink: list[str]) -> None:
    if stream is None:
        return
    while True:
        line = await stream.readline()
        if not line:
            return
        sink.append(line.decode("utf-8", errors="replace"))
        if sum(len(item) for item in sink) > 32768:
            del sink[: len(sink) // 2]


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        await asyncio.wait_for(process.wait(), timeout=5)
    except (ProcessLookupError, asyncio.TimeoutError):
        if process.returncode is None:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            await process.wait()


async def _server_ready_port(process: asyncio.subprocess.Process) -> int:
    async def read_until_ready() -> int:
        while True:
            line = await process.stdout.readline()
            if not line:
                raise RuntimeError("Hermes Server exited before becoming ready")
            match = re.search(r"HERMES_BACKEND_READY\s+port=(\d+)", line.decode("utf-8", errors="replace"))
            if match:
                return int(match.group(1))

    return await asyncio.wait_for(
        read_until_ready(),
        timeout=float(os.getenv("HERMES_SERVER_START_TIMEOUT_SECONDS", "20")),
    )


def _normalized_server_usage(usage: dict[str, Any] | None) -> dict[str, int]:
    values = usage or {}
    input_tokens = int(values.get("input_tokens") or values.get("input") or 0)
    output_tokens = int(values.get("output_tokens") or values.get("output") or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


async def _run_hermes_server_events(payload: dict[str, Any]):
    if (payload.get("provider") or "").strip().lower() == "mock":
        content = _mock_runtime_response(payload)
        yield {"type": "delta", "content": content}
        yield {
            "type": "complete",
            "content": content,
            "usage": {
                "input_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 4),
                "output_tokens": max(1, len(content) // 4),
            },
        }
        return

    source_profile_home = _profile_home(payload)
    with tempfile.TemporaryDirectory(prefix="hermes-run-") as temp_root:
        runtime_profile_home = Path(temp_root) / "profile"
        runtime_workspace_path = _stage_runtime_profile(source_profile_home, runtime_profile_home)
        runtime_payload = {
            **payload,
            "runtime_attachment_paths": _stage_attachments(payload, runtime_workspace_path),
        }
        runtime_payload, mcp_proxy_token = _register_mcp_proxy(runtime_payload)
        (runtime_profile_home / "config.yaml").write_text(
            _config_yaml(runtime_payload, runtime_profile_home, runtime_workspace_path),
            encoding="utf-8",
        )
        prompt = _build_prompt(runtime_payload)
        _log_runtime_prompt(runtime_payload, prompt)
        server_token = uuid4().hex
        server_env = _runtime_env(runtime_payload, runtime_profile_home)
        server_env["HERMES_DASHBOARD_SESSION_TOKEN"] = server_token
        try:
            process = await asyncio.create_subprocess_exec(
                "hermes",
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                "0",
                "--skip-build",
                cwd=runtime_workspace_path,
                env=server_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
        except BaseException:
            if mcp_proxy_token:
                _mcp_proxy_runs.pop(mcp_proxy_token, None)
            raise
        stderr_lines: list[str] = []
        stderr_task = asyncio.create_task(_drain_process_stream(process.stderr, stderr_lines))
        stdout_task = None
        gateway_message_task = None
        try:
            port = await _server_ready_port(process)
            stdout_lines: list[str] = []
            stdout_task = asyncio.create_task(_drain_process_stream(process.stdout, stdout_lines))
            uri = f"ws://127.0.0.1:{port}/api/ws?token={server_token}"
            async with websockets.connect(
                uri,
                open_timeout=10,
                close_timeout=2,
                max_size=None,
                ping_interval=20,
            ) as websocket:
                create_id = uuid4().hex
                await websocket.send(json.dumps({
                    "jsonrpc": "2.0",
                    "id": create_id,
                    "method": "session.create",
                    "params": {
                        "cwd": str(runtime_workspace_path),
                        "source": "cli",
                        "title": "AgentSaaS runtime request",
                        "model": payload.get("model") or DEFAULT_MODEL,
                        "provider": _provider_name(payload.get("provider") or "custom"),
                        "close_on_disconnect": True,
                    },
                }))
                session_id = ""
                while not session_id:
                    message = json.loads(await websocket.recv())
                    if message.get("id") != create_id:
                        continue
                    if message.get("error"):
                        raise RuntimeError(message["error"].get("message") or "Hermes session creation failed")
                    session_id = str((message.get("result") or {}).get("session_id") or "")
                    if not session_id:
                        raise RuntimeError("Hermes Server did not return a session id")

                submit_id = uuid4().hex
                await websocket.send(json.dumps({
                    "jsonrpc": "2.0",
                    "id": submit_id,
                    "method": "prompt.submit",
                    "params": {"session_id": session_id, "text": prompt},
                }))
                complete_payload: dict[str, Any] | None = None
                pending_text = ""
                raw_streamed_text = ""
                tools_used: set[str] = set()
                mcp_servers_used: set[str] = set()
                deadline = (
                    asyncio.get_running_loop().time()
                    + float(os.getenv("HERMES_RUN_TIMEOUT_SECONDS", "120"))
                )
                proxy_queue = (_mcp_proxy_runs.get(mcp_proxy_token) or {}).get("approval_queue") if mcp_proxy_token else None
                gateway_message_task = asyncio.create_task(websocket.recv())
                while complete_payload is None:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError("Hermes Server run timed out")
                    proxy_task = asyncio.create_task(proxy_queue.get()) if proxy_queue is not None else None
                    waiters = {gateway_message_task}
                    if proxy_task is not None:
                        waiters.add(proxy_task)
                    done, _ = await asyncio.wait(
                        waiters,
                        timeout=remaining,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        if proxy_task is not None:
                            proxy_task.cancel()
                        raise asyncio.TimeoutError("Hermes Server run timed out")
                    if proxy_task is not None and proxy_task in done:
                        approval = proxy_task.result()
                        future = approval.pop("future")
                        key = (str(approval["run_id"]), str(approval["approval_id"]))
                        if not future.done():
                            deadline = max(
                                deadline,
                                asyncio.get_running_loop().time() + settings.mcp_approval_timeout_seconds + 5,
                            )
                            _pending_approvals[key] = future
                            future.add_done_callback(lambda _future, approval_key=key: _pending_approvals.pop(approval_key, None))
                            yield {
                                "type": "mcp_approval_required",
                                **approval,
                                "choices": ["approve", "deny"],
                            }
                        continue
                    if proxy_task is not None:
                        proxy_task.cancel()
                        await asyncio.gather(proxy_task, return_exceptions=True)
                    message = json.loads(gateway_message_task.result())
                    gateway_message_task = asyncio.create_task(websocket.recv())
                    if message.get("id") == submit_id:
                        if message.get("error"):
                            raise RuntimeError(message["error"].get("message") or "Hermes prompt failed")
                        continue
                    if message.get("method") != "event":
                        continue
                    params = message.get("params") or {}
                    if params.get("session_id") != session_id:
                        continue
                    event_type = params.get("type")
                    event_payload = params.get("payload") or {}
                    if event_type == "approval.request":
                        await websocket.send(json.dumps({
                            "jsonrpc": "2.0",
                            "id": uuid4().hex,
                            "method": "approval.respond",
                            "params": {
                                "session_id": session_id,
                                "choice": "deny",
                                "all": True,
                            },
                        }))
                    elif event_type == "tool.start":
                        tool_name = str(event_payload.get("name") or "")
                        if tool_name:
                            tools_used.add(tool_name)
                        identity = _mcp_tool_identity(tool_name, payload.get("mcp_servers") or [])
                        if identity:
                            mcp_servers_used.add(identity[0])
                            yield {
                                "type": "mcp_tool_started",
                                "run_id": str(payload.get("run_id") or ""),
                                "call_id": str(event_payload.get("tool_id") or ""),
                                "server": identity[0],
                                "tool": identity[1],
                            }
                    elif event_type == "tool.complete":
                        tool_name = str(event_payload.get("name") or "")
                        if tool_name:
                            tools_used.add(tool_name)
                        identity = _mcp_tool_identity(tool_name, payload.get("mcp_servers") or [])
                        if identity:
                            mcp_servers_used.add(identity[0])
                            result = event_payload.get("result")
                            failed = isinstance(result, dict) and bool(result.get("isError") or result.get("error"))
                            yield {
                                "type": "mcp_tool_failed" if failed else "mcp_tool_completed",
                                "run_id": str(payload.get("run_id") or ""),
                                "call_id": str(event_payload.get("tool_id") or ""),
                                "server": identity[0],
                                "tool": identity[1],
                                "duration_ms": int(float(event_payload.get("duration_s") or 0) * 1000),
                                "summary": str(event_payload.get("summary") or "")[:1000],
                            }
                    elif event_type == "message.delta":
                        delta = str(event_payload.get("text") or "")
                        raw_streamed_text += delta
                        pending_text += delta
                        whitespace = max(pending_text.rfind(" "), pending_text.rfind("\n"), pending_text.rfind("\t"))
                        if whitespace >= 0:
                            safe_chunk = _sanitize_internal_paths(pending_text[: whitespace + 1])
                            pending_text = pending_text[whitespace + 1 :]
                            if safe_chunk:
                                yield {"type": "delta", "content": safe_chunk}
                    elif event_type == "error":
                        raise RuntimeError(str(event_payload.get("message") or "Hermes Server runtime failure"))
                    elif event_type == "message.complete":
                        complete_payload = event_payload

                raw_text = str(complete_payload.get("text") or "")
                if pending_text:
                    safe_chunk = _sanitize_internal_paths(pending_text)
                    if safe_chunk:
                        yield {"type": "delta", "content": safe_chunk}
                elif not raw_streamed_text and raw_text:
                    yield {"type": "delta", "content": _sanitize_internal_paths(raw_text)}
                if complete_payload.get("status") == "error":
                    raise RuntimeError(raw_text or "Hermes Server returned an error")

                safe_text = _sanitize_internal_paths(raw_text)
                workspace = payload.get("workspace") or {}
                if not workspace.get("root_name") and not (workspace.get("selected_files") or []):
                    safe_text = _render_inline_artifact_response(
                        runtime_workspace_path,
                        _workspace_generated_files(runtime_workspace_path),
                        safe_text,
                    )
                yield {
                    "type": "complete",
                    "content": safe_text,
                    "usage": _normalized_server_usage(complete_payload.get("usage")),
                    "tools_used": sorted(tools_used),
                    "mcp_servers_used": sorted(mcp_servers_used),
                }
        except BaseException as exc:
            if isinstance(exc, (asyncio.CancelledError, GeneratorExit)):
                raise
            details = "".join(stderr_lines).strip()
            raise RuntimeError(details or str(exc)) from exc
        finally:
            if mcp_proxy_token:
                _mcp_proxy_runs.pop(mcp_proxy_token, None)
            await _stop_process(process)
            for task in (gateway_message_task, stdout_task, stderr_task):
                if task is not None:
                    task.cancel()
            await asyncio.gather(
                *(task for task in (gateway_message_task, stdout_task, stderr_task) if task is not None),
                return_exceptions=True,
            )


@app.post("/runs")
async def run_agent(
    payload: dict[str, Any],
    x_hermes_runtime_secret: str | None = Header(default=None),
):
    _authorize_runtime(x_hermes_runtime_secret)
    runtime_result = await _run_hermes_result({**payload, "interactive_approvals": False})
    content = runtime_result["content"]
    usage = runtime_result.get("usage") or {
        "input_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 4),
        "output_tokens": max(1, len(content) // 4),
    }
    cowork = payload.get("cowork") or {}
    if cowork.get("protocol") == "cowork_v1":
        normalized = _normalize_cowork_response(content)
        return {
            **normalized,
            "content": normalized.get("content", ""),
            "upstream_target": _upstream_target(payload),
            "tools_used": ["hermes-agent"],
            "mcp_servers_used": [],
            "total_cost": 0.0,
            "usage": usage,
        }
    return {
        "content": content,
        "upstream_target": _upstream_target(payload),
        "tools_used": ["hermes-agent"],
        "mcp_servers_used": [],
        "total_cost": 0.0,
        "usage": usage,
    }


@app.post("/runs/stream")
async def run_agent_stream(
    payload: dict[str, Any],
    x_hermes_runtime_secret: str | None = Header(default=None),
):
    _authorize_runtime(x_hermes_runtime_secret)
    payload = {**payload, "interactive_approvals": True}
    cowork = payload.get("cowork") or {}

    async def events():
        yield f"data: {json.dumps({'type': 'start'}, ensure_ascii=False)}\n\n"
        if cowork.get("protocol") == "cowork_v1":
            content = await _run_hermes(payload)
            normalized = _normalize_cowork_response(content)
            if normalized.get("type") != "assistant_final":
                yield f"data: {json.dumps(normalized, ensure_ascii=False)}\n\n"
                return
            chunk_content = normalized.get("content", "")
            if chunk_content:
                yield f"data: {json.dumps({'type': 'assistant_chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"
            usage = {
                "input_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 4),
                "output_tokens": max(1, len(content) // 4),
            }
        else:
            content = ""
            usage = {}
            tools_used: list[str] = []
            mcp_servers_used: list[str] = []
            async for event in _run_hermes_server_events(payload):
                if event.get("type") == "delta":
                    chunk_content = event.get("content", "")
                    content += chunk_content
                    if chunk_content:
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"
                elif event.get("type") == "complete":
                    usage = event.get("usage") or {}
                    tools_used = event.get("tools_used") or []
                    mcp_servers_used = event.get("mcp_servers_used") or []
                else:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        done = {
            "type": "done",
            "content": "",
            "upstream_target": _upstream_target(payload),
            "tools_used": ["hermes-agent", *tools_used] if not cowork.get("protocol") == "cowork_v1" else ["hermes-agent"],
            "mcp_servers_used": mcp_servers_used if not cowork.get("protocol") == "cowork_v1" else [],
            "total_cost": 0.0,
            "usage": usage or {
                "input_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 4),
                "output_tokens": max(1, len(content) // 4),
            },
        }
        yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/approvals")
async def respond_approval(
    payload: dict[str, Any],
    x_hermes_runtime_secret: str | None = Header(default=None),
):
    _authorize_runtime(x_hermes_runtime_secret)
    run_id = str(payload.get("run_id") or "").strip()
    approval_id = str(payload.get("approval_id") or "").strip()
    decision = str(payload.get("decision") or "").strip()
    if decision not in {"approve", "deny"}:
        raise HTTPException(status_code=400, detail="Invalid approval decision")
    future = _pending_approvals.get((run_id, approval_id))
    if future is None or future.done():
        raise HTTPException(status_code=404, detail="MCP approval is no longer pending")
    future.set_result(decision)
    return {"status": "accepted", "decision": decision}
