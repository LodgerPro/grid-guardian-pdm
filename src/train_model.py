"""
Grid Guardian — Stage 4: train XGBoost multiclass model.

Two evaluation strategies (both reported, primary is chronological):

    1) PRIMARY — chronological 80/20 split:
       Train on first ~19 months, test on last ~5 months.
       All 50 units are present in both partitions (real-world ops scenario:
       a model that learned from the past predicts the near future).
       This is the split that backs the headline metrics in the thesis.

    2) ROBUSTNESS — equipment 40/10 split (stratified by degradation flag):
       2 degraded + 8 healthy units held out as test;
       train sees 7 degraded + 33 healthy.
       Tests generalization to *unseen transformers*, a stricter check.

Imbalance handling
------------------
Class High covers ~2 % of valid rows. We use sklearn's
compute_sample_weight('balanced', y_train) and pass it to XGBClassifier.fit
as sample_weight. This is the standard multiclass equivalent of
scale_pos_weight and prevents the model from collapsing onto the majority
"Low" class.

Feature matrix
--------------
X excludes:
    - keys (timestamp, equipment_id)
    - the label column (risk_class)
    - 7 'domain' features that directly mirror the label rule
      (health_score and the six warning/critical threshold flags) — listed
      in artifacts/feature_list.json::training_feature_exclusions

Outputs
-------
    artifacts/model.json                 — XGBoost native, from PRIMARY split
    artifacts/metrics.json               — both splits, primary first
    artifacts/confusion_matrix.png       — PRIMARY split
    artifacts/roc_curve.png              — PRIMARY split (OvR per class)
    artifacts/feature_importance.png     — PRIMARY split, top-15 by gain
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve,
)
from sklearn.utils.class_weight import compute_sample_weight

SEED = 42

ROOT = Path(__file__).resolve().parent.parent
FEATURES_PQ = ROOT / "data" / "features.parquet"
LABELS_PQ = ROOT / "data" / "labels.parquet"
SUMMARY_JSON = ROOT / "artifacts" / "data_summary.json"
FEATURE_LIST_JSON = ROOT / "artifacts" / "feature_list.json"

OUT_MODEL = ROOT / "artifacts" / "model.json"
OUT_METRICS = ROOT / "artifacts" / "metrics.json"
OUT_CM_PNG = ROOT / "artifacts" / "confusion_matrix.png"
OUT_ROC_PNG = ROOT / "artifacts" / "roc_curve.png"
OUT_FI_PNG = ROOT / "artifacts" / "feature_importance.png"

CLASS_NAMES = ["Low (0)", "Medium (1)", "High (2)"]

XGB_PARAMS = dict(
    objective="multi:softprob",
    num_class=3,
    max_depth=6,
    learning_rate=0.1,
    n_estimators=100,
    eval_metric="mlogloss",
    tree_method="hist",
    random_state=SEED,
    n_jobs=-1,
)


# ---------------------------------------------------------------- data loading

def load_dataset() -> tuple[pd.DataFrame, list[str]]:
    """Join features and labels, drop invalid + NaN rows, return df + feature names."""
    feat = pd.read_parquet(FEATURES_PQ)
    lab = pd.read_parquet(LABELS_PQ)
    df = feat.merge(
        lab[["timestamp", "equipment_id", "risk_class", "valid"]],
        on=["timestamp", "equipment_id"], how="inner",
    )
    n0 = len(df)
    df = df[df["valid"] == 1].drop(columns=["valid"])
    n1 = len(df)
    df = df.dropna()
    n2 = len(df)
    df["risk_class"] = df["risk_class"].astype(np.int8)
    print(f"[train] rows raw={n0:,}  after valid==1: {n1:,}  after dropna: {n2:,}")

    with FEATURE_LIST_JSON.open(encoding="utf-8") as f:
        fl = json.load(f)
    excluded = set(fl["training_feature_exclusions"]["excluded_features"])
    drop_cols = ["timestamp", "equipment_id", "risk_class"] + sorted(excluded)
    feature_cols = [c for c in df.columns if c not in drop_cols]
    print(f"[train] X feature count = {len(feature_cols)} "
          f"(excluded {len(excluded)} domain features from training)")
    return df, feature_cols


# ---------------------------------------------------------------- split makers

def chronological_split(df: pd.DataFrame, train_frac: float = 0.80) -> dict:
    """Cut at the 80%-th unique timestamp."""
    times = np.sort(df["timestamp"].unique())
    cut = times[int(len(times) * train_frac)]
    mask_tr = df["timestamp"] < cut
    mask_te = ~mask_tr
    return {
        "name": "chronological_80_20",
        "cut_timestamp": pd.Timestamp(cut).isoformat(),
        "mask_train": mask_tr.values,
        "mask_test": mask_te.values,
        "n_train": int(mask_tr.sum()),
        "n_test": int(mask_te.sum()),
        "rationale": (
            "Train on the first ~80% of the time axis, test on the last ~20%. "
            "Realistic ops: a model trained on past data predicts the near future."
        ),
    }


def equipment_split(df: pd.DataFrame, seed: int = SEED) -> dict:
    """Hold out 2 degraded + 8 healthy units as test."""
    with SUMMARY_JSON.open(encoding="utf-8") as f:
        summary = json.load(f)
    deg = sorted(summary["degradation"]["units"])
    all_units = sorted(df["equipment_id"].unique())
    healthy = [u for u in all_units if u not in deg]

    rng = np.random.default_rng(seed)
    test_deg = sorted(rng.choice(deg, size=2, replace=False).tolist())
    test_healthy = sorted(rng.choice(healthy, size=8, replace=False).tolist())
    test_units = set(test_deg) | set(test_healthy)
    mask_te = df["equipment_id"].isin(test_units).values
    mask_tr = ~mask_te
    return {
        "name": "equipment_40_10_stratified",
        "test_units_degraded": test_deg,
        "test_units_healthy": test_healthy,
        "n_train_units": len(all_units) - len(test_units),
        "n_test_units": len(test_units),
        "mask_train": mask_tr,
        "mask_test": mask_te,
        "n_train": int(mask_tr.sum()),
        "n_test": int(mask_te.sum()),
        "rationale": (
            "10 units held out (2 degraded + 8 healthy to keep stratification). "
            "Forces the model to generalize to *unseen transformers*; "
            "stricter than chronological split."
        ),
    }


# ---------------------------------------------------------------- train + eval

def fit_xgb(X_tr: pd.DataFrame, y_tr: np.ndarray) -> xgb.XGBClassifier:
    sw = compute_sample_weight("balanced", y_tr)
    clf = xgb.XGBClassifier(**XGB_PARAMS)
    clf.fit(X_tr, y_tr, sample_weight=sw, verbose=False)
    return clf


def baseline_metrics_block(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Metrics for a hard-predictor (no probabilities). Used for the no-ML
    threshold-rule baseline so we can compare on identical splits."""
    labels = [0, 1, 2]
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    p, r, f, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0)
    return {
        "per_class": {
            CLASS_NAMES[c]: {
                "precision": float(p[c]),
                "recall": float(r[c]),
                "f1": float(f[c]),
            } for c in labels
        },
        "macro_f1": float(np.mean(f)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "confusion_matrix": cm.tolist(),
    }


def _threshold_rule_predict(df_subset: pd.DataFrame) -> np.ndarray:
    """No-ML baseline: apply the spec's class rule to the CURRENT (time-t) sensor
    values to predict the t+24h class. If this baseline already scores near-perfect,
    the headline metrics reflect slow-degradation data structure, not modelling skill.
    """
    def per_p(v, w, c):
        return np.where(v > c, 2, np.where(v > w, 1, 0))
    cls_t = per_p(df_subset["temperature_top"].to_numpy(), 85.0, 100.0)
    cls_c = per_p(df_subset["gas_c2h2"].to_numpy(), 25.0, 50.0)
    cls_v = per_p(df_subset["vibration_x"].to_numpy(), 5.0, 8.0)
    return np.maximum.reduce([cls_t, cls_c, cls_v]).astype(np.int8)


def metrics_block(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray) -> dict:
    labels = [0, 1, 2]
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    p, r, f, s = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = float(np.mean(f))

    classes_present = sorted(np.unique(y_true).tolist())
    try:
        roc_auc_ovr = float(roc_auc_score(
            y_true, y_proba, multi_class="ovr",
            labels=labels, average="macro",
        ))
    except ValueError:
        roc_auc_ovr = None

    pr_auc = {}
    for c in labels:
        if c in classes_present:
            pr_auc[c] = float(average_precision_score(
                (y_true == c).astype(int), y_proba[:, c]
            ))
        else:
            pr_auc[c] = None

    # Trivial "always Low" baseline for context — illustrates accuracy trap.
    baseline_pred = np.zeros_like(y_true)
    baseline_acc = float(accuracy_score(y_true, baseline_pred))
    _, baseline_r, _, _ = precision_recall_fscore_support(
        y_true, baseline_pred, labels=labels, zero_division=0
    )

    return {
        "support_per_class": {CLASS_NAMES[c]: int(s[c]) for c in labels},
        "per_class": {
            CLASS_NAMES[c]: {
                "precision": float(p[c]),
                "recall": float(r[c]),
                "f1": float(f[c]),
                "pr_auc": pr_auc[c],
            } for c in labels
        },
        "primary_metrics_high_class": {
            "recall": float(r[2]),
            "f1": float(f[2]),
            "precision": float(p[2]),
            "pr_auc": pr_auc[2],
        },
        "roc_auc_ovr_macro": roc_auc_ovr,
        "macro_f1": macro_f1,
        "accuracy": float(acc),
        "trivial_baseline_always_low": {
            "accuracy": baseline_acc,
            "recall_high": float(baseline_r[2]),
            "note": (
                "A model that always predicts Low scores this accuracy. "
                "Use it as a sanity floor — high accuracy alone is meaningless "
                "under ~93 % majority class."
            ),
        },
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_row_labels_true": CLASS_NAMES,
        "confusion_matrix_col_labels_pred": CLASS_NAMES,
    }


# ---------------------------------------------------------------- plots

def plot_confusion(cm: np.ndarray, path: Path, title: str):
    cm = np.asarray(cm)
    cm_norm = cm / cm.sum(axis=1, keepdims=True).clip(min=1)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3))
    for ax, mat, fmt, sub in [
        (axes[0], cm, "{:,}", "Counts"),
        (axes[1], cm_norm, "{:.2%}", "Row-normalized (recall per true class)"),
    ]:
        im = ax.imshow(mat, cmap="Blues", vmin=0, vmax=mat.max() if mat.max() else 1)
        ax.set_xticks(range(3)); ax.set_yticks(range(3))
        ax.set_xticklabels(CLASS_NAMES, rotation=20, ha="right")
        ax.set_yticklabels(CLASS_NAMES)
        ax.set_xlabel("Predicted"); ax.set_ylabel("True")
        ax.set_title(sub)
        for i in range(3):
            for j in range(3):
                val = mat[i, j]
                colour = "white" if val > mat.max() * 0.5 else "black"
                ax.text(j, i, fmt.format(val), ha="center", va="center",
                        color=colour, fontsize=10)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(title, fontsize=13)
    plt.tight_layout()
    plt.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_roc(y_true: np.ndarray, y_proba: np.ndarray, path: Path, title: str):
    fig, ax = plt.subplots(figsize=(6.5, 5))
    colours = ["#1f77b4", "#ff7f0e", "#d62728"]
    for c in [0, 1, 2]:
        y_bin = (y_true == c).astype(int)
        if y_bin.sum() == 0:
            continue
        fpr, tpr, _ = roc_curve(y_bin, y_proba[:, c])
        auc_val = roc_auc_score(y_bin, y_proba[:, c])
        ax.plot(fpr, tpr, color=colours[c],
                label=f"{CLASS_NAMES[c]}  AUC={auc_val:.3f}", lw=2)
    ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5, label="random")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(title)
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_feature_importance(clf, feature_names: list[str], path: Path, title: str, top_k: int = 15):
    booster = clf.get_booster()
    score = booster.get_score(importance_type="gain")
    df_imp = (
        pd.Series(score).reindex(feature_names).fillna(0)
          .sort_values(ascending=False)
          .head(top_k)
    )
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(df_imp.index[::-1], df_imp.values[::-1], color="#1f77b4")
    ax.set_xlabel("Importance (gain)")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.3)
    for i, v in enumerate(df_imp.values[::-1]):
        ax.text(v, i, f"  {v:.1f}", va="center", fontsize=9)
    plt.tight_layout()
    plt.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- main

