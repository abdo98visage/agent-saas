"""
WebSocket endpoint for real-time chat streaming.
Replaces SSE with bidirectional WebSocket connection.
Includes heartbeat for online status tracking and activity logging.
"""
import asyncio
import json
import logging
import time
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from sqlalchemy import select, update, func

from app.core.config import settings
from app.core.db import async_session
from app.core.security import decode_access_token
from app.api.auth import consume_ws_ticket
from app.models.user import User
from app.models.session import Session
from app.models.message import Message
from app.models.user_activity import UserActivity
from app.models.agent_run import AgentRun, AgentRunEvent
from app.services.agent_service import AgentService
from app.services.hermes_orchestrator import hermes_orchestrator
from app.services.pricing_service import pricing_service
from app.services.token_tracker import (
    check_request_quota,
    check_token_quota,
    release_token_reservation,
    reserve_token_quota,
    reserve_request_quota,
    settle_token_reservation,
    TokenQuotaExceeded,
)
from app.services.presence_service import presence_service
from app.services.attachments import normalize_image_attachments, persist_image_attachments

router = APIRouter()
agent_service = AgentService()
logger = logging.getLogger("fqsaas.websocket")
READ_ONLY_COWORK_TOOLS = {"list_files", "search_files", "read_file", "read_multiple_files"}
ALL_COWORK_TOOLS = READ_ONLY_COWORK_TOOLS | {"propose_patch"}
MAX_COWORK_STEPS = 8
CLIENT_EVENT_TIMEOUT_SECONDS = 300


async def _reserve_cowork_token_quota(
    user: "WebSocketUser",
    conversation_id: str,
    agent_template_name: str,
    profile_name: Optional[str],
    user_message: str,
    project_context: Optional[str],
) -> str:
    async with async_session() as db:
        full_prompt, _model, _resolved, _temperature, max_tokens = await agent_service.get_system_prompt(
            db,
            user.id,
            agent_template_name,
            profile_name=profile_name,
        )
        profile = await agent_service.resolve_user_profile(db, user.id, profile_name=profile_name)
        provider, _api_key, api_key_id = await agent_service._resolve_runtime_provider_and_key(
            db,
            user.id,
            profile,
        )
        history_result = await db.execute(
            select(Message)
            .join(Session, Session.id == Message.session_id)
            .where(
                Session.user_id == user.id,
                Session.id == UUID(conversation_id),
            )
            .order_by(Message.created_at.desc())
            .limit(20)
        )
        messages = [{"role": "system", "content": full_prompt}]
        messages.extend(
            {"role": message.role, "content": message.content}
            for message in reversed(history_result.scalars().all())
        )
        if project_context:
            messages.append({"role": "system", "content": project_context})
        messages.append({"role": "user", "content": user_message})
        requested_tokens = agent_service._reservation_tokens(
            messages,
            max_tokens,
            runtime_overhead_tokens=settings.hermes_runtime_reservation_overhead_tokens,
        ) * MAX_COWORK_STEPS
        return await reserve_token_quota(
            user_id=str(user.id),
            user_daily_limit=user.max_tokens_per_day,
            requested_tokens=requested_tokens,
            provider=provider,
            profile_id=str(profile.id) if profile else None,
            profile_daily_limit=profile.max_tokens_per_day if profile else None,
            api_key_id=str(api_key_id) if api_key_id else None,
        )


def _profile_cowork_tools(profile) -> set[str]:
    configured = {str(item).strip().lower() for item in (profile.allowed_tools or []) if str(item).strip()}
    explicit = configured & ALL_COWORK_TOOLS
    if explicit:
        return explicit
    if configured & {"documents", "document", "spreadsheets", "workspace", "files", "cowork"}:
        return set(ALL_COWORK_TOOLS)
    # Backward-compatible legacy profiles remain usable, but all writes still
    # require an explicit server-enforced approval below.
    return set(ALL_COWORK_TOOLS) if not configured else set()


def _profile_requires_approval(profile, tool_name: str) -> bool:
    configured = {
        str(item).strip().lower()
        for item in (profile.approval_required_tools or [])
        if str(item).strip()
    }
    return tool_name in configured or bool(
        configured & {"documents", "document", "workspace", "files", "cowork"}
    )


def _debug_log(event: str, **payload):
    print(json.dumps({"debug_event": event, **payload}, ensure_ascii=False), flush=True)


def _canonicalize_apply_changes(changes: list[dict] | None) -> str:
    normalized: list[dict] = []
    for change in changes or []:
        normalized.append(
            {
                "action": str(change.get("action") or ""),
                "path": str(change.get("path") or ""),
                "new_path": str(change.get("new_path") or ""),
                "content": str(change.get("content") or ""),
            }
        )
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


