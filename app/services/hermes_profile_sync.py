from datetime import datetime, timezone
from typing import Any

from app.models.profile import Profile
from app.services.hermes_orchestrator import HermesOrchestratorClient, HermesOrchestratorUnavailable, hermes_orchestrator


def build_profile_sync_payload(profile: Profile) -> dict[str, Any]:
    skills_md = "\n".join(f"- {skill}" for skill in (profile.skills or []))
    return {
        "profile": {
            "id": str(profile.id),
            "name": profile.name,
            "slug": profile.slug,
            "version": profile.version,
            "runtime_type": profile.runtime_type,
            "provider_key_id": str(profile.provider_key_id) if profile.provider_key_id else None,
            "limits": {
                "max_tokens_per_day": profile.max_tokens_per_day,
                "max_requests_per_day": profile.max_requests_per_day,
                "daily_cost_budget": profile.daily_cost_budget,
            },
            "providers": profile.allowed_providers or [],
            "mcp_servers": profile.allowed_mcp_servers or [],
            "allowed_tools": profile.allowed_tools or [],
            "approval_required_tools": profile.approval_required_tools or [],
            "memory_settings": profile.memory_settings or {},
        },
        "files": {
            "AGENTS.md": profile.agents_md or "",
            "soul.md": profile.soul_md or "",
            "skills.md": skills_md,
            "system_prompt.md": profile.system_prompt or "",
        },
    }


class HermesProfileSyncService:
    def __init__(self, orchestrator: HermesOrchestratorClient = hermes_orchestrator) -> None:
        self.orchestrator = orchestrator

    async def sync(self, profile: Profile) -> dict[str, Any]:
        if profile.runtime_type != "hermes":
            profile.hermes_sync_status = "not_applicable"
            profile.hermes_sync_error = None
            return {"status": "not_applicable"}

        payload = build_profile_sync_payload(profile)
        try:
            result = await self.orchestrator.sync_profile(payload)
        except HermesOrchestratorUnavailable as exc:
            profile.hermes_sync_status = "not_configured"
            profile.hermes_sync_error = str(exc)
            return {"status": "not_configured", "error": str(exc)}
        except Exception as exc:
            profile.hermes_sync_status = "sync_failed"
            profile.hermes_sync_error = str(exc)
            return {"status": "sync_failed", "error": str(exc)}

        profile.hermes_profile_id = result.get("hermes_profile_id") or profile.hermes_profile_id or profile.slug
        profile.hermes_workspace_path = result.get("workspace_path") or profile.hermes_workspace_path
        profile.hermes_sync_status = result.get("status", "synced")
        profile.hermes_sync_error = None
        profile.last_synced_at = datetime.now(timezone.utc)
        return result


hermes_profile_sync_service = HermesProfileSyncService()
