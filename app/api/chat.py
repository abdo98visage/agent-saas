from uuid import UUID, uuid4
from typing import Optional
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.config import settings
from app.core.db import async_session, get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.session import Session
from app.models.message import Message
from app.schemas.chat import ChatMessage
from app.services.agent_service import AgentService
from app.services.token_tracker import (
    check_token_quota,
    reserve_request_quota,
    TokenQuotaExceeded,
)
from app.services.attachments import attachments_for_response, resolve_signed_attachment

router = APIRouter()
agent_service = AgentService()
logger = logging.getLogger("fqsaas.chat")


async def generate_sse(events):
    """Generate SSE (Server-Sent Events) stream."""
    import json
    async for event in events:
        yield f"event: {event.get('type', 'message')}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.get("/attachments/{token}")
async def download_attachment(token: str):
    """Serve a blob only through a short-lived tamper-proof URL."""
    try:
        target = resolve_signed_attachment(token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(target, headers={"Cache-Control": "private, max-age=300"})


@router.post("/message")
async def send_message(
    request: ChatMessage,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a message to the agent (non-streaming)."""
    message = request.message
    conversation_id = str(request.conversation_id) if request.conversation_id else None
    agent_template_name = request.agent_template_name
    project_context = request.project_context
    profile_name = request.profile_name
    attachments = [item.model_dump() for item in request.attachments]

    if not user.is_activated:
        raise HTTPException(status_code=403, detail="Account not activated. Please activate first.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated. Contact admin.")

    if not await reserve_request_quota(db, str(user.id), user.max_requests_per_day):
        raise HTTPException(
            status_code=429,
            detail="Daily request quota exceeded. Contact admin."
        )
    if not await check_token_quota(db, str(user.id), user.max_tokens_per_day):
        raise HTTPException(
            status_code=429,
            detail="Daily token quota exceeded. Contact admin."
        )
    await db.commit()

    # SECURITY: Audit user action
    from app.models.audit_log import AuditLog
    audit = AuditLog(
        user_id=user.id,
        action="send_message",
        details={"conversation_id": conversation_id, "template": agent_template_name, "msg_length": len(message)},
    )
    db.add(audit)

    # Resolve or create conversation
    session_obj = None
    if conversation_id:
        result = await db.execute(
            select(Session).where(
                Session.id == UUID(conversation_id),
                Session.user_id == user.id,
            )
        )
        session_obj = result.scalar_one_or_none()
        if not session_obj:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        session_obj = Session(
            id=uuid4(),
            user_id=user.id,
            agent_template_name=agent_template_name,
        )
        db.add(session_obj)
        await db.flush()

    conversation_id = str(session_obj.id)

    # Call agent
    try:
        result = await agent_service.run_agent(
            db=db,
            user_id=str(user.id),
            conversation_id=conversation_id,
            user_message=message,
            agent_template_name=agent_template_name,
            project_context=project_context,
            profile_name=profile_name,
            attachments=attachments,
        )
    except TokenQuotaExceeded:
        raise HTTPException(status_code=429, detail="Daily token quota exceeded. Contact admin.")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent request")
    except Exception:
        error_id = str(uuid4())
        logger.exception("Agent request failed error_id=%s", error_id)
        raise HTTPException(status_code=500, detail=f"Agent request failed. Reference: {error_id}")

    return {
        "conversation_id": conversation_id,
        "message_id": result.get("message_id"),
        "content": result.get("content", ""),
        "tokens_used": result.get("tokens_used"),
        "model": result.get("model"),
        "profile_name": result.get("profile_name"),
        "attachments": result.get("attachments", []),
        "citations": result.get("citations", []),
    }


@router.post("/message/stream")
async def send_message_stream(
    request: ChatMessage,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a message to the agent with SSE streaming response."""
    message = request.message
    conversation_id = str(request.conversation_id) if request.conversation_id else None
    agent_template_name = request.agent_template_name
    project_context = request.project_context
    profile_name = request.profile_name
    attachments = [item.model_dump() for item in request.attachments]

    if not user.is_activated:
        raise HTTPException(status_code=403, detail="Account not activated. Please activate first.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated. Contact admin.")

    if not await reserve_request_quota(db, str(user.id), user.max_requests_per_day):
        raise HTTPException(
            status_code=429,
            detail="Daily request quota exceeded. Contact admin."
        )
    if not await check_token_quota(db, str(user.id), user.max_tokens_per_day):
        raise HTTPException(
            status_code=429,
            detail="Daily token quota exceeded. Contact admin."
        )
    await db.commit()

    # SECURITY: Audit user action
    from app.models.audit_log import AuditLog
    audit = AuditLog(
        user_id=user.id,
        action="send_message_stream",
        details={"conversation_id": conversation_id, "template": agent_template_name},
    )
    db.add(audit)

    # Resolve or create conversation
    session_obj = None
    if conversation_id:
        result = await db.execute(
            select(Session).where(
                Session.id == UUID(conversation_id),
                Session.user_id == user.id,
            )
        )
        session_obj = result.scalar_one_or_none()
        if not session_obj:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        session_obj = Session(
            id=uuid4(),
            user_id=user.id,
            agent_template_name=agent_template_name,
        )
        db.add(session_obj)
        await db.flush()

    conversation_id = str(session_obj.id)
    user_id = user.id
    await db.commit()

    async def event_generator():
        try:
            # Send conversation start event
            import json
            yield f"event: start\ndata: {json.dumps({'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"

            async with async_session.begin() as stream_db:
                stream = agent_service.run_agent_stream(
                    db=stream_db,
                    user_id=str(user_id),
                    conversation_id=conversation_id,
                    user_message=message,
                    agent_template_name=agent_template_name,
                    project_context=project_context,
                    profile_name=profile_name,
                    attachments=attachments,
                )
                try:
                    async for chunk in stream:
                        event_type = chunk.get("type", "message")
                        data = {k: v for k, v in chunk.items() if k != "type"}
                        yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                finally:
                    await stream.aclose()

        except TokenQuotaExceeded:
            import json
            yield f"event: error\ndata: {json.dumps({'error': 'Daily token quota exceeded'}, ensure_ascii=False)}\n\n"
        except Exception:
            import json
            error_id = str(uuid4())
            logger.exception("Agent stream failed error_id=%s", error_id)
            yield f"event: error\ndata: {json.dumps({'error': 'Agent request failed', 'error_id': error_id}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List conversations for current user."""
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(desc(Session.created_at))
        .limit(limit)
    )
    sessions = result.scalars().all()
    return {
        "conversations": [
            {
                "conversation_id": str(s.id),
                "title": s.title,
                "agent_template_name": s.agent_template_name,
                "profile_name": s.profile_name,
                "created_at": str(s.created_at),
            }
            for s in sessions
        ],
        "count": len(sessions),
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: UUID,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get messages for a conversation."""
    result = await db.execute(
        select(Session).where(
            Session.id == conversation_id,
            Session.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.session_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return {
        "conversation_id": str(conversation_id),
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "tokens_used": m.tokens_used,
                "created_at": str(m.created_at),
                "attachments": attachments_for_response(m.attachments),
            }
            for m in messages
        ],
        "count": len(messages),
    }


@router.post("/conversations/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: UUID,
    title: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update conversation title."""
    result = await db.execute(
        select(Session).where(
            Session.id == conversation_id,
            Session.user_id == user.id,
        )
    )
    session_obj = result.scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=404, detail="Conversation not found")
    session_obj.title = title
    return {"conversation_id": str(conversation_id), "title": title}
