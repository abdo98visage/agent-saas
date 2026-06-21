import secrets
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.models.telegram_binding import TelegramBinding
from app.models.user import User
from app.services.agent_service import AgentService

router = APIRouter()
agent_service = AgentService()


async def _send_telegram_message(chat_id: int, text: str) -> dict[str, Any]:
    if not settings.telegram_bot_token:
        return {"sent": False, "error": "Telegram bot token is not configured"}

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
        )
        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        if not response.is_success:
            return {"sent": False, "status_code": response.status_code, "telegram_response": payload}
        return {"sent": True, "status_code": response.status_code, "telegram_response": payload}


async def _reply(chat_id: int, text: str, **extra: Any) -> dict[str, Any]:
    delivery = await _send_telegram_message(chat_id, text)
    return {
        "status": "ok",
        "chat_id": chat_id,
        "response": text,
        "delivery": delivery,
        **extra,
    }


async def _get_bound_user(db: AsyncSession, chat_id: int) -> tuple[TelegramBinding | None, User | None]:
    result = await db.execute(
        select(TelegramBinding).where(TelegramBinding.telegram_chat_id == chat_id)
    )
    binding = result.scalar_one_or_none()
    if not binding:
        return None, None

    user_result = await db.execute(select(User).where(User.id == binding.user_id))
    return binding, user_result.scalar_one_or_none()


def _inactive_user_message(user: User | None) -> str | None:
    if not user:
        return "The linked platform user no longer exists. Contact the administrator."
    if not user.is_activated:
        return "Your platform account is not activated yet. Open the desktop app and activate it with your invite code."
    if not user.is_active:
        return "Your platform account is disabled. Contact the administrator to reactivate it."
    return None


def _binding_expired(binding: TelegramBinding) -> bool:
    return bool(binding.binding_token_expires_at and binding.binding_token_expires_at < datetime.utcnow())


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive Telegram webhook updates and send the bot reply through Telegram."""
    if settings.telegram_webhook_secret:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    data = await request.json()
    message = data.get("message")
    if not message:
        return {"status": "ok", "ignored": True}

    text = (message.get("text") or "").strip()
    chat_id = message.get("chat", {}).get("id")
    if not chat_id or not text:
        return {"status": "ok", "ignored": True}

    if text.startswith("/bind "):
        bind_code = text[6:].strip()
        result = await db.execute(
            select(TelegramBinding).where(TelegramBinding.binding_token == bind_code)
        )
        binding = result.scalar_one_or_none()
        if not binding:
            return await _reply(
                chat_id,
                "Invalid bind code. Generate a new code from the desktop app and try again.",
                bound=False,
            )
        if _binding_expired(binding):
            await db.delete(binding)
            return await _reply(
                chat_id,
                "This bind code expired. Generate a new code from the desktop app and try again.",
                bound=False,
            )

        binding.telegram_chat_id = chat_id
        binding.binding_token_expires_at = None
        await db.flush()

        user_result = await db.execute(select(User).where(User.id == binding.user_id))
        bound_user = user_result.scalar_one_or_none()
        inactive_message = _inactive_user_message(bound_user)
        if inactive_message:
            return await _reply(chat_id, inactive_message, bound=bool(bound_user))

        return await _reply(
            chat_id,
            "Telegram has been linked successfully. You can now send platform messages here.",
            user_id=str(binding.user_id),
            bound=True,
        )

    if text == "/start":
        binding, user = await _get_bound_user(db, chat_id)
        if binding:
            inactive_message = _inactive_user_message(user)
            if inactive_message:
                return await _reply(chat_id, inactive_message, bound=True)
            return await _reply(
                chat_id,
                "Your Telegram account is already linked. Send a message and the platform agent will answer.",
                bound=True,
            )
        return await _reply(
            chat_id,
            "Welcome. This bot is for platform employees only. Generate a Telegram bind code from the desktop app, then send /bind <code> here.",
            bound=False,
        )

    binding, bound_user = await _get_bound_user(db, chat_id)
    if not binding:
        return await _reply(
            chat_id,
            "This bot is for platform employees only. Contact the administrator to get access.",
            bound=False,
        )

    inactive_message = _inactive_user_message(bound_user)
    if inactive_message:
        return await _reply(chat_id, inactive_message, user_id=str(binding.user_id), bound=True)

    try:
        result = await agent_service.run_agent(
            db=db,
            user_id=str(binding.user_id),
            conversation_id=None,
            user_message=text,
            agent_template_name="default",
        )
        response_text = result.get("content") or "No response was generated."
    except Exception:
        response_text = "The agent could not process this message. Try again later."

    return await _reply(
        chat_id,
        response_text,
        user_id=str(binding.user_id),
        bound=True,
    )


@router.get("/send/{chat_id}")
async def send_telegram_message(
    chat_id: int,
    text: str = "",
):
    """Send a message to a Telegram chat via Bot API."""
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    return await _send_telegram_message(chat_id, text)


@router.post("/bind")
async def bind_telegram(
    req: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bind current user to their Telegram chat_id."""
    telegram_chat_id = req.get("telegram_chat_id")
    if not telegram_chat_id:
        raise HTTPException(status_code=400, detail="telegram_chat_id is required")

    existing_by_chat = await db.execute(
        select(TelegramBinding).where(TelegramBinding.telegram_chat_id == telegram_chat_id)
    )
    existing = existing_by_chat.scalar_one_or_none()
    if existing:
        if existing.user_id == user.id:
            return {
                "message": "Already bound",
                "binding_token": existing.binding_token,
                "telegram_chat_id": telegram_chat_id,
            }
        await db.delete(existing)

    existing_user_binding = await db.execute(
        select(TelegramBinding).where(TelegramBinding.user_id == user.id)
    )
    user_binding = existing_user_binding.scalar_one_or_none()
    if user_binding:
        user_binding.telegram_chat_id = telegram_chat_id
        binding = user_binding
    else:
        binding = TelegramBinding(
            user_id=user.id,
            telegram_chat_id=telegram_chat_id,
            binding_token=secrets.token_hex(32),
            binding_token_expires_at=datetime.utcnow() + timedelta(minutes=settings.telegram_bind_code_ttl_minutes),
        )
        db.add(binding)

    await db.flush()
    return {
        "message": "Telegram chat bound successfully",
        "telegram_chat_id": telegram_chat_id,
        "binding_token": binding.binding_token,
    }


