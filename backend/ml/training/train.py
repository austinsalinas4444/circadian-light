"""
Train CircadianNet on policy-labelled health data.

Reads:   backend/ml/training/training_data.csv
Writes:  backend/ml/models/circadian_model.pt

Run from the backend/ directory:
    python -m ml.training.train

Training configuration:
    - 80/20 train/val split (shuffled)
    - MSELoss, Adam lr=0.001
    - 100 epochs
    - Reports MAE for CCT and brightness on validation set
"""
import sys
import logging
from pathlib import Path

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.models.circadian_net import CircadianNet
from ml.preprocessing import FeatureProcessor, FEATURE_STATS

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

DATA_PATH = Path(__file__).resolve().parent / "training_data.csv"
MODEL_OUT = Path(__file__).resolve().parents[1] / "models" / "circadian_model.pt"

FEATURE_COLS = ["hrv_ms", "sleep_hours", "sleep_score", "resting_hr",
                "steps", "active_energy", "hour", "day_of_week"]
LABEL_COLS = ["cct_kelvin", "brightness_percent"]

BATCH_SIZE = 64
EPOCHS = 100
LR = 0.001
SPLIT = 0.8
SEED = 42


def build_tensors(df: pd.DataFrame) -> tuple[torch.Tensor, torch.Tensor]:
    """Z-score normalize features and min-max normalize targets."""
    stats = list(FEATURE_STATS.values())
    X = df[FEATURE_COLS].to_numpy(dtype=float)
    for i, (mean, std) in enumerate(stats):
        X[:, i] = (X[:, i] - mean) / (std if std > 0 else 1.0)

    raw_labels = df[LABEL_COLS].to_numpy(dtype=float)
    norm_labels = np.array([
        FeatureProcessor.normalize_target(row[0], row[1])
        for row in raw_labels
    ])

    return (
        torch.tensor(X, dtype=torch.float32),
        torch.tensor(norm_labels, dtype=torch.float32),
    )


def train() -> None:
    if not DATA_PATH.exists():
        logger.error(
            "Training data not found at %s. Run generate_labels.py first.", DATA_PATH
        )
        sys.exit(1)

    df = pd.read_csv(DATA_PATH)
    logger.info("Loaded %d rows from %s", len(df), DATA_PATH)

    X, y = build_tensors(df)
    dataset = TensorDataset(X, y)

    train_size = int(len(dataset) * SPLIT)
    val_size = len(dataset) - train_size
    torch.manual_seed(SEED)
    train_ds, val_ds = random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)

    model = CircadianNet()
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.MSELoss()

    logger.info(
        "Training CircadianNet: %d train / %d val, %d epochs",
        train_size, val_size, EPOCHS,
    )

    for epoch in range(1, EPOCHS + 1):
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(xb)
        train_loss /= train_size

        if epoch % 10 == 0 or epoch == EPOCHS:
            model.eval()
            cct_mae_total = bri_mae_total = 0.0
            with torch.no_grad():
                for xb, yb in val_loader:
                    pred = model(xb)
                    # Denormalize to compute MAE in real units
                    for p, t in zip(pred, yb):
                        p_cct, p_bri = FeatureProcessor.denormalize_output(p)
                        t_cct, t_bri = FeatureProcessor.denormalize_output(t)
                        cct_mae_total += abs(p_cct - t_cct)
                        bri_mae_total += abs(p_bri - t_bri)
            n = val_size
            logger.info(
                "Epoch %3d | train_loss=%.5f | val MAE: CCT=%.1fK  Bri=%.2f%%",
                epoch, train_loss, cct_mae_total / n, bri_mae_total / n,
            )

    MODEL_OUT.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_OUT)
    logger.info("Model saved to %s", MODEL_OUT)


if __name__ == "__main__":
    train()
