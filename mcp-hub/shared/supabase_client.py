from typing import Optional
from supabase import Client, create_client
from .config import get_env


def get_supabase_client() -> Optional[Client]:
    url = get_env("SUPABASE_URL")
    key = get_env("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)
