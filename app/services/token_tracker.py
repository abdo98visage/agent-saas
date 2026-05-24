from uuid import uuid4
from app.core.db import supabase


async def track_token_usage(organization_id: str, model: str, input_tokens: int, output_tokens: int, estimated_cost: float, agent_run_id: str = None):
    """Track token usage for an organization."""
    try:
        supabase.table("token_usage").insert({
            "id": str(uuid4()),
            "organization_id": organization_id,
            "agent_run_id": agent_run_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": round(estimated_cost, 6),
        }).execute()
    except Exception as e:
        print(f"Error tracking token usage: {e}")


async def get_org_token_usage(organization_id: str, days: int = 30) -> dict:
    """Get token usage summary for an organization."""
    try:
        response = supabase.rpc(
            "get_org_token_usage",
            {
                "org_id": organization_id,
                "days": days,
            }
        ).execute()
        return response.data or {}
    except Exception:
        # Fallback: direct query
        response = supabase.table("token_usage").select("*").eq("organization_id", organization_id).execute()
        
        usage = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0,
            "num_runs": 0,
        }
        
        for row in (response.data or []):
            usage["total_input_tokens"] += row.get("input_tokens", 0)
            usage["total_output_tokens"] += row.get("output_tokens", 0)
            usage["total_cost"] += row.get("estimated_cost", 0)
            usage["num_runs"] += 1
        
        return usage
