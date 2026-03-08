"""
Request models for the CircadianLight API.
These match the Swift CodingKeys from CircadianLight/Models/Models.swift
"""
from pydantic import BaseModel, Field
from typing import Optional


class HealthFeaturesRequest(BaseModel):
    """
    Health data from iOS app to generate lighting recommendations.

    Core fields (required):
        hrv_ms, sleep_hours, step_count

    Extended fields (optional, enrich recommendations):
        sleep_score         — composite 0-100 quality score (pre-computed by
                              client, or computed server-side from components)
        deep_sleep_pct      — fraction of sleep in deep/slow-wave stage (0-1)
        rem_sleep_pct       — fraction of sleep in REM stage (0-1)
        sleep_efficiency    — fraction of time-in-bed actually asleep (0-1)
        resting_hr          — resting heart rate (bpm) for ML features
        active_energy       — active calories burned today (kcal) for ML features
        local_hour          — client local hour 0-23 for phase calculation
        user_id             — opaque identifier for Supabase logging

    JSON fields match Swift HealthFeatures CodingKeys (snake_case):
        hrv_ms → HealthFeatures.hrvMilliseconds
        sleep_hours → HealthFeatures.sleepHours
        step_count → HealthFeatures.stepCount
    """

    # --- Core fields ---
    hrv_ms: float = Field(..., description="Heart Rate Variability SDNN (ms)", ge=0)
    sleep_hours: float = Field(..., description="Total sleep duration (h)", ge=0, le=24)
    step_count: int = Field(..., description="Daily step count", ge=0)
    local_hour: Optional[int] = Field(
        None, description="Client local hour (0-23) for circadian phase", ge=0, le=23
    )

    # --- Sleep quality components (for compute_sleep_score) ---
    sleep_score: Optional[float] = Field(
        None, description="Pre-computed composite sleep score (0-100)", ge=0, le=100
    )
    deep_sleep_pct: Optional[float] = Field(
        None, description="Deep/slow-wave sleep fraction of total (0-1)", ge=0, le=1
    )
    rem_sleep_pct: Optional[float] = Field(
        None, description="REM sleep fraction of total (0-1)", ge=0, le=1
    )
    sleep_efficiency: Optional[float] = Field(
        None, description="Fraction of time-in-bed asleep (0-1)", ge=0, le=1
    )

    # --- Additional health metrics (ML features) ---
    resting_hr: Optional[float] = Field(
        None, description="Resting heart rate (bpm)", ge=20, le=120
    )
    active_energy: Optional[float] = Field(
        None, description="Active calories burned today (kcal)", ge=0
    )

    # --- Identity ---
    user_id: Optional[str] = Field(
        None, description="Opaque user identifier for logging/personalization"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "hrv_ms": 72.0,
                "sleep_hours": 7.5,
                "step_count": 9200,
                "local_hour": 14,
                "sleep_score": 74.0,
                "deep_sleep_pct": 0.18,
                "rem_sleep_pct": 0.23,
                "sleep_efficiency": 0.91,
                "resting_hr": 50.0,
                "active_energy": 420.0,
                "user_id": "user_abc123"
            }
        }


class FeedbackRequest(BaseModel):
    """
    User feedback on a lighting recommendation.

    JSON fields match Swift LightingFeedback CodingKeys (snake_case):
        recommendation_id → LightingFeedback.recommendationId
        rating → LightingFeedback.rating
        comment → LightingFeedback.comment
    """

    recommendation_id: Optional[str] = Field(
        None, description="ID of the recommendation being rated"
    )
    rating: int = Field(..., description="User rating (1-5 stars)", ge=1, le=5)
    comment: Optional[str] = Field(None, description="Optional free-text comment")
    feedback_type: Optional[str] = Field(
        None,
        description="Structured feedback: too_warm | too_cool | too_bright | too_dim | perfect",
    )
    user_id: Optional[str] = Field(None, description="Opaque user identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "recommendation_id": "rec_123456",
                "rating": 4,
                "comment": "Brightness was perfect but slightly too cool",
                "feedback_type": "too_cool",
                "user_id": "user_abc123"
            }
        }