def _last_successful_apply_signature(transcript: list[dict]) -> str | None:
    for index in range(len(transcript) - 1, 0, -1):
        current = transcript[index]
        previous = transcript[index - 1]
        if current.get("type") != "apply_result" or previous.get("type") != "apply_request":
            continue
        if not current.get("ok"):
            continue
        return _canonicalize_apply_changes(previous.get("changes") or [])
    return None


@dataclass(frozen=True)
class WebSocketUser:
    id: UUID
    email: str
    full_name: str | None
    department: str | None
    role: str
    is_active: bool
    is_activated: bool
    max_requests_per_day: int
    max_tokens_per_day: int


async def get_websocket_user(token: str, app=None) -> Optional[WebSocketUser]:
    """Extract user from WebSocket query token."""
    payload = decode_access_token(token)
    if not payload:
        return None
    if payload.get("purpose") != "ws":
        return None
    ticket_id = payload.get("jti")
    if not ticket_id or app is None:
        return None
    if not await consume_ws_ticket(app, ticket_id):
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            return None
        if int(payload.get("ver", 0)) != int(user.token_version or 0):
            return None
        return WebSocketUser(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            department=user.department,
            role=user.role,
            is_active=user.is_active,
            is_activated=user.is_activated,
            max_requests_per_day=user.max_requests_per_day,
            max_tokens_per_day=user.max_tokens_per_day,
        )


async def log_user_activity(user_id: UUID, action: str, details: dict = None, session_id: UUID = None):
    """Log user activity for real-time monitoring."""
    async with async_session.begin() as db:
        activity = UserActivity(
            user_id=user_id,
            action=action,
            details=details or {},
            session_id=session_id,
        )
        db.add(activity)


async def update_last_seen(user_id: UUID):
    """Update user's last_seen_at timestamp for online status."""
    async with async_session.begin() as db:
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_seen_at=datetime.utcnow())
        )


def _normalize_workspace_payload(msg: dict) -> dict:
    workspace = msg.get("workspace") or {}
    root_name = str(workspace.get("root_name") or "").strip()
    root_path = str(workspace.get("root_path") or "").strip()
    selected_files = workspace.get("selected_files") or []
    file_paths = workspace.get("file_paths") or []
    if not isinstance(selected_files, list):
        selected_files = []
    if not isinstance(file_paths, list):
        file_paths = []
    return {
        "root_name": root_name[:200],
        "root_path": root_path[:1000],
        "selected_files": [str(item)[:500] for item in selected_files[:100] if item],
        "file_paths": [str(item)[:500] for item in file_paths[:200] if item],
    }


def _normalize_attachments_payload(msg: dict) -> list[dict]:
    return normalize_image_attachments(msg.get("attachments") or [])


def _has_workspace_context(workspace: dict) -> bool:
    return bool(workspace.get("root_name") or workspace.get("root_path") or workspace.get("selected_files") or workspace.get("file_paths"))


def _cowork_match_phrases(user_message: str, workspace: dict) -> list[str]:
    if not _has_workspace_context(workspace):
        return []

    normalized = str(user_message or "").strip().lower()
    if not normalized:
        return []

    explicit_file_operations = [
        "create file", "edit file", "update file", "rewrite file", "append to file",
        "rename file", "delete file", "save file", "write file", "read file",
        "list files", "show files", "what files", "what folders", "open file",
        "file", "files", "folder", "folders", "directory",
        "انشئ ملف", "أنشئ ملف", "عدل ملف", "عدّل ملف", "حدث ملف", "حدّث ملف",
        "احذف ملف", "غيّر اسم", "غير اسم", "اقرأ ملف", "افتح ملف",
        "اعرض الملفات", "أعرض الملفات", "ما هي الملفات", "ما الملفات",
        "قائمة الملفات", "ملفات المشروع", "ما الموجود في المجلد",
        "ملف", "ملفات", "مجلد", "مجلدات",
    ]

    return [phrase for phrase in explicit_file_operations if phrase in normalized]


def _should_use_cowork_mode(user_message: str, workspace: dict) -> bool:
    return bool(_cowork_match_phrases(user_message, workspace))


