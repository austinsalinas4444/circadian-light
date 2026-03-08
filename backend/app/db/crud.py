"""
Async CRUD helpers for Supabase.

All functions are async-safe via asyncio.to_thread() since the supabase-py
sync client is used under the hood. Every function handles a None client
gracefully (Supabase not configured) — callers never need to check.
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta

from app.db.supabase_client import supabase
from app.db.schemas import HealthSnapshot, LightingFeedback, UserSettings

logger = logging.getLogger(__name__)

_TABLE_SNAPSHOTS = "health_snapshots"
_TABLE_FEEDBACK = "lighting_feedback"
_TABLE_SETTINGS = "user_settings"


async def save_health_snapshot(snapshot: HealthSnapshot) -> None:
    """
    Insert a health snapshot row into Supabase.
    Silently no-ops when Supabase is not configured.
    """
    if supabase is None:
        return

    try:
        data = snapshot.model_dump(exclude_none=True)
        await asyncio.to_thread(
            lambda: supabase.table(_TABLE_SNAPSHOTS).insert(data).execute()
        )
    except Exception as exc:
        logger.warning("save_health_snapshot failed: %s", exc)


async def save_feedback(feedback: LightingFeedback) -> None:
    """
    Insert a feedback row into Supabase.
    Silently no-ops when Supabase is not configured.
    """
    if supabase is None:
        return

    try:
        data = feedback.model_dump(exclude_none=True)
        await asyncio.to_thread(
            lambda: supabase.table(_TABLE_FEEDBACK).insert(data).execute()
        )
    except Exception as exc:
        logger.warning("save_feedback failed: %s", exc)


async def get_user_history(user_id: str, days: int = 30) -> list[dict]:
    """
    Fetch the last `days` days of health snapshots for a user.

    Returns:
        List of snapshot dicts ordered by timestamp descending,
        or empty list if Supabase is not configured / query fails.
    """
    if supabase is None:
        return []

    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        result = await asyncio.to_thread(
            lambda: (
                supabase.table(_TABLE_SNAPSHOTS)
                .select("*")
                .eq("user_id", user_id)
                .gte("timestamp", since)
                .order("timestamp", desc=True)
                .execute()
            )
        )
        return result.data or []
    except Exception as exc:
        logger.warning("get_user_history failed: %s", exc)
        return []


async def get_user_settings(user_id: str) -> UserSettings:
    """
    Fetch per-user settings from Supabase.

    Returns:
        UserSettings for the user, or sensible defaults if not found
        or Supabase is not configured.
    """
    if supabase is None:
        return UserSettings(user_id=user_id)

    try:
        result = await asyncio.to_thread(
            lambda: (
                supabase.table(_TABLE_SETTINGS)
                .select("*")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
        )
        if result.data:
            return UserSettings(**result.data)
    except Exception as exc:
        logger.warning("get_user_settings failed: %s", exc)

    return UserSettings(user_id=user_id)
