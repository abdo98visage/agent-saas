"""
WebSocket endpoint for real-time chat streaming.
Replaces SSE with bidirectional WebSocket connection.
Includes heartbeat for online status tracking and activity logging.
"""
import json
from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from sqlalchemy import select, update, func
from datetime import date

from app.core.config import settings
from app.core.db import async_session
from app.core.security import decode_access_token
from app.models.user import User
from app.models.session import Session
from app.models.message import Message
from app.models.kpi import KPI
from app.models.user_activity import UserActivity
from app.services.agent_service import AgentService
from app.services.token_tracker import check_request_quota, check_token_quota, record_token_usage

router = APIRouter()
agent_service = AgentService()


async def get_websocket_user(token: str) -> Optional[User]:
    """Extract user from WebSocket query token."""
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            return None
        return user


async def track_kpi(user_id: str):
    """Track KPI: increment daily messages."""
    today = date.today().isoformat()
    async with async_session() as db:
        result = await db.execute(
            select(KPI).where(KPI.user_id == user_id, KPI.date == today)
        )
        kpi = result.scalar_one_or_none()
        if kpi:
            kpi.messages_sent += 1
        else:
            kpi = KPI(user_id=user_id, date=today, messages_sent=1)
            db.add(kpi)
        await db.commit()


async def log_user_activity(user_id: UUID, action: str, details: dict = None, session_id: UUID = None):
    """Log user activity for real-time monitoring."""
    async with async_session() as db:
        activity = UserActivity(
            user_id=user_id,
            action=action,
            details=details or {},
            session_id=session_id,
        )
        db.add(activity)
        await db.commit()


async def update_last_seen(user_id: UUID):
    """Update user's last_seen_at timestamp for online status."""
    async with async_session() as db:
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_seen_at=datetime.utcnow())
        )
        await db.commit()


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
    user = await get_websocket_user(token)
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
    await update_last_seen(user.id)
    await log_user_activity(user.id, "ws_connected", details={"agent_template": agent_template_name})

    # 2. Resolve or create conversation
    active_conversation_id = conversation_id

    async with async_session() as db:
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

        if not conversation_id:
            new_session = Session(
                id=uuid4(),
                user_id=user.id,
                agent_template_name=agent_template_name,
            )
            db.add(new_session)
            await db.flush()
            active_conversation_id = str(new_session.id)

        await db.commit()

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
                await update_last_seen(user.id)
                continue

            if msg_type != "message":
                await websocket.send_json({"type": "error", "detail": f"Unknown message type: {msg_type}"})
                continue

            user_message = msg.get("content", "").strip()
            project_context = msg.get("project_context")

            if not user_message:
                await websocket.send_json({"type": "error", "detail": "Empty message"})
                continue

            async with async_session() as db:
                if not await check_request_quota(db, str(user.id), user.max_requests_per_day):
                    await websocket.send_json({"type": "error", "detail": "Daily request quota exceeded"})
                    continue
                if not await check_token_quota(db, str(user.id), user.max_tokens_per_day, provider=settings.llm_provider):
                    await websocket.send_json({"type": "error", "detail": "Daily token quota exceeded"})
                    continue

            # Send start event
            await websocket.send_json({
                "type": "start",
                "conversation_id": active_conversation_id,
            })

            # Stream LLM response — run_agent_stream handles saving messages internally
            full_response = ""
            assistant_msg_id = str(uuid4())
            model_name = ""
            resolved_profile = ""
            resolved_profile_id = None
            tokens_used = 0
            total_cost = 0.0

            try:
                async with async_session() as db:
                    async for chunk in agent_service.run_agent_stream(
                        db=db,
                        user_id=str(user.id),
                        conversation_id=active_conversation_id,
                        user_message=user_message,
                        agent_template_name=agent_template_name,
                        project_context=project_context,
                        profile_name=profile_name,
                    ):
                        event_type = chunk.get("type", "chunk")

                        if event_type == "chunk":
                            content = chunk.get("content", "")
                            full_response += content
                            await websocket.send_json({
                                "type": "chunk",
                                "content": content,
                                "message_id": assistant_msg_id,
                            })
                        elif event_type == "done":
                            model_name = chunk.get("model", "")
                            resolved_profile = chunk.get("profile_name", "")
                            resolved_profile_id = chunk.get("profile_id")
                            tokens_used = chunk.get("tokens_used", 0)
                            total_cost = float(chunk.get("total_cost", 0.0) or 0.0)
                            await db.commit()

            except Exception as e:
                await websocket.send_json({"type": "error", "detail": f"Streaming error: {str(e)}"})
                continue

            # Track token usage & KPI (outside the streaming session)
            if tokens_used and model_name:
                async with async_session() as db:
                    await record_token_usage(
                        db,
                        str(user.id),
                        model_name,
                        tokens_used,
                        total_cost,
                        provider=settings.llm_provider,
                        profile_id=resolved_profile_id,
                    )
                    await db.commit()

            await track_kpi(str(user.id))

            # Log activity
            await log_user_activity(
                user.id, "message_sent",
                details={"tokens_used": tokens_used, "model": model_name, "profile": resolved_profile},
                session_id=UUID(active_conversation_id) if active_conversation_id else None,
            )

            # Send done event
            await websocket.send_json({
                "type": "done",
                "message_id": assistant_msg_id,
                "tokens_used": tokens_used,
                "model": model_name,
                "profile_name": resolved_profile,
                "conversation_id": active_conversation_id,
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "detail": str(e)})
        except Exception:
            pass
    finally:
        try:
            await log_user_activity(user.id, "ws_disconnected", details={})
        except Exception:
            pass
