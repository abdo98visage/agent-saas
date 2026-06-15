"""
Internal Hermes Orchestrator service.

This service is intended to run on the private Docker network with Docker socket access.
FastAPI calls this service through fixed endpoints instead of executing Docker commands itself.
"""
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse


ORCHESTRATOR_SECRET = os.getenv("HERMES_ORCHESTRATOR_SECRET", "")
ORCHESTRATOR_REQUIRE_SECRET = os.getenv("HERMES_ORCHESTRATOR_REQUIRE_SECRET", "true").lower() == "true"
HERMES_IMAGE = os.getenv("HERMES_IMAGE", "ghcr.io/hermes-agent/hermes:latest")
HERMES_CONTAINER = os.getenv("HERMES_CONTAINER", "agent-saas-hermes")
HERMES_PORT = os.getenv("HERMES_PORT", "8787")
HERMES_WORKSPACE_ROOT = Path(os.getenv("HERMES_WORKSPACE_ROOT", "/data/hermes/profiles"))
HERMES_INTERNAL_URL = os.getenv("HERMES_INTERNAL_URL", f"http://{HERMES_CONTAINER}:{HERMES_PORT}")
HERMES_RUN_PATH = os.getenv("HERMES_RUN_PATH", "/runs")
HERMES_RUN_STREAM_PATH = os.getenv("HERMES_RUN_STREAM_PATH", "/runs/stream")
HERMES_HEALTH_PATH = os.getenv("HERMES_HEALTH_PATH", "/health")
HERMES_DOCKER_NETWORK = os.getenv("HERMES_DOCKER_NETWORK", "")
HERMES_PUBLISH_PORT = os.getenv("HERMES_PUBLISH_PORT", "false").lower() == "true"
HERMES_REQUEST_TIMEOUT_SECONDS = float(os.getenv("HERMES_REQUEST_TIMEOUT_SECONDS", "300"))
HERMES_MANAGED_EXTERNALLY = os.getenv("HERMES_MANAGED_EXTERNALLY", "false").lower() == "true"

app = FastAPI(title="AgentSaaS Hermes Orchestrator", version="0.1.0")


def _authorize(secret: str | None) -> None:
    if ORCHESTRATOR_REQUIRE_SECRET and not ORCHESTRATOR_SECRET:
        raise HTTPException(status_code=503, detail="Hermes orchestrator secret is not configured")
    if ORCHESTRATOR_SECRET and secret != ORCHESTRATOR_SECRET:
        raise HTTPException(status_code=403, detail="Invalid orchestrator secret")


