from typing import Any, AsyncGenerator, Optional

from app.models.profile import Profile
from app.models.user import User
from app.services.hermes_orchestrator import HermesOrchestratorClient, hermes_orchestrator


class DirectLLMRuntime:
    runtime_type = "direct_llm"

    def __init__(self, agent_service: Any) -> None:
        self.agent_service = agent_service

    async def complete(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: Optional[str],
        provider: Optional[str],
    ) -> dict:
        return await self.agent_service._call_llm(messages, model, temperature, max_tokens, api_key, provider)

    async def stream(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: Optional[str],
        provider: Optional[str],
    ) -> AsyncGenerator[str, None]:
        async for chunk in self.agent_service._call_llm_stream(messages, model, temperature, max_tokens, api_key, provider):
            yield chunk


class HermesRuntime:
    runtime_type = "hermes"

    def __init__(self, orchestrator: HermesOrchestratorClient = hermes_orchestrator) -> None:
        self.orchestrator = orchestrator

    def _payload(
        self,
        user: User,
        profile: Profile,
        session_id: str,
        user_message: str,
        project_context: Optional[str],
        api_key: Optional[str],
        model: str,
        provider: str,
    ) -> dict[str, Any]:
        return {
            "employee": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "department": user.department,
            },
            "profile": {
                "id": str(profile.id),
                "slug": profile.slug,
                "name": profile.name,
                "version": profile.version,
                "hermes_profile_id": profile.hermes_profile_id,
            },
            "session_id": session_id,
            "message": user_message,
            "project_context": project_context,
            "provider": provider,
            "model": model,
            "api_key": api_key,
        }

    async def complete(
        self,
        user: User,
        profile: Profile,
        session_id: str,
        user_message: str,
        project_context: Optional[str],
        api_key: Optional[str],
        model: str,
        provider: str,
    ) -> dict[str, Any]:
        return await self.orchestrator.run_agent(
            self._payload(user, profile, session_id, user_message, project_context, api_key, model, provider)
        )

    async def stream(
        self,
        user: User,
        profile: Profile,
        session_id: str,
        user_message: str,
        project_context: Optional[str],
        api_key: Optional[str],
        model: str,
        provider: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        async for event in self.orchestrator.run_agent_stream(
            self._payload(user, profile, session_id, user_message, project_context, api_key, model, provider)
        ):
            yield event


class AgentRuntimeRouter:
    def __init__(self, agent_service: Any) -> None:
        self.direct = DirectLLMRuntime(agent_service)
        self.hermes = HermesRuntime()

    def for_profile(self, profile: Optional[Profile]) -> Any:
        if profile and profile.runtime_type == "hermes":
            return self.hermes
        return self.direct
