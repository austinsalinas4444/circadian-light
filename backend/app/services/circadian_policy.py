"""
Circadian lighting policy service with biologically-aware recommendations.

This module implements a 4-phase circadian lighting strategy that adjusts
color temperature (CCT) and brightness based on:
1. Time of day (via local_hour)
2. Sleep quality (via sleep_hours)
3. Recovery status (via hrv_ms - Heart Rate Variability)
4. Activity level (via step_count)
"""
from datetime import datetime
import uuid
from typing import Optional
from app.models.request_models import HealthFeaturesRequest
from app.models.response_models import LightingRecommendation


# Baseline thresholds for health metrics
HRV_BASELINE_LOW = 50.0  # Below this suggests poor recovery
HRV_BASELINE_STRONG = 75.0  # Above this suggests excellent recovery
SLEEP_BASELINE_LOW = 6.0  # Below this is suboptimal
SLEEP_BASELINE_GOOD = 8.0  # Above this is excellent
ACTIVITY_HIGH = 12000  # Above this suggests high activity day


class CircadianPhase:
    """Enum-like class for circadian phases"""
    MORNING_RAMPUP = "morning_rampup"
    FOCUS = "focus"
    WINDDOWN = "wind_down"
    NIGHT = "night"


class CircadianPolicyService:
    """
    Service for generating biologically-aware circadian lighting recommendations.

    The policy adapts to the user's circadian rhythm and health metrics to optimize
    alertness during the day and sleep quality at night.
    """

    @staticmethod
    def generate_recommendation(health_features: HealthFeaturesRequest) -> LightingRecommendation:
        """
        Generate a lighting recommendation based on health data and time of day.

        Args:
            health_features: Health data including HRV, sleep, steps, and local hour

        Returns:
            LightingRecommendation with optimized color temperature, brightness, and reasoning

        The algorithm follows a 4-phase approach:
        1. Determine circadian phase from local_hour
        2. Set base CCT and brightness for that phase
        3. Modulate based on health metrics (sleep quality, HRV, activity)
        4. Generate human-readable reasoning
        """
        # Determine local hour (fall back to server time if not provided)
        local_hour = health_features.local_hour
        if local_hour is None:
            local_hour = datetime.now().hour

        # Determine circadian phase
        phase = CircadianPolicyService._determine_phase(local_hour)

        # Get base CCT and brightness for this phase
        base_cct, base_brightness = CircadianPolicyService._get_base_values(phase)

        # Modulate based on health metrics
        final_cct, final_brightness = CircadianPolicyService._modulate_for_health(
            base_cct=base_cct,
            base_brightness=base_brightness,
            phase=phase,
            sleep_hours=health_features.sleep_hours,
            hrv_ms=health_features.hrv_ms,
            step_count=health_features.step_count,
            local_hour=local_hour
        )

        # Generate reasoning
        reasoning = CircadianPolicyService._build_reasoning(
            phase=phase,
            sleep_hours=health_features.sleep_hours,
            hrv_ms=health_features.hrv_ms,
            step_count=health_features.step_count,
            local_hour=local_hour
        )

        return LightingRecommendation(
            recommendation_id=f"rec_{uuid.uuid4().hex[:12]}",
            color_temp_kelvin=final_cct,
            brightness_percent=final_brightness,
            reasoning=reasoning
        )

    @staticmethod
    def _determine_phase(local_hour: int) -> str:
        """
        Determine circadian phase based on local hour.

        Phases:
        - 05:00-09:00 → Morning ramp-up (cortisol rise, waking)
        - 09:00-17:00 → Focus (peak cognitive performance)
        - 17:00-21:00 → Wind-down (preparation for sleep)
        - 21:00-05:00 → Night (sleep/melatonin phase)

        Args:
            local_hour: Hour of the day (0-23)

        Returns:
            CircadianPhase constant
        """
        if 5 <= local_hour < 9:
            return CircadianPhase.MORNING_RAMPUP
        elif 9 <= local_hour < 17:
            return CircadianPhase.FOCUS
        elif 17 <= local_hour < 21:
            return CircadianPhase.WINDDOWN
        else:  # 21-05
            return CircadianPhase.NIGHT

    @staticmethod
    def _get_base_values(phase: str) -> tuple[int, int]:
        """
        Get base color temperature and brightness for a circadian phase.

        Base values are optimized for circadian entrainment:
        - Morning: Moderate CCT to support cortisol rise
        - Focus: Higher CCT for alertness and task performance
        - Wind-down: Lower CCT to allow melatonin onset
        - Night: Very low CCT to minimize circadian disruption

        Args:
            phase: CircadianPhase constant

        Returns:
            Tuple of (color_temp_kelvin, brightness_percent)
        """
        base_values = {
            CircadianPhase.MORNING_RAMPUP: (4000, 70),  # 3500-4500K, 60-80%
            CircadianPhase.FOCUS: (5000, 90),            # 4500-5500K, 80-100%
            CircadianPhase.WINDDOWN: (2900, 50),         # 2700-3200K, 40-60%
            CircadianPhase.NIGHT: (2100, 20),            # 1800-2400K, 10-30%
        }
        return base_values.get(phase, (3500, 60))

    @staticmethod
    def _modulate_for_health(
        base_cct: int,
        base_brightness: int,
        phase: str,
        sleep_hours: Optional[float],
        hrv_ms: Optional[float],
        step_count: Optional[int],
        local_hour: int
    ) -> tuple[int, int]:
        """
        Modulate base lighting values based on health metrics.

        Health-based adjustments:
        - Poor sleep (<6h) → Warmer, dimmer (prioritize recovery)
        - Low HRV (<50ms) → Warmer, dimmer (reduce stress)
        - Good sleep (≥8h) + Strong HRV (≥75ms) → Cooler, brighter (optimize performance)
        - High activity (>12k steps) in evening → Extra dim for recovery

        Args:
            base_cct: Base color temperature
            base_brightness: Base brightness percentage
            phase: Current circadian phase
            sleep_hours: Hours of sleep (optional)
            hrv_ms: Heart rate variability in ms (optional)
            step_count: Steps taken today (optional)
            local_hour: Current local hour

        Returns:
            Tuple of (adjusted_cct, adjusted_brightness)
        """
        adjusted_cct = base_cct
        adjusted_brightness = base_brightness

        # Handle None values gracefully - no modulation if data missing
        if sleep_hours is None or hrv_ms is None:
            return adjusted_cct, adjusted_brightness

        # Determine recovery status
        poor_sleep = sleep_hours < SLEEP_BASELINE_LOW
        good_sleep = sleep_hours >= SLEEP_BASELINE_GOOD
        low_hrv = hrv_ms < HRV_BASELINE_LOW
        strong_hrv = hrv_ms >= HRV_BASELINE_STRONG

        # Recovery mode: Poor sleep OR low HRV
        if poor_sleep or low_hrv:
            if phase == CircadianPhase.MORNING_RAMPUP:
                # Morning after poor sleep: slightly warmer to reduce stress
                adjusted_cct -= 300
                adjusted_brightness -= 5
            elif phase == CircadianPhase.FOCUS:
                # Daytime with poor recovery: need to push through but reduce intensity
                adjusted_cct -= 200
                adjusted_brightness -= 10
            elif phase in (CircadianPhase.WINDDOWN, CircadianPhase.NIGHT):
                # Evening/night with poor recovery: prioritize deep sleep
                adjusted_cct -= 400
                adjusted_brightness -= 15

        # Performance mode: Good sleep AND strong HRV
        elif good_sleep and strong_hrv:
            if phase == CircadianPhase.MORNING_RAMPUP:
                # Morning after great sleep: cooler for energy
                adjusted_cct += 300
                adjusted_brightness += 10
            elif phase == CircadianPhase.FOCUS:
                # Daytime with strong recovery: maximize alertness
                adjusted_cct += 300
                adjusted_brightness += 10
            # Don't increase brightness in wind-down/night even with good recovery

        # Activity-based adjustment
        if step_count is not None and step_count > ACTIVITY_HIGH:
            # High activity day → extra recovery support in evening
            if phase in (CircadianPhase.WINDDOWN, CircadianPhase.NIGHT):
                adjusted_cct -= 200
                adjusted_brightness -= 10

        # Clamp to valid ranges
        adjusted_cct = max(1800, min(6500, adjusted_cct))
        adjusted_brightness = max(10, min(100, adjusted_brightness))

        return adjusted_cct, adjusted_brightness

    @staticmethod
    def _build_reasoning(
        phase: str,
        sleep_hours: Optional[float],
        hrv_ms: Optional[float],
        step_count: Optional[int],
        local_hour: int
    ) -> str:
        """
        Build a human-readable explanation for the lighting recommendation.

        The reasoning explains:
        1. Current circadian phase and base rationale
        2. Health metric status and adjustments made
        3. Overall goal (alertness, recovery, sleep preparation, etc.)

        Args:
            phase: Current circadian phase
            sleep_hours: Hours of sleep
            hrv_ms: Heart rate variability
            step_count: Steps taken
            local_hour: Current local hour

        Returns:
            Detailed reasoning string
        """
        # Base reasoning by phase
        phase_messages = {
            CircadianPhase.MORNING_RAMPUP: (
                "Morning ramp-up: Moderate brightness and cool-neutral light support "
                "natural cortisol rise and waking alertness."
            ),
            CircadianPhase.FOCUS: (
                "Daytime focus: Bright, cooler light optimizes cognitive performance, "
                "alertness, and task concentration."
            ),
            CircadianPhase.WINDDOWN: (
                "Evening wind-down: Warm, dimmer light reduces blue light exposure "
                "and allows natural melatonin onset."
            ),
            CircadianPhase.NIGHT: (
                "Night mode: Very warm, minimal light preserves melatonin production "
                "and supports circadian alignment."
            )
        }

        base_message = phase_messages.get(phase, "Time-optimized lighting for your circadian rhythm.")

        # Add health context if available
        health_context = []

        if sleep_hours is not None:
            if sleep_hours < SLEEP_BASELINE_LOW:
                health_context.append(
                    f"After {sleep_hours:.1f}h sleep (below optimal), using slightly warmer, dimmer settings to prioritize recovery."
                )
            elif sleep_hours >= SLEEP_BASELINE_GOOD:
                health_context.append(
                    f"With {sleep_hours:.1f}h quality sleep, using cooler, brighter settings to maximize performance."
                )

        if hrv_ms is not None:
            if hrv_ms < HRV_BASELINE_LOW:
                health_context.append(
                    f"Lower HRV ({hrv_ms:.0f}ms) suggests reduced recovery - adjusting for gentle stimulation and stress reduction."
                )
            elif hrv_ms >= HRV_BASELINE_STRONG:
                health_context.append(
                    f"Strong HRV ({hrv_ms:.0f}ms) indicates excellent recovery - optimized for peak alertness."
                )

        if step_count is not None and step_count > ACTIVITY_HIGH:
            if phase in (CircadianPhase.WINDDOWN, CircadianPhase.NIGHT):
                health_context.append(
                    f"After a highly active day ({step_count:,} steps), using extra-dim, warm light to support recovery."
                )

        # Combine base and health context
        if health_context:
            return base_message + " " + " ".join(health_context)
        else:
            return base_message + " Based on time of day (health metrics not provided)."
