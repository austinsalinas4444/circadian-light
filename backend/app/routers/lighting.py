"""
Lighting recommendation API endpoints.
"""
from fastapi import APIRouter, HTTPException, status
from app.models.request_models import HealthFeaturesRequest, FeedbackRequest
from app.models.response_models import LightingRecommendation, FeedbackResponse
from app.services.circadian_policy import CircadianPolicyService
from app.services.wiz_lighting import WizLightingService
import uuid

router = APIRouter(prefix="/api/v1", tags=["lighting"])

# Initialize services
policy_service = CircadianPolicyService()
wiz_service = WizLightingService()


@router.post(
    "/health-features",
    response_model=LightingRecommendation,
    status_code=status.HTTP_200_OK,
    summary="Generate lighting recommendation",
    description="Accepts health features (HRV, sleep, steps) and returns a personalized, biologically-aware lighting recommendation"
)
async def get_lighting_recommendation(health_features: HealthFeaturesRequest) -> LightingRecommendation:
    """
    Generate a lighting recommendation based on health data and time of day.

    The recommendation uses a 4-phase circadian model:
    - Morning ramp-up (05:00-09:00): 3500-4500K, 60-80% brightness
    - Focus (09:00-17:00): 4500-5500K, 80-100% brightness
    - Wind-down (17:00-21:00): 2700-3200K, 40-60% brightness
    - Night (21:00-05:00): 1800-2400K, 10-30% brightness

    Health metrics modulate these base values:
    - Poor sleep (<6h) or low HRV (<50ms) → warmer, dimmer
    - Good sleep (≥8h) and strong HRV (≥75ms) → cooler, brighter
    - High activity (>12k steps) → dimmer in evening

    Args:
        health_features: User's health metrics (HRV, sleep hours, step count, local hour)

    Returns:
        LightingRecommendation with optimized color temperature, brightness, and reasoning

    Raises:
        HTTPException: If recommendation generation fails
    """
    print(f"Received health data: HRV={health_features.hrv_ms}ms, Sleep={health_features.sleep_hours}h, Steps={health_features.step_count}")

    try:
        recommendation = policy_service.generate_recommendation(health_features)
        print(f"Recommendation: {recommendation.color_temp_kelvin}K, {recommendation.brightness_percent}%, Phase: {recommendation.reasoning}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendation: {str(e)}"
        )

    try:
        await wiz_service.apply_recommendation(
            color_temp_kelvin=recommendation.color_temp_kelvin,
            brightness_percent=recommendation.brightness_percent,
        )
    except Exception as e:
        print(f"[WIZ] Failed to apply recommendation to bulb: {e}")

    return recommendation


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit user feedback",
    description="Submit feedback (rating and optional comment) on a lighting recommendation"
)
async def submit_feedback(feedback: FeedbackRequest) -> FeedbackResponse:
    """
    Record user feedback on a lighting recommendation.

    In production, this would store feedback in a database for:
    - Model training and improvement
    - Quality monitoring
    - Personalization algorithms

    Currently returns a success response and logs feedback to console.

    Args:
        feedback: User's rating (1-5) and optional comment

    Returns:
        FeedbackResponse confirming the feedback was recorded

    Raises:
        HTTPException: If feedback submission fails
    """
    try:
        # TODO: Store feedback in database when implemented
        # For now, log and return success
        feedback_id = f"feedback_{uuid.uuid4().hex[:8]}"

        print(f"[FEEDBACK] ID: {feedback_id}")
        print(f"  Recommendation: {feedback.recommendation_id}")
        print(f"  Rating: {feedback.rating}/5")
        if feedback.comment:
            print(f"  Comment: {feedback.comment}")

        return FeedbackResponse(
            success=True,
            message="Thank you for your feedback!",
            feedback_id=feedback_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )
