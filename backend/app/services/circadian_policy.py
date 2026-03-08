"""
Circadian lighting policy service with research-validated recommendations.

6-phase model anchored to user wake/sleep times:
  night       → 2100K, 15%    (deep sleep preservation)
  wake_ramp   → ramp 3000→5500K, 50→80%  (cortisol rise support)
  morning     → 5500K, 90%    (peak alertness onset)
  focus       → 5000K, 85%    (sustained cognitive performance)
  transition  → ramp 4500→3000K, 70→50%  (melatonin onset prep)
  wind_down   → ramp 2700→2200K, 40→25%  (sleep preparation)

Health thresholds (research-based):
  HRV_LOW=40ms, HRV_HIGH=80ms, SLEEP_HOURS_LOW=6h, SLEEP_SCORE_LOW=70

Recovery mode activates when hrv < 40 OR sleep_hours < 6 OR sleep_score <= 70:
  - Caps CCT at 3500K
  - Multiplies brightness by 0.7
"""
import os
from datetime import datetime
from typing import Optional
import uuid

from app.models.request_models import HealthFeaturesRequest
from app.models.response_models import LightingRecommendation

# --- User anchors (overridable via env) ---
WAKE_TIME = int(os.getenv("WAKE_TIME", 8))   # hour of wake (e.g. 8 = 8am)
SLEEP_TIME = int(os.getenv("SLEEP_TIME", 24)) # hour of sleep (24 = midnight for math)

# --- Health thresholds ---
HRV_LOW = 40.0           # ms — below: stress / poor recovery
HRV_HIGH = 80.0          # ms — above: excellent recovery
SLEEP_HOURS_LOW = 6.0    # h  — below: suboptimal sleep quantity
SLEEP_SCORE_LOW = 70.0   # 0-100 — at/below: recovery mode triggers
ACTIVITY_HIGH = 12000    # steps — above: high activity day


class CircadianPhase:
    NIGHT = "night"
    WAKE_RAMP = "wake_ramp"
    MORNING = "morning"
    FOCUS = "focus"
    TRANSITION = "transition"
    WIND_DOWN = "wind_down"


def compute_sleep_score(
    sleep_hours: float,
    deep_sleep_pct: float,
    rem_sleep_pct: float,
    sleep_efficiency: float,
) -> float:
    """
    Compute a 0-100 sleep quality score from component metrics.

    Weights:
      - sleep_hours    → up to 30 pts  (target: 8h)
      - deep_sleep_pct → up to 25 pts  (target: 20% of total)
      - rem_sleep_pct  → up to 25 pts  (target: 25% of total)
      - sleep_efficiency → up to 20 pts (fraction 0-1, e.g. 0.90 = 90%)

    Args:
        sleep_hours:     total hours of sleep
        deep_sleep_pct:  fraction of sleep in deep/slow-wave stage (0-1)
        rem_sleep_pct:   fraction of sleep in REM stage (0-1)
        sleep_efficiency: fraction of time-in-bed actually asleep (0-1)

    Returns:
        Score clamped to [0, 100]
    """
    score = (sleep_hours / 8.0) * 30.0
    score += (deep_sleep_pct / 0.20) * 25.0
    score += (rem_sleep_pct / 0.25) * 25.0
    score += sleep_efficiency * 20.0
    return max(0.0, min(100.0, score))


