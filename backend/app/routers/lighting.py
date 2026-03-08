"""
Lighting recommendation API endpoints.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.models.request_models import HealthFeaturesRequest, FeedbackRequest
from app.models.response_models import LightingRecommendation, FeedbackResponse
from app.services.circadian_policy import CircadianPolicyService
from app.services.wiz_lighting import WizLightingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["lighting"])

# --- Feature flags ---
USE_ML_MODEL: bool = os.getenv("USE_ML_MODEL", "false").lower() == "true"

# --- Service singletons ---
policy_service = CircadianPolicyService()
wiz_service = WizLightingService()

# Lazy-init ML inference so missing torch doesn't break startup
_ml_inference = None


def _get_ml_inference():
    global _ml_inference
    if _ml_inference is None:
        try:
            from ml.inference import CircadianModelInference
            _ml_inference = CircadianModelInference()
        except ImportError:
            logger.warning("ml.inference unavailable — ML model disabled.")
    return _ml_inference


@router.post(
    "/health-features",
    response_model=LightingRecommendation,
    status_code=status.HTTP_200_OK,
    summary="Generate lighting recommendation",
    description=(
        "Accepts health features (HRV, sleep, steps, optional sleep quality metrics) "
        "and returns a personalized, biologically-aware lighting recommendation. "
        "Uses CircadianNet ML model when USE_ML_MODEL=true, otherwise rule-based policy."
    ),
)
async def get_lighting_recommendation(
    health_features: HealthFeaturesRequest,
) -> LightingRecommendation:
    """
    Generate a lighting recommendation from health data and time of day.

    Decision flow:
      1. If USE_ML_MODEL=true → attempt CircadianModelInference.predict()
      2. Fall back to CircadianPolicyService on failure or when flag is false
      3. Apply recommendation to WiZ bulb (non-blocking on error)
      4. Persist health snapshot to Supabase as background task (fire-and-forget)
    """
    local_hour = health_features.local_hour if health_features.local_hour is not None else datetime.now().hour
    logger.info(
        "Request: HRV=%.0fms  sleep=%.1fh  steps=%d  hour=%d",
        health_features.hrv_ms,
        health_features.sleep_hours,
        health_features.step_count,
        local_hour,
    )

    recommendation: LightingRecommendation | None = None

    # --- ML path ---
    if USE_ML_MODEL:
        inference = _get_ml_inference()
        if inference is not None:
            try:
                result = await asyncio.to_thread(
                    inference.predict,
                    hrv_ms=health_features.hrv_ms,
                    sleep_hours=health_features.sleep_hours,
                    sleep_score=health_features.sleep_score or 68.0,
                    resting_hr=health_features.resting_hr or 50.0,
                    steps=float(health_features.step_count),
                    active_energy=health_features.active_energy or 350.0,
                    hour=local_hour,
                    day_of_week=datetime.now().weekday(),
                )
                if result is not None:
                    cct, bri = result
                    recommendation = LightingRecommendation(
                        recommendation_id=f"rec_{uuid.uuid4().hex[:12]}",
                        color_temp_kelvin=cct,
                        brightness_percent=bri,
                        reasoning="CircadianNet ML model prediction.",
                        recovery_mode=False,
                    )
                    logger.info("ML prediction: %dK  %d%%", cct, bri)
            except Exception as exc:
                logger.warning("ML inference error, falling back to policy: %s", exc)

    # --- Policy fallback ---
    if recommendation is None:
        try:
            recommendation = policy_service.generate_recommendation(health_features)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate recommendation: {exc}",
            )

    logger.info(
        "Recommendation: %dK  %d%%  recovery_mode=%s",
        recommendation.color_temp_kelvin,
        recommendation.brightness_percent,
        recommendation.recovery_mode,
    )

    # --- WiZ bulb (non-blocking on error) ---
    try:
        await wiz_service.apply_recommendation(
            color_temp_kelvin=recommendation.color_temp_kelvin,
            brightness_percent=recommendation.brightness_percent,
        )
    except Exception as exc:
        logger.warning("[WIZ] Failed to apply recommendation: %s", exc)

    # --- Supabase snapshot (fire-and-forget) ---
    if health_features.user_id:
        asyncio.create_task(
            _save_health_snapshot_bg(health_features)
        )

    return recommendation


async def _save_health_snapshot_bg(health_features: HealthFeaturesRequest) -> None:
    """Background task: persist health snapshot to Supabase. Never raises."""
    try:
        from app.db.crud import save_health_snapshot
        from app.db.schemas import HealthSnapshot

        snapshot = HealthSnapshot(
            user_id=health_features.user_id,
            hrv_ms=health_features.hrv_ms,
            sleep_hours=health_features.sleep_hours,
            sleep_score=health_features.sleep_score,
            resting_hr=health_features.resting_hr,
            steps=health_features.step_count,
            active_energy=health_features.active_energy,
        )
        await save_health_snapshot(snapshot)
    except Exception as exc:
        logger.warning("Background Supabase save failed: %s", exc)


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit user feedback",
    description="Submit a rating and optional structured feedback on a lighting recommendation",
)
async def submit_feedback(feedback: FeedbackRequest) -> FeedbackResponse:
    """
    Record user feedback on a lighting recommendation.

    Persists to Supabase when user_id is provided. Always returns success
    so the iOS app is never blocked by a storage failure.
    """
    try:
        feedback_id = f"feedback_{uuid.uuid4().hex[:8]}"

        logger.info(
            "[FEEDBACK] id=%s  rec=%s  rating=%d/5  type=%s",
            feedback_id,
            feedback.recommendation_id,
            feedback.rating,
            feedback.feedback_type,
        )
        if feedback.comment:
            logger.info("[FEEDBACK] comment: %s", feedback.comment)

        if feedback.user_id and feedback.recommendation_id:
            asyncio.create_task(_save_feedback_bg(feedback, feedback_id))

        return FeedbackResponse(
            success=True,
            message="Thank you for your feedback!",
            feedback_id=feedback_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {exc}",
        )


async def _save_feedback_bg(feedback: FeedbackRequest, feedback_id: str) -> None:
    """Background task: persist feedback to Supabase. Never raises."""
    try:
        from app.db.crud import save_feedback
        from app.db.schemas import LightingFeedback

        row = LightingFeedback(
            user_id=feedback.user_id,
            recommended_cct=0,
            recommended_brightness=0,
            rating=feedback.rating,
            feedback_type=feedback.feedback_type,
        )
        await save_feedback(row)
    except Exception as exc:
        logger.warning("Background feedback save failed: %s", exc)