def run_split(df: pd.DataFrame, feature_cols: list[str], split: dict,
              is_primary: bool) -> dict:
    mask_tr = split["mask_train"]
    mask_te = split["mask_test"]
    X_tr = df.loc[mask_tr, feature_cols]
    y_tr = df.loc[mask_tr, "risk_class"].to_numpy()
    X_te = df.loc[mask_te, feature_cols]
    y_te = df.loc[mask_te, "risk_class"].to_numpy()

    print(f"[train:{split['name']}] X_train={X_tr.shape}  X_test={X_te.shape}")
    class_dist_tr = {CLASS_NAMES[c]: int((y_tr == c).sum()) for c in [0, 1, 2]}
    class_dist_te = {CLASS_NAMES[c]: int((y_te == c).sum()) for c in [0, 1, 2]}
    print(f"[train:{split['name']}] train class counts: {class_dist_tr}")
    print(f"[train:{split['name']}] test  class counts: {class_dist_te}")

    clf = fit_xgb(X_tr, y_tr)
    y_pred = clf.predict(X_te)
    y_proba = clf.predict_proba(X_te)
    mblock = metrics_block(y_te, y_pred, y_proba)

    # Diagnostic: how well does a no-ML "apply spec thresholds to current sensors" rule do?
    df_test_subset = df.loc[mask_te, ["temperature_top", "gas_c2h2", "vibration_x"]]
    y_rule = _threshold_rule_predict(df_test_subset)
    rule_acc = float(accuracy_score(y_te, y_rule))
    _, rule_r, rule_f, _ = precision_recall_fscore_support(
        y_te, y_rule, labels=[0, 1, 2], zero_division=0
    )
    mblock["threshold_rule_baseline"] = {
        "description": (
            "Apply the spec class rule (max of per-parameter classes on "
            "temperature_top, gas_c2h2, vibration_x) to the CURRENT-time-t "
            "sensor values to predict the t+24h class — no model, no features."
        ),
        "accuracy": rule_acc,
        "recall_per_class": {CLASS_NAMES[c]: float(rule_r[c]) for c in [0, 1, 2]},
        "f1_per_class": {CLASS_NAMES[c]: float(rule_f[c]) for c in [0, 1, 2]},
        "interpretation": (
            "If this baseline matches the model's metrics, slow synthetic "
            "degradation makes sensor(t) ≈ sensor(t+24), so most of the signal "
            "is in the present. If model > baseline, the model genuinely "
            "predicts trajectory rather than reading off current state."
        ),
    }

    if is_primary:
        clf.get_booster().save_model(str(OUT_MODEL))
        print(f"[train] saved model to {OUT_MODEL}")
        plot_confusion(np.array(mblock["confusion_matrix"]), OUT_CM_PNG,
                       "Confusion matrix — chronological 80/20 split (test)")
        plot_roc(y_te, y_proba, OUT_ROC_PNG,
                 "ROC (One-vs-Rest) — chronological 80/20 split")
        plot_feature_importance(clf, feature_cols, OUT_FI_PNG,
                                "Top-15 feature importance (gain) — chronological split")
        print(f"[train] saved {OUT_CM_PNG.name}, {OUT_ROC_PNG.name}, {OUT_FI_PNG.name}")

    return {
        "split_name": split["name"],
        "rationale": split["rationale"],
        "n_train": split["n_train"],
        "n_test": split["n_test"],
        "train_class_counts": class_dist_tr,
        "test_class_counts": class_dist_te,
        **({"cut_timestamp": split["cut_timestamp"]} if "cut_timestamp" in split else {}),
        **({"test_units_degraded": split["test_units_degraded"],
            "test_units_healthy": split["test_units_healthy"]}
           if "test_units_degraded" in split else {}),
        **mblock,
    }


