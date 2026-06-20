"""
Hermes CLI bridge runtime.

This service keeps the existing AgentSaaS HTTP contract while delegating each
run to a real hermes-agent profile stored under /data/hermes/profiles/<slug>.
"""
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse


HERMES_PROFILES_ROOT = Path(os.getenv("HERMES_PROFILES_ROOT", "/data/hermes/profiles"))
OPENAI_COMPAT_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "")

app = FastAPI(title="AgentSaaS Hermes Runtime", version="0.2.0")


@app.get("/health")
async def health():
    return {"status": "healthy", "runtime": "hermes-agent-cli"}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug or "default"


def _profile_paths(payload: dict[str, Any]) -> tuple[Path, Path]:
    profile = payload.get("profile") or {}
    slug = _slugify(profile.get("slug") or profile.get("hermes_profile_id") or "default")
    profile_home = HERMES_PROFILES_ROOT / slug
    workspace = profile_home / "workspace"
    profile_home.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    return profile_home, workspace


def _profile_skill_names(profile_home: Path) -> list[str]:
    skills_dir = profile_home / "skills"
    if not skills_dir.exists():
        return []
    return sorted(entry.name for entry in skills_dir.iterdir() if entry.is_dir() and (entry / "SKILL.md").exists())


def _provider_name(provider: str) -> str:
    if provider == "openai":
        return "custom"
    return provider


def _config_yaml(payload: dict[str, Any], profile_home: Path, workspace: Path) -> str:
    provider = payload.get("provider") or "custom"
    model = payload.get("model") or "qwen3-14b"
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
            f"  cwd: {json.dumps(str(workspace))}",
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


def _build_prompt(payload: dict[str, Any]) -> str:
    profile_home, _ = _profile_paths(payload)
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
    parts.append(f"User request:\n{payload.get('message') or ''}")
    return "\n\n".join(parts)


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


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


def _run_hermes(payload: dict[str, Any]) -> str:
    profile_home, workspace = _profile_paths(payload)
    (profile_home / "config.yaml").write_text(_config_yaml(payload, profile_home, workspace), encoding="utf-8")
    env = _runtime_env(payload, profile_home)
    command = [
        "hermes",
        "-z",
        _build_prompt(payload),
        "--provider",
        _provider_name(payload.get("provider") or "custom"),
        "-m",
        payload.get("model") or "qwen3-14b",
        "--yolo",
    ]
    for skill_name in _profile_skill_names(profile_home):
        command.extend(["--skills", skill_name])
    result = subprocess.run(
        command,
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        timeout=float(os.getenv("HERMES_RUN_TIMEOUT_SECONDS", "300")),
        check=False,
    )
    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip() or "Unknown Hermes runtime failure"
        raise RuntimeError(error)
    return _extract_response_text(result.stdout)


@app.post("/runs")
async def run_agent(payload: dict[str, Any]):
    content = _run_hermes(payload)
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
