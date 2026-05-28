"""
Grid Guardian — Stage 2: feature engineering.

Builds 95 engineered features from raw telemetry, split into 6 groups:
    temporal (8), rolling (40), lags (12), derivatives (10),
    interactions (15), domain (10).

Anti-leakage guarantees:
    * All rolling stats use right-aligned windows (past-only, no center=True).
    * Lags use only positive shift values (look backwards in time).
    * Diffs are current_value - past_value.
    * Every per-row computation that crosses time is grouped by equipment_id,
      so windows/lags never bleed between transformers at boundaries.

Outputs:
    data/features.parquet            — keys + raw sensors + 95 engineered features
    artifacts/feature_list.json      — exact group breakdown for the thesis
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN_PARQUET = ROOT / "data" / "telemetry.parquet"
OUT_PARQUET = ROOT / "data" / "features.parquet"
OUT_FEATURE_LIST = ROOT / "artifacts" / "feature_list.json"

WINDOWS = [3, 6, 12, 24]                  # hours, right-aligned (past-only)
LAGS = [1, 3, 6, 12]                      # hours, positive shift (past-only)
ROLL_FULL_AGGS = ["mean", "std", "min", "max"]
ROLL_PARTIAL_AGGS = ["mean", "std"]

RAW_SENSORS = [
    "temperature_top", "temperature_oil",
    "voltage_phase_a", "voltage_phase_b", "voltage_phase_c",
    "current_phase_a", "current_phase_b", "current_phase_c",
    "gas_h2", "gas_ch4", "gas_c2h2",
    "vibration_x", "vibration_y", "vibration_z",
    "humidity", "load_percentage",
]


def _add_rolling(out: pd.DataFrame, grp, sensor: str, aggs: list[str], names: list[str]):
    """Past-only rolling: groupby().rolling() is right-aligned by default."""
    for w in WINDOWS:
        rolled = grp[sensor].rolling(window=w, min_periods=1)
        for agg in aggs:
            name = f"{sensor}_roll{w}_{agg}"
            vals = getattr(rolled, agg)().reset_index(level=0, drop=True)
            out[name] = vals.astype("float32")
            names.append(name)


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    # Critical: sort by (equipment_id, timestamp) so groupby ops act on time-ordered series.
    df = df.sort_values(["equipment_id", "timestamp"]).reset_index(drop=True)

    out = df[["timestamp", "equipment_id"] + RAW_SENSORS].copy()
    groups: dict[str, list[str]] = {
        "temporal": [], "rolling": [], "lags": [],
        "derivatives": [], "interactions": [], "domain": [],
    }

    ts = df["timestamp"]

    # ---------- 1) Temporal (8) ----------
    out["hour"] = ts.dt.hour.astype("int16")
    out["day_of_week"] = ts.dt.dayofweek.astype("int16")
    out["month"] = ts.dt.month.astype("int16")
    out["hour_sin"] = np.sin(2 * np.pi * ts.dt.hour / 24).astype("float32")
    out["hour_cos"] = np.cos(2 * np.pi * ts.dt.hour / 24).astype("float32")
    out["month_sin"] = np.sin(2 * np.pi * ts.dt.month / 12).astype("float32")
    out["month_cos"] = np.cos(2 * np.pi * ts.dt.month / 12).astype("float32")
    out["is_weekend"] = (ts.dt.dayofweek >= 5).astype("int8")
    groups["temporal"] = [
        "hour", "day_of_week", "month",
        "hour_sin", "hour_cos", "month_sin", "month_cos",
        "is_weekend",
    ]

    grp = df.groupby("equipment_id", sort=False)

    # ---------- 2) Rolling statistics (40) ----------
    # temperature_top: 4 windows × 4 aggs = 16
    # gas_c2h2:        4 windows × 4 aggs = 16
    # vibration_x:     4 windows × {mean,std} = 8
    # Total: 40.
    roll_names: list[str] = []
    _add_rolling(out, grp, "temperature_top", ROLL_FULL_AGGS, roll_names)
    _add_rolling(out, grp, "gas_c2h2", ROLL_FULL_AGGS, roll_names)
    _add_rolling(out, grp, "vibration_x", ROLL_PARTIAL_AGGS, roll_names)
    groups["rolling"] = roll_names

    # ---------- 3) Lags (12) ----------
    lag_sensors = ["temperature_top", "gas_c2h2", "vibration_x"]
    for sensor in lag_sensors:
        for k in LAGS:
            name = f"{sensor}_lag{k}"
            out[name] = grp[sensor].shift(k).astype("float32")
            groups["lags"].append(name)

    # ---------- 4) Derivatives (10) ----------
    # First derivative (d1) = current - previous (1h step), per equipment_id.
    deriv_sensors = ["temperature_top", "temperature_oil",
                     "gas_c2h2", "vibration_x", "load_percentage"]
    d1_names = []
    for sensor in deriv_sensors:
        name = f"{sensor}_d1"
        out[name] = grp[sensor].diff().astype("float32")
        groups["derivatives"].append(name)
        d1_names.append(name)

    # Second derivative (d2) = diff of d1, computed per equipment_id from the d1 column.
    grp_out = out.groupby("equipment_id", sort=False)
    for d1_name in d1_names:
        sensor = d1_name[:-3]
        name = f"{sensor}_d2"
        out[name] = grp_out[d1_name].diff().astype("float32")
        groups["derivatives"].append(name)

    # ---------- 5) Interactions (15) — purely cross-sensor at row t, no time mixing ----------
    eps = 1e-3
    out["temp_x_load"] = (df["temperature_top"] * df["load_percentage"] / 100).astype("float32")
    out["temp_x_humidity"] = (df["temperature_top"] * df["humidity"] / 100).astype("float32")
    out["oil_to_top_ratio"] = (df["temperature_oil"] / (df["temperature_top"] + eps)).astype("float32")
    out["c2h2_x_temp"] = (df["gas_c2h2"] * df["temperature_top"]).astype("float32")
    out["c2h2_to_h2"] = (df["gas_c2h2"] / (df["gas_h2"] + 1)).astype("float32")
    out["ch4_to_h2"] = (df["gas_ch4"] / (df["gas_h2"] + 1)).astype("float32")
    out["c2h2_to_ch4"] = (df["gas_c2h2"] / (df["gas_ch4"] + 1)).astype("float32")
    out["vibration_magnitude"] = np.sqrt(
        df["vibration_x"]**2 + df["vibration_y"]**2 + df["vibration_z"]**2
    ).astype("float32")
    I = df[["current_phase_a", "current_phase_b", "current_phase_c"]].to_numpy()
    V = df[["voltage_phase_a", "voltage_phase_b", "voltage_phase_c"]].to_numpy()
    I_mean = I.mean(axis=1)
    V_mean = V.mean(axis=1)
    out["current_imbalance"] = ((I.max(axis=1) - I.min(axis=1)) / (I_mean + eps)).astype("float32")
    out["voltage_imbalance"] = ((V.max(axis=1) - V.min(axis=1)) / (V_mean + eps)).astype("float32")
    out["current_avg"] = I_mean.astype("float32")
    out["voltage_avg"] = V_mean.astype("float32")
    out["apparent_power_proxy"] = (I_mean * V_mean).astype("float32")
    out["vib_x_load"] = (out["vibration_magnitude"] * df["load_percentage"] / 100).astype("float32")
    out["temp_per_load"] = (df["temperature_top"] / (df["load_percentage"] + 1)).astype("float32")
    groups["interactions"] = [
        "temp_x_load", "temp_x_humidity", "oil_to_top_ratio", "c2h2_x_temp",
        "c2h2_to_h2", "ch4_to_h2", "c2h2_to_ch4",
        "vibration_magnitude",
        "current_imbalance", "voltage_imbalance",
        "current_avg", "voltage_avg", "apparent_power_proxy",
        "vib_x_load", "temp_per_load",
    ]

    # ---------- 6) Domain features (10) ----------
    temp_score = np.clip((df["temperature_top"] - 55) / (100 - 55), 0, 1)
    c2h2_score = np.clip(df["gas_c2h2"] / 50, 0, 1)
    vib_score = np.clip(df["vibration_x"] / 8, 0, 1)
    out["health_score"] = (1 - (0.6 * c2h2_score + 0.2 * temp_score + 0.2 * vib_score)).astype("float32")
    out["temp_warning_flag"] = (df["temperature_top"] > 85).astype("int8")
    out["temp_critical_flag"] = (df["temperature_top"] > 100).astype("int8")
    out["c2h2_warning_flag"] = (df["gas_c2h2"] > 25).astype("int8")
    out["c2h2_critical_flag"] = (df["gas_c2h2"] > 50).astype("int8")
    out["vib_warning_flag"] = (df["vibration_x"] > 5).astype("int8")
    out["vib_critical_flag"] = (df["vibration_x"] > 8).astype("int8")
    out["load_high_flag"] = (df["load_percentage"] > 80).astype("int8")
    out["gas_total"] = (df["gas_h2"] + df["gas_ch4"] + df["gas_c2h2"]).astype("float32")
    t0 = ts.min()
    out["hours_since_start"] = ((ts - t0).dt.total_seconds() / 3600).astype("float32")
    groups["domain"] = [
        "health_score",
        "temp_warning_flag", "temp_critical_flag",
        "c2h2_warning_flag", "c2h2_critical_flag",
        "vib_warning_flag", "vib_critical_flag",
        "load_high_flag",
        "gas_total", "hours_since_start",
    ]

    return out, groups


def build_feature_list(groups: dict, out: pd.DataFrame) -> dict:
    counts = {g: len(names) for g, names in groups.items()}
    total = sum(counts.values())
    sample_features = list(groups["rolling"][:4]) + list(groups["lags"][:2]) + list(groups["derivatives"][:2])

    return {
        "engineered_feature_count": total,
        "expected_count": 95,
        "match_expected": total == 95,
        "anti_leakage": {
            "rolling": "groupby('equipment_id') + rolling(window=W); past-only (right-aligned, no center=True); min_periods=1",
            "lags": "groupby('equipment_id') + shift(k>0); only past values",
            "derivatives": "groupby('equipment_id') + diff() = current - previous; d2 = diff(d1)",
            "interactions_and_domain": "Computed at single timestamp t; no time-axis mixing",
        },
        "windows_hours": WINDOWS,
        "lags_hours": LAGS,
        "group_counts": counts,
        "groups": {
            g: {"count": counts[g], "features": names}
            for g, names in groups.items()
        },
        "raw_sensors_passed_through": RAW_SENSORS,
        "total_columns_in_features_parquet": int(out.shape[1]),
        "sample_engineered_feature_names": sample_features,
        "notes": [
            "NaN at the head of each unit's series is expected for lags/derivatives/rolling-std at window>1.",
            "Stage 4 will drop these initial rows (or rely on XGBoost native NaN handling).",
        ],
    }


def main():
    print(f"[feature_engineering] reading {IN_PARQUET}")
    df = pd.read_parquet(IN_PARQUET)
    print(f"[feature_engineering] input rows={len(df):,}, cols={df.shape[1]}")

    out, groups = build_features(df)
    print(f"[feature_engineering] output rows={len(out):,}, cols={out.shape[1]}")
    for g, names in groups.items():
        print(f"  {g:14s} {len(names):3d} features")
    total = sum(len(v) for v in groups.values())
    print(f"  {'TOTAL':14s} {total:3d}")
    assert total == 95, f"Expected 95 engineered features, got {total}"

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    OUT_FEATURE_LIST.parent.mkdir(parents=True, exist_ok=True)

    out.to_parquet(OUT_PARQUET, index=False, compression="snappy")
    size_mb = OUT_PARQUET.stat().st_size / 1024 / 1024
    print(f"[feature_engineering] wrote {OUT_PARQUET} ({size_mb:.1f} MB)")

    feature_list = build_feature_list(groups, out)
    with OUT_FEATURE_LIST.open("w", encoding="utf-8") as f:
        json.dump(feature_list, f, indent=2, ensure_ascii=False)
    print(f"[feature_engineering] wrote {OUT_FEATURE_LIST}")


if __name__ == "__main__":
    main()
