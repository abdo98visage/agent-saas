"""Auth service - Supabase Auth integration."""
from uuid import uuid4
from app.core.db import supabase


async def signup(email: str, password: str, full_name: str = None):
    """Register a new user with Supabase Auth."""
    try:
        result = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "full_name": full_name,
                }
            }
        })
        return {
            "user_id": result.user.id,
            "email": email,
            "message": "Registration successful. Please check your email to verify your account."
        }
    except Exception as e:
        raise Exception(f"Registration failed: {str(e)}")


async def create_organization(name: str, owner_id: str):
    """Create a new organization for a user."""
    org_id = str(uuid4())
    
    # Create organization
    supabase.table("organizations").insert({
        "id": org_id,
        "name": name,
        "subscription_plan": "starter",
        "subscription_status": "active",
    }).execute()
    
    # Add owner as member
    supabase.table("organization_members").insert({
        "user_id": owner_id,
        "organization_id": org_id,
        "role": "owner",
    }).execute()
    
    return {"organization_id": org_id, "name": name, "plan": "starter"}


async def get_user_organizations(user_id: str) -> list:
    """Get all organizations for a user."""
    response = supabase.table("organization_members").select(
        "*, organizations(*)"
    ).eq("user_id", user_id).execute()
    
    return response.data or []


async def get_user_org_id(user_id: str) -> str:
    """Get the primary organization ID for a user."""
    orgs = await get_user_organizations(user_id)
    if orgs:
        return orgs[0]["organizations"]["id"]
    return None
