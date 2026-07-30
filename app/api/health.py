import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.db import engine
from app.services.hermes_orchestrator import hermes_orchestrator

router = APIRouter()


async def _database_check() -> tuple[bool, str]:
    try:
        async with asyncio.timeout(settings.dependency_health_timeout_seconds):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return True, "connected"
    except Exception:
        return False, "unavailable"


async def _redis_check() -> tuple[bool, str]:
    try:
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=settings.dependency_health_timeout_seconds,
            socket_timeout=settings.dependency_health_timeout_seconds,
        )
        try:
            async with asyncio.timeout(settings.dependency_health_timeout_seconds):
                await redis_client.ping()
        finally:
            await redis_client.aclose()
        return True, "connected"
    except Exception:
        return False, "unavailable"


async def _hermes_check() -> tuple[bool | None, str]:
    if not settings.hermes_orchestrator_url:
        return None, "not_configured"
    try:
        async with asyncio.timeout(settings.dependency_health_timeout_seconds):
            status = await hermes_orchestrator.status()
        healthy = status.get("run_health") == "healthy" or status.get("status") in {"ready", "managed_externally", "healthy"}
        return healthy, status.get("status", "unknown")
    except Exception:
        return False, "unavailable"


@router.get("/live")
async def live_check():
    return {"status": "alive", "app": settings.app_name, "version": settings.version}


@router.get("/ready")
async def readiness_check():
    database_ok, database_status = await _database_check()
    redis_ok, redis_status = await _redis_check()
    hermes_ok, hermes_status = await _hermes_check()

    runtime_required = settings.environment.lower() == "production" or bool(settings.hermes_orchestrator_url)
    ready = database_ok and redis_ok and (hermes_ok is True if runtime_required else hermes_ok is not False)
    payload = {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "database": database_status,
            "redis": redis_status,
            "hermes": hermes_status,
        },
    }
    if ready:
        return payload
    return JSONResponse(status_code=503, content=payload)


@router.get("/health")
async def health_check():
    """Detailed health check for operators."""
    database_ok, database_status = await _database_check()
    redis_ok, redis_status = await _redis_check()
    hermes_ok, hermes_status = await _hermes_check()

    checks = {
        "database": database_status,
        "redis": redis_status,
        "hermes": hermes_status,
    }
    status = "ok"
    if not database_ok or not redis_ok:
        status = "degraded"
    if hermes_ok is False:
        status = "degraded"

    return {
        "status": status,
        "app": settings.app_name,
        "version": settings.version,
        "checks": checks,
    }
