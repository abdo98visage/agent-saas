"""
Local Hermes-compatible runtime for Docker validation.

This runtime implements the same HTTP contract that AgentSaaS expects from
Hermes: health checks, non-streaming runs, and streaming runs. It is meant for
repeatable local Docker validation of the platform plumbing before a VPS deploy.
"""
import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse


app = FastAPI(title="AgentSaaS Local Hermes Runtime", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "healthy", "runtime": "agentsaas-local-hermes"}


def _build_response(payload: dict[str, Any]) -> str:
    profile = payload.get("profile") or {}
    message = payload.get("message") or ""
    profile_slug = profile.get("slug") or "default"
    return f"[Local Hermes:{profile_slug}] {message}"


@app.post("/runs")
async def run_agent(payload: dict[str, Any]):
    return {
        "content": _build_response(payload),
        "tools_used": ["local_runtime"],
        "mcp_servers_used": [],
        "total_cost": 0.0,
        "usage": {
            "input_tokens": max(1, len(json.dumps(payload, ensure_ascii=False)) // 4),
            "output_tokens": max(1, len(_build_response(payload)) // 4),
        },
    }


@app.post("/runs/stream")
async def run_agent_stream(payload: dict[str, Any]):
    content = _build_response(payload)
    midpoint = max(1, len(content) // 2)
    chunks = [
        {"type": "chunk", "content": content[:midpoint]},
        {"type": "chunk", "content": content[midpoint:]},
        {
            "type": "done",
            "content": "",
            "tools_used": ["local_runtime"],
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
