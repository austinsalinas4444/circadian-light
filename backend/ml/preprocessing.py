"""
Feature preprocessing for CircadianNet.

Handles z-score normalization of input features and min-max
denormalization of network outputs back to human-readable units.

Feature statistics are derived from Austin's health export data
(backend/data/*.csv, Dec 2025 – Jan 2026 range).
"""
import torch
from typing import Optional

# --- Feature statistics (mean, std) derived from Austin's health data ---
# Order must match the input vector used in normalize() and train.py.
FEATURE_STATS: dict[str, tuple[float, float]] = {
    "hrv_ms":        (100.0, 35.0),   # SDNN ms; observed range ~52-191
    "sleep_hours":   (7.0,   1.5),    # total nightly sleep hours
    "sleep_score":   (68.0,  15.0),   # composite 0-100 score
    "resting_hr":    (49.5,  3.0),    # bpm; observed 47-52
    "steps":         (7000.0, 4000.0),# daily step count
    "active_energy": (350.0, 200.0),  # daily kcal
    "hour":          (11.5,  6.92),   # hour of day 0-23 (uniform dist)
    "day_of_week":   (3.0,   2.0),    # 0=Mon … 6=Sun (uniform dist)
}

# --- Output scaling ---
CCT_MIN, CCT_MAX = 1800.0, 6500.0
BRI_MIN, BRI_MAX = 10.0, 100.0


class FeatureProcessor:
    """
    Stateless utility for converting health features to model tensors
    and converting model outputs back to actionable lighting values.
    """

    @staticmethod
    def normalize(
        hrv_ms: float,
        sleep_hours: float,
        sleep_score: float,
        resting_hr: float,
        steps: float,
        active_energy: float,
        hour: int,
        day_of_week: int,
    ) -> torch.Tensor:
        """
        Z-score normalize a single feature vector.

        Args:
            hrv_ms:        Heart rate variability (ms)
            sleep_hours:   Total sleep duration (h)
            sleep_score:   Composite sleep quality score (0-100)
            resting_hr:    Resting heart rate (bpm)
            steps:         Daily step count
            active_energy: Daily active calories (kcal)
            hour:          Local hour of day (0-23)
            day_of_week:   Day of week (0=Monday … 6=Sunday)

        Returns:
            Float32 tensor of shape (1, 8), normalized.
        """
        raw = [hrv_ms, sleep_hours, sleep_score, resting_hr,
               steps, active_energy, float(hour), float(day_of_week)]

        stats = list(FEATURE_STATS.values())
        normalized = [(v - mean) / (std if std > 0 else 1.0)
                      for v, (mean, std) in zip(raw, stats)]
        return torch.tensor([normalized], dtype=torch.float32)

    @staticmethod
    def denormalize_output(tensor: torch.Tensor) -> tuple[int, int]:
        """
        Convert model output tensor to (cct_kelvin, brightness_percent).

        Expects a tensor of shape (1, 2) or (2,) with values nominally
        in [0, 1] (the model is trained with normalized targets in that range).
        Out-of-range predictions are clamped before scaling.

        Returns:
            (color_temp_kelvin, brightness_percent) as integers.
        """
        values = tensor.squeeze().tolist()
        if isinstance(values, float):
            values = [values, 0.5]

        cct_norm = max(0.0, min(1.0, float(values[0])))
        bri_norm = max(0.0, min(1.0, float(values[1])))

        cct = int(cct_norm * (CCT_MAX - CCT_MIN) + CCT_MIN)
        bri = int(bri_norm * (BRI_MAX - BRI_MIN) + BRI_MIN)
        return cct, bri

    @staticmethod
    def normalize_target(cct: float, brightness: float) -> list[float]:
        """
        Normalize a CCT/brightness pair to [0, 1] for use as training labels.

        Args:
            cct:        Color temperature in Kelvin (1800-6500)
            brightness: Brightness percent (10-100)

        Returns:
            [cct_norm, brightness_norm] in [0, 1]
        """
        cct_norm = (cct - CCT_MIN) / (CCT_MAX - CCT_MIN)
        bri_norm = (brightness - BRI_MIN) / (BRI_MAX - BRI_MIN)
        return [cct_norm, bri_norm]
