"""
Response models for the CircadianLight API.
These match the Swift CodingKeys from CircadianLight/Models/Models.swift
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


class LightingRecommendation(BaseModel):
    """
    Lighting recommendation based on health data and time of day.

    JSON fields match Swift LightingRecommendation CodingKeys (snake_case):
    - recommendation_id → LightingRecommendation.id
    - color_temp_kelvin → LightingRecommendation.colorTemperature
    - brightness_percent → LightingRecommendation.brightness
    - reasoning → LightingRecommendation.reasoning
    - generated_at → LightingRecommendation.timestamp

    Note: Swift expects ISO8601 datetime string with fractional seconds
    """

    recommendation_id: Optional[str] = Field(None, description="Unique ID for tracking feedback")
    color_temp_kelvin: int = Field(..., description="Color temperature in Kelvin (2000-6500)", ge=2000, le=6500)
    brightness_percent: int = Field(..., description="Brightness percentage (0-100)", ge=0, le=100)
    reasoning: str = Field(..., description="Explanation for this recommendation")
    generated_at: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
        description="ISO8601 timestamp of generation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "recommendation_id": "rec_123456",
                "color_temp_kelvin": 3500,
                "brightness_percent": 75,
                "reasoning": "Evening wind-down: warm light at moderate brightness supports melatonin production",
                "generated_at": "2025-12-03T18:30:00.000Z"
            }
        }


class FeedbackResponse(BaseModel):
    """
    Response after submitting feedback.

    JSON fields match Swift FeedbackResponse CodingKeys (snake_case):
    - success → FeedbackResponse.success
    - message → FeedbackResponse.message
    - feedback_id → FeedbackResponse.feedbackId
    """

    success: bool = Field(..., description="Whether feedback was recorded successfully")
    message: str = Field(..., description="Human-readable response message")
    feedback_id: Optional[str] = Field(None, description="ID of the recorded feedback")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Thank you for your feedback!",
                "feedback_id": "feedback_789"
            }
        }
