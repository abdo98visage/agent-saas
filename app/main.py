"""
AgentSaaS - AI Agent Platform
Main entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import health, auth, agents, chat, documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting {settings.app_name} v0.1.0")
    print(f"Debug mode: {settings.debug}")
    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI Agent SaaS Platform - Config-driven business agents",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])


@app.get("/")
async def root():
    return {"status": "ok", "platform": settings.app_name}


@app.get("/api/status")
async def status():
    """Full platform status endpoint."""
    return {
        "platform": settings.app_name,
        "version": "0.1.0",
        "debug": settings.debug,
        "supabase_connected": bool(settings.supabase_url),
        "openai_configured": bool(settings.openai_api_key),
    }


def main():
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
