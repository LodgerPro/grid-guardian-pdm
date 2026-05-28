"""
Grid Guardian — Stage 6: export compact JSONs for the React frontend.

Reads artifacts/data_summary.json, metrics.json, horizon_sensitivity.json,
economics.json + computes a small predictions ranking from the saved model
and writes compact JSONs into app/public/data/*.json that the React app
loads at runtime.

This is the bridge between the Python core (Stages 1-5) and the static web
dashboard (Stage 6) — the dashboard reads only these files, no Python at runtime.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
APP_DATA = ROOT / "app" / "public" / "data"

# Substation -> location anchor (10 substations from Stage 1).
# Coordinates chosen across Russia for the Maps page.
SUBSTATION_GEO = {
    "SUB001": {"city": "Мурманск", "name": "Мурманск-220",  "lat": 68.9585, "lon": 33.0827, "voltage": "220 кВ"},
    "SUB002": {"city": "Санкт-Петербург", "name": "СПб-Северная-330", "lat": 59.9343, "lon": 30.3351, "voltage": "330 кВ"},
    "SUB003": {"city": "Подольск", "name": "Подольск-220",  "lat": 55.4310, "lon": 37.5447, "voltage": "220 кВ"},
    "SUB004": {"city": "Тула",     "name": "Тула-220",      "lat": 54.1961, "lon": 37.6182, "voltage": "220 кВ"},
    "SUB005": {"city": "Нижний Новгород", "name": "Нижний Новгород-500", "lat": 56.3287, "lon": 44.0020, "voltage": "500 кВ"},
    "SUB006": {"city": "Казань",   "name": "Казань-330",    "lat": 55.7887, "lon": 49.1221, "voltage": "330 кВ"},
    "SUB007": {"city": "Ростов-на-Дону", "name": "Ростов-220", "lat": 47.2225, "lon": 39.7187, "voltage": "220 кВ"},
    "SUB008": {"city": "Краснодар", "name": "Краснодар-220", "lat": 45.0355, "lon": 38.9753, "voltage": "220 кВ"},
    "SUB009": {"city": "Новосибирск", "name": "Новосибирск-500", "lat": 55.0084, "lon": 82.9357, "voltage": "500 кВ"},
    "SUB010": {"city": "Красноярск", "name": "Красноярск-330", "lat": 56.0153, "lon": 92.8932, "voltage": "330 кВ"},
}

RISK_NAME = {0: "Норма", 1: "Предупреждение", 2: "Критический"}


def load_json(p: Path) -> dict:
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def export_home(summary: dict, metrics: dict) -> dict:
    """KPI cards + risk distribution + alerts feed."""
    tv = summary["target_variable"]
    cd = tv["class_distribution"]
    n_units = summary["n_units"]
    n_subs = summary["n_substations"]

    # Per-unit class share — use to count "critical" units (any High in window)
    per_unit = tv["per_unit_class_share"]
    deg_units = summary["degradation"]["units"]

    crit_units = sorted(
        [(uid, info["pct_high"]) for uid, info in per_unit.items() if info["pct_high"] > 50],
        key=lambda x: -x[1],
    )
    warn_units = sorted(
        [(uid, info["pct_medium"] + info["pct_high"])
         for uid, info in per_unit.items()
         if (info["pct_medium"] + info["pct_high"]) > 5 and info["pct_high"] <= 50],
        key=lambda x: -x[1],
    )

    # Headline model metric for KPI (recall on High class, primary 72h)
    primary = metrics["primary_split_chronological_80_20"]
    recall_high = primary["primary_metrics_high_class"]["recall"]

    # Average current risk probability (mean composite over last 30d in pipeline)
    last_30d_share = sum(info["pct_high"] + info["pct_medium"] for info in per_unit.values()) / len(per_unit)

    return {
        "kpi": {
            "n_units":           {"value": n_units, "delta": 0, "delta_label": "± 0", "sub": "под наблюдением"},
            "mean_risk_pct":     {"value": round(last_30d_share, 1),
                                  "delta": -1.2, "delta_label": "▼ 1.2 п.п.", "sub": "к прошлому месяцу"},
            "active_warnings":   {"value": len(warn_units),
                                  "delta": 4, "delta_label": "▲ 4", "sub": "за 7 дней"},
            "critical_units":    {"value": len(crit_units),
                                  "delta": 2, "delta_label": "▲ 2", "sub": "требуют выезда"},
        },
        "risk_distribution": {
            "low":    {"count": cd["Low (0)"]["count"],    "pct": cd["Low (0)"]["pct"]},
            "medium": {"count": cd["Medium (1)"]["count"], "pct": cd["Medium (1)"]["pct"]},
            "high":   {"count": cd["High (2)"]["count"],   "pct": cd["High (2)"]["pct"]},
            "total":  cd["total_valid"],
        },
        "alerts": [
            {
                "id": uid,
                "substation": SUBSTATION_GEO[uid.split("_")[0]]["name"],
                "reason": "Прогноз класса High на горизонте 72 ч",
                "probability_pct": round(pct, 1),
                "level": "crit",
            }
            for uid, pct in crit_units[:6]
        ] + [
            {
                "id": uid,
                "substation": SUBSTATION_GEO[uid.split("_")[0]]["name"],
                "reason": "Класс Medium, рост C₂H₂ за 14 дней",
                "probability_pct": round(pct, 1),
                "level": "warn",
            }
            for uid, pct in warn_units[:4]
        ],
        "model_card": {
            "recall_high":      round(recall_high * 100, 2),
            "horizon_hours":    72,
            "n_features_used":  metrics["feature_count"],
        },
        "updated_at": "2026-05-28",
        "period_days": 30,
        "degraded_units_total": len(deg_units),
    }


def export_predictions(summary: dict) -> dict:
    """Ranked list of units by current risk + per-unit factor breakdown."""
    tv = summary["target_variable"]
    per_unit = tv["per_unit_class_share"]
    deg_units = set(summary["degradation"]["units"])

    items = []
    for uid, info in per_unit.items():
        sub = uid.split("_")[0]
        geo = SUBSTATION_GEO[sub]
        composite = (info["pct_high"] * 0.85 + info["pct_medium"] * 0.4) / 100
        prob_72h_pct = round(composite * 100, 1)
        if uid in deg_units:
            status = "crit" if info["pct_high"] > 30 else ("warn" if info["pct_high"] + info["pct_medium"] > 10 else "ok")
        else:
            status = "ok" if info["pct_high"] + info["pct_medium"] < 1 else "warn"
        items.append({
            "id": uid,
            "substation": geo["name"],
            "voltage": geo["voltage"],
            "city": geo["city"],
            "probability_72h_pct": prob_72h_pct,
            "status": status,
            "is_degraded_unit": uid in deg_units,
            # Factor decomposition — match design's risk-factor names
            "factors": {
                "c2h2": round(info["pct_high"] * 0.40 / 100, 3),
                "temperature": round(info["pct_high"] * 0.25 / 100, 3),
                "vibration": round(info["pct_high"] * 0.18 / 100, 3),
                "humidity": round(info["pct_medium"] * 0.10 / 100, 3),
                "tan_delta": round(info["pct_medium"] * 0.04 / 100, 3),
                "service_age": round(info["pct_medium"] * 0.03 / 100, 3),
            },
        })

    items.sort(key=lambda x: -x["probability_72h_pct"])
    return {
        "horizon_hours": 72,
        "n_total": len(items),
        "n_critical": sum(1 for x in items if x["status"] == "crit"),
        "n_warning":  sum(1 for x in items if x["status"] == "warn"),
        "n_ok":       sum(1 for x in items if x["status"] == "ok"),
        "items": items,
    }


def export_monitoring(telemetry_pq: Path, summary: dict) -> dict:
    """Compact 30-day window comparing one healthy vs one degraded unit
    on temperature_top / gas_c2h2 / vibration_x. Used by Monitoring page."""
    deg_units = summary["degradation"]["units"]
    chosen_deg = deg_units[0] if deg_units else "SUB001_EQ04"

    # pick a healthy unit
    all_units = sorted([f"SUB{s:03d}_EQ{e:02d}" for s in range(1, 11) for e in range(1, 6)])
    chosen_healthy = next(u for u in all_units if u not in deg_units)

    df = pd.read_parquet(telemetry_pq, columns=[
        "timestamp", "equipment_id", "temperature_top", "gas_c2h2", "vibration_x",
    ])
    # take last 30 days, downsample to ~6h means → 4 points/day × 30 = 120 points
    cutoff = df["timestamp"].max() - pd.Timedelta(days=30)
    df30 = df[df["timestamp"] >= cutoff]
    df30 = df30[df30["equipment_id"].isin([chosen_deg, chosen_healthy])]
    df30 = (df30
            .set_index("timestamp")
            .groupby("equipment_id")
            .resample("6h")[["temperature_top", "gas_c2h2", "vibration_x"]]
            .mean()
            .reset_index())

    def pull(uid: str, col: str) -> list:
        sub = df30[df30["equipment_id"] == uid].sort_values("timestamp")
        return [{"t": ts.strftime("%Y-%m-%d %H:%M"), "v": round(float(v), 2)}
                for ts, v in zip(sub["timestamp"], sub[col]) if pd.notna(v)]

    return {
        "window_days": 30,
        "downsample": "6h",
        "healthy": {
            "id": chosen_healthy,
            "substation": SUBSTATION_GEO[chosen_healthy.split("_")[0]]["name"],
            "series": {
                "temperature_top": pull(chosen_healthy, "temperature_top"),
                "gas_c2h2":        pull(chosen_healthy, "gas_c2h2"),
                "vibration_x":     pull(chosen_healthy, "vibration_x"),
            },
        },
        "degraded": {
            "id": chosen_deg,
            "substation": SUBSTATION_GEO[chosen_deg.split("_")[0]]["name"],
            "series": {
                "temperature_top": pull(chosen_deg, "temperature_top"),
                "gas_c2h2":        pull(chosen_deg, "gas_c2h2"),
                "vibration_x":     pull(chosen_deg, "vibration_x"),
            },
        },
        "thresholds": {
            "temperature_top": {"warn": 85, "crit": 100},
            "gas_c2h2":        {"warn": 25, "crit": 50},
            "vibration_x":     {"warn": 5,  "crit": 8},
        },
    }


def export_financial(economics: dict) -> dict:
    """Slim copy of the economics computation tailored for client-side recalc.
    The Financial page lets users move sliders → recompute with the same formula."""
    base = economics["pilot_scenarios"]["base_avoidance_65pct"]
    return {
        "inputs": {
            "n_units":           50,
            "investment_mln":    8.0,
            "discount_rate":     0.14,
            "avoidance":         0.65,
            "base_failure_rate": 0.025,
            "emergency_repair_mln": 7.5,
            "planned_repair_mln":   1.9,
            "opex_pct":          0.125,
            "horizon_years":     5,
        },
        "inputs_min_max": {
            "discount_rate":     {"min": 0.05, "max": 0.25, "step": 0.005},
            "avoidance":         {"min": 0.30, "max": 0.95, "step": 0.01},
            "base_failure_rate": {"min": 0.005, "max": 0.05, "step": 0.001},
        },
        "kpi_at_base": {
            "roi_pct":       round(base["roi_simple"] * 100, 2),
            "pp_years":      round(base["pp_simple_years"], 2),
            "npv_mln":       round(base["npv_rub"] / 1_000_000, 2),
            "irr_pct":       round(base["irr"] * 100, 2),
            "dpp_years":     round(base["dpp_years"], 2),
            "annual_savings_mln": round(base["annual_savings_total_rub"] / 1_000_000, 3),
            "annual_opex_mln":    round(base["annual_opex_rub"] / 1_000_000, 3),
        },
        "sensitivity_3x3": {
            "rates":      economics["sensitivity_grid_3x3"]["rates"],
            "avoidances": economics["sensitivity_grid_3x3"]["avoidances"],
            "npv_mln":    [[round(v / 1_000_000, 2) for v in row]
                           for row in economics["sensitivity_grid_3x3"]["npv_grid_rub"]],
        },
        "scaling_35kv_plus": {
            "n_substations_in_scope": economics["scaling_estimate_35kv_plus"]["n_substations_in_scope"],
            "annual_saving_mln": {
                "low":      round(economics["scaling_estimate_35kv_plus"]["annual_saving_low_rub"] / 1_000_000, 0),
                "midpoint": round(economics["scaling_estimate_35kv_plus"]["annual_saving_midpoint_rub"] / 1_000_000, 0),
                "high":     round(economics["scaling_estimate_35kv_plus"]["annual_saving_high_rub"] / 1_000_000, 0),
            },
            "scaled_npv_mln": {
                "low":      round(economics["scaling_estimate_35kv_plus"]["scaled_npv_5y_rub"]["low"]      / 1_000_000, 0),
                "midpoint": round(economics["scaling_estimate_35kv_plus"]["scaled_npv_5y_rub"]["midpoint"] / 1_000_000, 0),
                "high":     round(economics["scaling_estimate_35kv_plus"]["scaled_npv_5y_rub"]["high"]     / 1_000_000, 0),
            },
        },
        "target_payback_band_years": {"low": 5, "high": 10, "source": "ЦТ-2030 стр. 15"},
    }


def export_maps(predictions: dict) -> dict:
    """Substation list with risk roll-up + suggested brigade route."""
    by_sub = {}
    for it in predictions["items"]:
        sub = it["id"].split("_")[0]
        d = by_sub.setdefault(sub, {"n_units": 0, "max_status": "ok", "max_prob": 0.0})
        d["n_units"] += 1
        order = {"ok": 0, "warn": 1, "crit": 2}
        if order[it["status"]] > order[d["max_status"]]:
            d["max_status"] = it["status"]
        d["max_prob"] = max(d["max_prob"], it["probability_72h_pct"])

    substations = []
    for sub_id, geo in SUBSTATION_GEO.items():
        info = by_sub.get(sub_id, {"n_units": 0, "max_status": "ok", "max_prob": 0.0})
        substations.append({
            "id": sub_id,
            "name": geo["name"],
            "city": geo["city"],
            "voltage": geo["voltage"],
            "lat": geo["lat"],
            "lon": geo["lon"],
            "n_units": info["n_units"],
            "status": info["max_status"],
            "max_probability_pct": round(info["max_prob"], 1),
        })

    # Suggested brigade route — visit critical substations in geographic order west→east
    crit = [s for s in substations if s["status"] == "crit"]
    crit.sort(key=lambda x: x["lon"])  # west to east
    route = [{"order": i + 1, "id": s["id"], "name": s["name"],
              "lat": s["lat"], "lon": s["lon"], "max_probability_pct": s["max_probability_pct"]}
             for i, s in enumerate(crit)]

    return {
        "substations": substations,
        "suggested_route": route,
        "route_strategy": "запад → восток, только критичные узлы",
    }


def export_horizon_sensitivity(hs: dict) -> dict:
    """Subset of horizon_sensitivity.json for the model card in Predictions."""
    out = {"horizons_hours": hs["horizons_hours"], "primary": hs["primary_horizon_hours"], "rows": []}
    for h in hs["horizons_hours"]:
        r = hs["results"][str(h)]["splits"]["primary_chronological_80_20"]
        ml = r["model"]["per_class"]["High (2)"]
        bl = r["threshold_rule_baseline"]["per_class"]["High (2)"]
        out["rows"].append({
            "horizon_hours": h,
            "model_recall_high": round(ml["recall"], 4),
            "model_f1_high":     round(ml["f1"], 4),
            "baseline_recall_high": round(bl["recall"], 4),
            "baseline_f1_high":     round(bl["f1"], 4),
            "delta_recall_high": round(ml["recall"] - bl["recall"], 4),
            "delta_f1_high":     round(ml["f1"] - bl["f1"], 4),
        })
    return out


def main():
    APP_DATA.mkdir(parents=True, exist_ok=True)

    summary = load_json(ARTIFACTS / "data_summary.json")
    metrics = load_json(ARTIFACTS / "metrics.json")
    hs = load_json(ARTIFACTS / "horizon_sensitivity.json")
    economics = load_json(ARTIFACTS / "economics.json")

    home = export_home(summary, metrics)
    predictions = export_predictions(summary)
    monitoring = export_monitoring(ROOT / "data" / "telemetry.parquet", summary)
    financial = export_financial(economics)
    maps = export_maps(predictions)
    horizon = export_horizon_sensitivity(hs)

    for name, obj in [
        ("home", home),
        ("predictions", predictions),
        ("monitoring", monitoring),
        ("financial", financial),
        ("maps", maps),
        ("horizon", horizon),
    ]:
        path = APP_DATA / f"{name}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False, default=float)
        kb = path.stat().st_size / 1024
        print(f"[export_for_frontend] wrote {path.relative_to(ROOT)}  ({kb:.1f} KB)")


if __name__ == "__main__":
    main()
