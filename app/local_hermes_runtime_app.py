"""
Hermes CLI bridge runtime.

This service keeps the existing AgentSaaS HTTP contract while delegating each
run to a real hermes-agent profile stored under /data/hermes/profiles/<slug>.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import StreamingResponse


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
    return {"status": "healthy", "runtime": "hermes-agent-cli"}


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
    return "\n".join(lines) + "\n"


def _runtime_env(payload: dict[str, Any], profile_home: Path) -> dict[str, str]:
    env = os.environ.copy()
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


def _build_prompt(payload: dict[str, Any]) -> str:
    profile_home = _profile_home(payload)
    employee = payload.get("employee") or {}
    parts = [
        f"Employee: {employee.get('full_name') or employee.get('email') or 'Unknown'}",
        f"Employee email: {employee.get('email') or 'Unknown'}",
    ]
    system_prompt_path = profile_home / "system_prompt.md"
    if system_prompt_path.exists():
        system_prompt = system_prompt_path.read_text(encoding="utf-8", errors="ignore").strip()
        if system_prompt:
            parts.append(f"Profile system instructions:\n{system_prompt}")
    if employee.get("department"):
        parts.append(f"Department: {employee['department']}")
    if payload.get("project_context"):
        parts.append(f"Project context:\n{payload['project_context']}")
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
    parts.append(f"User request:\n{payload.get('message') or ''}")
    return "\n\n".join(parts)


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
    cleaned = _strip_ansi(stdout).replace("\r", "")
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


def _normalize_cowork_response(raw_text: str) -> dict[str, Any]:
    parsed = _extract_first_json_object(raw_text)
    if not parsed:
        return {"type": "assistant_final", "content": raw_text.strip()}

    event_type = parsed.get("type")
    if event_type == "tool_request":
        return {
            "type": "tool_request",
            "request_id": parsed.get("request_id") or str(uuid4()),
            "tool": parsed.get("tool") or "",
            "args": parsed.get("args") or {},
        }
    if event_type == "apply_request":
        return {
            "type": "apply_request",
            "request_id": parsed.get("request_id") or str(uuid4()),
            "mode": parsed.get("mode") or "workspace_changes",
            "summary": parsed.get("summary") or "Apply requested workspace changes",
            "changes": parsed.get("changes") or [],
        }
    content = parsed.get("content")
    if isinstance(content, str) and content.strip():
        return {"type": "assistant_final", "content": content.strip()}
    return {"type": "assistant_final", "content": raw_text.strip()}


def _run_hermes(payload: dict[str, Any]) -> str:
    source_profile_home = _profile_home(payload)
    with tempfile.TemporaryDirectory(prefix="hermes-run-") as temp_root:
        runtime_profile_home = Path(temp_root) / "profile"
        runtime_workspace_path = _stage_runtime_profile(source_profile_home, runtime_profile_home)
        (runtime_profile_home / "config.yaml").write_text(
            _config_yaml(payload, runtime_profile_home, runtime_workspace_path),
            encoding="utf-8",
        )
        env = _runtime_env(payload, runtime_profile_home)
        command = [
            "hermes",
            "-z",
            _build_prompt(payload),
            "--provider",
            _provider_name(payload.get("provider") or "custom"),
            "-m",
            payload.get("model") or DEFAULT_MODEL,
            "--yolo",
        ]
        for skill_name in _profile_skill_names(runtime_profile_home):
            command.extend(["--skills", skill_name])
        result = subprocess.run(
            command,
            cwd=runtime_workspace_path,
            env=env,
            text=True,
            capture_output=True,
            timeout=float(os.getenv("HERMES_RUN_TIMEOUT_SECONDS", "300")),
            check=False,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "Unknown agent runtime failure"
            raise RuntimeError(error)
        raw_text = _extract_response_text(result.stdout)
        safe_text = _sanitize_internal_paths(raw_text)
        workspace = payload.get("workspace") or {}
        if not workspace.get("root_name") and not (workspace.get("selected_files") or []):
            generated_files = _workspace_generated_files(runtime_workspace_path)
            return _render_inline_artifact_response(runtime_workspace_path, generated_files, safe_text)
        return safe_text


@app.post("/runs")
async def run_agent(payload: dict[str, Any]):
    content = _run_hermes(payload)
    cowork = payload.get("cowork") or {}
    if cowork.get("protocol") == "cowork_v1":
        normalized = _normalize_cowork_response(content)
        return {
            **normalized,
            "content": normalized.get("content", ""),
            "tools_used": ["hermes-agent"],
            "mcp_servers_used": [],
            "total_cost": 0.0,
            "usage": {
                "input_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 4),
                "output_tokens": max(1, len(content) // 4),
            },
        }
    return {
        "content": content,
        "tools_used": ["hermes-agent"],
        "mcp_servers_used": [],
        "total_cost": 0.0,
        "usage": {
            "input_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 4),
            "output_tokens": max(1, len(content) // 4),
        },
    }


@app.post("/runs/stream")
async def run_agent_stream(payload: dict[str, Any]):
    content = _run_hermes(payload)
    cowork = payload.get("cowork") or {}
    if cowork.get("protocol") == "cowork_v1":
        normalized = _normalize_cowork_response(content)
        chunks = [normalized]
        if normalized.get("type") == "assistant_final":
            chunks = [
                {"type": "assistant_chunk", "content": normalized.get("content", "")},
                {
                    "type": "done",
                    "content": "",
                    "tools_used": ["hermes-agent"],
                    "mcp_servers_used": [],
                    "total_cost": 0.0,
                    "usage": {
                        "input_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 4),
                        "output_tokens": max(1, len(content) // 4),
                    },
                },
            ]
        else:
            chunks = [normalized]

        async def cowork_events():
            for event in chunks:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return StreamingResponse(cowork_events(), media_type="text/event-stream")
    midpoint = max(1, len(content) // 2)
    chunks = [
        {"type": "chunk", "content": content[:midpoint]},
        {"type": "chunk", "content": content[midpoint:]},
        {
            "type": "done",
            "content": "",
            "tools_used": ["hermes-agent"],
            "mcp_servers_used": [],
            "total_cost": 0.0,
            "usage": {
                "input_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 4),
                "output_tokens": max(1, len(content) // 4),
            },
        },
    ]

    async def events():
        for event in chunks:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
