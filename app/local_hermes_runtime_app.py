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
import signal
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
import websockets
from app.core.runtime_policy import RUNTIME_TOOLSETS, SAFE_RUNTIME_TOOLSETS, normalize_runtime_toolsets
from app.services.attachments import normalize_image_attachments


HERMES_PROFILES_ROOT = Path(os.getenv("HERMES_PROFILES_ROOT", "/data/hermes/profiles"))
OPENAI_COMPAT_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen3-14b")
INLINE_TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".css",
    ".js", ".ts", ".py", ".sql", ".toml", ".ini", ".cfg", ".conf",
}

app = FastAPI(title="AgentSaaS Agent Runtime", version="0.2.0")


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
    lines = [
        "model:",
        f"  provider: {provider_name}",
        f"  default: {json.dumps(model)}",
    ]
    if provider_name == "custom" and OPENAI_COMPAT_BASE_URL:
        lines.append(f"  base_url: {json.dumps(OPENAI_COMPAT_BASE_URL.rsplit('/chat/completions', 1)[0])}")
        lines.append("  api_key: ${OPENAI_API_KEY}")
    elif provider_name == "minimax" and MINIMAX_BASE_URL:
        lines.append(f"  base_url: {json.dumps(MINIMAX_BASE_URL)}")
    elif provider_name == "ollama" and OLLAMA_BASE_URL:
        lines.append(f"  base_url: {json.dumps(OLLAMA_BASE_URL)}")
    lines.extend(
        [
            "terminal:",
            "  backend: local",
            f"  cwd: {json.dumps(str(runtime_workspace))}",
        ]
    )
    configured_toolsets = normalize_runtime_toolsets(
        (payload.get("profile") or {}).get("runtime_toolsets", list(SAFE_RUNTIME_TOOLSETS))
    )
    disabled_toolsets = sorted(RUNTIME_TOOLSETS - set(configured_toolsets))
    lines.append("platform_toolsets:")
    if configured_toolsets:
        lines.append("  cli:")
        lines.extend(f"    - {item}" for item in configured_toolsets)
    else:
        lines.append("  cli: []")
    lines.extend(["agent:", "  disabled_toolsets:"])
    lines.extend(f"    - {item}" for item in disabled_toolsets)
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
        (runtime_profile_home / "config.yaml").write_text(
            _config_yaml(runtime_payload, runtime_profile_home, runtime_workspace_path),
            encoding="utf-8",
        )
        prompt = _build_prompt(runtime_payload)
        _log_runtime_prompt(runtime_payload, prompt)
        server_token = uuid4().hex
        server_env = _runtime_env(runtime_payload, runtime_profile_home)
        server_env["HERMES_DASHBOARD_SESSION_TOKEN"] = server_token
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
        stderr_lines: list[str] = []
        stderr_task = asyncio.create_task(_drain_process_stream(process.stderr, stderr_lines))
        stdout_task = None
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
                deadline = (
                    asyncio.get_running_loop().time()
                    + float(os.getenv("HERMES_RUN_TIMEOUT_SECONDS", "120"))
                )
                while complete_payload is None:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError("Hermes Server run timed out")
                    message = json.loads(
                        await asyncio.wait_for(
                            websocket.recv(),
                            timeout=remaining,
                        )
                    )
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
                }
        except BaseException as exc:
            if isinstance(exc, (asyncio.CancelledError, GeneratorExit)):
                raise
            details = "".join(stderr_lines).strip()
            raise RuntimeError(details or str(exc)) from exc
        finally:
            await _stop_process(process)
            for task in (stdout_task, stderr_task):
                if task is not None:
                    task.cancel()
            await asyncio.gather(
                *(task for task in (stdout_task, stderr_task) if task is not None),
                return_exceptions=True,
            )


@app.post("/runs")
async def run_agent(payload: dict[str, Any]):
    runtime_result = await _run_hermes_result(payload)
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
async def run_agent_stream(payload: dict[str, Any]):
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
            async for event in _run_hermes_server_events(payload):
                if event.get("type") == "delta":
                    chunk_content = event.get("content", "")
                    content += chunk_content
                    if chunk_content:
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"
                elif event.get("type") == "complete":
                    usage = event.get("usage") or {}
        done = {
            "type": "done",
            "content": "",
            "upstream_target": _upstream_target(payload),
            "tools_used": ["hermes-agent"],
            "mcp_servers_used": [],
            "total_cost": 0.0,
            "usage": usage or {
                "input_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 4),
                "output_tokens": max(1, len(content) // 4),
            },
        }
        yield f"data: {json.dumps(done, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
