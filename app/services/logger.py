from uuid import uuid4
from app.core.db import supabase


async def log_agent_run(organization_id: str, agent_id: str, conversation_id: str, input_prompt: str, output: str, status: str, error_message: str = None, latency_ms: int = None):
    """Log an agent run for observability."""
    try:
        supabase.table("agent_runs").insert({
            "id": str(uuid4()),
            "organization_id": organization_id,
            "agent_id": agent_id,
            "conversation_id": conversation_id,
            "input_prompt": input_prompt,
            "output": output,
            "status": status,
            "error_message": error_message or "",
            "latency_ms": latency_ms or 0,
        }).execute()
    except Exception as e:
        print(f"Error logging agent run: {e}")


async def log_tool_call(organization_id: str, tool_name: str, input_data: dict, output_data: dict, status: str, error_message: str = None, latency_ms: int = None, agent_run_id: str = None):
    """Log a tool call for observability."""
    try:
        import json
        supabase.table("tool_logs").insert({
            "id": str(uuid4()),
            "organization_id": organization_id,
            "agent_run_id": agent_run_id,
            "tool_name": tool_name,
            "input_data": input_data,
            "output_data": output_data,
            "status": status,
            "error_message": error_message or "",
            "latency_ms": latency_ms or 0,
        }).execute()
    except Exception as e:
        print(f"Error logging tool call: {e}")
