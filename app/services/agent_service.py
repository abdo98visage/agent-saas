"""
Agent Service — Core AI inference engine with profile resolution,
per-user API keys, streaming support, and token tracking.
"""
import json
import time
from uuid import uuid4, UUID
from typing import Optional, Dict, Any, AsyncGenerator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.agent_template import AgentTemplate
from app.models.session import Session
from app.models.message import Message
from app.models.user import User
from app.models.profile import Profile
from app.models.profile_user import ProfileUser
from app.models.user_api_key import UserApiKey


class AgentService:
    """Core agent service: profile resolution, per-user API keys, LLM routing, streaming."""

    async def resolve_user_profile(
        self, db: AsyncSession, user_id: UUID, profile_name: Optional[str] = None
    ) -> Optional[Profile]:
        """Resolve the active profile for a user by name or highest priority."""
        query = select(ProfileUser, Profile).join(Profile).where(ProfileUser.user_id == user_id)
        if profile_name:
            query = query.where(Profile.name == profile_name)
        result = await db.execute(query)
        rows = result.all()
        if not rows:
            return None
        if profile_name:
            return rows[0][1]
        # Return highest priority profile
        rows.sort(key=lambda r: r[0].priority, reverse=True)
        return rows[0][1]

    async def resolve_user_api_key(
        self, db: AsyncSession, user_id: UUID
    ) -> Optional[str]:
        """Resolve the active API key for a user. Decrypt with Fernet."""
        result = await db.execute(
            select(UserApiKey).where(
                UserApiKey.user_id == user_id,
                UserApiKey.is_active == True,
            ).limit(1)
        )
        key_obj = result.scalar_one_or_none()
        if not key_obj:
            return None
        # SECURITY: Cache Fernet instance to avoid recreating on every request
        if not hasattr(self, '_fernet'):
            from cryptography.fernet import Fernet
            self._fernet = Fernet(settings.fernet_key.encode())
        return self._fernet.decrypt(key_obj.encrypted_key.encode()).decode()

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
                model_name="qwen3-14b",
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

        # 1. Resolve system prompt, model, profile
        full_prompt, model_name, resolved_profile, temperature, max_tokens = (
            await self.get_system_prompt(
                db,
                user_uuid,
                agent_template_name,
                profile_name=profile_name,
            )
        )
        session_obj = await self._ensure_session(db, user_uuid, conversation_id, agent_template_name)
        if resolved_profile:
            session_obj.profile_name = resolved_profile

        # 2. Resolve user's API key (fallback to shared key)
        user_api_key = await self.resolve_user_api_key(db, user_uuid)

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

        # 5. Call LLM
        response_text = await self._call_llm(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=user_api_key,
        )

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
            tokens_used=self._estimate_tokens(response_text),
        )
        db.add(assistant_msg)
        await db.flush()

        latency = (time.time() - start_time) * 1000

        return {
            "content": response_text,
            "message_id": str(assistant_msg.id),
            "tokens_used": assistant_msg.tokens_used,
            "latency_ms": latency,
            "model": model_name,
            "profile_name": resolved_profile,
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

        # 1. Resolve system prompt, model, profile
        full_prompt, model_name, resolved_profile, temperature, max_tokens = (
            await self.get_system_prompt(
                db,
                user_uuid,
                agent_template_name,
                profile_name=profile_name,
            )
        )
        session_obj = await self._ensure_session(db, user_uuid, conversation_id, agent_template_name)
        if resolved_profile:
            session_obj.profile_name = resolved_profile

        # 2. Resolve user's API key
        user_api_key = await self.resolve_user_api_key(db, user_uuid)

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

        # 6. Stream LLM response
        full_response = ""
        assistant_msg_id = str(uuid4())

        async for chunk in self._call_llm_stream(
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

        # 7. Save assistant message after streaming completes
        assistant_msg = Message(
            id=UUID(assistant_msg_id),
            session_id=user_msg.session_id,
            role="assistant",
            content=full_response,
            tokens_used=self._estimate_tokens(full_response),
        )
        db.add(assistant_msg)
        await db.flush()

        # Final event
        yield {
            "type": "done",
            "message_id": assistant_msg_id,
            "tokens_used": assistant_msg.tokens_used,
            "model": model_name,
            "profile_name": resolved_profile,
            "conversation_id": str(user_msg.session_id),
        }

    async def _call_llm(
        self,
        messages: list,
        model: str,
        temperature: float,
        max_tokens: int,
        api_key: Optional[str] = None,
    ) -> str:
        """Call the configured LLM provider."""
        if settings.is_mock:
            return self._mock_response(messages)

        if settings.is_minimax:
            return await self._call_minimax(messages, model, temperature, max_tokens, api_key)

        if settings.is_openai:
            return await self._call_openai(messages, model, temperature, max_tokens, api_key)

        if settings.is_ollama:
            return await self._call_ollama(messages, model, temperature)

        return self._mock_response(messages)

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
    ) -> str:
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
            return response.json()["choices"][0]["message"]["content"]

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
    ) -> str:
        """Call OpenAI-compatible API."""
        auth_key = api_key or settings.openai_api_key
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {auth_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

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
                "https://api.openai.com/v1/chat/completions",
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
    ) -> str:
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
            return response.json()["message"]["content"]

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