class CircadianPolicyService:
    """
    Generates biologically-aware circadian lighting recommendations.

    The policy adapts to the user's circadian rhythm (anchored to wake/sleep
    times) and health metrics (HRV, sleep quantity/quality, activity level).
    """

    @staticmethod
    def generate_recommendation(health_features: HealthFeaturesRequest) -> LightingRecommendation:
        """
        Generate a lighting recommendation from health data and time of day.

        Algorithm:
          1. Determine circadian phase from local_hour relative to WAKE/SLEEP anchors
          2. Compute base CCT and brightness (with linear ramps for transition phases)
          3. Resolve sleep_score from request or component metrics
          4. Check recovery mode (hrv < HRV_LOW, sleep_hours < SLEEP_HOURS_LOW,
             or sleep_score <= SLEEP_SCORE_LOW)
          5. Apply health modulation (warm/dim shifts) or recovery cap
          6. Build human-readable reasoning

        Returns:
            LightingRecommendation with color_temp_kelvin, brightness_percent,
            reasoning, and recovery_mode flag
        """
        local_hour = health_features.local_hour
        if local_hour is None:
            local_hour = datetime.now().hour

        phase = CircadianPolicyService._determine_phase(local_hour)
        base_cct, base_brightness = CircadianPolicyService._get_base_values(phase, local_hour)

        # Resolve sleep_score
        sleep_score = health_features.sleep_score
        if sleep_score is None and all(v is not None for v in [
            health_features.deep_sleep_pct,
            health_features.rem_sleep_pct,
            health_features.sleep_efficiency,
        ]):
            sleep_score = compute_sleep_score(
                sleep_hours=health_features.sleep_hours or 7.0,
                deep_sleep_pct=health_features.deep_sleep_pct,
                rem_sleep_pct=health_features.rem_sleep_pct,
                sleep_efficiency=health_features.sleep_efficiency,
            )

        # Recovery mode check
        recovery_mode = CircadianPolicyService._is_recovery_mode(
            hrv_ms=health_features.hrv_ms,
            sleep_hours=health_features.sleep_hours,
            sleep_score=sleep_score,
        )

        # Apply adjustments
        final_cct, final_brightness = CircadianPolicyService._apply_adjustments(
            base_cct=base_cct,
            base_brightness=base_brightness,
            phase=phase,
            hrv_ms=health_features.hrv_ms,
            sleep_hours=health_features.sleep_hours,
            step_count=health_features.step_count,
            recovery_mode=recovery_mode,
        )

        reasoning = CircadianPolicyService._build_reasoning(
            phase=phase,
            hrv_ms=health_features.hrv_ms,
            sleep_hours=health_features.sleep_hours,
            sleep_score=sleep_score,
            step_count=health_features.step_count,
            recovery_mode=recovery_mode,
            local_hour=local_hour,
        )

        return LightingRecommendation(
            recommendation_id=f"rec_{uuid.uuid4().hex[:12]}",
            color_temp_kelvin=final_cct,
            brightness_percent=final_brightness,
            reasoning=reasoning,
            recovery_mode=recovery_mode,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_phase(local_hour: int) -> str:
        """
        Map local_hour to a circadian phase.

        Phase boundaries (default WAKE=8, SLEEP=24):
          night:      00:00 – 06:59  (0 to WAKE_TIME-2 inclusive)
          wake_ramp:  07:00 – 08:59  (WAKE_TIME-1 to WAKE_TIME inclusive)
          morning:    09:00 – 10:59  (WAKE_TIME+1 to WAKE_TIME+2 inclusive)
          focus:      11:00 – 16:59  (WAKE_TIME+3 to SLEEP_TIME-8 inclusive)
          transition: 17:00 – 20:59  (SLEEP_TIME-7 to SLEEP_TIME-4 inclusive)
          wind_down:  21:00 – 23:59  (SLEEP_TIME-3 to SLEEP_TIME-1 inclusive)
        """
        wt = WAKE_TIME
        st = SLEEP_TIME

        if local_hour < wt - 1:
            return CircadianPhase.NIGHT
        elif local_hour < wt + 1:
            return CircadianPhase.WAKE_RAMP
        elif local_hour < wt + 3:
            return CircadianPhase.MORNING
        elif local_hour < st - 7:
            return CircadianPhase.FOCUS
        elif local_hour < st - 3:
            return CircadianPhase.TRANSITION
        else:
            return CircadianPhase.WIND_DOWN

    @staticmethod
    def _get_base_values(phase: str, local_hour: int) -> tuple[int, int]:
        """
        Compute base CCT and brightness for the phase, interpolating linearly
        within ramp phases (wake_ramp, transition, wind_down).

        Returns:
            (color_temp_kelvin, brightness_percent)
        """
        wt = WAKE_TIME
        st = SLEEP_TIME

        if phase == CircadianPhase.NIGHT:
            return 2100, 15

        elif phase == CircadianPhase.WAKE_RAMP:
            # 3000K→5500K, 50%→80% over 2 hours (WAKE_TIME-1 to WAKE_TIME+1)
            progress = (local_hour - (wt - 1)) / 2.0
            progress = max(0.0, min(1.0, progress))
            cct = int(3000 + progress * (5500 - 3000))
            bri = int(50 + progress * (80 - 50))
            return cct, bri

        elif phase == CircadianPhase.MORNING:
            return 5500, 90

        elif phase == CircadianPhase.FOCUS:
            return 5000, 85

        elif phase == CircadianPhase.TRANSITION:
            # 4500K→3000K, 70%→50% over 4 hours (SLEEP_TIME-7 to SLEEP_TIME-3)
            progress = (local_hour - (st - 7)) / 4.0
            progress = max(0.0, min(1.0, progress))
            cct = int(4500 + progress * (3000 - 4500))
            bri = int(70 + progress * (50 - 70))
            return cct, bri

        else:  # WIND_DOWN
            # 2700K→2200K, 40%→25% over 3 hours (SLEEP_TIME-3 to SLEEP_TIME)
            progress = (local_hour - (st - 3)) / 3.0
            progress = max(0.0, min(1.0, progress))
            cct = int(2700 + progress * (2200 - 2700))
            bri = int(40 + progress * (25 - 40))
            return cct, bri

    @staticmethod
    def _is_recovery_mode(
        hrv_ms: Optional[float],
        sleep_hours: Optional[float],
        sleep_score: Optional[float],
    ) -> bool:
        """
        Activate recovery mode when any critical threshold is breached:
          - HRV < HRV_LOW (40ms)
          - sleep_hours < SLEEP_HOURS_LOW (6h)
          - sleep_score <= SLEEP_SCORE_LOW (70)
        """
        if hrv_ms is not None and hrv_ms < HRV_LOW:
            return True
        if sleep_hours is not None and sleep_hours < SLEEP_HOURS_LOW:
            return True
        if sleep_score is not None and sleep_score <= SLEEP_SCORE_LOW:
            return True
        return False

    @staticmethod
    def _apply_adjustments(
        base_cct: int,
        base_brightness: int,
        phase: str,
        hrv_ms: Optional[float],
        sleep_hours: Optional[float],
        step_count: Optional[int],
        recovery_mode: bool,
    ) -> tuple[int, int]:
        """
        Apply health-based modulation to base CCT and brightness.

        Recovery mode:
          - Cap CCT at 3500K
          - Multiply brightness by 0.7

        Normal modulation (when not in recovery mode):
          - Low HRV (40-60ms): -300K, -10%
          - Poor sleep (<6.5h): -200K, -15%
          - High HRV (>80ms): no additional shift (full phase CCT is fine)
          - High activity (>12k steps) in evening phases: -10% brightness

        All values are clamped to valid ranges: 1800-6500K, 10-100%.
        """
        cct = base_cct
        bri = base_brightness

        if recovery_mode:
            cct = min(cct, 3500)
            bri = int(bri * 0.7)
        else:
            # HRV modulation — only the intermediate-low range (40-60ms)
            if hrv_ms is not None and HRV_LOW <= hrv_ms < 60.0:
                cct -= 300
                bri -= 10

            # Sleep quantity modulation
            if sleep_hours is not None and sleep_hours < 6.5:
                cct -= 200
                bri -= 15

        # High-activity evening dimming (applies regardless of recovery mode)
        if step_count is not None and step_count > ACTIVITY_HIGH:
            if phase in (CircadianPhase.TRANSITION, CircadianPhase.WIND_DOWN):
                bri -= 10

        # Clamp to hardware-safe ranges
        cct = max(1800, min(6500, cct))
        bri = max(10, min(100, bri))
        return cct, bri

    @staticmethod
    def _build_reasoning(
        phase: str,
        hrv_ms: Optional[float],
        sleep_hours: Optional[float],
        sleep_score: Optional[float],
        step_count: Optional[int],
        recovery_mode: bool,
        local_hour: int,
    ) -> str:
        """
        Build a human-readable explanation of the current recommendation.
        Explains phase rationale, recovery mode activation, and health adjustments.
        """
        phase_messages = {
            CircadianPhase.NIGHT: (
                "Night mode: Very warm, minimal light preserves melatonin production "
                "and protects circadian alignment during sleep."
            ),
            CircadianPhase.WAKE_RAMP: (
                "Wake ramp: Gradually brightening, cooling light supports the natural "
                "cortisol rise and eases the transition from sleep to wakefulness."
            ),
            CircadianPhase.MORNING: (
                "Morning: Bright, cool light (5500K) maximizes cortisol response, "
                "establishes strong circadian entrainment, and drives alertness onset."
            ),
            CircadianPhase.FOCUS: (
                "Focus: Bright, slightly cooler-than-neutral light (5000K) sustains "
                "cognitive performance and suppresses midday drowsiness."
            ),
            CircadianPhase.TRANSITION: (
                "Transition: Progressively warming, dimming light reduces blue-light "
                "stimulation and begins melatonin onset preparation."
            ),
            CircadianPhase.WIND_DOWN: (
                "Wind-down: Warm, dim light (2700→2200K) minimizes circadian-active "
                "photons and signals the brain that sleep is imminent."
            ),
        }

        base = phase_messages.get(phase, "Time-optimized lighting for your circadian rhythm.")
        context: list[str] = []

        if recovery_mode:
            reasons: list[str] = []
            if hrv_ms is not None and hrv_ms < HRV_LOW:
                reasons.append(f"low HRV ({hrv_ms:.0f}ms)")
            if sleep_hours is not None and sleep_hours < SLEEP_HOURS_LOW:
                reasons.append(f"short sleep ({sleep_hours:.1f}h)")
            if sleep_score is not None and sleep_score <= SLEEP_SCORE_LOW:
                reasons.append(f"low sleep score ({sleep_score:.0f}/100)")
            trigger = ", ".join(reasons) if reasons else "poor recovery indicators"
            context.append(
                f"Recovery mode active ({trigger}): CCT capped at 3500K and brightness "
                "reduced 30% to minimize stress and prioritize physiological recovery."
            )
        else:
            if hrv_ms is not None and HRV_LOW <= hrv_ms < 60.0:
                context.append(
                    f"Moderate HRV ({hrv_ms:.0f}ms) suggests suboptimal recovery — "
                    "applying a warm shift and slight dim to reduce autonomic load."
                )
            elif hrv_ms is not None and hrv_ms >= HRV_HIGH:
                context.append(
                    f"Strong HRV ({hrv_ms:.0f}ms) indicates excellent recovery — "
                    "full phase settings applied."
                )

            if sleep_hours is not None and sleep_hours < 6.5:
                context.append(
                    f"Short sleep ({sleep_hours:.1f}h) — applying warm shift and dim "
                    "to support recovery without over-stimulating."
                )
            elif sleep_hours is not None and sleep_hours >= 8.0:
                if sleep_score is not None:
                    context.append(
                        f"Good sleep ({sleep_hours:.1f}h, score {sleep_score:.0f}/100) "
                        "— full phase settings applied."
                    )
                else:
                    context.append(
                        f"Good sleep duration ({sleep_hours:.1f}h) — full phase settings applied."
                    )

        if step_count is not None and step_count > ACTIVITY_HIGH:
            if phase in (CircadianPhase.TRANSITION, CircadianPhase.WIND_DOWN):
                context.append(
                    f"High-activity day ({step_count:,} steps) — extra 10% brightness "
                    "reduction to support muscular and metabolic recovery overnight."
                )

        if not context and not recovery_mode:
            context.append("Health metrics within normal range — standard phase settings applied.")

        return base + " " + " ".join(context)
