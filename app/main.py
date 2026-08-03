"""
FQ-SaaS - Enterprise AI Agent Platform
Main application entry point.
"""
import json
import logging
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Dict, List

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
except ImportError:  # optional until runtime deps are refreshed
    sentry_sdk = None
    FastApiIntegration = None

from app.core.config import settings
from app.core.audit_context import correlation_id_context, trace_id_context
from app.api import health, auth, chat, admin, telegram, websocket_chat, mcp_admin, mcp_user, durable_tasks, observability, evaluations, knowledge

# Structured request logging
logger = logging.getLogger("fqsaas.requests")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)
logger.propagate = False

if settings.sentry_dsn and sentry_sdk and FastApiIntegration:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        enable_tracing=settings.sentry_traces_sample_rate > 0,
        integrations=[FastApiIntegration()],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    print(f"Starting {settings.app_name} v{settings.version}")
    print(f"LLM provider: {settings.llm_provider}")
    print(f"Debug mode: {settings.debug}")
    app.state.redis = None
    if settings.rate_limit_backend == "redis":
        try:
            app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await app.state.redis.ping()
        except Exception as exc:
            app.state.redis = None
            if settings.environment.lower() == "production":
                raise RuntimeError("Redis rate limiter is required in production") from exc
            print(f"Redis rate limiter unavailable, falling back to in-memory limits: {exc}")
    yield
    if app.state.redis:
        await app.state.redis.close()
    print(f"Shutting down {settings.app_name}")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Enterprise AI Agent Platform - Multi-user isolation, admin control, and quota management",
    lifespan=lifespan,
)


@app.exception_handler(IntegrityError)
async def database_conflict_handler(request: Request, _exc: IntegrityError):
    request_id = str(uuid.uuid4())[:8]
    logger.warning(json.dumps({
        "event": "database_conflict",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
    }))
    return JSONResponse(
        status_code=409,
        content={"detail": f"Request conflicts with existing data. Reference: {request_id}"},
    )

# SECURITY: Restrict CORS to specific methods and headers only
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Client-Type", "X-CSRF-Token", "X-Correlation-ID", "traceparent"],
    expose_headers=["X-Correlation-ID", "traceparent"],
    max_age=3600,  # Cache preflight for 1 hour
)


# ==================== Rate limiting middleware ====================

# ==================== Structured Request Logging ====================

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Structured request/response logging for observability."""
    start = time.perf_counter()
    incoming_correlation = request.headers.get("X-Correlation-ID", "")
    correlation_id = incoming_correlation if 0 < len(incoming_correlation) <= 64 and incoming_correlation.isascii() else str(uuid.uuid4())
    traceparent = request.headers.get("traceparent", "")
    parts = traceparent.split("-")
    trace_id = parts[1].lower() if len(parts) == 4 and len(parts[1]) == 32 and all(char in "0123456789abcdefABCDEF" for char in parts[1]) else uuid.uuid4().hex
    correlation_token = correlation_id_context.set(correlation_id)
    trace_token = trace_id_context.set(trace_id)
    client_ip = request.client.host if request.client else "unknown"
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["traceparent"] = f"00-{trace_id}-{uuid.uuid4().hex[:16]}-01"
        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(json.dumps({
            "event": "http_request", "correlation_id": correlation_id, "trace_id": trace_id,
            "method": request.method, "path": request.url.path, "status": response.status_code,
            "ip": client_ip, "latency_ms": round(latency_ms, 1),
        }, ensure_ascii=False))
        return response
    finally:
        correlation_id_context.reset(correlation_token)
        trace_id_context.reset(trace_token)


# ==================== Rate limiting middleware ====================

# In-memory store: {ip: [timestamps]}
_rate_store: Dict[str, List[float]] = defaultdict(list)
_RATE_LIMIT = settings.rate_limit_per_minute  # requests per minute per IP
_RATE_WINDOW = 60.0  # seconds
# Auth endpoints have stricter limits
_AUTH_RATE_LIMIT = settings.auth_rate_limit_per_minute  # attempts per minute for auth
def _is_auth_endpoint(path: str) -> bool:
    """Check if path is an auth-sensitive endpoint."""
    return any(p in path for p in ["/auth/login", "/auth/activate", "/auth/register"])


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiter with stricter limits for auth endpoints."""
    client_ip = request.client.host if request.client else "unknown"
    limit = _AUTH_RATE_LIMIT if _is_auth_endpoint(request.url.path) else _RATE_LIMIT

    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        key = f"rate-limit:{client_ip}:{request.url.path if _is_auth_endpoint(request.url.path) else 'global'}"
        try:
            count = await redis_client.incr(key)
            if count == 1:
                await redis_client.expire(key, int(_RATE_WINDOW))
        except Exception:
            redis_client = None
        else:
            if count > limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Rate limit exceeded. {limit} requests per minute."
                    },
                )
            return await call_next(request)

    now = time.time()
    window_start = now - _RATE_WINDOW

    # Prune old entries for this IP
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if t > window_start]

    if len(_rate_store[client_ip]) >= limit:
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Rate limit exceeded. {limit} requests per minute."
            },
        )

    _rate_store[client_ip].append(now)
    response = await call_next(request)
    return response


# Routes
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])
app.include_router(mcp_admin.router, prefix="/api/admin/mcp", tags=["Admin MCP"])
app.include_router(mcp_user.router, prefix="/api/auth/mcp", tags=["MCP"])
app.include_router(durable_tasks.router, prefix="/api/tasks", tags=["Durable Tasks"])
app.include_router(observability.router, prefix="/api", tags=["Observability"])
app.include_router(evaluations.router, prefix="/api", tags=["Evaluations"])
app.include_router(knowledge.router, prefix="/api", tags=["Knowledge"])
app.include_router(telegram.router, prefix="/api/telegram", tags=["Telegram"])
app.include_router(websocket_chat.router, prefix="/api/chat", tags=["WebSocket"])


@app.get("/api/status")
async def status():
    """Full platform status — production-safe (no sensitive info)."""
    return {
        "platform": settings.app_name,
        "version": settings.version,
        # SECURITY: Never expose debug mode, LLM provider, or DB connection status
        "status": "healthy",
    }


def main():
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
