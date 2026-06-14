import hmac
import secrets
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.db import get_db
from app.models.telegram_binding import TelegramBinding
from app.models.user import User
from app.services.agent_service import AgentService
from app.api.auth import get_current_user
from app.core.config import settings

router = APIRouter()
agent_service = AgentService()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive Telegram webhook updates."""
    # Verify webhook secret token
    if settings.telegram_webhook_secret:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")

    data = await request.json()

    # Only handle messages
    if "message" not in data:
        return {"status": "ok"}

    message = data["message"]
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")

    if not chat_id or not text:
        return {"status": "ok"}

    # Handle /bind <code> command — allows any user to attempt binding
    if text.startswith("/bind "):
        bind_code = text[6:].strip()
        result = await db.execute(
            select(TelegramBinding).where(TelegramBinding.binding_token == bind_code)
        )
        temp_binding = result.scalar_one_or_none()
        if temp_binding:
            temp_binding.telegram_chat_id = chat_id
            await db.flush()

            # Check user status
            user_result = await db.execute(select(User).where(User.id == temp_binding.user_id))
            bound_user = user_result.scalar_one_or_none()

            if not bound_user:
                return {
                    "status": "ok",
                    "chat_id": chat_id,
                    "response": "❌ المستخدم غير موجود في المنصة.",
                    "bound": False,
                }
            if not bound_user.is_activated:
                return {
                    "status": "ok",
                    "chat_id": chat_id,
                    "response": "⚠️ حسابك غير مفعل بعد. افتح تطبيق FQ-SaaS على جهازك وقم بتفعيل الحساب بكود الدعوة.",
                    "bound": True,
                }
            if not bound_user.is_active:
                return {
                    "status": "ok",
                    "chat_id": chat_id,
                    "response": "🔒 حسابك معطل. تواصل مع الإدارة لإعادة التفعيل.",
                    "bound": True,
                }

            return {
                "status": "ok",
                "chat_id": chat_id,
                "response": "✅ تم ربط حسابك بنجاح! يمكنك الآن استخدام التلجرام.",
                "user_id": str(temp_binding.user_id),
                "bound": True,
            }
        else:
            return {
                "status": "ok",
                "chat_id": chat_id,
                "response": "❌ كود الربط غير صحيح. تأكد من الكود وحاول مرة أخرى.",
                "bound": False,
            }

    # Handle /start command
    if text == "/start":
        # Check if this chat is already bound
        existing_bind = await db.execute(
            select(TelegramBinding).where(TelegramBinding.telegram_chat_id == chat_id)
        )
        if existing_bind.scalar_one_or_none():
            return {
                "status": "ok",
                "chat_id": chat_id,
                "response": "مرحباً! حسابك مرتبط بالفعل. اكتب رسالتك وسأرد عليك.",
            }
        return {
            "status": "ok",
            "chat_id": chat_id,
            "response": "👋 مرحباً! هذا البوت مخصص لموظفي منصة FQ-SaaS فقط.\n\nلربط حسابك:\n1. افتح تطبيق FQ-SaaS على جهازك\n2. اذهب للإعدادات (Ctrl+,)\n3. اضغط 'توليد كود' في قسم التلجرام\n4. أرسل الكود هنا بصيغة: /bind <الكود>\n\nإذا لم يكن لديك حساب، تواصل مع الإدارة.",
        }

    # For all other messages — user MUST be bound AND active
    result = await db.execute(
        select(TelegramBinding).where(TelegramBinding.telegram_chat_id == chat_id)
    )
    binding = result.scalar_one_or_none()
    if not binding:
        return {
            "status": "ok",
            "chat_id": chat_id,
            "response": "🚫 هذا البوت مخصص لموظفي منصة FQ-SaaS فقط. تواصل مع الإدارة للتسجيل.",
        }

    user_id = binding.user_id

    # Check user status
    user_result = await db.execute(select(User).where(User.id == user_id))
    bound_user = user_result.scalar_one_or_none()

    if not bound_user:
        return {
            "status": "ok",
            "chat_id": chat_id,
            "response": "❌ المستخدم غير موجود في المنصة. تواصل مع الإدارة.",
        }
    if not bound_user.is_activated:
        return {
            "status": "ok",
            "chat_id": chat_id,
            "response": "⚠️ حسابك غير مفعل. افتح تطبيق FQ-SaaS وقم بتفعيل الحساب بكود الدعوة.",
        }
    if not bound_user.is_active:
        return {
            "status": "ok",
            "chat_id": chat_id,
            "response": "🔒 حسابك معطل. تواصل مع الإدارة لإعادة التفعيل.",
        }

    # Process message through agent
    try:
        result = await agent_service.run_agent(
            db=db,
            user_id=str(user_id),
            conversation_id=None,
            user_message=text,
            agent_template_name="default",
        )
        response_text = result.get("content", "No response")
    except Exception as e:
        response_text = f"Error: {str(e)}"

    return {
        "status": "ok",
        "chat_id": chat_id,
        "response": response_text,
        "user_id": str(user_id),
    }


@router.get("/send/{chat_id}")
async def send_telegram_message(
    chat_id: int,
    text: str = "",
):
    """Send a message to a Telegram chat via Bot API.
    This is called internally after processing a webhook response."""
    if not settings.telegram_bot_token:
        return {"error": "Telegram bot token not configured"}

    import httpx
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
            },
        )
        return response.json()


@router.post("/bind")
async def bind_telegram(
    req: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bind current user to their Telegram chat_id. Creates or updates binding."""
    telegram_chat_id = req.get("telegram_chat_id")
    if not telegram_chat_id:
        raise HTTPException(status_code=400, detail="telegram_chat_id is required")

    # Check if this chat_id is already bound to another user
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
        # Bound to different user — remove old binding
        db.delete(existing)

    # Check if user already has a binding
    existing_user_binding = await db.execute(
        select(TelegramBinding).where(TelegramBinding.user_id == user.id)
    )
    user_binding = existing_user_binding.scalar_one_or_none()
    if user_binding:
        user_binding.telegram_chat_id = telegram_chat_id
    else:
        binding = TelegramBinding(
            user_id=user.id,
            telegram_chat_id=telegram_chat_id,
            binding_token=secrets.token_hex(32),
        )
        db.add(binding)

    await db.flush()
    return {
        "message": "Telegram chat bound successfully",
        "telegram_chat_id": telegram_chat_id,
        "binding_token": binding.binding_token if not user_binding else user_binding.binding_token,
    }