@router.post("/generate-bind-code")
async def generate_telegram_bind_code(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a one-time bind code for Telegram binding from Desktop."""
    existing = await db.execute(
        select(TelegramBinding).where(TelegramBinding.user_id == user.id)
    )
    existing_binding = existing.scalar_one_or_none()
    if existing_binding:
        if _binding_expired(existing_binding):
            await db.delete(existing_binding)
        elif existing_binding.telegram_chat_id != 0:
            return {
                "message": "Already bound",
                "telegram_chat_id": existing_binding.telegram_chat_id,
            }
        else:
            return {
                "bind_code": existing_binding.binding_token,
                "expires_at": existing_binding.binding_token_expires_at.isoformat() if existing_binding.binding_token_expires_at else None,
                "message": "Send /bind <code> to the Telegram bot",
            }

    code = secrets.token_hex(6)
    binding = TelegramBinding(
        user_id=user.id,
        telegram_chat_id=0,
        binding_token=code,
        binding_token_expires_at=datetime.utcnow() + timedelta(minutes=settings.telegram_bind_code_ttl_minutes),
    )
    db.add(binding)
    await db.flush()

    return {
        "bind_code": code,
        "expires_at": binding.binding_token_expires_at.isoformat() if binding.binding_token_expires_at else None,
        "message": "Send /bind <code> to the Telegram bot",
    }


@router.post("/bind-with-code")
async def bind_with_code(
    req: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Confirm that Telegram updated the temporary binding through /bind."""
    binding_code = req.get("binding_code", "")
    if not binding_code:
        raise HTTPException(status_code=400, detail="binding_code is required")

    result = await db.execute(
        select(TelegramBinding).where(
            TelegramBinding.user_id == user.id,
            TelegramBinding.binding_token == binding_code,
        )
    )
    binding = result.scalar_one_or_none()
    if not binding:
        raise HTTPException(status_code=404, detail="Invalid or expired bind code")
    if _binding_expired(binding):
        await db.delete(binding)
        raise HTTPException(status_code=410, detail="Bind code expired. Generate a new code and try again.")
    if binding.telegram_chat_id == 0:
        raise HTTPException(
            status_code=400,
            detail="Not bound yet. Send /bind <code> to the Telegram bot first.",
        )

    binding.binding_token_expires_at = None
    return {"message": "Telegram bound successfully", "telegram_chat_id": binding.telegram_chat_id}
