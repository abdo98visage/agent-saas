from uuid import uuid4
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.db import supabase


async def summarize_conversation(conversation_id: str, messages: list) -> str:
    """Generate a summary of recent messages using OpenAI."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    summary_prompt = f"""Summarize this conversation concisely in 2-3 sentences. Focus on key decisions, topics discussed, and action items.

Conversation:
{chr(10).join(f'{m["role"]}: {m["content"][:500]}' for m in messages[-10:])}

Summary:"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.3,
            max_tokens=200,
        )
        return response.choices[0].message.content
    except Exception:
        return "\n".join(m["content"][:100] for m in messages[-3:])


async def save_memory(conversation_id: str, organization_id: str, messages: list, start_idx: int, end_idx: int):
    """Save a conversation summary as memory."""
    summary = await summarize_conversation(conversation_id, messages)
    
    try:
        supabase.table("conversation_memory").insert({
            "id": str(uuid4()),
            "conversation_id": conversation_id,
            "organization_id": organization_id,
            "summary": summary,
            "message_range_start": start_idx,
            "message_range_end": end_idx,
        }).execute()
    except Exception as e:
        print(f"Error saving memory: {e}")


async def should_summarize(conversation_id: str) -> bool:
    """Check if a conversation has enough messages to warrant summarization."""
    try:
        response = supabase.table("messages").select("*", count="exact").eq("conversation_id", conversation_id).execute()
        return (response.count or 0) >= 10  # Summarize every 10 messages
    except Exception:
        return False