def _effective_project_context(project_context: Optional[str], workspace: dict, workspace_supplied: bool) -> Optional[str]:
    parts: list[str] = [
        "\n".join(
            [
                "Desktop messaging rule:",
                "The employee's latest user message is the primary request and may be written in Arabic or English.",
                "Treat that message as valid text unless it visibly contains broken replacement characters such as � or obvious mojibake.",
                "Do not claim that the message is garbled, encoded incorrectly, or unreadable unless those broken characters are actually present.",
            ]
        )
    ]
    if workspace_supplied:
        root_name = str(workspace.get("root_name") or "").strip()
        root_path = str(workspace.get("root_path") or "").strip()
        selected_files = workspace.get("selected_files") or []
        file_paths = workspace.get("file_paths") or []
        if root_name:
            workspace_lines = [
                f"Desktop active project root: {root_name}",
                "Treat this desktop project as the employee's current project.",
                "Do not substitute Hermes runtime folders or internal agent directories for the employee's project.",
            ]
            if root_path:
                workspace_lines.insert(1, f"Desktop active project path: {root_path}")
            parts.append("\n".join(workspace_lines))
        else:
            parts.append(
                "\n".join(
                    [
                        "No desktop project is currently selected.",
                        "If asked where you are or what project is open, state that no desktop project is attached instead of inspecting Hermes internal folders.",
                    ]
                )
            )
        if selected_files:
            parts.append(
                "Desktop selected files (highest-priority context): "
                f"{json.dumps(selected_files[:20], ensure_ascii=False)}"
            )
        if file_paths:
            limited_paths = file_paths[:20]
            parts.append(
                "Desktop visible project files snapshot (truncated): "
                f"{json.dumps(limited_paths, ensure_ascii=False)}"
            )
    if project_context:
        parts.append(project_context)
    merged = "\n\n".join(part for part in parts if part)
    return merged or None


async def _save_run_event(db, run_id: UUID, event_type: str, payload: dict):
    db.add(AgentRunEvent(run_id=run_id, event_type=event_type, payload=payload))
    await db.flush()


async def _fail_active_cowork_run(user_id: UUID, conversation_id: str, exc: Exception) -> None:
    try:
        session_id = UUID(conversation_id)
    except ValueError:
        return
    async with async_session.begin() as db:
        result = await db.execute(
            select(AgentRun)
            .where(
                AgentRun.user_id == user_id,
                AgentRun.session_id == session_id,
                AgentRun.status == "running",
            )
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        )
        run = result.scalar_one_or_none()
        if run:
            await agent_service._finish_run(
                db,
                run,
                "failed",
                0,
                error_code=exc.__class__.__name__,
                error_message=str(exc)[:2000],
            )


async def _wait_for_client_event(websocket: WebSocket, user: WebSocketUser, allowed_types: set[str]) -> dict:
    while True:
        try:
            raw = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=CLIENT_EVENT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Timed out waiting for the desktop client") from exc
        if len(raw.encode("utf-8")) > settings.websocket_max_message_bytes:
            await websocket.send_json({"type": "error", "detail": "Message too large"})
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
            continue

        msg_type = msg.get("type", "message")
        if msg_type == "ping":
            await websocket.send_json({"type": "pong"})
            await update_last_seen(user.id)
            continue
        if msg_type == "heartbeat":
            await websocket.send_json({"type": "heartbeat_ack", "online": True})
            await presence_service.heartbeat(user.id)
            await update_last_seen(user.id)
            continue
        if msg_type not in allowed_types:
            await websocket.send_json({"type": "error", "detail": f"Unexpected message type while awaiting cowork result: {msg_type}"})
            continue
        return msg


