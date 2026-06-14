from fastapi import APIRouter
from sqlalchemy import text
from app.core.config import settings
from app.core.db import get_db

router = APIRouter()


@router.get("/health")
async def health_check(db=None):
    """Health check with actual DB and Redis connectivity tests."""
    health = {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.version,
        "llm_provider": settings.llm_provider,
        "checks": {},
    }

    # Check PostgreSQL connectivity
    db_status = "unavailable"
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(settings.database_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        health["status"] = "degraded"
    health["checks"]["database"] = db_status

    # Check Redis connectivity
    redis_status = "unavailable"
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        await redis_client.close()
        redis_status = "connected"
    except Exception as e:
        redis_status = f"error: {str(e)}"
        health["status"] = "degraded"
    health["checks"]["redis"] = redis_status

    return health
