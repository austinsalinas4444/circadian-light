"""
CircadianNet — a lightweight feedforward network for personalized lighting prediction.

Architecture:
    Input (8 features) → Linear(8,32) → ReLU → Linear(32,16) → ReLU → Linear(16,2)

Input features:
    hrv_ms, sleep_hours, sleep_score, resting_hr, steps,
    active_energy, hour, day_of_week

Output (2 values, normalized to [0, 1]):
    cct_normalized    → denormalized to 1800-6500K
    brightness_normalized → denormalized to 10-100%

Training uses MSELoss on normalized targets. Use FeatureProcessor
in preprocessing.py to prepare inputs and convert outputs back to
human-readable units.
"""
import torch
import torch.nn as nn


class CircadianNet(nn.Module):
    """
    Lightweight feedforward network predicting circadian lighting settings
    from health features and time-of-day context.

    Args:
        input_dim:  Number of input features (default 8)
        hidden_dim: Width of first hidden layer (default 32)
        output_dim: Number of outputs — [cct_norm, brightness_norm] (default 2)
    """

    def __init__(self, input_dim: int = 8, hidden_dim: int = 32, output_dim: int = 2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 16),
            nn.ReLU(),
            nn.Linear(16, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Float tensor of shape (batch_size, input_dim)

        Returns:
            Float tensor of shape (batch_size, output_dim)
            Values are raw (not sigmoid-squashed) — clamp to [0, 1] before
            passing to FeatureProcessor.denormalize_output().
        """
        return self.net(x)
