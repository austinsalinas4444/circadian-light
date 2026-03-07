"""
Request models for the CircadianLight API.
These match the Swift CodingKeys from CircadianLight/Models/Models.swift
"""
from pydantic import BaseModel, Field
from typing import Optional


class HealthFeaturesRequest(BaseModel):
    """
    Health data from iOS app to generate lighting recommendations.

    JSON fields match Swift HealthFeatures CodingKeys (snake_case):
    - hrv_ms → HealthFeatures.hrvMilliseconds
    - sleep_hours → HealthFeatures.sleepHours
    - step_count → HealthFeatures.stepCount
    - local_hour → Added for circadian phase calculation
    """

    hrv_ms: float = Field(..., description="Heart Rate Variability in milliseconds", ge=0)
    sleep_hours: float = Field(..., description="Hours of sleep", ge=0, le=24)
    step_count: int = Field(..., description="Number of steps taken", ge=0)
    local_hour: Optional[int] = Field(None, description="Client's local hour (0-23) for circadian phase", ge=0, le=23)

    class Config:
        json_schema_extra = {
            "example": {
                "hrv_ms": 65.0,
                "sleep_hours": 7.5,
                "step_count": 8500,
                "local_hour": 14
            }
        }


class FeedbackRequest(BaseModel):
    """
    User feedback on a lighting recommendation.

    JSON fields match Swift LightingFeedback CodingKeys (snake_case):
    - recommendation_id → LightingFeedback.recommendationId
    - rating → LightingFeedback.rating
    - comment → LightingFeedback.comment
    """

    recommendation_id: Optional[str] = Field(None, description="ID of the recommendation being rated")
    rating: int = Field(..., description="User rating (1-5 stars)", ge=1, le=5)
    comment: Optional[str] = Field(None, description="Optional user comment")

    class Config:
        json_schema_extra = {
            "example": {
                "recommendation_id": "rec_123456",
                "rating": 4,
                "comment": "The brightness was perfect but could be slightly warmer"
            }
        }
