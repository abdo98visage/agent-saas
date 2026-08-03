from typing import Any, AsyncGenerator, Optional

import json
import httpx

from app.core.config import settings


class HermesOrchestratorUnavailable(RuntimeError):
    pass


class HermesOrchestratorClient:
    """Strict client for the internal Hermes orchestrator service."""

    def __init__(self, base_url: Optional[str] = None, secret: Optional[str] = None) -> None:
        self.base_url = (base_url if base_url is not None else settings.hermes_orchestrator_url).rstrip("/")
        self.secret = secret if secret is not None else settings.hermes_orchestrator_secret

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def _headers(self, payload: Optional[dict[str, Any]] = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Hermes-Orchestrator-Secret"] = self.secret
        payload = payload or {}
        if payload.get("correlation_id"):
            headers["X-Correlation-ID"] = str(payload["correlation_id"])
        trace_id = str(payload.get("trace_id") or "")
        if len(trace_id) == 32:
            headers["traceparent"] = f"00-{trace_id}-{trace_id[:16]}-01"
        return headers

    async def _request(self, method: str, path: str, json: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if not self.configured:
            raise HermesOrchestratorUnavailable("Agent orchestrator URL is not configured")
        async with httpx.AsyncClient(timeout=settings.hermes_request_timeout_seconds) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(json),
                json=json,
            )
            response.raise_for_status()
            return response.json()

    async def status(self) -> dict[str, Any]:
        if not self.configured:
            return {
                "installed": False,
                "running": False,
                "status": "not_configured",
                "docker_image": None,
                "version": None,
                "last_sync_status": None,
                "queue_health": "unknown",
                "run_health": "unknown",
                "message": "Configure the agent orchestrator URL to enable runtime control.",
            }
        return await self._request("GET", "/status")

    async def logs(self, limit: int = 200) -> dict[str, Any]:
        if not self.configured:
            return {"logs": [], "status": "not_configured"}
        return await self._request("GET", f"/logs?limit={limit}")

    async def lifecycle(self, action: str) -> dict[str, Any]:
        if action not in {"install", "start", "restart", "stop", "repair-sync"}:
            raise ValueError(f"Unsupported agent lifecycle action: {action}")
        return await self._request("POST", f"/{action}")

    async def sync_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/profiles/sync", json=payload)

    async def delete_profile(self, hermes_profile_id: str) -> dict[str, Any]:
        return await self._request("POST", "/profiles/delete", json={"hermes_profile_id": hermes_profile_id})

    async def run_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/runs", json=payload)

    async def respond_approval(self, run_id: str, approval_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"approve", "deny"}:
            raise ValueError("Unsupported approval decision")
        return await self._request(
            "POST",
            "/approvals",
            json={"run_id": run_id, "approval_id": approval_id, "decision": decision},
        )

    async def run_agent_stream(self, payload: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
        if not self.configured:
            raise HermesOrchestratorUnavailable("Agent orchestrator URL is not configured")
        timeout = httpx.Timeout(
            connect=5.0,
            read=settings.hermes_request_timeout_seconds,
            write=10.0,
            pool=5.0,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/runs/stream",
                headers=self._headers(payload),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("event:"):
                        continue
                    if line.startswith("data: "):
                        line = line[6:]
                    event = json.loads(line)
                    if event.get("type") == "error":
                        raise HermesOrchestratorUnavailable(event.get("error") or event.get("detail") or "Agent stream failed")
                    yield event


hermes_orchestrator = HermesOrchestratorClient()
