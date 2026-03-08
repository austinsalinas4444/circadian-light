"""
Generate training labels for CircadianNet from Austin's health export CSVs.

Pipeline:
  1. Load all CSVs from backend/data/
  2. Aggregate metrics to daily granularity
  3. For each day × hour (0-23), build a feature row
  4. Apply the circadian policy to generate CCT/brightness labels
  5. Write backend/ml/training/training_data.csv

Run from the backend/ directory:
    python -m ml.training.generate_labels

Output columns:
    date, hour, day_of_week,
    hrv_ms, sleep_hours, sleep_score, resting_hr, steps, active_energy,
    cct_kelvin, brightness_percent
"""
import sys
from pathlib import Path
import logging

import pandas as pd
import numpy as np

# Allow running from backend/ directory
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.circadian_policy import CircadianPolicyService, compute_sleep_score
from app.models.request_models import HealthFeaturesRequest

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OUT_PATH = Path(__file__).resolve().parent / "training_data.csv"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_hrv(path: Path) -> pd.Series:
    """Daily mean HRV (ms)."""
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["date"] = df["timestamp"].dt.date
    return df.groupby("date")["value_ms"].mean().rename("hrv_ms")


def load_sleep(path: Path) -> pd.DataFrame:
    """
    Aggregate sleep stages per night to:
      sleep_hours, deep_sleep_pct, rem_sleep_pct, sleep_efficiency, sleep_score

    Apple Health sleep stages: Deep Sleep, Core Sleep, REM Sleep, Awake
    """
    df = pd.read_csv(path, parse_dates=["start_time", "end_time"])
    # Use the calendar date of start_time as the "night" anchor
    df["date"] = df["start_time"].dt.date

    results = []
    for date, group in df.groupby("date"):
        total_dur = group["duration_hours"].sum()
        deep = group.loc[group["sleep_stage"] == "Deep Sleep", "duration_hours"].sum()
        rem = group.loc[group["sleep_stage"] == "REM Sleep", "duration_hours"].sum()
        awake = group.loc[group["sleep_stage"] == "Awake", "duration_hours"].sum()
        sleep_dur = total_dur - awake

        deep_pct = deep / sleep_dur if sleep_dur > 0 else 0.0
        rem_pct = rem / sleep_dur if sleep_dur > 0 else 0.0
        efficiency = sleep_dur / total_dur if total_dur > 0 else 0.0

        score = compute_sleep_score(sleep_dur, deep_pct, rem_pct, efficiency)
        results.append({
            "date": date,
            "sleep_hours": round(sleep_dur, 3),
            "deep_sleep_pct": round(deep_pct, 4),
            "rem_sleep_pct": round(rem_pct, 4),
            "sleep_efficiency": round(efficiency, 4),
            "sleep_score": round(score, 2),
        })

    return pd.DataFrame(results).set_index("date")


def load_resting_hr(path: Path) -> pd.Series:
    """Daily resting HR (bpm) — last reading of each day."""
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["date"] = df["timestamp"].dt.date
    return df.groupby("date")["bpm"].last().rename("resting_hr")


def load_steps(path: Path) -> pd.Series:
    """Daily total step count."""
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["date"] = df["timestamp"].dt.date
    return df.groupby("date")["step_count"].sum().rename("steps")


def load_active_energy(path: Path) -> pd.Series:
    """Daily total active energy (kcal)."""
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["date"] = df["timestamp"].dt.date
    return df.groupby("date")["calories"].sum().rename("active_energy")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("Loading CSV data from %s", DATA_DIR)

    hrv = load_hrv(DATA_DIR / "hrv.csv")
    sleep_df = load_sleep(DATA_DIR / "sleep.csv")
    resting_hr = load_resting_hr(DATA_DIR / "resting_hr.csv")
    steps = load_steps(DATA_DIR / "steps.csv")
    energy = load_active_energy(DATA_DIR / "active_energy.csv")

    # Combine daily metrics
    daily = (
        hrv.to_frame()
        .join(sleep_df[["sleep_hours", "sleep_score", "deep_sleep_pct",
                         "rem_sleep_pct", "sleep_efficiency"]], how="outer")
        .join(resting_hr, how="outer")
        .join(steps, how="outer")
        .join(energy, how="outer")
    )

    # Fill gaps with population defaults
    daily = daily.fillna({
        "hrv_ms": 70.0,
        "sleep_hours": 7.0,
        "sleep_score": 68.0,
        "resting_hr": 50.0,
        "steps": 7000,
        "active_energy": 350.0,
        "deep_sleep_pct": 0.20,
        "rem_sleep_pct": 0.25,
        "sleep_efficiency": 0.90,
    })

    logger.info("Daily records after merge: %d", len(daily))

    # Core columns required to build a valid HealthFeaturesRequest
    required_cols = ["hrv_ms", "sleep_hours", "sleep_score", "steps", "active_energy"]

    rows = []
    for date, row in daily.iterrows():
        # Skip rows that still contain NaN in any required column
        if row[required_cols].isna().any():
            logger.warning("Skipping %s — NaN in required columns", date)
            continue

        dt = pd.Timestamp(date)
        dow = dt.dayofweek  # 0=Mon…6=Sun

        for hour in range(24):
            # Build a HealthFeaturesRequest and run the policy
            req = HealthFeaturesRequest(
                hrv_ms=float(row["hrv_ms"]),
                sleep_hours=float(row["sleep_hours"]),
                sleep_score=float(row["sleep_score"]),
                step_count=int(row["steps"]),
                active_energy=float(row["active_energy"]),
                local_hour=hour,
            )
            rec = CircadianPolicyService.generate_recommendation(req)

            rows.append({
                "date": str(date),
                "hour": hour,
                "day_of_week": dow,
                "hrv_ms": round(row["hrv_ms"], 2),
                "sleep_hours": round(row["sleep_hours"], 3),
                "sleep_score": round(row["sleep_score"], 2),
                "resting_hr": round(row["resting_hr"], 1),
                "steps": int(row["steps"]),
                "active_energy": round(row["active_energy"], 2),
                "cct_kelvin": rec.color_temp_kelvin,
                "brightness_percent": rec.brightness_percent,
            })

    out_df = pd.DataFrame(rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_PATH, index=False)
    logger.info("Wrote %d rows to %s", len(out_df), OUT_PATH)


if __name__ == "__main__":
    main()
