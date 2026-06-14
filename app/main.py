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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api import health, auth, chat, admin, telegram, websocket_chat

# Structured request logging
logger = logging.getLogger("fqsaas.requests")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)
logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    print(f"Starting {settings.app_name} v{settings.version}")
    print(f"LLM provider: {settings.llm_provider}")
    print(f"Debug mode: {settings.debug}")
    yield
    print(f"Shutting down {settings.app_name}")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Enterprise AI Agent Platform - Multi-user isolation, admin control, and quota management",
    lifespan=lifespan,
)

# SECURITY: Restrict CORS to specific methods and headers only
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=3600,  # Cache preflight for 1 hour
)


# ==================== Rate limiting middleware ====================

# ==================== Structured Request Logging ====================

@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Structured request/response logging for observability."""
    start = time.perf_counter()
    request_id = str(uuid.uuid4())[:8]
    client_ip = request.client.host if request.client else "unknown"

    response = await call_next(request)

    latency_ms = (time.perf_counter() - start) * 1000

    # Log structured JSON to stdout
    log_entry = {
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "ip": client_ip,
        "latency_ms": round(latency_ms, 1),
    }
    logger.info(json.dumps(log_entry, ensure_ascii=False))

    return response


# ==================== Rate limiting middleware ====================

# In-memory store: {ip: [timestamps]}
_rate_store: Dict[str, List[float]] = defaultdict(list)
_RATE_LIMIT = 100  # requests per minute per IP
_RATE_WINDOW = 60.0  # seconds
# Auth endpoints have stricter limits
_AUTH_RATE_LIMIT = 10  # 10 attempts per minute for auth
_AUTH_LOCKOUT_THRESHOLD = 5  # Lock out after 5 failures


def _is_auth_endpoint(path: str) -> bool:
    """Check if path is an auth-sensitive endpoint."""
    return any(p in path for p in ["/auth/login", "/auth/activate", "/auth/register"])


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiter with stricter limits for auth endpoints."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - _RATE_WINDOW

    # Prune old entries for this IP
    _rate_store[client_ip] = [t for t in _rate_store[client_ip] if t > window_start]

    # Use stricter limits for auth endpoints
    limit = _AUTH_RATE_LIMIT if _is_auth_endpoint(request.url.path) else _RATE_LIMIT

    if len(_rate_store[client_ip]) >= limit:
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Rate limit exceeded. {limit} requests per minute."
                + (" Account temporarily locked. Contact admin." if _is_auth_endpoint(request.url.path) else "")
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
