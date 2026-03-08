"""
ML inference wrapper for CircadianNet.

Loads a saved .pt model and provides a predict() method that takes
health data and returns (cct_kelvin, brightness_percent).

Fallback behaviour:
    If the model file doesn't exist, fails to load, or raises during
    inference, predict() returns None and the caller falls back to
    the rule-based circadian policy.
"""
import logging
from pathlib import Path
from typing import Optional

import torch

from ml.models.circadian_net import CircadianNet
from ml.preprocessing import FeatureProcessor

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).parent / "models" / "circadian_model.pt"


class CircadianModelInference:
    """
    Loads CircadianNet from disk and runs inference.

    Usage:
        inference = CircadianModelInference()
        inference.load_model()                    # optional — auto-called on predict()
        cct, bri = inference.predict(health_data) # returns None on any failure
    """

    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        self._model: Optional[CircadianNet] = None
        self._loaded = False

    def load_model(self, path: Optional[Path] = None) -> bool:
        """
        Load model weights from a .pt file.

        Args:
            path: Override model path (defaults to self.model_path)

        Returns:
            True on success, False on failure.
        """
        target = path or self.model_path
        if not target.exists():
            logger.info("ML model not found at %s — will use policy fallback.", target)
            return False

        try:
            self._model = CircadianNet()
            state_dict = torch.load(target, map_location="cpu", weights_only=True)
            self._model.load_state_dict(state_dict)
            self._model.eval()
            self._loaded = True
            logger.info("CircadianNet loaded from %s", target)
            return True
        except Exception as exc:
            logger.warning("Failed to load CircadianNet: %s", exc)
            self._model = None
            self._loaded = False
            return False

    def predict(
        self,
        hrv_ms: float,
        sleep_hours: float,
        sleep_score: float,
        resting_hr: float,
        steps: float,
        active_energy: float,
        hour: int,
        day_of_week: int,
    ) -> Optional[tuple[int, int]]:
        """
        Run inference and return (cct_kelvin, brightness_percent).

        Lazily loads the model on first call. Returns None on any failure
        so the caller can transparently fall back to the policy.

        Args:
            hrv_ms:        HRV in milliseconds
            sleep_hours:   Total sleep hours
            sleep_score:   Composite sleep quality score (0-100)
            resting_hr:    Resting heart rate (bpm)
            steps:         Daily step count
            active_energy: Daily active calories (kcal)
            hour:          Local hour of day (0-23)
            day_of_week:   Day of week (0=Mon…6=Sun)

        Returns:
            (cct_kelvin, brightness_percent) or None
        """
        if not self._loaded:
            success = self.load_model()
            if not success:
                return None

        try:
            tensor = FeatureProcessor.normalize(
                hrv_ms=hrv_ms,
                sleep_hours=sleep_hours,
                sleep_score=sleep_score,
                resting_hr=resting_hr,
                steps=steps,
                active_energy=active_energy,
                hour=hour,
                day_of_week=day_of_week,
            )
            with torch.no_grad():
                output = self._model(tensor)
            return FeatureProcessor.denormalize_output(output)
        except Exception as exc:
            logger.warning("CircadianNet inference failed: %s", exc)
            return None
