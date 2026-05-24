"""Auth endpoints - registration and organization management."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services.auth import signup, create_organization, get_user_organizations
from app.schemas import RegisterRequest, TokenResponse

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """Register a new user."""
    try:
        result = await signup(request.email, request.password, request.full_name)
        return {
            "access_token": result["user_id"],  # In production, get actual JWT from Supabase
            "token_type": "bearer",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/organizations")
async def create_org(name: str, user_id: str = Depends(lambda: None)):
    """Create a new organization."""
    try:
        # TODO: In production, extract user_id from JWT token
        # For now, use a placeholder
        actual_user_id = user_id or "00000000-0000-0000-0000-000000000000"
        result = await create_organization(name, actual_user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/organizations")
async def list_orgs(user_id: str = Depends(lambda: None)):
    """List user's organizations."""
    try:
        actual_user_id = user_id or "00000000-0000-0000-0000-000000000000"
        orgs = await get_user_organizations(actual_user_id)
        return orgs
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