def _docker(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _container_inspect() -> dict[str, Any] | None:
    result = _docker(["inspect", HERMES_CONTAINER], timeout=20)
    if result.returncode != 0:
        return None
    data = json.loads(result.stdout)
    return data[0] if data else None


def _runtime_status() -> dict[str, Any]:
    inspect_data = _container_inspect()
    if not inspect_data:
        return {
            "installed": False,
            "running": False,
            "status": "not_installed",
            "docker_image": HERMES_IMAGE,
            "version": None,
            "last_sync_status": None,
            "queue_health": "unknown",
            "run_health": "unknown",
        }
    state = inspect_data.get("State", {})
    return {
        "installed": True,
        "running": bool(state.get("Running")),
        "status": state.get("Status", "unknown"),
        "docker_image": inspect_data.get("Config", {}).get("Image", HERMES_IMAGE),
        "version": inspect_data.get("Config", {}).get("Labels", {}).get("org.opencontainers.image.version"),
        "last_sync_status": "available",
        "queue_health": "unknown",
        "run_health": "unknown",
    }


def _hermes_url(path: str) -> str:
    return f"{HERMES_INTERNAL_URL.rstrip('/')}/{path.lstrip('/')}"


async def _hermes_health() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(_hermes_url(HERMES_HEALTH_PATH))
            return {
                "ok": response.is_success,
                "status_code": response.status_code,
                "body": response.json() if "application/json" in response.headers.get("content-type", "") else None,
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _normalize_run_result(result: dict[str, Any]) -> dict[str, Any]:
    content = (
        result.get("content")
        or result.get("response")
        or result.get("output")
        or result.get("final_output")
        or result.get("message")
        or ""
    )
    return {
        **result,
        "content": content,
        "tools_used": result.get("tools_used") or result.get("tools") or [],
        "mcp_servers_used": result.get("mcp_servers_used") or result.get("mcp_servers") or [],
        "total_cost": result.get("total_cost") or result.get("cost") or 0.0,
    }


@app.get("/healthz")
async def healthz():
    return {"status": "healthy"}


@app.get("/status")
async def status(x_hermes_orchestrator_secret: str | None = Header(default=None)):
    _authorize(x_hermes_orchestrator_secret)
    if HERMES_MANAGED_EXTERNALLY:
        health = await _hermes_health()
        return {
            "installed": health.get("ok", False),
            "running": health.get("ok", False),
            "status": "running" if health.get("ok") else "unhealthy",
            "docker_image": HERMES_IMAGE,
            "version": None,
            "last_sync_status": "available" if health.get("ok") else None,
            "queue_health": "unknown",
            "run_health": "healthy" if health.get("ok") else "unhealthy",
            "health": health,
            "managed_externally": True,
        }
    runtime = _runtime_status()
    if runtime["running"]:
        health = await _hermes_health()
        runtime["run_health"] = "healthy" if health.get("ok") else "unhealthy"
        runtime["health"] = health
    return runtime


@app.get("/logs")
async def logs(
    limit: int = Query(200, le=1000),
    x_hermes_orchestrator_secret: str | None = Header(default=None),
):
    _authorize(x_hermes_orchestrator_secret)
    result = _docker(["logs", "--tail", str(limit), HERMES_CONTAINER], timeout=20)
    if result.returncode != 0:
        return {"status": "not_available", "logs": [result.stderr.strip()] if result.stderr else []}
    return {"status": "ok", "logs": result.stdout.splitlines()}


@app.post("/install")
async def install(x_hermes_orchestrator_secret: str | None = Header(default=None)):
    _authorize(x_hermes_orchestrator_secret)
    if HERMES_MANAGED_EXTERNALLY:
        return {"status": "managed_externally", **(await status(x_hermes_orchestrator_secret))}
    pull = _docker(["pull", HERMES_IMAGE], timeout=600)
    if pull.returncode != 0:
        return {"status": "failed", "step": "pull", "error": pull.stderr}
    existing = _container_inspect()
    if existing:
        return {"status": "installed", **_runtime_status()}
    HERMES_WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    run_args = [
        "run", "-d",
        "--name", HERMES_CONTAINER,
        "--restart", "unless-stopped",
        "-v", f"{HERMES_WORKSPACE_ROOT}:/data/hermes/profiles",
    ]
    if HERMES_DOCKER_NETWORK:
        run_args.extend(["--network", HERMES_DOCKER_NETWORK])
    if HERMES_PUBLISH_PORT:
        run_args.extend(["-p", f"{HERMES_PORT}:{HERMES_PORT}"])
    run_args.append(HERMES_IMAGE)
    run = _docker(run_args, timeout=120)
    if run.returncode != 0:
        return {"status": "failed", "step": "run", "error": run.stderr}
    return {"status": "installed", **_runtime_status()}


@app.post("/start")
async def start(x_hermes_orchestrator_secret: str | None = Header(default=None)):
    _authorize(x_hermes_orchestrator_secret)
    if HERMES_MANAGED_EXTERNALLY:
        return {"status": "managed_externally", **(await status(x_hermes_orchestrator_secret))}
    result = _docker(["start", HERMES_CONTAINER], timeout=60)
    return {"status": "started" if result.returncode == 0 else "failed", "error": result.stderr or None, **_runtime_status()}


@app.post("/restart")
async def restart(x_hermes_orchestrator_secret: str | None = Header(default=None)):
    _authorize(x_hermes_orchestrator_secret)
    if HERMES_MANAGED_EXTERNALLY:
        return {"status": "managed_externally", **(await status(x_hermes_orchestrator_secret))}
    result = _docker(["restart", HERMES_CONTAINER], timeout=120)
    return {"status": "restarted" if result.returncode == 0 else "failed", "error": result.stderr or None, **_runtime_status()}


@app.post("/stop")
async def stop(x_hermes_orchestrator_secret: str | None = Header(default=None)):
    _authorize(x_hermes_orchestrator_secret)
    if HERMES_MANAGED_EXTERNALLY:
        return {"status": "managed_externally", **(await status(x_hermes_orchestrator_secret))}
    result = _docker(["stop", HERMES_CONTAINER], timeout=60)
    return {"status": "stopped" if result.returncode == 0 else "failed", "error": result.stderr or None, **_runtime_status()}


@app.post("/repair-sync")
async def repair_sync(x_hermes_orchestrator_secret: str | None = Header(default=None)):
    _authorize(x_hermes_orchestrator_secret)
    HERMES_WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    return {"status": "ready", "workspace_root": str(HERMES_WORKSPACE_ROOT)}


@app.post("/profiles/sync")
async def sync_profile(payload: dict[str, Any], x_hermes_orchestrator_secret: str | None = Header(default=None)):
    _authorize(x_hermes_orchestrator_secret)
    profile = payload.get("profile", {})
    slug = profile.get("slug")
    if not slug:
        raise HTTPException(status_code=400, detail="profile.slug is required")
    workspace = HERMES_WORKSPACE_ROOT / slug
    workspace.mkdir(parents=True, exist_ok=True)
    for filename, content in (payload.get("files") or {}).items():
        if "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail=f"Invalid filename: {filename}")
        (workspace / filename).write_text(content or "", encoding="utf-8")
    (workspace / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "status": "synced",
        "hermes_profile_id": slug,
        "workspace_path": str(workspace),
    }


@app.post("/profiles/delete")
async def delete_profile(payload: dict[str, Any], x_hermes_orchestrator_secret: str | None = Header(default=None)):
    _authorize(x_hermes_orchestrator_secret)
    hermes_profile_id = payload.get("hermes_profile_id")
    if not hermes_profile_id:
        raise HTTPException(status_code=400, detail="hermes_profile_id is required")
    workspace = HERMES_WORKSPACE_ROOT / hermes_profile_id
    if workspace.exists():
        for file in workspace.iterdir():
            if file.is_file():
                file.unlink()
        workspace.rmdir()
    return {"status": "deleted", "hermes_profile_id": hermes_profile_id}


@app.post("/runs")
async def run_agent(payload: dict[str, Any], x_hermes_orchestrator_secret: str | None = Header(default=None)):
    _authorize(x_hermes_orchestrator_secret)
    try:
        async with httpx.AsyncClient(timeout=HERMES_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(_hermes_url(HERMES_RUN_PATH), json=payload)
            response.raise_for_status()
            return _normalize_run_result(response.json())
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Hermes run failed: {exc.response.text}") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Hermes runtime unavailable: {exc}") from exc


@app.post("/runs/stream")
async def run_agent_stream(payload: dict[str, Any], x_hermes_orchestrator_secret: str | None = Header(default=None)):
    _authorize(x_hermes_orchestrator_secret)

    async def event_generator():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", _hermes_url(HERMES_RUN_STREAM_PATH), json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            yield f"{line}\n\n"
                        elif line.startswith("event:"):
                            continue
                        else:
                            yield f"data: {line}\n\n"
        except Exception as exc:
            error = json.dumps({"type": "error", "error": str(exc)}, ensure_ascii=False)
            yield f"data: {error}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
