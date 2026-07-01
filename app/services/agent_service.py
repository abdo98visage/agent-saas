"""
Agent Service — Core AI inference engine with profile resolution,
per-user API keys, streaming support, and token tracking.
"""
import json
import time
from datetime import datetime, date, time as dt_time
from uuid import uuid4, UUID
from typing import Optional, Dict, Any, AsyncGenerator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.core.config import settings
from app.models.agent_template import AgentTemplate
from app.models.session import Session
from app.models.message import Message
from app.models.user import User
from app.models.profile import Profile
from app.models.profile_user import ProfileUser
from app.models.user_api_key import UserApiKey
from app.models.agent_run import AgentRun, AgentRunEvent
from app.services.api_key_resolver import api_key_resolver
from app.services.agent_runtime import AgentRuntimeRouter
from app.services.pricing_service import pricing_service


class AgentService:
    """Core agent service: profile resolution, per-user API keys, LLM routing, streaming."""

    def _runtime_request_url(self, profile: Optional[Profile]) -> str:
        runtime = self._runtime_router().for_profile(profile)
        if runtime.runtime_type == "hermes":
            return f"{settings.hermes_orchestrator_url.rstrip('/')}/runs" if settings.hermes_orchestrator_url else ""
        if settings.is_openai:
            return settings.openai_base_url
        if settings.is_minimax:
            return settings.minimax_base_url
        if settings.is_ollama:
            return f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        return ""

    async def resolve_user_profile(
        self, db: AsyncSession, user_id: UUID, profile_name: Optional[str] = None
    ) -> Optional[Profile]:
        """Resolve the active profile for a user by name or highest priority."""
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError("Employee not found")

        query = (
            select(ProfileUser, Profile)
            .join(Profile)
            .where(ProfileUser.user_id == user_id, Profile.is_active == True)
        )
        if profile_name:
            normalized_profile_name = profile_name.strip()
            query = query.where(
                (Profile.name == normalized_profile_name) | (Profile.slug == normalized_profile_name)
            )
        result = await db.execute(query)
        rows = result.all()
        if not rows:
            if profile_name and user.role == "admin":
                normalized_profile_name = profile_name.strip()
                admin_profile_result = await db.execute(
                    select(Profile).where(
                        ((Profile.name == normalized_profile_name) | (Profile.slug == normalized_profile_name)),
                        Profile.is_active == True,
                    )
                )
                admin_profile = admin_profile_result.scalar_one_or_none()
                if admin_profile:
                    return admin_profile
            if profile_name:
                raise ValueError("Profile is not assigned to this employee or is inactive")
            return None
        if profile_name:
            return rows[0][1]
        # Lower numeric priority means higher precedence.
        rows.sort(key=lambda r: r[0].priority)
        return rows[0][1]

    async def resolve_user_api_key(
        self, db: AsyncSession, user_id: UUID, profile_id: Optional[UUID] = None
    ) -> Optional[str]:
        """Resolve active provider key by employee override, profile key, then platform fallback."""
        return await api_key_resolver.resolve(
            db,
            user_id=user_id,
            provider=settings.llm_provider,
            profile_id=profile_id,
        )

    @staticmethod
    def _provider_requires_key() -> bool:
        return settings.llm_provider in {"minimax", "openai"}

    async def _resolve_runtime_api_key(
        self, db: AsyncSession, user_id: UUID, profile: Optional[Profile]
    ) -> Optional[str]:
        key_obj = await api_key_resolver.resolve_key(
            db,
            user_id=user_id,
            provider=settings.llm_provider,
            profile_id=profile.id if profile else None,
        )
        if not key_obj:
            if self._provider_requires_key():
                raise RuntimeError(
                    "No active provider API key is configured for this employee/profile/platform."
                )
            return None
        if key_obj.spent_today >= key_obj.daily_budget:
            raise RuntimeError("Provider API key daily budget exceeded")
        return api_key_resolver.decrypt(key_obj)

    async def get_system_prompt(
        self,
        db: AsyncSession,
        user_id: UUID,
        agent_template_name: str = "default",
        profile_name: Optional[str] = None,
    ) -> tuple[str, str, str, float, int]:
        """
        Build system prompt from Profile + AgentTemplate.
        Returns: (full_system_prompt, model_name, profile_name, temperature, max_tokens)
        """
        # Load agent template
        result = await db.execute(
            select(AgentTemplate).where(AgentTemplate.name == agent_template_name)
        )
        template = result.scalar_one_or_none()
        if not template:
            template = AgentTemplate(
                name="default",
                system_prompt="You are a helpful AI assistant. Be professional, clear, and concise.",
                model_name=settings.default_model,
                temperature=0.7,
                max_tokens_per_request=4000,
            )

        model_name = template.model_name
        temperature = template.temperature
        max_tokens = template.max_tokens_per_request

        # Try to resolve user's profile
        profile = await self.resolve_user_profile(db, user_id, profile_name=profile_name)
        resolved_profile_name = profile.name if profile else None

        # Build system prompt: Profile agents.md + soul.md + template system prompt
        parts = []
        if profile and profile.agents_md:
            parts.append(profile.agents_md)
        if profile and profile.soul_md:
            parts.append(profile.soul_md)
        if profile and profile.system_prompt:
            parts.append(profile.system_prompt)
        if template.system_prompt:
            parts.append(template.system_prompt)

        full_prompt = "\n\n".join(parts) if parts else template.system_prompt

        return full_prompt, model_name, resolved_profile_name or "", temperature, max_tokens

    async def _ensure_session(
        self,
        db: AsyncSession,
        user_id: UUID,
        conversation_id: Optional[str],
        agent_template_name: str,
    ) -> Session:
        if conversation_id:
            session_result = await db.execute(
                select(Session).where(
                    Session.id == UUID(conversation_id),
                    Session.user_id == user_id,
                )
            )
            session_obj = session_result.scalar_one_or_none()
            if session_obj:
                return session_obj

        session_obj = Session(
            id=uuid4(),
            user_id=user_id,
            agent_template_name=agent_template_name,
        )
        db.add(session_obj)
        await db.flush()
        return session_obj

    async def _get_user(self, db: AsyncSession, user_id: UUID) -> User:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("Employee not found")
        return user

    async def _enforce_profile_ready(self, profile: Optional[Profile]) -> None:
        if not profile:
            return
        if not profile.is_active:
            raise ValueError("Profile is inactive")
        if profile.allowed_providers and settings.llm_provider not in profile.allowed_providers:
            raise RuntimeError(f"Provider {settings.llm_provider} is not allowed for this profile")
        if profile.runtime_type == "hermes" and profile.hermes_sync_status != "synced":
            raise RuntimeError(
                f"Agent profile is not ready: {profile.hermes_sync_status or 'pending'}"
            )

    async def _enforce_profile_request_limit(self, db: AsyncSession, profile: Optional[Profile]) -> None:
        if not profile or not profile.max_requests_per_day:
            return
        today_start = datetime.combine(date.today(), dt_time.min)
        result = await db.execute(
            select(AgentRun).where(
                AgentRun.profile_id == profile.id,
                AgentRun.created_at >= today_start,
            )
        )
        if len(result.scalars().all()) >= profile.max_requests_per_day:
            raise RuntimeError("Profile daily request quota exceeded")

    async def _enforce_profile_usage_limits(self, db: AsyncSession, profile: Optional[Profile]) -> None:
        if not profile:
            return
        today_start = datetime.combine(date.today(), dt_time.min)
        if profile.max_tokens_per_day:
            tokens_today = await db.execute(
                select(func.coalesce(func.sum(AgentRun.output_tokens), 0)).where(
                    AgentRun.profile_id == profile.id,
                    AgentRun.created_at >= today_start,
                )
            )
            if int(tokens_today.scalar() or 0) >= profile.max_tokens_per_day:
                raise RuntimeError("Profile daily token quota exceeded")
        if profile.daily_cost_budget:
            cost_today = await db.execute(
                select(func.coalesce(func.sum(AgentRun.total_cost), 0)).where(
                    AgentRun.profile_id == profile.id,
                    AgentRun.created_at >= today_start,
                )
            )
            if float(cost_today.scalar() or 0.0) >= float(profile.daily_cost_budget):
                raise RuntimeError("Profile daily cost budget exceeded")

    def _runtime_router(self) -> AgentRuntimeRouter:
        return AgentRuntimeRouter(self)

    async def _create_run(
        self,
        db: AsyncSession,
        session_obj: Session,
        user_id: UUID,
        profile: Optional[Profile],
        runtime_type: str,
        model_name: str,
    ) -> AgentRun:
        run = AgentRun(
            id=uuid4(),
            session_id=session_obj.id,
            user_id=user_id,
            profile_id=profile.id if profile else None,
            profile_version=profile.version if profile else None,
            runtime_type=runtime_type,
            status="running",
            started_at=datetime.utcnow(),
            model=model_name,
            provider=settings.llm_provider,
        )
        db.add(run)
        await db.flush()
        return run

    async def _finish_run(
        self,
        db: AsyncSession,
        run: AgentRun,
        status: str,
        latency_ms: int,
        output_tokens: int = 0,
        input_tokens: int = 0,
        total_cost: float = 0.0,
        tools_used: Optional[list] = None,
        mcp_servers_used: Optional[list] = None,
        pricing_snapshot: Optional[dict] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        run.status = status
        run.ended_at = datetime.utcnow()
        run.latency_ms = latency_ms
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
        run.total_cost = total_cost
        run.tools_used = tools_used or []
        run.mcp_servers_used = mcp_servers_used or []
        run.pricing_snapshot = pricing_snapshot or {}
        run.error_code = error_code
        run.error_message = error_message

    def _estimate_message_tokens(self, messages: list[dict[str, Any]]) -> int:
        total = 0
        for message in messages:
            total += self._estimate_tokens(str(message.get("content") or ""))
        return total

    def _resolve_usage_tokens(
        self,
        messages: list[dict[str, Any]],
        response_text: str,
        usage: dict[str, Any],
    ) -> tuple[int, int]:
        input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        if input_tokens <= 0:
            input_tokens = self._estimate_message_tokens(messages)
        if output_tokens <= 0:
            output_tokens = self._estimate_tokens(response_text)
        return input_tokens, output_tokens

    async def run_agent(
        self,
        db: AsyncSession,
        user_id: str,
        conversation_id: Optional[str],
        user_message: str,
        agent_template_name: str = "default",
        project_context: Optional[str] = None,
        profile_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the agent for a user message (non-streaming)."""
        start_time = time.time()
        user_uuid = UUID(user_id)
        user = await self._get_user(db, user_uuid)

        # 1. Resolve system prompt, model, profile
        full_prompt, model_name, resolved_profile, temperature, max_tokens = (
            await self.get_system_prompt(
                db,
                user_uuid,
                agent_template_name,
                profile_name=profile_name,
            )
        )
        profile = await self.resolve_user_profile(db, user_uuid, profile_name=profile_name)
        await self._enforce_profile_ready(profile)
        await self._enforce_profile_request_limit(db, profile)
        await self._enforce_profile_usage_limits(db, profile)
        session_obj = await self._ensure_session(db, user_uuid, conversation_id, agent_template_name)
        if resolved_profile:
            session_obj.profile_name = resolved_profile
        if profile:
            session_obj.profile_id = profile.id
            session_obj.profile_version = profile.version

        # 2. Resolve provider key by employee override, profile key, then platform fallback.
        user_api_key = await self._resolve_runtime_api_key(db, user_uuid, profile)

        # 3. Load conversation history (last 20 messages)
        history_messages = []
        if conversation_id:
            try:
                c_id = UUID(conversation_id)
                result = await db.execute(
                    select(Message)
                    .where(Message.session_id == c_id)
                    .order_by(Message.created_at.asc())
                    .limit(20)
                )
                for m in result.scalars().all():
                    history_messages.append({"role": m.role, "content": m.content})
            except ValueError:
                pass

        # 4. Build messages payload
        messages = [{"role": "system", "content": full_prompt}]

        if project_context:
            messages.append({
                "role": "system",
                "content": f"Project Context:\n{project_context}",
            })

        messages.extend(history_messages)
        messages.append({"role": "user", "content": user_message})

        # 5. Call selected runtime
        runtime = self._runtime_router().for_profile(profile)
        run = await self._create_run(db, session_obj, user_uuid, profile, runtime.runtime_type, model_name)
        try:
            if runtime.runtime_type == "hermes":
                runtime_result = await runtime.complete(
                    user=user,
                    profile=profile,
                    session_id=str(session_obj.id),
                    user_message=user_message,
                    project_context=project_context,
                    api_key=user_api_key,
                    model=model_name,
                    provider=settings.llm_provider,
                )
                response_text = runtime_result.get("content", "")
                tools_used = runtime_result.get("tools_used", [])
                mcp_servers_used = runtime_result.get("mcp_servers_used", [])
                runtime_cost = float(runtime_result.get("total_cost", 0.0) or 0.0)
                usage = runtime_result.get("usage") or {}
            else:
                runtime_result = await runtime.complete(
                    messages=messages,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=user_api_key,
                )
                response_text = runtime_result.get("content", "")
                tools_used = []
                mcp_servers_used = []
                runtime_cost = float(runtime_result.get("total_cost", 0.0) or 0.0)
                usage = runtime_result.get("usage") or {}
        except Exception as exc:
            latency = int((time.time() - start_time) * 1000)
            await self._finish_run(
                db,
                run,
                "failed",
                latency,
                error_code=exc.__class__.__name__,
                error_message=str(exc),
            )
            await db.flush()
            await db.commit()
            raise

        # 6. Save messages to DB
        user_msg = Message(
            id=uuid4(),
            session_id=session_obj.id,
            role="user",
            content=user_message,
            project_context=project_context,
        )
        db.add(user_msg)
        await db.flush()

        assistant_msg = Message(
            id=uuid4(),
            session_id=user_msg.session_id,
            role="assistant",
            content=response_text,
            tokens_used=int(usage.get("output_tokens") or usage.get("completion_tokens") or self._estimate_tokens(response_text)),
        )
        db.add(assistant_msg)
        await db.flush()

        latency = int((time.time() - start_time) * 1000)
        input_tokens, output_tokens = self._resolve_usage_tokens(messages, response_text, usage)
        cost_calc = await pricing_service.calculate_cost(
            db,
            settings.llm_provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            fallback_cost=runtime_cost,
        )
        await self._finish_run(
            db,
            run,
            "completed",
            latency,
            output_tokens=output_tokens,
            input_tokens=input_tokens,
            total_cost=cost_calc.total_cost,
            tools_used=tools_used,
            mcp_servers_used=mcp_servers_used,
            pricing_snapshot=cost_calc.pricing_snapshot,
        )

        return {
            "conversation_id": str(session_obj.id),
            "content": response_text,
            "message_id": str(assistant_msg.id),
            "tokens_used": input_tokens + output_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "latency_ms": latency,
            "model": model_name,
            "provider": settings.llm_provider,
            "runtime_type": runtime.runtime_type,
            "request_url": self._runtime_request_url(profile),
            "profile_name": resolved_profile,
            "profile_id": str(profile.id) if profile else None,
            "total_cost": cost_calc.total_cost,
            "pricing_snapshot": cost_calc.pricing_snapshot,
        }

    async def run_agent_stream(
        self,
        db: AsyncSession,
        user_id: str,
        conversation_id: Optional[str],
        user_message: str,
        agent_template_name: str = "default",
        project_context: Optional[str] = None,
        profile_name: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Run the agent for a user message with SSE streaming."""
        user_uuid = UUID(user_id)
        user = await self._get_user(db, user_uuid)

        # 1. Resolve system prompt, model, profile
        full_prompt, model_name, resolved_profile, temperature, max_tokens = (
            await self.get_system_prompt(
                db,
                user_uuid,
                agent_template_name,
                profile_name=profile_name,
            )
        )
        profile = await self.resolve_user_profile(db, user_uuid, profile_name=profile_name)
        await self._enforce_profile_ready(profile)
        await self._enforce_profile_request_limit(db, profile)
        await self._enforce_profile_usage_limits(db, profile)
        session_obj = await self._ensure_session(db, user_uuid, conversation_id, agent_template_name)
        if resolved_profile:
            session_obj.profile_name = resolved_profile
        if profile:
            session_obj.profile_id = profile.id
            session_obj.profile_version = profile.version

        # 2. Resolve provider key by employee override, profile key, then platform fallback.
        user_api_key = await self._resolve_runtime_api_key(db, user_uuid, profile)

        # 3. Load conversation history
        history_messages = []
        if conversation_id:
            try:
                c_id = UUID(conversation_id)
                result = await db.execute(
                    select(Message)
                    .where(Message.session_id == c_id)
                    .order_by(Message.created_at.asc())
                    .limit(20)
                )
                for m in result.scalars().all():
                    history_messages.append({"role": m.role, "content": m.content})
            except ValueError:
                pass

        # 4. Build messages payload
        messages = [{"role": "system", "content": full_prompt}]
        if project_context:
            messages.append({
                "role": "system",
                "content": f"Project Context:\n{project_context}",
            })
        messages.extend(history_messages)
        messages.append({"role": "user", "content": user_message})

        # 5. Save user message immediately
        user_msg = Message(
            id=uuid4(),
            session_id=session_obj.id,
            role="user",
            content=user_message,
            project_context=project_context,
        )
        db.add(user_msg)
        await db.flush()

        # 6. Stream selected runtime response
        full_response = ""
        assistant_msg_id = str(uuid4())
        runtime = self._runtime_router().for_profile(profile)
        run = await self._create_run(db, session_obj, user_uuid, profile, runtime.runtime_type, model_name)
        start_time = time.time()
        tools_used: list = []
        mcp_servers_used: list = []
        runtime_cost = 0.0
        usage: dict[str, Any] = {}

        try:
            if runtime.runtime_type == "hermes":
                async for event in runtime.stream(
                    user=user,
                    profile=profile,
                    session_id=str(session_obj.id),
                    user_message=user_message,
                    project_context=project_context,
                    api_key=user_api_key,
                    model=model_name,
                    provider=settings.llm_provider,
                ):
                    db.add(AgentRunEvent(run_id=run.id, event_type=event.get("type", "event"), payload=event))
                    chunk = event.get("content", "")
                    if event.get("type") == "done":
                        tools_used = event.get("tools_used", [])
                        mcp_servers_used = event.get("mcp_servers_used", [])
                        runtime_cost = float(event.get("total_cost", 0.0) or 0.0)
                        usage = event.get("usage") or {}
                    if chunk:
                        full_response += chunk
                        yield {
                            "type": "chunk",
                            "content": chunk,
                            "message_id": assistant_msg_id,
                        }
            else:
                async for chunk in runtime.stream(
                    messages=messages,
                    model=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=user_api_key,
                ):
                    full_response += chunk
                    yield {
                        "type": "chunk",
                        "content": chunk,
                        "message_id": assistant_msg_id,
                    }
        except Exception as exc:
            latency = int((time.time() - start_time) * 1000)
            await self._finish_run(
                db,
                run,
                "failed",
                latency,
                error_code=exc.__class__.__name__,
                error_message=str(exc),
            )
            await db.flush()
            await db.commit()
            raise

        # 7. Save assistant message after streaming completes
        assistant_msg = Message(
            id=UUID(assistant_msg_id),
            session_id=user_msg.session_id,
            role="assistant",
            content=full_response,
            tokens_used=self._resolve_usage_tokens(messages, full_response, usage)[1],
        )
        db.add(assistant_msg)
        await db.flush()
        latency = int((time.time() - start_time) * 1000)
        input_tokens, output_tokens = self._resolve_usage_tokens(messages, full_response, usage)
        cost_calc = await pricing_service.calculate_cost(
            db,
            settings.llm_provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            fallback_cost=runtime_cost,
        )
        await self._finish_run(
            db,
            run,
            "completed",
            latency,
            output_tokens=output_tokens,
            input_tokens=input_tokens,
            total_cost=cost_calc.total_cost,
            tools_used=tools_used,
            mcp_servers_used=mcp_servers_used,
            pricing_snapshot=cost_calc.pricing_snapshot,
        )

        # Final event
        yield {
            "type": "done",
            "message_id": assistant_msg_id,
            "tokens_used": input_tokens + output_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "model": model_name,
            "provider": settings.llm_provider,
            "runtime_type": runtime.runtime_type,
            "request_url": self._runtime_request_url(profile),
            "profile_name": resolved_profile,
            "profile_id": str(profile.id) if profile else None,
            "total_cost": cost_calc.total_cost,
            "pricing_snapshot": cost_calc.pricing_snapshot,
            "conversation_id": str(user_msg.session_id),
        }

    async def _call_llm(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Call the configured LLM provider."""
        if settings.is_mock:
            return {"content": self._mock_response(messages), "usage": {}}

        if settings.is_minimax:
            return await self._call_minimax(messages, model, temperature, max_tokens, api_key)

        if settings.is_openai:
            return await self._call_openai(messages, model, temperature, max_tokens, api_key)

        if settings.is_ollama:
            return await self._call_ollama(messages, model, temperature)

        return {"content": self._mock_response(messages), "usage": {}}

    async def _call_llm_stream(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Call the configured LLM provider with streaming."""
        if settings.is_mock:
            response = self._mock_response(messages)
            for chunk in response:
                yield chunk
            return

        if settings.is_minimax:
            async for chunk in self._call_minimax_stream(messages, model, temperature, max_tokens, api_key):
                yield chunk
            return

        if settings.is_openai:
            async for chunk in self._call_openai_stream(messages, model, temperature, max_tokens, api_key):
                yield chunk
            return

        if settings.is_ollama:
            async for chunk in self._call_ollama_stream(messages, model, temperature):
                yield chunk
            return

        # Fallback
        response = self._mock_response(messages)
        for chunk in response:
            yield chunk

    async def _call_minimax(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Call MiniMax API."""
        auth_key = api_key or settings.minimax_api_key
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                settings.minimax_base_url,
                headers={"Authorization": f"Bearer {auth_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return {
                "content": payload["choices"][0]["message"]["content"],
                "usage": payload.get("usage") or {},
            }

    async def _call_minimax_stream(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Call MiniMax API with streaming."""
        auth_key = api_key or settings.minimax_api_key
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                settings.minimax_base_url,
                headers={"Authorization": f"Bearer {auth_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data)
                            content = parsed.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

    async def _call_openai(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Call OpenAI-compatible API."""
        auth_key = api_key or settings.openai_api_key
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                settings.openai_base_url,
                headers={"Authorization": f"Bearer {auth_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            payload = response.json()
            return {
                "content": payload["choices"][0]["message"]["content"],
                "usage": payload.get("usage") or {},
            }

    async def _call_openai_stream(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Call OpenAI-compatible API with streaming."""
        auth_key = api_key or settings.openai_api_key
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                settings.openai_base_url,
                headers={"Authorization": f"Bearer {auth_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data)
                            content = parsed.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

    async def _call_ollama(
        self,
        messages: list,
        model: str,
        temperature: float,
    ) -> dict[str, Any]:
        """Call Ollama API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
            )
            response.raise_for_status()
            payload = response.json()
            return {
                "content": payload["message"]["content"],
                "usage": payload.get("usage") or {},
            }

    async def _call_ollama_stream(
        self,
        messages: list,
        model: str,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Call Ollama API with streaming."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": temperature},
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    try:
                        parsed = json.loads(line)
                        content = parsed.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    def _mock_response(self, messages: list) -> str:
        """Mock LLM response for testing."""
        user_msg = ""
        for m in messages:
            if m["role"] == "user":
                user_msg = m["content"]
        if user_msg:
            return f"[Mock] You asked: {user_msg}\n\nThis is a mock response. Configure an LLM provider in .env to get real responses."
        return "[Mock] Hello! I'm a mock agent response."

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        Estimate token count using a more accurate heuristic.
        English: ~4 chars/token, Arabic: ~3 chars/token, Code: ~2 chars/token.
        Falls back to 1 token minimum.
        """
        if not text:
            return 0
        # Detect if text contains significant code blocks
        code_blocks = text.count("```")
        if code_blocks >= 2:
            return max(1, len(text) // 2)
        # Arabic detection (Arabic Unicode range)
        arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        if arabic_chars > len(text) * 0.3:
            return max(1, len(text) // 3)
        # Default English/mixed
        return max(1, len(text) // 4)

    def _count_llm_tokens(self, response_json: dict) -> int:
        """
        Extract actual token usage from LLM response if available.
        Falls back to _estimate_tokens if the API doesn't return usage.
        """
        usage = response_json.get("usage", {})
        if usage:
            return usage.get("total_tokens", usage.get("completion_tokens", 0))
        return 0
