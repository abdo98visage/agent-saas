from supabase import create_client, Client
from app.core.config import settings

# Service role client - has full permissions (backend only)
supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_key
)
