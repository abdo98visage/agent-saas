"""Agents endpoints - list available agents."""
from fastapi import APIRouter, HTTPException
from app.core.db import supabase

router = APIRouter()


@router.get("/")
async def list_agents():
    """List all active agents available."""
    try:
        response = supabase.table("agents").select("*").eq("active", True).execute()
        return {
            "agents": response.data or [],
            "count": len(response.data or []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_slug}")
async def get_agent(agent_slug: str):
    """Get a specific agent by slug."""
    try:
        response = supabase.table("agents").select("*").eq("slug", agent_slug).eq("active", True).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_slug}")
        
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
