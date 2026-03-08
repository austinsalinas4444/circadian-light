"""
Supabase client initialization.

Reads SUPABASE_URL and SUPABASE_KEY from environment variables.
Exports a single `supabase` client instance for use across the app.

To configure, set environment variables (or use .env with python-dotenv):
  SUPABASE_URL=https://<project>.supabase.co
  SUPABASE_KEY=<anon-or-service-role-key>
"""
import os
from supabase import create_client, Client

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

# Client is None when env vars are not set — all CRUD functions handle this gracefully.
supabase: Client | None = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    import logging
    logging.getLogger(__name__).warning(
        "SUPABASE_URL or SUPABASE_KEY not set — Supabase persistence is disabled."
    )
