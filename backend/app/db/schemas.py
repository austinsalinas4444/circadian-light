"""
Pydantic schemas for Supabase table rows.

These mirror the table definitions in Supabase and are used for
insert/select operations in crud.py.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class HealthSnapshot(BaseModel):
    """
    A point-in-time snapshot of the user's health metrics.
    Maps to the `health_snapshots` table in Supabase.
    """
    user_id: str
    timestamp: str = Field(default_factory=_now_utc)
    hrv_ms: Optional[float] = None
    sleep_hours: Optional[float] = None
    sleep_score: Optional[float] = None
    resting_hr: Optional[float] = None
    steps: Optional[int] = None
    active_energy: Optional[float] = None  # kcal


class LightingFeedback(BaseModel):
    """
    User feedback on a lighting recommendation.
    Maps to the `lighting_feedback` table in Supabase.
    """
    user_id: str
    timestamp: str = Field(default_factory=_now_utc)
    recommended_cct: int
    recommended_brightness: int
    actual_cct: Optional[int] = None
    actual_brightness: Optional[int] = None
    rating: int = Field(..., ge=1, le=5, description="User rating 1-5")
    feedback_type: Optional[str] = Field(
        None,
        description="One of: too_warm, too_cool, too_bright, too_dim, perfect",
    )


class UserSettings(BaseModel):
    """
    Per-user configuration overrides.
    Maps to the `user_settings` table in Supabase.
    """
    user_id: str
    wake_time: int = Field(8, ge=0, le=23, description="Wake hour (0-23)")
    sleep_time: int = Field(24, ge=1, le=24, description="Sleep hour (1-24, 24=midnight)")
    bulb_ip: Optional[str] = None