async def _run_cowork_loop(
    websocket: WebSocket,
    user: WebSocketUser,
    active_conversation_id: str,
    agent_template_name: str,
    user_message: str,
    project_context: Optional[str],
    effective_profile_name: Optional[str],
    workspace: dict,
    approval_mode: str,
    attachments: list[dict],
    client_message_id: Optional[UUID],
) -> dict:
    run_started_at = time.monotonic()
    async with async_session() as db:
        user_obj = await agent_service._get_user(db, user.id)
        _, model_name, resolved_profile, _temperature, _max_tokens = await agent_service.get_system_prompt(
            db,
            user.id,
            agent_template_name,
            profile_name=effective_profile_name,
        )
        profile = await agent_service.resolve_user_profile(db, user.id, profile_name=effective_profile_name)
        allowed_cowork_tools = _profile_cowork_tools(profile)
        effective_provider, api_key, _api_key_id = await agent_service._resolve_runtime_provider_and_key(db, user.id, profile)
        await agent_service._enforce_profile_ready(profile, effective_provider)
        await agent_service._enforce_profile_request_limit(db, profile)
        await agent_service._enforce_profile_usage_limits(db, profile)
        session_obj = await agent_service._ensure_session(db, user.id, active_conversation_id, agent_template_name)
        if resolved_profile:
            session_obj.profile_name = resolved_profile
        if profile:
            session_obj.profile_id = profile.id
            session_obj.profile_version = profile.version

        history_result = await db.execute(
            select(Message)
            .where(Message.session_id == session_obj.id)
            .order_by(Message.created_at.desc())
            .limit(20)
        )
        conversation_history = [
            {"role": message.role, "content": message.content}
            for message in reversed(history_result.scalars().all())
        ]

        user_message_id = uuid4()
        stored_attachments = await asyncio.to_thread(
            persist_image_attachments,
            attachments,
            user.id,
            session_obj.id,
            user_message_id,
        )
        user_msg = Message(
            id=user_message_id,
            session_id=session_obj.id,
            role="user",
            content=user_message,
            project_context=project_context,
            attachments=stored_attachments,
            client_message_id=client_message_id,
        )
        db.add(user_msg)
        await db.flush()

        run = await agent_service._create_run(db, session_obj, user.id, profile, "hermes", model_name, effective_provider)
        await _save_run_event(
            db,
            run.id,
            "cowork_user_message",
            {
                "type": "cowork_user_message",
                "content": user_message,
                "workspace": workspace,
                "profile_name": resolved_profile,
            },
        )
        await db.commit()

        transcript: list[dict] = []
        final_content = ""
        total_cost = 0.0
        output_tokens = 0
        input_tokens = 0
        approval_granted_for_message = False

        for _step in range(MAX_COWORK_STEPS):
            payload = {
                "employee": {
                    "id": str(user_obj.id),
                    "email": user_obj.email,
                    "full_name": user_obj.full_name,
                    "department": user_obj.department,
                },
                "profile": {
                    "id": str(profile.id),
                    "slug": profile.slug,
                    "name": profile.name,
                    "version": profile.version,
                    "hermes_profile_id": profile.hermes_profile_id,
                    "runtime_toolsets": profile.runtime_toolsets,
                },
                "session_id": str(session_obj.id),
                "history": conversation_history,
                "message": user_message,
                "project_context": project_context,
                "attachments": attachments,
                "provider": effective_provider,
                "model": model_name,
                "api_key": api_key,
                "workspace": workspace,
                "cowork": {
                    "protocol": "cowork_v1",
                    "allowed_tools": sorted(allowed_cowork_tools),
                    "transcript": transcript,
                },
            }
            result = await hermes_orchestrator.run_agent(payload)
            event_type = result.get("type") or "assistant_final"
            usage = result.get("usage") or {}
            total_cost += float(result.get("total_cost", 0.0) or 0.0)
            output_tokens += int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
            input_tokens += int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)

            async with async_session() as event_db:
                await _save_run_event(event_db, run.id, event_type, result)
                await event_db.commit()

            if event_type == "tool_request":
                request_id = result.get("request_id") or str(uuid4())
                tool_name = result.get("tool") or ""
                if tool_name not in READ_ONLY_COWORK_TOOLS or tool_name not in allowed_cowork_tools:
                    raise RuntimeError(f"Unsupported cowork tool requested by the smart agent: {tool_name}")
                tool_event = {
                    "type": "tool_request",
                    "request_id": request_id,
                    "tool": tool_name,
                    "args": result.get("args") or {},
                }
                await websocket.send_json(tool_event)
                tool_result = await _wait_for_client_event(websocket, user, {"tool_result"})
                if tool_result.get("request_id") != request_id:
                    raise RuntimeError("Tool result request_id mismatch")
                transcript.append(tool_event)
                transcript.append({
                    "type": "tool_result",
                    "request_id": request_id,
                    "tool": tool_name,
                    "ok": bool(tool_result.get("ok")),
                    "result": tool_result.get("result"),
                    "error": tool_result.get("error"),
                })
                async with async_session() as event_db:
                    await _save_run_event(event_db, run.id, "tool_result", transcript[-1])
                    await event_db.commit()
                continue

            if event_type == "apply_request":
                request_id = result.get("request_id") or str(uuid4())
                if "propose_patch" not in allowed_cowork_tools:
                    raise RuntimeError("This profile is not allowed to modify workspace files")
                current_apply_signature = _canonicalize_apply_changes(result.get("changes") or [])
                previous_apply_signature = _last_successful_apply_signature(transcript)
                if previous_apply_signature and previous_apply_signature == current_apply_signature:
                    final_content = result.get("summary") or "تم تطبيق التعديلات المحلية المطلوبة بنجاح."
                    async with async_session() as event_db:
                        await _save_run_event(
                            event_db,
                            run.id,
                            "assistant_final",
                            {
                                "type": "assistant_final",
                                "content": final_content,
                                "deduplicated_repeated_apply_request": True,
                            },
                        )
                        await event_db.commit()
                    result = {"type": "assistant_final", "content": final_content}
                    event_type = "assistant_final"
                else:
                    require_approval = (
                        _profile_requires_approval(profile, "propose_patch")
                        or not approval_granted_for_message
                    )
                    approval_event = None
                    if require_approval:
                        approval_event = {
                            "type": "approval_required",
                            "request_id": request_id,
                            "title": "Apply proposed workspace changes?",
                            "summary": result.get("summary") or "The smart agent proposed local workspace changes.",
                        }
                        await websocket.send_json(approval_event)
                    apply_event = {
                        "type": "apply_request",
                        "request_id": request_id,
                        "mode": result.get("mode") or "workspace_changes",
                        "summary": result.get("summary") or "Apply proposed workspace changes",
                        "changes": result.get("changes") or [],
                        "require_approval": require_approval,
                        "approval_mode": "ask_for_approval" if require_approval else "approved_for_message",
                    }
                    await websocket.send_json(apply_event)
                    apply_result = await _wait_for_client_event(websocket, user, {"apply_result"})
                    if apply_result.get("request_id") != request_id:
                        raise RuntimeError("Apply result request_id mismatch")
                    if bool(apply_result.get("ok")) and require_approval and bool((apply_result.get("result") or {}).get("approved")):
                        approval_granted_for_message = True
                    transcript.append(apply_event)
                    transcript.append({
                        "type": "apply_result",
                        "request_id": request_id,
                        "ok": bool(apply_result.get("ok")),
                        "result": apply_result.get("result"),
                        "error": apply_result.get("error"),
                    })
                    async with async_session() as event_db:
                        if approval_event:
                            await _save_run_event(event_db, run.id, "approval_required", approval_event)
                        await _save_run_event(event_db, run.id, "apply_result", transcript[-1])
                        await event_db.commit()
                    continue

            final_content = (result.get("content") or "").strip()
            if final_content:
                await websocket.send_json({
                    "type": "assistant_chunk",
                    "content": final_content,
                })
            assistant_msg = Message(
                id=uuid4(),
                session_id=session_obj.id,
                role="assistant",
                content=final_content,
                tokens_used=output_tokens or agent_service._estimate_tokens(final_content),
            )
            async with async_session() as final_db:
                persisted_run = await final_db.get(AgentRun, run.id)
                effective_input_tokens = input_tokens or agent_service._estimate_tokens(
                    "\n".join(part for part in [user_message, project_context or ""] if part)
                )
                effective_output_tokens = output_tokens or assistant_msg.tokens_used
                cost_calc = await pricing_service.calculate_cost(
                    final_db,
                    result.get("provider") or settings.llm_provider,
                    input_tokens=effective_input_tokens,
                    output_tokens=effective_output_tokens,
                    fallback_cost=total_cost,
                )
                final_db.add(assistant_msg)
                await final_db.flush()
                await agent_service._finish_run(
                    final_db,
                    persisted_run,
                    "completed",
                    int((time.monotonic() - run_started_at) * 1000),
                    output_tokens=effective_output_tokens,
                    input_tokens=effective_input_tokens,
                    total_cost=cost_calc.total_cost,
                    tools_used=["hermes-agent", *sorted({item["tool"] for item in transcript if item.get("type") == "tool_request"})],
                    mcp_servers_used=[],
                    pricing_snapshot=cost_calc.pricing_snapshot,
                )
                await final_db.commit()
            return {
                "message_id": str(assistant_msg.id),
                "tokens_used": effective_input_tokens + effective_output_tokens,
                "input_tokens": effective_input_tokens,
                "output_tokens": effective_output_tokens,
                "total_tokens": effective_input_tokens + effective_output_tokens,
                "model": model_name,
                "provider": effective_provider,
                "profile_name": resolved_profile,
                "profile_id": str(profile.id) if profile else None,
                "total_cost": cost_calc.total_cost,
                "pricing_snapshot": cost_calc.pricing_snapshot,
                "conversation_id": str(session_obj.id),
            }

        async with async_session() as failed_db:
            persisted_run = await failed_db.get(AgentRun, run.id)
            await agent_service._finish_run(
                failed_db,
                persisted_run,
                "failed",
                int((time.monotonic() - run_started_at) * 1000),
                output_tokens=output_tokens,
                input_tokens=input_tokens,
                total_cost=total_cost,
                tools_used=["hermes-agent"],
                mcp_servers_used=[],
                error_code="CoworkStepLimit",
                error_message="Cowork step limit exceeded before final assistant response",
            )
            await failed_db.commit()
        raise RuntimeError("Cowork step limit exceeded before final assistant response")


