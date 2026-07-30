from datetime import datetime
from typing import Any
import re

from app.models.profile import Profile
from app.models.skill_definition import SkillDefinition
from app.services.hermes_orchestrator import HermesOrchestratorClient, HermesOrchestratorUnavailable, hermes_orchestrator


def _slugify_skill_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return slug or "skill"


def build_profile_sync_payload(
    profile: Profile,
    skill_definitions: list[SkillDefinition] | None = None,
) -> dict[str, Any]:
    declared_skills = [skill.strip() for skill in (profile.skills or []) if skill and skill.strip()]
    skill_map = {skill.slug: skill for skill in (skill_definitions or [])}
    files: dict[str, str] = {
        "SOUL.md": profile.soul_md or "",
        "workspace/AGENTS.md": profile.agents_md or "",
        "system_prompt.md": profile.system_prompt or "",
        "skills/platform-profile/SKILL.md": (
            "---\n"
            "name: platform-profile\n"
            f"description: Role-specific operating guide for the {profile.name} profile.\n"
            "---\n\n"
            f"# {profile.name} profile context\n\n"
            "Use this skill as the role-specific operating guide for this smart-agent profile.\n\n"
            "## System instructions\n\n"
            f"{profile.system_prompt or 'No additional system instructions were configured.'}\n\n"
            "## Declared skill tags\n\n"
            + ("\n".join(f"- {skill}" for skill in declared_skills) if declared_skills else "- none")
        ),
    }
    for skill in declared_skills:
        skill_slug = _slugify_skill_name(skill)
        definition = skill_map.get(skill_slug)
        if definition:
            instructions = definition.instructions_md or f"# {definition.name}\n\nNo additional instructions were configured."
            files[f"skills/{skill_slug}/SKILL.md"] = (
                "---\n"
                f"name: {definition.name}\n"
                f"description: {definition.description or f'Profile-local skill for {definition.name}.'}\n"
                "---\n\n"
                f"{instructions.rstrip()}\n"
            )
        else:
            raise ValueError(f"Missing active skill definition for profile skill: {skill}")
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
            "runtime_toolsets": profile.runtime_toolsets or [],
            "memory_settings": profile.memory_settings or {},
        },
        "files": files,
    }


class HermesProfileSyncService:
    def __init__(self, orchestrator: HermesOrchestratorClient = hermes_orchestrator) -> None:
        self.orchestrator = orchestrator

    async def sync(
        self,
        profile: Profile,
        skill_definitions: list[SkillDefinition] | None = None,
    ) -> dict[str, Any]:
        if profile.runtime_type != "hermes":
            profile.hermes_sync_status = "not_applicable"
            profile.hermes_sync_error = None
            return {"status": "not_applicable"}

        try:
            payload = build_profile_sync_payload(profile, skill_definitions)
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
        profile.last_synced_at = datetime.utcnow()
        return result


hermes_profile_sync_service = HermesProfileSyncService()
