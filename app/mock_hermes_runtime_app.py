"""
Small Hermes-compatible runtime used by local Docker E2E tests.

The production stack points the orchestrator at the real Hermes runtime. This
app exists only so the full AgentSaaS journey can be exercised in Docker without
requiring a real Hermes image or external provider key.
"""
import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse


app = FastAPI(title="Mock Hermes Runtime", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "healthy", "runtime": "mock-hermes"}


@app.post("/runs")
async def run_agent(payload: dict[str, Any]):
    profile = payload.get("profile") or {}
    message = payload.get("message") or ""
    content = f"[Mock Hermes:{profile.get('slug', 'profile')}] {message}"
    return {
        "content": content,
        "tools_used": ["mock_tool"],
        "mcp_servers_used": ["mock_mcp"],
        "total_cost": 0.01,
    }


@app.post("/runs/stream")
async def run_agent_stream(payload: dict[str, Any]):
    profile = payload.get("profile") or {}
    message = payload.get("message") or ""
    chunks = [
        {"type": "chunk", "content": f"[Mock Hermes:{profile.get('slug', 'profile')}] "},
        {"type": "chunk", "content": message},
        {
            "type": "done",
            "content": "",
            "tools_used": ["mock_tool"],
            "mcp_servers_used": ["mock_mcp"],
            "total_cost": 0.01,
        },
    ]

    async def events():
        for event in chunks:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
