"""Chat endpoints - send messages to agents."""
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.agents.engine import agent_engine
from app.core.db import supabase
from app.services.memory import should_summarize, save_memory

router = APIRouter()


class ChatMessage(BaseModel):
    agent_slug: str
    message: str
    conversation_id: Optional[str] = None
    organization_id: str


class ConversationCreate(BaseModel):
    agent_slug: str
    organization_id: str
    user_id: str
    title: Optional[str] = None


@router.post("/message")
async def send_message(req: ChatMessage):
    """Send a message to an agent."""
    try:
        # Auto-create conversation if none provided
        conversation_id = req.conversation_id
        if not conversation_id:
            response = supabase.table("agents").select("id").eq("slug", req.agent_slug).single().execute()
            if not response.data:
                raise HTTPException(status_code=404, detail=f"Agent not found: {req.agent_slug}")
            
            agent_id = response.data["id"]
            conversation_id = str(uuid4())
            
            supabase.table("conversations").insert({
                "id": conversation_id,
                "organization_id": req.organization_id,
                "user_id": req.organization_id,  # TODO: Get actual user_id
                "agent_id": agent_id,
                "title": req.message[:50] + "..." if len(req.message) > 50 else req.message,
            }).execute()
        
        # Run the agent
        result = await agent_engine.run(
            agent_slug=req.agent_slug,
            user_message=req.message,
            organization_id=req.organization_id,
            conversation_id=conversation_id,
        )
        
        # Check if we should summarize
        if await should_summarize(conversation_id):
            history_resp = supabase.table("messages").select("*").eq("conversation_id", conversation_id).execute()
            messages = [{"role": m["role"], "content": m["content"]} for m in (history_resp.data or [])]
            await save_memory(conversation_id, req.organization_id, messages, 0, len(messages))
        
        return {
            "conversation_id": conversation_id,
            **result,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversation", status_code=201)
async def create_conversation(req: ConversationCreate):
    """Create a new conversation."""
    try:
        response = supabase.table("agents").select("id").eq("slug", req.agent_slug).single().execute()
        if not response.data:
            raise HTTPException(status_code=404, detail=f"Agent not found: {req.agent_slug}")
        
        conv_id = str(uuid4())
        supabase.table("conversations").insert({
            "id": conv_id,
            "organization_id": req.organization_id,
            "user_id": req.user_id,
            "agent_id": response.data["id"],
            "title": req.title or "New Conversation",
        }).execute()
        
        return {"conversation_id": conv_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str, limit: int = Query(50, le=200)):
    """Get messages for a conversation."""
    try:
        response = supabase.table("messages").select("*").eq("conversation_id", conversation_id).order("created_at", desc=False).limit(limit).execute()
        return {
            "conversation_id": conversation_id,
            "messages": response.data or [],
            "count": len(response.data or []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/organization/{organization_id}/conversations")
async def list_conversations(organization_id: str):
    """List conversations for an organization."""
    try:
        response = supabase.table("conversations").select(
            "*, agents(slug, name)"
        ).eq("organization_id", organization_id).order("updated_at", desc=True).limit(50).execute()
        
        return {
            "conversations": response.data or [],
            "count": len(response.data or []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