@router.post("/generate-bind-code")
async def generate_telegram_bind_code(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a one-time bind code for Telegram binding from Desktop."""
    code = secrets.token_hex(6)  # 12-char code

    # Store as a temporary binding record (telegram_chat_id=0 means not yet bound)
    existing = await db.execute(
        select(TelegramBinding).where(TelegramBinding.user_id == user.id)
    )
    existing_binding = existing.scalar_one_or_none()
    if existing_binding:
        return {"message": "Already bound", "telegram_chat_id": existing_binding.telegram_chat_id}

    temp_binding = TelegramBinding(
        user_id=user.id,
        telegram_chat_id=0,  # Placeholder — will be updated when bot receives /bind
        binding_token=code,
    )
    db.add(temp_binding)
    await db.flush()

    return {
        "bind_code": code,
        "message": "Send /bind <code> to the Telegram bot",
    }


@router.post("/bind-with-code")
async def bind_with_code(
    req: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Called by Desktop after bot confirms binding."""
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
    if binding.telegram_chat_id != 0:
        return {"message": "Already bound", "telegram_chat_id": binding.telegram_chat_id}

    # The bot should have updated telegram_chat_id via webhook
    # If not yet updated, the user needs to send /bind to the bot first
    if binding.telegram_chat_id == 0:
        raise HTTPException(
            status_code=400,
            detail="Not bound yet. Send /bind <code> to the Telegram bot first."
        )

    return {"message": "Telegram bound successfully", "telegram_chat_id": binding.telegram_chat_id}
