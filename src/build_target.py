"""
Grid Guardian — Stage 3: target variable (3-class risk).

Semantics — PREDICTIVE, not diagnostic
--------------------------------------
For each row at time t, the label is the risk class evaluated 24 hours later,
i.e. label(t) = class( sensor_state(t + 24h) ).

Why this matters
----------------
If the label were taken from sensor_state(t) (current-state diagnosis), a model
that sees the raw sensors at t would solve the task trivially by reading
thresholds back — that is tautology, not prediction. Shifting the label
24 hours into the future forces the model to learn evolution patterns
(degradation curves, lead indicators in DGA/vibration) from past+current
features at t.

Class rule (per-parameter, then worst-of)
-----------------------------------------
For each of {temperature_top, gas_c2h2, vibration_x} we compute a per-parameter
class with the spec thresholds, then take the maximum:

    temperature_top:  0 <85,   1 [85..100],  2 >100
    gas_c2h2:         0 <25,   1 [25..50],   2 >50
    vibration_x:      0 <5,    1 [5..8],     2 >8

    overall_class = max(temp_class, c2h2_class, vib_class)

Composite continuous risk score (also at t+24h)
-----------------------------------------------
    temp_norm = clip( (T - 55) / (100 - 55), 0, 1 )
    c2h2_norm = clip( C / 50, 0, 1 )
    vib_norm  = clip( V / 8,  0, 1 )
    composite = 0.60 * c2h2_norm + 0.20 * temp_norm + 0.20 * vib_norm
(DGA 60 %, temp 20 %, vibration 20 % — per spec.)

Anti-leakage notes propagated to feature_list.json
---------------------------------------------------
The label rule uses the same thresholds and composite weights that define
7 of the 10 'domain' features (health_score and 6 threshold flags). To avoid
tautological leakage, those 7 features are flagged as excluded from training
in artifacts/feature_list.json. Stage 4 must drop them from X.

Outputs
-------
    data/labels.parquet              — timestamp, equipment_id, risk_class,
                                       composite_score, valid, horizon_hours
    artifacts/data_summary.json      — appended with class distribution
    artifacts/feature_list.json      — appended with training_feature_exclusions
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
IN_FEATURES = ROOT / "data" / "features.parquet"
IN_TELEMETRY = ROOT / "data" / "telemetry.parquet"
OUT_LABELS = ROOT / "data" / "labels.parquet"
SUMMARY_JSON = ROOT / "artifacts" / "data_summary.json"
FEATURE_LIST_JSON = ROOT / "artifacts" / "feature_list.json"

HORIZON_HOURS = 72  # primary forecast horizon for the thesis (3 days ahead)

# Spec thresholds (warn, critical)
TEMP_WARN, TEMP_CRIT = 85.0, 100.0
C2H2_WARN, C2H2_CRIT = 25.0, 50.0
VIB_WARN, VIB_CRIT = 5.0, 8.0

# Composite weights from spec: DGA 60 %, temp 20 %, vib 20 %
W_C2H2, W_TEMP, W_VIB = 0.60, 0.20, 0.20

# Domain features that depend on the same thresholds / composite as the label.
TRAINING_EXCLUSIONS = [
    "health_score",
    "temp_warning_flag", "temp_critical_flag",
    "c2h2_warning_flag", "c2h2_critical_flag",
    "vib_warning_flag", "vib_critical_flag",
]


def per_parameter_class(values: np.ndarray, warn: float, crit: float) -> np.ndarray:
    """0 if v < warn, 1 if warn <= v <= crit, 2 if v > crit. NaN propagates as -1."""
    out = np.full(values.shape, -1, dtype=np.int8)
    mask = ~np.isnan(values)
    v = values[mask]
    cls = np.where(v > crit, 2, np.where(v > warn, 1, 0)).astype(np.int8)
    out[mask] = cls
    return out


def compute_labels(df_telemetry: pd.DataFrame, horizon_hours: int) -> pd.DataFrame:
    """Build the 3-class label and composite score at t + horizon_hours.

    Returns a DataFrame with columns:
        timestamp, equipment_id, risk_class (Int8, NA where invalid),
        composite_score (float32, NaN where invalid),
        valid (int8), horizon_hours (int).

    Used both by main() (writes labels.parquet) and by the sensitivity sweep
    in horizon_sensitivity.py.
    """
    df = df_telemetry.sort_values(["equipment_id", "timestamp"]).reset_index(drop=True)
    grp = df.groupby("equipment_id", sort=False)

    future_temp = grp["temperature_top"].shift(-horizon_hours).to_numpy(dtype=np.float64)
    future_c2h2 = grp["gas_c2h2"].shift(-horizon_hours).to_numpy(dtype=np.float64)
    future_vib = grp["vibration_x"].shift(-horizon_hours).to_numpy(dtype=np.float64)

    cls_t = per_parameter_class(future_temp, TEMP_WARN, TEMP_CRIT)
    cls_c = per_parameter_class(future_c2h2, C2H2_WARN, C2H2_CRIT)
    cls_v = per_parameter_class(future_vib, VIB_WARN, VIB_CRIT)
    valid_mask = (cls_t >= 0) & (cls_c >= 0) & (cls_v >= 0)
    risk_class = np.where(valid_mask, np.maximum.reduce([cls_t, cls_c, cls_v]), -1).astype(np.int8)

    tn = np.clip((future_temp - 55.0) / (100.0 - 55.0), 0.0, 1.0)
    cn = np.clip(future_c2h2 / 50.0, 0.0, 1.0)
    vn = np.clip(future_vib / 8.0, 0.0, 1.0)
    composite = (W_C2H2 * cn + W_TEMP * tn + W_VIB * vn).astype(np.float32)

    labels = df[["timestamp", "equipment_id"]].copy()
    labels["risk_class"] = pd.array(
        np.where(valid_mask, risk_class, np.iinfo(np.int8).min), dtype="Int8")
    labels.loc[~valid_mask, "risk_class"] = pd.NA
    labels["composite_score"] = composite
    labels.loc[~valid_mask, "composite_score"] = np.nan
    labels["valid"] = valid_mask.astype("int8")
    labels["horizon_hours"] = horizon_hours
    return labels


def main():
    print(f"[build_target] reading {IN_TELEMETRY}")
    df = pd.read_parquet(IN_TELEMETRY)
    df = df.sort_values(["equipment_id", "timestamp"]).reset_index(drop=True)
    print(f"[build_target] rows={len(df):,}, units={df['equipment_id'].nunique()}, "
          f"horizon={HORIZON_HOURS}h")

    labels = compute_labels(df, HORIZON_HOURS)
    valid_mask = (labels["valid"] == 1).to_numpy()
    risk_class = labels["risk_class"].astype("Int64").fillna(-1).to_numpy().astype(np.int8)

    OUT_LABELS.parent.mkdir(parents=True, exist_ok=True)
    labels.to_parquet(OUT_LABELS, index=False, compression="snappy")
    size_mb = OUT_LABELS.stat().st_size / 1024 / 1024
    print(f"[build_target] wrote {OUT_LABELS} ({size_mb:.2f} MB)")

    # ---- Distribution ----
    valid_classes = risk_class[valid_mask]
    total_valid = int(valid_mask.sum())
    total_invalid = int((~valid_mask).sum())
    counts = {int(k): int(v) for k, v in zip(*np.unique(valid_classes, return_counts=True))}
    distribution = {
        "Low (0)": {
            "count": counts.get(0, 0),
            "pct": round(counts.get(0, 0) / total_valid * 100, 3),
        },
        "Medium (1)": {
            "count": counts.get(1, 0),
            "pct": round(counts.get(1, 0) / total_valid * 100, 3),
        },
        "High (2)": {
            "count": counts.get(2, 0),
            "pct": round(counts.get(2, 0) / total_valid * 100, 3),
        },
        "total_valid": total_valid,
        "invalid_horizon_overrun": total_invalid,
    }

    # Per-equipment summary: how often each unit ends up in High at t + HORIZON_HOURS
    per_unit = (
        labels[labels["valid"] == 1]
        .assign(rc=lambda x: x["risk_class"].astype(int))
        .groupby("equipment_id")["rc"]
        .agg(lambda s: {
            "rows": int(len(s)),
            "pct_high": round((s == 2).mean() * 100, 2),
            "pct_medium": round((s == 1).mean() * 100, 2),
            "pct_low": round((s == 0).mean() * 100, 2),
        })
        .to_dict()
    )

    # ---- Append to data_summary.json ----
    with SUMMARY_JSON.open("r", encoding="utf-8") as f:
        summary = json.load(f)
    summary["target_variable"] = {
        "semantics": "PREDICTIVE: label at row t = risk class at row t + horizon_hours",
        "horizon_hours": HORIZON_HOURS,
        "class_rule": "max(per_param_class(future_temperature_top), per_param_class(future_gas_c2h2), per_param_class(future_vibration_x))",
        "thresholds": {
            "temperature_top": {"warn": TEMP_WARN, "critical": TEMP_CRIT},
            "gas_c2h2": {"warn": C2H2_WARN, "critical": C2H2_CRIT},
            "vibration_x": {"warn": VIB_WARN, "critical": VIB_CRIT},
        },
        "composite_score_formula": (
            f"{W_C2H2}*clip(c2h2/50,0,1) + {W_TEMP}*clip((T-55)/45,0,1) + {W_VIB}*clip(vib/8,0,1) "
            "[all evaluated at t + horizon_hours]"
        ),
        "class_distribution": distribution,
        "per_unit_class_share": per_unit,
        "imbalance_strategy_hint": (
            "Class High is rare (large imbalance expected). For Stage 4 consider: "
            "scale_pos_weight or sample_weight in XGBoost, stratified evaluation, "
            "and prioritise recall on class High in metric reporting."
        ),
        "anti_leakage_notes": [
            "Label uses future sensor values via groupby('equipment_id').shift(-24) — no cross-unit bleeding.",
            "Last 24 rows per unit are unlabeled (valid=0) and must be dropped before training.",
            "7 'domain' features are direct subcomponents of the label rule; they are listed as training exclusions in artifacts/feature_list.json.",
        ],
        "output_file": str(OUT_LABELS.relative_to(ROOT)).replace("\\", "/"),
    }
    with SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[build_target] updated {SUMMARY_JSON}")

    # ---- Append to feature_list.json ----
    with FEATURE_LIST_JSON.open("r", encoding="utf-8") as f:
        fl = json.load(f)
    fl["training_feature_exclusions"] = {
        "reason": (
            "These 7 'domain' features use the same thresholds (or the same "
            "DGA60/temp20/vib20 composite) that define the label. Including "
            "them in training would let the model recover the label rule "
            "directly from features at time t and would inflate metrics."
        ),
        "excluded_features": TRAINING_EXCLUSIONS,
        "excluded_count": len(TRAINING_EXCLUSIONS),
        "engineered_features_after_exclusion": fl["engineered_feature_count"] - len(TRAINING_EXCLUSIONS),
        "kept_domain_features": [
            f for f in fl["groups"]["domain"]["features"] if f not in TRAINING_EXCLUSIONS
        ],
    }
    with FEATURE_LIST_JSON.open("w", encoding="utf-8") as f:
        json.dump(fl, f, indent=2, ensure_ascii=False)
    print(f"[build_target] updated {FEATURE_LIST_JSON}")

    # ---- Console summary ----
    print()
    print("[build_target] class distribution (valid rows only):")
    for k in ["Low (0)", "Medium (1)", "High (2)"]:
        d = distribution[k]
        print(f"  {k:12s} count={d['count']:>9,}  pct={d['pct']:6.3f}%")
    print(f"  TOTAL valid = {total_valid:,}  invalid (horizon overrun) = {total_invalid:,}")
    deg_units = summary["degradation"]["units"]
    n_high_in_deg = sum(1 for u in deg_units if per_unit[u]["pct_high"] > 0)
    print(f"[build_target] degraded units showing any High label: {n_high_in_deg}/{len(deg_units)}")
    print(f"[build_target] training features after exclusion: "
          f"{fl['training_feature_exclusions']['engineered_features_after_exclusion']} engineered "
          f"(+ {len(fl['raw_sensors_passed_through'])} raw)")


if __name__ == "__main__":
    main()