@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Bearer token"),
    conversation_id: Optional[str] = Query(None),
    agent_template_name: str = Query("default"),
    profile_name: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for real-time chat.

    Client sends JSON:
      {"type": "message", "content": "...", "project_context": "..."}

    Server sends JSON:
      {"type": "start", "conversation_id": "..."}
      {"type": "chunk", "content": "...", "message_id": "..."}
      {"type": "done", "message_id": "...", "tokens_used": N, "model": "...", "profile_name": "..."}
      {"type": "error", "detail": "..."}
    """
    # 1. Authenticate
    user = await get_websocket_user(token, websocket.app)
    if not user:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await websocket.accept()

    # Check account status
    if not user.is_activated:
        await websocket.send_json({"type": "error", "detail": "حسابك غير مفعل. قم بتفعيل الحساب من خلال كود الدعوة."})
        await websocket.close()
        return
    if not user.is_active:
        await websocket.send_json({"type": "error", "detail": "حسابك معطل. تواصل مع الإدارة."})
        await websocket.close()
        return

    # Log connection + update online status
    await presence_service.connect(user.id)
    await update_last_seen(user.id)
    await log_user_activity(user.id, "ws_connected", details={"agent_template": agent_template_name})

    # 2. Resolve existing conversation if one was provided.
    active_conversation_id = conversation_id

    async with async_session.begin() as db:
        # Quota check
        quota_ok = await check_request_quota(db, str(user.id), user.max_requests_per_day)
        if not quota_ok:
            await websocket.send_json({"type": "error", "detail": "Daily request quota exceeded"})
            await websocket.close()
            return

        if conversation_id:
            try:
                c_id = UUID(conversation_id)
                result = await db.execute(
                    select(Session).where(
                        Session.id == c_id,
                        Session.user_id == user.id,
                    )
                )
                if not result.scalar_one_or_none():
                    conversation_id = None
            except ValueError:
                conversation_id = None

    # 3. Main message loop
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            if len(data.encode("utf-8")) > settings.websocket_max_message_bytes:
                await websocket.send_json({"type": "error", "detail": "Message too large"})
                continue
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            msg_type = msg.get("type", "message")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                await update_last_seen(user.id)
                continue

            if msg_type == "heartbeat":
                await websocket.send_json({"type": "heartbeat_ack", "online": True})
                await presence_service.heartbeat(user.id)
                await update_last_seen(user.id)
                continue

            if msg_type not in {"message", "user_message"}:
                await websocket.send_json({"type": "error", "detail": f"Unknown message type: {msg_type}"})
                continue

            requested_conversation_id = msg.get("conversation_id") if "conversation_id" in msg else active_conversation_id
            async with async_session.begin() as db:
                if requested_conversation_id:
                    try:
                        requested_uuid = UUID(requested_conversation_id)
                    except ValueError:
                        await websocket.send_json({"type": "error", "detail": "Invalid conversation_id"})
                        continue

                    result = await db.execute(
                        select(Session).where(
                            Session.id == requested_uuid,
                            Session.user_id == user.id,
                        )
                    )
                    if not result.scalar_one_or_none():
                        await websocket.send_json({"type": "error", "detail": "Conversation not found"})
                        continue
                else:
                    new_session = Session(
                        id=uuid4(),
                        user_id=user.id,
                        agent_template_name=agent_template_name,
                    )
                    db.add(new_session)
                    await db.flush()
                    requested_conversation_id = str(new_session.id)

            active_conversation_id = requested_conversation_id
            user_message = msg.get("content", "").strip()
            raw_client_message_id = msg.get("client_message_id")
            client_message_id = None
            if raw_client_message_id:
                try:
                    client_message_id = UUID(str(raw_client_message_id))
                except ValueError:
                    await websocket.send_json({
                        "type": "error",
                        "detail": "Invalid client_message_id",
                        "client_message_id": str(raw_client_message_id),
                    })
                    continue
            project_context = msg.get("project_context")
            effective_profile_name = msg.get("profile_name") or profile_name
            approval_mode = str(msg.get("approval_mode") or "ask_for_approval").strip()
            if approval_mode not in {"ask_for_approval", "approve_for_me", "full_access"}:
                approval_mode = "ask_for_approval"
            # The desktop value is a UX preference only. It must never expand
            # the profile policy or bypass server-side write approval.
            approval_mode = "ask_for_approval"
            workspace = _normalize_workspace_payload(msg)
            try:
                attachments = _normalize_attachments_payload(msg)
            except ValueError as exc:
                await websocket.send_json({"type": "error", "detail": str(exc)})
                continue
            cowork_matches = _cowork_match_phrases(user_message, workspace)
            has_workspace = _has_workspace_context(workspace)
            effective_project_context = _effective_project_context(
                project_context=project_context,
                workspace=workspace,
                workspace_supplied="workspace" in msg,
            )

            if not user_message:
                await websocket.send_json({
                    "type": "error",
                    "detail": "Empty message",
                    "client_message_id": str(client_message_id) if client_message_id else None,
                })
                continue

            if client_message_id:
                async with async_session.begin() as db:
                    duplicate_result = await db.execute(
                        select(Message).where(
                            Message.session_id == UUID(active_conversation_id),
                            Message.role == "user",
                            Message.client_message_id == client_message_id,
                        )
                    )
                    duplicate_user_message = duplicate_result.scalar_one_or_none()
                    duplicate_assistant_message = None
                    if duplicate_user_message:
                        assistant_result = await db.execute(
                            select(Message)
                            .where(
                                Message.session_id == duplicate_user_message.session_id,
                                Message.role == "assistant",
                                Message.created_at >= duplicate_user_message.created_at,
                            )
                            .order_by(Message.created_at.asc())
                            .limit(1)
                        )
                        duplicate_assistant_message = assistant_result.scalar_one_or_none()
                if duplicate_user_message:
                    if duplicate_assistant_message:
                        await websocket.send_json({
                            "type": "done",
                            "message_id": str(duplicate_assistant_message.id),
                            "tokens_used": duplicate_assistant_message.tokens_used or 0,
                            "conversation_id": active_conversation_id,
                            "client_message_id": str(client_message_id),
                            "replayed": True,
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "detail": "The previous request with this id is still incomplete",
                            "client_message_id": str(client_message_id),
                            "retryable": True,
                        })
                    continue

            async with async_session.begin() as db:
                if not await reserve_request_quota(db, str(user.id), user.max_requests_per_day):
                    await websocket.send_json({
                        "type": "error",
                        "detail": "Daily request quota exceeded",
                        "client_message_id": str(client_message_id) if client_message_id else None,
                    })
                    continue
                if not await check_token_quota(db, str(user.id), user.max_tokens_per_day, provider=settings.llm_provider):
                    await websocket.send_json({
                        "type": "error",
                        "detail": "Daily token quota exceeded",
                        "client_message_id": str(client_message_id) if client_message_id else None,
                    })
                    continue

            # Send start event
            await websocket.send_json({
                "type": "start",
                "conversation_id": active_conversation_id,
                "client_message_id": str(client_message_id) if client_message_id else None,
            })
            async with async_session.begin() as db:
                resolved_profile_obj = await agent_service.resolve_user_profile(
                    db,
                    user.id,
                    profile_name=effective_profile_name,
                )

            use_cowork = bool(
                resolved_profile_obj
                and resolved_profile_obj.runtime_type == "hermes"
                and _should_use_cowork_mode(user_message, workspace)
                and not attachments
            )
            force_direct_runtime = False
            _debug_log(
                "ws_route_decision",
                user_id=str(user.id),
                conversation_id=active_conversation_id,
                runtime_type=getattr(resolved_profile_obj, "runtime_type", None),
                profile_name=effective_profile_name,
                has_workspace=has_workspace,
                cowork_matches=cowork_matches,
                use_cowork=use_cowork,
                force_direct_runtime=force_direct_runtime,
                user_message_length=len(user_message),
            )

            if use_cowork:
                cowork_reservation_id = None
                try:
                    cowork_reservation_id = await _reserve_cowork_token_quota(
                        user,
                        active_conversation_id,
                        agent_template_name,
                        effective_profile_name,
                        user_message,
                        effective_project_context,
                    )
                    cowork_done_payload = await _run_cowork_loop(
                        websocket=websocket,
                        user=user,
                        active_conversation_id=active_conversation_id,
                        agent_template_name=agent_template_name,
                        user_message=user_message,
                        project_context=effective_project_context,
                        effective_profile_name=effective_profile_name,
                        workspace=workspace,
                        approval_mode=approval_mode,
                        attachments=attachments,
                        client_message_id=client_message_id,
                    )
                except asyncio.CancelledError:
                    if cowork_reservation_id:
                        await release_token_reservation(cowork_reservation_id)
                    raise
                except TokenQuotaExceeded:
                    await websocket.send_json({
                        "type": "error",
                        "detail": "Daily token quota exceeded",
                        "client_message_id": str(client_message_id) if client_message_id else None,
                    })
                    continue
                except Exception as e:
                    if cowork_reservation_id:
                        await release_token_reservation(cowork_reservation_id)
                    await _fail_active_cowork_run(user.id, active_conversation_id, e)
                    error_id = str(uuid4())
                    logger.exception("Cowork run failed error_id=%s", error_id)
                    await websocket.send_json({
                        "type": "error",
                        "detail": f"Agent request failed. Reference: {error_id}",
                        "client_message_id": str(client_message_id) if client_message_id else None,
                    })
                    continue

                await settle_token_reservation(
                    cowork_reservation_id,
                    model=cowork_done_payload.get("model", ""),
                    actual_tokens=int(cowork_done_payload.get("tokens_used", 0) or 0),
                    cost=float(cowork_done_payload.get("total_cost", 0.0) or 0.0),
                )

                await websocket.send_json({
                    "type": "done",
                    "client_message_id": str(client_message_id) if client_message_id else None,
                    **cowork_done_payload,
                })

                await log_user_activity(
                    user.id, "message_sent",
                    details={
                        "tokens_used": cowork_done_payload.get("tokens_used", 0),
                        "model": cowork_done_payload.get("model", ""),
                        "profile": cowork_done_payload.get("profile_name", ""),
                        "mode": "cowork",
                    },
                    session_id=UUID(active_conversation_id) if active_conversation_id else None,
                )
                continue

            # Stream LLM response — run_agent_stream handles saving messages internally
            full_response = ""
            assistant_msg_id = str(uuid4())
            model_name = ""
            resolved_profile = ""
            resolved_profile_id = None
            tokens_used = 0
            total_cost = 0.0
            done_payload = None

            try:
                async with async_session.begin() as db:
                    stream = agent_service.run_agent_stream(
                        db=db,
                        user_id=str(user.id),
                        conversation_id=active_conversation_id,
                        user_message=user_message,
                        agent_template_name=agent_template_name,
                        project_context=effective_project_context,
                        profile_name=effective_profile_name,
                        force_direct_runtime=force_direct_runtime,
                        attachments=attachments,
                        client_message_id=client_message_id,
                    )
                    try:
                        async for chunk in stream:
                            event_type = chunk.get("type", "chunk")

                            if event_type == "chunk":
                                assistant_msg_id = chunk.get("message_id") or assistant_msg_id
                                content = chunk.get("content", "")
                                full_response += content
                                await websocket.send_json({
                                    "type": "chunk",
                                    "content": content,
                                    "message_id": assistant_msg_id,
                                    "client_message_id": str(client_message_id) if client_message_id else None,
                                })
                            elif event_type == "done":
                                assistant_msg_id = chunk.get("message_id") or assistant_msg_id
                                model_name = chunk.get("model", "")
                                resolved_profile = chunk.get("profile_name", "")
                                resolved_profile_id = chunk.get("profile_id")
                                tokens_used = chunk.get("tokens_used", 0)
                                total_cost = float(chunk.get("total_cost", 0.0) or 0.0)
                                done_payload = {
                                    "type": "done",
                                    "message_id": assistant_msg_id,
                                    "tokens_used": tokens_used,
                                    "input_tokens": chunk.get("input_tokens", 0),
                                    "output_tokens": chunk.get("output_tokens", 0),
                                    "total_tokens": chunk.get("total_tokens", tokens_used),
                                    "total_cost": total_cost,
                                    "model": model_name,
                                    "provider": chunk.get("provider") or "",
                                    "profile_id": resolved_profile_id,
                                    "profile_name": resolved_profile,
                                    "conversation_id": active_conversation_id,
                                    "client_message_id": str(client_message_id) if client_message_id else None,
                                }
                    finally:
                        await stream.aclose()

                    if done_payload is None:
                        raise RuntimeError("Agent stream completed without a done event")
            except asyncio.CancelledError:
                raise
            except TokenQuotaExceeded:
                await websocket.send_json({
                    "type": "error",
                    "detail": "Daily token quota exceeded",
                    "client_message_id": str(client_message_id) if client_message_id else None,
                })
                continue
            except Exception as e:
                error_id = str(uuid4())
                logger.exception("WebSocket stream failed error_id=%s", error_id)
                await websocket.send_json({
                    "type": "error",
                    "detail": f"Agent request failed. Reference: {error_id}",
                    "client_message_id": str(client_message_id) if client_message_id else None,
                })
                continue

            if done_payload is None:
                done_payload = {
                    "type": "done",
                    "message_id": assistant_msg_id,
                    "tokens_used": tokens_used,
                    "model": model_name,
                    "profile_name": resolved_profile,
                    "conversation_id": active_conversation_id,
                    "client_message_id": str(client_message_id) if client_message_id else None,
                }

            await websocket.send_json(done_payload)

            # Log activity
            await log_user_activity(
                user.id, "message_sent",
                details={"tokens_used": tokens_used, "model": model_name, "profile": resolved_profile},
                session_id=UUID(active_conversation_id) if active_conversation_id else None,
            )

    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception as e:
        error_id = str(uuid4())
        logger.exception("WebSocket handler failed error_id=%s", error_id)
        try:
            await websocket.send_json({"type": "error", "detail": f"Request failed. Reference: {error_id}"})
        except Exception:
            pass
    finally:
        await presence_service.disconnect(user.id)
        await log_user_activity(user.id, "ws_disconnected", details={"agent_template": agent_template_name})
