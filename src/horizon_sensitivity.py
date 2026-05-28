"""
Grid Guardian — Stage 4 sensitivity sweep over forecast horizon.

Re-evaluates the XGBoost model + no-ML threshold-rule baseline at horizons
{24, 72, 168} hours, on both the chronological 80/20 split (primary) and
the equipment 40/10 split (robustness). The primary horizon for the thesis
is 72 h — at longer horizons we expect the gap between model and baseline
to widen, because slow-degradation data makes 'read the sensor and apply a
threshold' a worse approximation of future state.

Outputs
-------
    artifacts/horizon_sensitivity.json    — full per-horizon metrics for ВКР table 3.2
    artifacts/horizon_sensitivity.png     — recall_High / F1_High vs horizon (ML vs baseline)
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Local imports (src/ is on sys.path when running 'python src/horizon_sensitivity.py')
from build_target import compute_labels
from train_model import (
    CLASS_NAMES, baseline_metrics_block, chronological_split, equipment_split,
    fit_xgb, metrics_block, _threshold_rule_predict,
)

HORIZONS = [24, 72, 168]
PRIMARY_HORIZON = 72  # for the headline ВКР narrative

ROOT = Path(__file__).resolve().parent.parent
TELEMETRY_PQ = ROOT / "data" / "telemetry.parquet"
FEATURES_PQ = ROOT / "data" / "features.parquet"
FEATURE_LIST_JSON = ROOT / "artifacts" / "feature_list.json"
OUT_JSON = ROOT / "artifacts" / "horizon_sensitivity.json"
OUT_PNG = ROOT / "artifacts" / "horizon_sensitivity.png"


def get_feature_cols(feat_df: pd.DataFrame) -> list[str]:
    with FEATURE_LIST_JSON.open(encoding="utf-8") as f:
        fl = json.load(f)
    excluded = set(fl["training_feature_exclusions"]["excluded_features"])
    drop_cols = {"timestamp", "equipment_id", "risk_class"} | excluded
    return [c for c in feat_df.columns if c not in drop_cols]


def run_horizon(tel: pd.DataFrame, feat: pd.DataFrame,
                feature_cols: list[str], horizon: int) -> dict:
    print(f"\n[sensitivity] === HORIZON = {horizon} h ===")
    labels = compute_labels(tel, horizon)

    df = feat.merge(
        labels[["timestamp", "equipment_id", "risk_class", "valid"]],
        on=["timestamp", "equipment_id"], how="inner",
    )
    n_raw = len(df)
    df = df[df["valid"] == 1].drop(columns=["valid"])
    n_after_valid = len(df)
    df = df.dropna()
    n_after_nan = len(df)
    df["risk_class"] = df["risk_class"].astype(np.int8)

    print(f"  rows: raw={n_raw:,}  after valid==1: {n_after_valid:,}  "
          f"after dropna: {n_after_nan:,}")

    # Per-class supports
    cls_counts = {CLASS_NAMES[c]: int((df["risk_class"] == c).sum()) for c in [0, 1, 2]}
    print(f"  class counts (full df): {cls_counts}")

    horizon_block = {
        "horizon_hours": horizon,
        "rows_dropped_horizon_overrun": horizon * 50,
        "rows_dropped_lag_head_nan": n_after_valid - n_after_nan,
        "rows_used_for_modeling": n_after_nan,
        "class_distribution": cls_counts,
        "splits": {},
    }

    for split_maker, split_key in [
        (chronological_split, "primary_chronological_80_20"),
        (equipment_split,     "robustness_equipment_40_10"),
    ]:
        split = split_maker(df)
        mask_tr = split["mask_train"]
        mask_te = split["mask_test"]

        X_tr = df.loc[mask_tr, feature_cols]
        y_tr = df.loc[mask_tr, "risk_class"].to_numpy()
        X_te = df.loc[mask_te, feature_cols]
        y_te = df.loc[mask_te, "risk_class"].to_numpy()

        train_counts = {CLASS_NAMES[c]: int((y_tr == c).sum()) for c in [0, 1, 2]}
        test_counts = {CLASS_NAMES[c]: int((y_te == c).sum()) for c in [0, 1, 2]}
        print(f"  [{split_key}] train={X_tr.shape}  test={X_te.shape}  "
              f"y_te counts={test_counts}")

        # ---- Train + evaluate model ----
        clf = fit_xgb(X_tr, y_tr)
        y_pred = clf.predict(X_te)
        y_proba = clf.predict_proba(X_te)
        m = metrics_block(y_te, y_pred, y_proba)

        # ---- No-ML threshold-rule baseline on same test rows ----
        df_test_subset = df.loc[mask_te, ["temperature_top", "gas_c2h2", "vibration_x"]]
        y_rule = _threshold_rule_predict(df_test_subset)
        b = baseline_metrics_block(y_te, y_rule)

        # ---- Top-10 feature importance (gain) ----
        booster = clf.get_booster()
        gain = pd.Series(booster.get_score(importance_type="gain"))
        gain = gain.reindex(feature_cols).fillna(0).sort_values(ascending=False)
        top10 = {name: float(val) for name, val in gain.head(10).items()}

        # ---- Compact comparison block (ML vs baseline) ----
        ml_high = m["per_class"]["High (2)"]
        bl_high = b["per_class"]["High (2)"]
        ml_med = m["per_class"]["Medium (1)"]
        bl_med = b["per_class"]["Medium (1)"]
        delta_recall_high = ml_high["recall"] - bl_high["recall"]
        delta_f1_high = ml_high["f1"] - bl_high["f1"]

        horizon_block["splits"][split_key] = {
            "n_train": int(mask_tr.sum()),
            "n_test": int(mask_te.sum()),
            "train_class_counts": train_counts,
            "test_class_counts": test_counts,
            "model": {
                "per_class": m["per_class"],
                "roc_auc_ovr_macro": m["roc_auc_ovr_macro"],
                "macro_f1": m["macro_f1"],
                "accuracy": m["accuracy"],
                "confusion_matrix": m["confusion_matrix"],
                "top10_features_by_gain": top10,
            },
            "threshold_rule_baseline": {
                "per_class": b["per_class"],
                "macro_f1": b["macro_f1"],
                "accuracy": b["accuracy"],
                "confusion_matrix": b["confusion_matrix"],
            },
            "ml_minus_baseline": {
                "recall_high": round(delta_recall_high, 4),
                "f1_high": round(delta_f1_high, 4),
                "recall_medium": round(ml_med["recall"] - bl_med["recall"], 4),
                "f1_medium": round(ml_med["f1"] - bl_med["f1"], 4),
                "accuracy": round(m["accuracy"] - b["accuracy"], 4),
            },
        }

        print(f"    model:   recall_high={ml_high['recall']:.4f}  "
              f"f1_high={ml_high['f1']:.4f}  acc={m['accuracy']:.4f}")
        print(f"    baseline:recall_high={bl_high['recall']:.4f}  "
              f"f1_high={bl_high['f1']:.4f}  acc={b['accuracy']:.4f}")
        print(f"    delta(ml-base): recall_high={delta_recall_high:+.4f}  "
              f"f1_high={delta_f1_high:+.4f}")

    return horizon_block


def plot_sensitivity(results: dict, out_path: Path):
    horizons = sorted(int(h) for h in results.keys())

    def pull(split_key: str, side: str, metric: str):
        return [results[str(h)]["splits"][split_key][side]["per_class"]["High (2)"][metric]
                for h in horizons]

    ml_recall = pull("primary_chronological_80_20", "model", "recall")
    bl_recall = pull("primary_chronological_80_20", "threshold_rule_baseline", "recall")
    ml_f1 = pull("primary_chronological_80_20", "model", "f1")
    bl_f1 = pull("primary_chronological_80_20", "threshold_rule_baseline", "f1")

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5))
    colours = {"ml": "#1f77b4", "bl": "#d62728"}

    for ax, ml_vals, bl_vals, ylabel, title in [
        (axes[0], ml_recall, bl_recall, "Recall (High class)",
         "Recall on critical class vs forecast horizon"),
        (axes[1], ml_f1, bl_f1, "F1 (High class)",
         "F1 on critical class vs forecast horizon"),
    ]:
        ax.plot(horizons, ml_vals, "o-", color=colours["ml"], lw=2.2, ms=8,
                label="XGBoost model")
        ax.plot(horizons, bl_vals, "s--", color=colours["bl"], lw=2.0, ms=7,
                label="No-ML threshold rule")
        for h, ml, bl in zip(horizons, ml_vals, bl_vals):
            ax.annotate(f"{ml:.3f}", (h, ml),
                        textcoords="offset points", xytext=(6, 7),
                        fontsize=9, color=colours["ml"], fontweight="bold")
            ax.annotate(f"{bl:.3f}", (h, bl),
                        textcoords="offset points", xytext=(6, -14),
                        fontsize=9, color=colours["bl"])
        ax.set_xlabel("Forecast horizon (hours)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_xticks(horizons)
        ax.set_xticklabels([f"{h} h" for h in horizons])
        ax.set_ylim(min(min(ml_vals), min(bl_vals)) - 0.05, 1.02)
        ax.grid(alpha=0.3)
        ax.legend(loc="lower left")
        # Mark the primary horizon
        ax.axvline(PRIMARY_HORIZON, color="gray", lw=1.0, alpha=0.4, linestyle=":")
        ax.text(PRIMARY_HORIZON, ax.get_ylim()[0] + 0.01,
                f"primary={PRIMARY_HORIZON}h", color="gray", fontsize=8,
                ha="center", alpha=0.7)

    fig.suptitle(
        "Grid Guardian — sensitivity to forecast horizon (chronological 80/20 split)",
        fontsize=13,
    )
    plt.tight_layout()
    plt.savefig(out_path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    print(f"[sensitivity] loading {TELEMETRY_PQ}")
    tel = pd.read_parquet(TELEMETRY_PQ)
    print(f"[sensitivity] loading {FEATURES_PQ}")
    feat = pd.read_parquet(FEATURES_PQ)
    feature_cols = get_feature_cols(feat)
    print(f"[sensitivity] feature_cols (training set) = {len(feature_cols)}")

    results: dict[str, dict] = {}
    for h in HORIZONS:
        results[str(h)] = run_horizon(tel, feat, feature_cols, h)

    out = {
        "horizons_hours": HORIZONS,
        "primary_horizon_hours": PRIMARY_HORIZON,
        "note": (
            "ML model vs no-ML threshold-rule baseline at three forecast horizons. "
            "The gap (ml_minus_baseline) is the methodological hook for thesis section 3.2: "
            "as the horizon grows, current sensor(t) becomes a worse proxy for sensor(t+h), "
            "and ML's use of trend features (rolling means, derivatives, lags) starts to matter."
        ),
        "results": results,
    }
    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n[sensitivity] wrote {OUT_JSON}")

    plot_sensitivity(results, OUT_PNG)
    print(f"[sensitivity] wrote {OUT_PNG}")

    # ---- Console table ----
    print()
    print("=" * 78)
    print(f"{'Horizon':>9} | {'ML recall_H':>12} | {'BL recall_H':>12} | "
          f"{'delta recall':>9} | {'ML F1_H':>9} | {'BL F1_H':>9} | {'delta F1':>7}")
    print("-" * 78)
    for h in HORIZONS:
        r = results[str(h)]["splits"]["primary_chronological_80_20"]
        ml = r["model"]["per_class"]["High (2)"]
        bl = r["threshold_rule_baseline"]["per_class"]["High (2)"]
        print(f"{h:>7}h  | {ml['recall']:>12.4f} | {bl['recall']:>12.4f} | "
              f"{ml['recall']-bl['recall']:>+9.4f} | "
              f"{ml['f1']:>9.4f} | {bl['f1']:>9.4f} | {ml['f1']-bl['f1']:>+7.4f}")


if __name__ == "__main__":
    main()
