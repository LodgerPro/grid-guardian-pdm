"""
Grid Guardian — Stage 1: synthetic telemetry generator.

Generates 2 years of hourly measurements for 50 transformers
(10 substations x 5 transformers each), 18 columns total,
with realistic daily/seasonal patterns and ~18% of units
exhibiting progressive degradation.

Outputs:
    data/telemetry.parquet         — full dataset (~876k rows)
    artifacts/data_summary.json    — descriptive stats and metadata
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_SUBSTATIONS = 10
N_TRANSFORMERS_PER_SUB = 5
N_UNITS = N_SUBSTATIONS * N_TRANSFORMERS_PER_SUB  # 50
N_HOURS = 17_520  # 2 years * 365 * 24
START = pd.Timestamp("2023-01-01 00:00:00")
DEGRADATION_FRACTION = 0.18  # ~18 % units accumulate damage
ASYMMETRY_FRACTION = 0.20    # phase-asymmetric units

ROOT = Path(__file__).resolve().parent.parent
OUT_PARQUET = ROOT / "data" / "telemetry.parquet"
OUT_SUMMARY = ROOT / "artifacts" / "data_summary.json"

NUMERIC_COLS = [
    "temperature_top", "temperature_oil",
    "voltage_phase_a", "voltage_phase_b", "voltage_phase_c",
    "current_phase_a", "current_phase_b", "current_phase_c",
    "gas_h2", "gas_ch4", "gas_c2h2",
    "vibration_x", "vibration_y", "vibration_z",
    "humidity", "load_percentage",
]


def _build_time_axis():
    timestamps = START + pd.to_timedelta(np.arange(N_HOURS), unit="h")
    hours = timestamps.hour.to_numpy()
    dow = timestamps.dayofweek.to_numpy()
    doy = timestamps.dayofyear.to_numpy()
    year_phase = 2 * np.pi * doy / 365.25
    day_phase = 2 * np.pi * hours / 24
    # Central-Russia-like ambient: ~ -10 °C in mid-January to ~ +25 °C in mid-July.
    ambient = 7.5 - 17.5 * np.cos(year_phase - 0.10)
    weekend = (dow >= 5).astype(float)
    return timestamps, day_phase, year_phase, weekend, ambient


def generate(rng: np.random.Generator) -> pd.DataFrame:
    timestamps, day_phase, year_phase, weekend, ambient = _build_time_axis()
    t_norm = np.arange(N_HOURS) / N_HOURS  # 0..1 progression

    unit_ids = [
        f"SUB{s:03d}_EQ{e:02d}"
        for s in range(1, N_SUBSTATIONS + 1)
        for e in range(1, N_TRANSFORMERS_PER_SUB + 1)
    ]

    n_deg = int(round(N_UNITS * DEGRADATION_FRACTION))
    n_asym = int(round(N_UNITS * ASYMMETRY_FRACTION))
    degraded_idx = set(rng.choice(N_UNITS, size=n_deg, replace=False).tolist())
    asym_idx = set(rng.choice(N_UNITS, size=n_asym, replace=False).tolist())

    base_load = rng.uniform(0.45, 0.65, size=N_UNITS)
    load_amp_daily = rng.uniform(0.12, 0.22, size=N_UNITS)
    load_amp_season = rng.uniform(0.08, 0.15, size=N_UNITS)

    # Per-unit degradation timing. We spread the moment of full degradation
    # across the 2-year window so some units cross into class High during the
    # training period and some during the test period — mirroring a real fleet
    # where historical failure data exists but new failures still occur.
    full_deg_t = rng.uniform(0.30, 0.95, size=N_UNITS)
    ramp_len = rng.uniform(0.20, 0.35, size=N_UNITS)
    onset_t = np.clip(full_deg_t - ramp_len, 0.02, 0.95)

    frames = []
    for idx, uid in enumerate(unit_ids):
        # ---- load profile (%) ----
        # cos(year_phase) peaks at year_phase=0 (early January) — winter heating demand.
        load = (
            base_load[idx]
            + load_amp_season[idx] * np.cos(year_phase)
            # twin daily peaks around 09:00 and 19:00
            + load_amp_daily[idx] * 0.5 * (
                np.cos(day_phase - 2 * np.pi * 9 / 24)
                + np.cos(day_phase - 2 * np.pi * 19 / 24)
            )
            - 0.05 * weekend
            + rng.normal(0, 0.03, size=N_HOURS)
        )
        load = np.clip(load, 0.15, 1.0) * 100.0  # convert to %

        # ---- degradation track ----
        # Per-unit onset/full-deg-time spreads class-High emergence across the
        # 2-year window — required so a chronological 80/20 split has High
        # examples in BOTH train and test partitions.
        if idx in degraded_idx:
            o = onset_t[idx]
            f = full_deg_t[idx]
            denom = max(f - o, 0.01)
            progression = np.clip((t_norm - o) / denom, 0, 1)
            deg = np.clip(
                progression ** 1.3 + rng.normal(0, 0.005, size=N_HOURS),
                0, 1.2,
            )
        else:
            deg = np.zeros(N_HOURS)

        # ---- humidity (%) ----
        humidity = np.clip(
            55
            + 15 * np.sin(year_phase - 0.5)
            + 5 * np.sin(day_phase + np.pi)
            + rng.normal(0, 4, size=N_HOURS),
            15, 98,
        )

        # ---- temperatures (°C) ----
        # Calibrated so healthy units sit inside the spec band 55-85 °C.
        # Top-oil rise above an internal ~50 °C baseline driven by load + minor
        # ambient/humidity coupling; degradation adds a slow creep up to ~+30 °C.
        temp_top = (
            50.0
            + 0.35 * load
            + 0.15 * ambient
            + 0.04 * (humidity - 50) * (load / 100)
            + rng.normal(0, 1.5, size=N_HOURS)
            + deg * 30
        )
        # bottom/bulk oil is slightly cooler under healthy operation
        oil_offset = rng.uniform(3.0, 7.0)
        temp_oil = (
            temp_top - oil_offset
            + rng.normal(0, 1.0, size=N_HOURS)
            + deg * 15
        )

        # ---- voltages (kV, nominal 10 kV) ----
        v_drift = 0.05 * np.sin(year_phase)
        v_a = 10.0 + v_drift + rng.normal(0, 0.08, size=N_HOURS)
        v_b = 10.0 + v_drift + rng.normal(0, 0.08, size=N_HOURS)
        v_c = 10.0 + v_drift + rng.normal(0, 0.08, size=N_HOURS)
        if idx in asym_idx:
            v_a += 0.15
            v_c -= 0.18

        # ---- currents (A) ----
        I_nom = 250.0
        scale_a = rng.uniform(0.95, 1.05)
        scale_b = rng.uniform(0.95, 1.05)
        scale_c = rng.uniform(0.95, 1.05)
        I_a = (load / 100) * I_nom * scale_a + rng.normal(0, 4, size=N_HOURS)
        I_b = (load / 100) * I_nom * scale_b + rng.normal(0, 4, size=N_HOURS)
        I_c = (load / 100) * I_nom * scale_c + rng.normal(0, 4, size=N_HOURS)
        if idx in asym_idx:
            I_a *= 1.08
            I_c *= 0.92

        # ---- DGA gases (ppm) ----
        h2_base = rng.uniform(8, 25)
        ch4_base = rng.uniform(5, 15)
        c2h2_base = rng.uniform(1, 6)
        gas_h2 = h2_base + np.abs(rng.normal(0, 3, size=N_HOURS)) + deg * 220
        gas_ch4 = ch4_base + np.abs(rng.normal(0, 2, size=N_HOURS)) + deg * 90
        gas_c2h2 = c2h2_base + np.abs(rng.normal(0, 0.8, size=N_HOURS)) + deg * 60

        # ---- vibration (mm/s) — 3 correlated axes ----
        vib_base = rng.uniform(1.5, 3.0)
        common = rng.normal(0, 0.3, size=N_HOURS) + deg * 5
        vib_x = np.clip(vib_base + common + rng.normal(0, 0.2, size=N_HOURS), 0.3, 15)
        vib_y = np.clip(vib_base + common + rng.normal(0, 0.2, size=N_HOURS), 0.3, 15)
        vib_z = np.clip(vib_base + common + rng.normal(0, 0.2, size=N_HOURS), 0.3, 15)

        df = pd.DataFrame({
            "timestamp": timestamps,
            "equipment_id": uid,
            "temperature_top": np.round(temp_top, 2).astype(np.float32),
            "temperature_oil": np.round(temp_oil, 2).astype(np.float32),
            "voltage_phase_a": np.round(v_a, 3).astype(np.float32),
            "voltage_phase_b": np.round(v_b, 3).astype(np.float32),
            "voltage_phase_c": np.round(v_c, 3).astype(np.float32),
            "current_phase_a": np.round(I_a, 2).astype(np.float32),
            "current_phase_b": np.round(I_b, 2).astype(np.float32),
            "current_phase_c": np.round(I_c, 2).astype(np.float32),
            "gas_h2": np.round(gas_h2, 2).astype(np.float32),
            "gas_ch4": np.round(gas_ch4, 2).astype(np.float32),
            "gas_c2h2": np.round(gas_c2h2, 2).astype(np.float32),
            "vibration_x": np.round(vib_x, 3).astype(np.float32),
            "vibration_y": np.round(vib_y, 3).astype(np.float32),
            "vibration_z": np.round(vib_z, 3).astype(np.float32),
            "humidity": np.round(humidity, 2).astype(np.float32),
            "load_percentage": np.round(load, 2).astype(np.float32),
        })
        frames.append(df)

    full = pd.concat(frames, ignore_index=True)
    full.attrs["degraded_units"] = sorted(unit_ids[i] for i in degraded_idx)
    full.attrs["asymmetric_units"] = sorted(unit_ids[i] for i in asym_idx)
    full.attrs["degradation_schedule"] = {
        unit_ids[i]: {
            "onset_t_norm": round(float(onset_t[i]), 3),
            "full_deg_t_norm": round(float(full_deg_t[i]), 3),
        }
        for i in degraded_idx
    }
    return full


def _percentile_stats(series: pd.Series) -> dict:
    return {
        "mean": float(series.mean()),
        "std": float(series.std()),
        "min": float(series.min()),
        "p05": float(series.quantile(0.05)),
        "p50": float(series.quantile(0.50)),
        "p95": float(series.quantile(0.95)),
        "p99": float(series.quantile(0.99)),
        "max": float(series.max()),
    }


def build_summary(df: pd.DataFrame) -> dict:
    deg_units = df.attrs.get("degraded_units", [])
    asym_units = df.attrs.get("asymmetric_units", [])

    # snapshot of the final 30 days to make degradation visible in the summary
    last_30d = df[df["timestamp"] >= df["timestamp"].max() - pd.Timedelta(days=30)]
    deg_last_30 = last_30d[last_30d["equipment_id"].isin(deg_units)]
    healthy_last_30 = last_30d[~last_30d["equipment_id"].isin(deg_units)]

    summary = {
        "random_seed": SEED,
        "n_substations": N_SUBSTATIONS,
        "n_transformers_per_substation": N_TRANSFORMERS_PER_SUB,
        "n_units": N_UNITS,
        "n_hours_per_unit": N_HOURS,
        "total_records": int(len(df)),
        "n_columns": int(df.shape[1]),
        "period": {
            "start": df["timestamp"].min().isoformat(),
            "end": df["timestamp"].max().isoformat(),
        },
        "degradation": {
            "fraction": DEGRADATION_FRACTION,
            "n_degraded_units": len(deg_units),
            "units": deg_units,
            "schedule": df.attrs.get("degradation_schedule", {}),
        },
        "asymmetry": {
            "fraction": ASYMMETRY_FRACTION,
            "n_units": len(asym_units),
            "units": asym_units,
        },
        "parameter_stats_global": {
            col: _percentile_stats(df[col]) for col in NUMERIC_COLS
        },
        "parameter_stats_last_30d_healthy_vs_degraded": {
            col: {
                "healthy": _percentile_stats(healthy_last_30[col]),
                "degraded": _percentile_stats(deg_last_30[col]) if len(deg_last_30) else None,
            }
            for col in ["temperature_top", "temperature_oil", "gas_c2h2",
                        "vibration_x", "vibration_y", "vibration_z"]
        },
        "sample_rows_first_5": (
            df.head(5)
              .assign(timestamp=lambda x: x["timestamp"].astype(str))
              .to_dict(orient="records")
        ),
        "output_files": {
            "telemetry_parquet": str(OUT_PARQUET.relative_to(ROOT)).replace("\\", "/"),
            "data_summary_json": str(OUT_SUMMARY.relative_to(ROOT)).replace("\\", "/"),
        },
    }
    return summary


def main():
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(SEED)
    print(f"[generate_data] seed={SEED}, units={N_UNITS}, hours/unit={N_HOURS}")

    df = generate(rng)
    print(f"[generate_data] generated dataframe: rows={len(df):,}, cols={df.shape[1]}")

    df.to_parquet(OUT_PARQUET, index=False, compression="snappy")
    size_mb = OUT_PARQUET.stat().st_size / 1024 / 1024
    print(f"[generate_data] wrote parquet -> {OUT_PARQUET} ({size_mb:.1f} MB)")

    summary = build_summary(df)
    with OUT_SUMMARY.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[generate_data] wrote summary -> {OUT_SUMMARY}")

    # Quick sanity print
    print("[generate_data] degraded units (",
          summary["degradation"]["n_degraded_units"], "):",
          ", ".join(summary["degradation"]["units"]))
    deg_temp = summary["parameter_stats_last_30d_healthy_vs_degraded"]["temperature_top"]
    print(f"[generate_data] last-30d temp_top p95: "
          f"healthy={deg_temp['healthy']['p95']:.1f} °C, "
          f"degraded={deg_temp['degraded']['p95'] if deg_temp['degraded'] else 'n/a'} °C")


if __name__ == "__main__":
    main()