def main():
    df, feature_cols = load_dataset()

    primary = chronological_split(df, train_frac=0.80)
    secondary = equipment_split(df)

    print()
    print("=" * 78)
    print("PRIMARY SPLIT — chronological 80/20")
    print("=" * 78)
    res_primary = run_split(df, feature_cols, primary, is_primary=True)

    print()
    print("=" * 78)
    print("ROBUSTNESS SPLIT — equipment 40/10 (stratified by degradation)")
    print("=" * 78)
    res_secondary = run_split(df, feature_cols, secondary, is_primary=False)

    out = {
        "seed": SEED,
        "model": "XGBoost multi:softprob, max_depth=6, lr=0.1, n_estimators=100",
        "xgb_params": XGB_PARAMS,
        "imbalance_handling": (
            "sklearn.utils.class_weight.compute_sample_weight('balanced', y_train) "
            "passed to XGBClassifier.fit(sample_weight=...)"
        ),
        "feature_count": len(feature_cols),
        "feature_cols": feature_cols,
        "metric_priority_for_thesis": [
            "recall (High class) — missing a critical-risk row = missed incident",
            "F1 (High class)",
            "PR-AUC (High class) — appropriate under heavy imbalance",
            "confusion matrix — shows High↔Medium confusion",
            "ROC-AUC One-vs-Rest (macro)",
            "macro F1",
            "accuracy LAST — trivial 'always Low' baseline already scores ~93%",
        ],
        "primary_split_chronological_80_20": res_primary,
        "robustness_split_equipment_40_10": res_secondary,
    }
    with OUT_METRICS.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print()
    print(f"[train] wrote metrics -> {OUT_METRICS}")

    print()
    print("==== HEADLINE METRICS (chronological / primary, on TEST) ====")
    hi = res_primary["primary_metrics_high_class"]
    print(f"  High recall   : {hi['recall']:.4f}")
    print(f"  High F1       : {hi['f1']:.4f}")
    print(f"  High precision: {hi['precision']:.4f}")
    print(f"  High PR-AUC   : {hi['pr_auc']:.4f}" if hi['pr_auc'] is not None else "  High PR-AUC   : n/a")
    print(f"  ROC-AUC OvR macro: {res_primary['roc_auc_ovr_macro']:.4f}")
    print(f"  Macro F1      : {res_primary['macro_f1']:.4f}")
    print(f"  Accuracy      : {res_primary['accuracy']:.4f}  (trivial baseline accuracy: "
          f"{res_primary['trivial_baseline_always_low']['accuracy']:.4f})")

    print()
    print("==== ROBUSTNESS (equipment split, on TEST) ====")
    hi2 = res_secondary["primary_metrics_high_class"]
    print(f"  High recall   : {hi2['recall']:.4f}")
    print(f"  High F1       : {hi2['f1']:.4f}")
    print(f"  Macro F1      : {res_secondary['macro_f1']:.4f}")
    print(f"  ROC-AUC OvR   : {res_secondary['roc_auc_ovr_macro']:.4f}"
          if res_secondary['roc_auc_ovr_macro'] is not None else "  ROC-AUC OvR   : n/a")


if __name__ == "__main__":
    main()
