"""
Grid Guardian — Stage 5: economics.

Computes ROI / PP / NPV / IRR / DPP over a 5-year horizon for three avoidance
scenarios (45 / 65 / 80 %), a 3×3 sensitivity grid (discount rate × avoidance),
and a scaling estimate for the full Rosseti 35 kV+ network.

Every key input parameter records `source` (document + section) so the figures
can be cited verbatim in the thesis. Page numbers are left null where they
need to be filled in after reading the source PDFs in docs/.

Outputs
-------
    artifacts/economics.json   — full parameterisation and all derived numbers
    artifacts/cashflow.png     — 5-year cash flow (base scenario)
    artifacts/sensitivity.png  — NPV heatmap (rate × avoidance)
    artifacts/scaling.png      — annual savings range when scaled to network
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "artifacts" / "economics.json"
OUT_CASHFLOW = ROOT / "artifacts" / "cashflow.png"
OUT_SENS = ROOT / "artifacts" / "sensitivity.png"
OUT_SCALING = ROOT / "artifacts" / "scaling.png"

HORIZON_YEARS = 5
MILLION = 1_000_000.0  # 1 mln rub = financial unit used internally

# ---------- helpers: NPV / IRR / DPP ----------

def npv(cashflows: list[float], rate: float) -> float:
    """Cashflows[0] is investment at year 0 (negative), [1..N] are inflows."""
    return float(sum(cf / (1 + rate) ** t for t, cf in enumerate(cashflows)))


def irr(cashflows: list[float], lo: float = -0.99, hi: float = 10.0,
        tol: float = 1e-9, max_iter: int = 200) -> float | None:
    """Bisection IRR. Returns None if no sign change in [lo, hi]."""
    f_lo, f_hi = npv(cashflows, lo), npv(cashflows, hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        f_mid = npv(cashflows, mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


def simple_payback(invest: float, annual_net: float) -> float | None:
    """Years to break even at constant annual_net inflow. Linear interp."""
    if annual_net <= 0:
        return None
    return invest / annual_net


def discounted_payback(cashflows: list[float], rate: float) -> float | None:
    """Year (fractional) at which the cumulative discounted cashflow first turns
    non-negative. Returns None if it never does inside the horizon."""
    cum = 0.0
    for t, cf in enumerate(cashflows):
        pv = cf / (1 + rate) ** t
        prev = cum
        cum += pv
        if cum >= 0 and t > 0:
            # crossing between year t-1 (prev < 0) and year t (cum >= 0)
            needed = -prev
            return (t - 1) + needed / pv
    return None


def build_cashflows(invest: float, annual_savings: float, annual_opex: float,
                    years: int) -> list[float]:
    net = annual_savings - annual_opex
    return [-invest] + [net] * years


# ---------- parameters with sources ----------

PARAMS = {
    "discount_rate": {
        "base": 0.14,
        "sensitivity_set": [0.12, 0.14, 0.17],
        "rationale": (
            "13.71 % — actual discount rate of PAO Rosseti used in impairment "
            "testing per RSBU 2024 (nominal rate, WACC-based). "
            "14 % — rounded up for safety margin (base case). "
            "17.1 % — weighted-average rate over the ENTIRE debt portfolio at "
            "end of 2024 (annual report 2024 page 59). "
            "12 % — optimistic scenario assuming key-rate easing."
        ),
        "sources": [
            {"file": "references/86_Россети_Отчетность_РСБУ_2024.pdf",
             "page": 41, "value": 0.1371, "ref_in_thesis": "[45]",
             "exact_quote": "Ставка дисконтирования (Номинальная ставка дисконтирования, определенная для целей теста на основе средневзвешенной стоимости капитала) — 13,71 %"},
            {"file": "references/21_Россети_Годовой_отчет_2024.pdf",
             "page": 59, "value": 0.1710, "ref_in_thesis": "[11]",
             "exact_quote": "Средневзвешенная процентная ставка по долговому портфелю Группы составила 17,10 % годовых, увеличившись относительно начала года в 1,4 раза"},
        ],
    },

    "emergency_repair_cost_rub": {
        "value": 7_500_000,
        "source": {
            "doc": "Методика Жилкиной (вне references/)",
            "ref_in_thesis": "[28]", "page": None,
            "note": "Damage structure for grid-equipment failure — NOT in references/ folder; cited as in thesis",
        },
        "breakdown": {
            "capital_repair": {"low": 2_000_000, "high": 2_500_000,
                               "midpoint": 2_250_000},
            "emergency_parts_logistics": {"low": 1_000_000, "high": 1_500_000,
                                          "midpoint": 1_250_000},
            "overtime_and_callouts": {"low": 500_000, "high": 1_000_000,
                                      "midpoint": 750_000},
            "energy_undersupply_damage": {"low": 2_500_000, "high": 3_500_000,
                                          "midpoint": 3_000_000},
            "midpoint_total": 7_250_000,  # close to canonical 7.5M
        },
    },

    "planned_repair_cost_rub": {
        "value": 1_900_000,
        "note": ("Approximately the capital-repair component only — no rush "
                 "logistics, no energy-undersupply damage. ≈ 25 % of emergency."),
        "source": {
            "doc": "PoC estimate aligned with Жилкина methodology",
            "ref_in_thesis": "[28]",
        },
    },

    "base_failure_rate_per_year": {
        "value": 0.025,
        "note": ("2.5 %/year — PoC estimate for medium-wear transformers. "
                 "Marked for refinement against actual Rosseti incident "
                 "statistics during pilot rollout."),
        "source": {"doc": "PoC assumption (industry-typical for aging fleet)",
                   "ref": "—", "page": None},
        "refinement_status": "PARAMETER_TO_BE_REFINED_WITH_REAL_INCIDENT_DATA",
    },

    "avoidance_scenarios": {
        "pessimistic": 0.45,
        "base": 0.65,
        "optimistic": 0.80,
        "avoidance_rationale": (
            "Model recall_High on 72 h horizon = 0.9991, but real-world failure "
            "avoidance is materially lower than recall due to: "
            "(a) organisational factors — crew unavailable, spare parts not "
            "ready, ambiguous alerts disregarded; "
            "(b) external causes of failures that ML cannot influence (Rosseti "
            "Annual Report 2024 attributes the 2024 uptick in technological "
            "disturbances to external factors); "
            "(c) first-year process maturation. "
            "Discount factor recall → avoidance ≈ 0.65 for the base case."
        ),
        "source_for_external_factors": {
            "file": "references/21_Россети_Годовой_отчет_2024.pdf",
            "page": 35, "ref_in_thesis": "[11]",
            "note": ("Section 'Отраслевые риски' describes external factors "
                     "(weather, third-party damage, sub-station ageing beyond "
                     "warranty) that drive technological disturbances regardless "
                     "of monitoring quality."),
        },
    },

    "pilot_investment_rub": {
        "value": 8_000_000,
        "composition": [
            "ML pipeline (data generator → FE → training → inference)",
            "Integration with existing data sources (ССПИ / АСМД / Rosseti IT)",
            "Web dashboard development and deployment",
            "Personnel training and rollout support",
        ],
        "key_positioning": (
            "Grid Guardian is an analytical layer over the data-collection "
            "infrastructure that already exists in Rosseti (ССПИ, АСМД). "
            "No new sensors, no new communication channels, no heavy hardware "
            "are required — only software, integration and process change. "
            "This is what justifies the relatively modest pilot CAPEX."
        ),
        "sources": [
            {"doc": "ВКР Глава 2.3 (Grid Guardian as analytical layer)",
             "ref_in_thesis": "[11], [34], [44]",
             "note": "Existing data-collection infrastructure (ССПИ, АСМД, IT-инфраструктура)"},
            {"file": "references/24_Россети_Программа_инновационного_развития_2024-2029.pdf",
             "page": None, "ref_in_thesis": "[44]",
             "note": "Innovation programme — confirms direction towards digital diagnostics overlays"},
        ],
    },

    "opex_pct_of_investment_per_year": {
        "low": 0.10,
        "midpoint": 0.125,
        "high": 0.15,
        "note": ("OPEX covers: model monitoring, periodic retraining on new "
                 "telemetry, infrastructure support, software updates."),
    },

    "pilot_units": {
        "value": 50,
        "substations": 10,
        "source": {"doc": "Stage 1 generated dataset", "ref": "self"},
    },

    "scaling_assumptions": {
        "substations_total_rosseti": {
            "value": 593_000,
            "source": {
                "file": "references/21_Россети_Годовой_отчет_2024.pdf",
                "page": 10, "ref_in_thesis": "[11]",
                "exact_quote": "Количество подстанций 593 тыс. шт.",
                "note": "Total substations across all voltage classes (mostly 0.4 kV distribution КТП)",
            },
        },
        "substations_with_digital_control_anchor": {
            "value": 40_100,
            "source": {
                "file": "references/21_Россети_Годовой_отчет_2024.pdf",
                "page": 10, "ref_in_thesis": "[11]",
                "exact_quote": "40,1 тыс. шт. — Подстанции с цифровым управлением",
                "note": (
                    "Used as the best PUBLISHED proxy for 35 kV+ substations: "
                    "digital control is deployed primarily at higher-voltage "
                    "nodes where oil transformers (DGA-relevant for Grid Guardian) "
                    "live. The annual report does not give a direct voltage-class "
                    "breakdown in open form."
                ),
            },
        },
        "n_substations_in_scope_range": {
            "low": 20_000,
            "midpoint": 40_100,
            "high": 60_000,
            "rationale": (
                "Anchored on 40,100 digitally-controlled substations from AR-2024 p. 10. "
                "Low (20 000): only the subset most ready for ML overlay. "
                "Midpoint (40 100): equals the digital-control fleet 1:1. "
                "High (60 000): ambitious rollout, includes substations being "
                "digitised in 2025-2030 per Rosseti TsT-2030."
            ),
        },
        "avg_transformers_per_substation": {
            "value": 3,
            "note": "Conservative average for 35 kV+ nodes; large 220-500 kV substations have more.",
        },
    },

    "rosseti_targets_for_reference": {
        "target_payback_years_digital_projects": {
            "low": 5, "high": 10,
            "source": {
                "file": "references/20_Россети_Концепция_Цифровая_трансформация_2030_2018.pdf",
                "page": 15, "ref_in_thesis": "[34]",
                "exact_quote": "сроки окупаемости различных цифровых технологий составляют от 5 до 10 лет",
            },
        },
        "opex_reduction_target_pct": 0.30,
        "capex_reduction_target_pct": 0.15,
        "source": {
            "file": "references/20_Россети_Концепция_Цифровая_трансформация_2030_2018.pdf",
            "page": None, "ref_in_thesis": "[34]",
            "note": "OPEX -30% / CAPEX -15% targets stated in ЦТ-2030 strategic goals",
        },
    },
}


# ---------- core computation ----------

def per_unit_economics(avoidance: float) -> dict:
    """Annual expected savings per single transformer at given avoidance rate."""
    failure_rate = PARAMS["base_failure_rate_per_year"]["value"]
    emergency = PARAMS["emergency_repair_cost_rub"]["value"]
    planned = PARAMS["planned_repair_cost_rub"]["value"]
    saving_per_avoidance = emergency - planned
    failures_per_year = failure_rate
    failures_avoided = failures_per_year * avoidance
    annual_saving_per_unit = failures_avoided * saving_per_avoidance
    return {
        "saving_per_avoided_failure": saving_per_avoidance,
        "expected_failures_per_year_per_unit": failures_per_year,
        "failures_avoided_per_year_per_unit": failures_avoided,
        "annual_saving_per_unit": annual_saving_per_unit,
    }


def pilot_scenario(avoidance: float, discount_rate: float,
                   opex_pct: float = 0.125) -> dict:
    invest = PARAMS["pilot_investment_rub"]["value"]
    n_units = PARAMS["pilot_units"]["value"]
    pue = per_unit_economics(avoidance)
    annual_savings_total = pue["annual_saving_per_unit"] * n_units
    annual_opex = invest * opex_pct
    net_annual = annual_savings_total - annual_opex

    cfs = build_cashflows(invest, annual_savings_total, annual_opex, HORIZON_YEARS)
    pv_each_year = [cf / (1 + discount_rate) ** t for t, cf in enumerate(cfs)]
    cumulative_pv = list(np.cumsum(pv_each_year))

    return {
        "inputs": {
            "avoidance": avoidance,
            "discount_rate": discount_rate,
            "opex_pct_of_investment": opex_pct,
            "investment_rub": invest,
            "n_units": n_units,
        },
        "per_unit": pue,
        "annual_savings_total_rub": annual_savings_total,
        "annual_opex_rub": annual_opex,
        "annual_net_cashflow_rub": net_annual,
        "cashflows_by_year_rub": cfs,
        "pv_by_year_rub": pv_each_year,
        "cumulative_pv_rub": cumulative_pv,
        "roi_simple": (net_annual * HORIZON_YEARS - invest) / invest if invest else None,
        "pp_simple_years": simple_payback(invest, net_annual),
        "npv_rub": npv(cfs, discount_rate),
        "irr": irr(cfs),
        "dpp_years": discounted_payback(cfs, discount_rate),
    }


def sensitivity_grid() -> dict:
    rates = PARAMS["discount_rate"]["sensitivity_set"]
    avoidances = [
        PARAMS["avoidance_scenarios"]["pessimistic"],
        PARAMS["avoidance_scenarios"]["base"],
        PARAMS["avoidance_scenarios"]["optimistic"],
    ]
    grid_npv = []
    grid_irr = []
    for av in avoidances:
        npv_row, irr_row = [], []
        for r in rates:
            s = pilot_scenario(av, r)
            npv_row.append(s["npv_rub"])
            irr_row.append(s["irr"])
        grid_npv.append(npv_row)
        grid_irr.append(irr_row)
    return {
        "rates": rates,
        "avoidances": avoidances,
        "npv_grid_rub": grid_npv,
        "irr_grid": grid_irr,
        "row_labels_avoidance": [f"{int(a*100)}%" for a in avoidances],
        "col_labels_rate": [f"{int(r*100)}%" for r in rates],
    }


def scaling_estimate() -> dict:
    sa = PARAMS["scaling_assumptions"]
    rng = sa["n_substations_in_scope_range"]
    avg_tx = sa["avg_transformers_per_substation"]["value"]

    avoidance_base = PARAMS["avoidance_scenarios"]["base"]
    pue = per_unit_economics(avoidance_base)
    saving_per_unit = pue["annual_saving_per_unit"]

    def saving_for(n_subs):
        n_units = n_subs * avg_tx
        return n_subs, n_units, n_units * saving_per_unit

    low_subs, low_units, low_save = saving_for(rng["low"])
    mid_subs, mid_units, mid_save = saving_for(rng["midpoint"])
    high_subs, high_units, high_save = saving_for(rng["high"])

    # Scaled NPV approx: CAPEX scales linearly with units relative to pilot.
    pilot_units = PARAMS["pilot_units"]["value"]
    pilot_invest = PARAMS["pilot_investment_rub"]["value"]
    # In practice scaling has economies of scale — invest grows sublinearly.
    # Use a sublinear scaling: invest_scaled = pilot_invest * (n_units / pilot_units) ** 0.7
    def scaled_npv(n_units_, annual_save_, rate_=0.14):
        scaled_invest = pilot_invest * (n_units_ / pilot_units) ** 0.70
        opex_pct = PARAMS["opex_pct_of_investment_per_year"]["midpoint"]
        cfs = build_cashflows(scaled_invest, annual_save_,
                              scaled_invest * opex_pct, HORIZON_YEARS)
        return scaled_invest, npv(cfs, rate_), irr(cfs)

    inv_low, npv_low, irr_low = scaled_npv(low_units, low_save)
    inv_mid, npv_mid, irr_mid = scaled_npv(mid_units, mid_save)
    inv_high, npv_high, irr_high = scaled_npv(high_units, high_save)

    return {
        "method": (
            "Linear scaling of saving (per-unit × n_units), sublinear scaling "
            "of CAPEX with exponent 0.70 — accounts for economies of scale on "
            "rollout. OPEX at midpoint 12.5 % of scaled CAPEX, discount 14 %."
        ),
        "annual_saving_low_rub": low_save,
        "annual_saving_midpoint_rub": mid_save,
        "annual_saving_high_rub": high_save,
        "n_substations_in_scope": {
            "low": low_subs, "midpoint": mid_subs, "high": high_subs,
        },
        "n_transformers_in_scope": {
            "low": low_units, "midpoint": mid_units, "high": high_units,
        },
        "scaled_investment_rub": {
            "low": inv_low, "midpoint": inv_mid, "high": inv_high,
        },
        "scaled_npv_5y_rub": {
            "low": npv_low, "midpoint": npv_mid, "high": npv_high,
        },
        "scaled_irr": {
            "low": irr_low, "midpoint": irr_mid, "high": irr_high,
        },
    }


# ---------- plots ----------

def plot_cashflow(base: dict, path: Path):
    cfs = base["cashflows_by_year_rub"]
    cum_undisc = np.cumsum(cfs) / MILLION
    cum_pv = np.array(base["cumulative_pv_rub"]) / MILLION
    years = list(range(len(cfs)))
    cf_mln = [c / MILLION for c in cfs]

    fig, ax = plt.subplots(figsize=(10, 5.5))
    colours = ["#d62728" if c < 0 else "#2ca02c" for c in cfs]
    bars = ax.bar(years, cf_mln, color=colours, alpha=0.85,
                  label="Annual cashflow (mln rub)")
    ax.axhline(0, color="black", lw=0.7)
    for i, c in enumerate(cf_mln):
        ax.text(i, c + (0.3 if c >= 0 else -0.6), f"{c:+.2f}",
                ha="center", fontsize=9,
                color="darkgreen" if c >= 0 else "darkred")

    ax2 = ax.twinx()
    ax2.plot(years, cum_undisc, "o-", color="#1f77b4", lw=2,
             label="Cumulative (undiscounted)")
    ax2.plot(years, cum_pv, "s--", color="#9467bd", lw=2,
             label="Cumulative (PV @ 14 %)")
    ax2.axhline(0, color="gray", lw=0.5, alpha=0.5)

    ax.set_xlabel("Year")
    ax.set_ylabel("Annual cashflow (mln rub)")
    ax2.set_ylabel("Cumulative cashflow (mln rub)")
    ax.set_xticks(years)
    ax.set_title("Grid Guardian — pilot cashflow, base scenario (avoidance 65 %)")
    ax.grid(axis="y", alpha=0.3)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="lower right")

    plt.tight_layout()
    plt.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_sensitivity(grid: dict, path: Path):
    npv_arr = np.array(grid["npv_grid_rub"]) / MILLION  # rows: avoidance, cols: rate
    rows = grid["row_labels_avoidance"]
    cols = grid["col_labels_rate"]

    fig, ax = plt.subplots(figsize=(7.5, 5))
    im = ax.imshow(npv_arr, cmap="RdYlGn",
                   vmin=npv_arr.min(), vmax=npv_arr.max(), aspect="auto")
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(rows)))
    ax.set_xticklabels(cols)
    ax.set_yticklabels(rows)
    ax.set_xlabel("Discount rate")
    ax.set_ylabel("Failure-avoidance after deployment")

    for i in range(npv_arr.shape[0]):
        for j in range(npv_arr.shape[1]):
            val = npv_arr[i, j]
            color = "white" if abs(val) > 0.5 * abs(npv_arr).max() else "black"
            ax.text(j, i, f"{val:.2f}\nmln rub", ha="center", va="center",
                    color=color, fontsize=11, fontweight="bold")

    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="NPV, mln rub")
    ax.set_title("Grid Guardian — pilot 5-year NPV sensitivity\n"
                 "(rate × failure-avoidance)")
    plt.tight_layout()
    plt.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_scaling(sc: dict, path: Path):
    n_low = sc["n_substations_in_scope"]["low"]
    n_mid = sc["n_substations_in_scope"]["midpoint"]
    n_high = sc["n_substations_in_scope"]["high"]
    labels = [
        f"Low\n({n_low/1000:.0f}k subs)",
        f"Midpoint\n({n_mid/1000:.1f}k subs)\nAR-2024 p.10 anchor",
        f"High\n({n_high/1000:.0f}k subs)",
    ]
    save_mln = np.array([sc["annual_saving_low_rub"],
                         sc["annual_saving_midpoint_rub"],
                         sc["annual_saving_high_rub"]]) / MILLION
    npv_mln = np.array([sc["scaled_npv_5y_rub"]["low"],
                        sc["scaled_npv_5y_rub"]["midpoint"],
                        sc["scaled_npv_5y_rub"]["high"]]) / MILLION

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    ax = axes[0]
    bars = ax.bar(labels, save_mln, color="#2ca02c", alpha=0.85)
    for b, v in zip(bars, save_mln):
        ax.text(b.get_x() + b.get_width()/2, v, f"{v:,.0f}\nmln rub",
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("Annual savings, mln rub")
    ax.set_title("Annual savings range — 35 kV+ network scope")
    ax.grid(axis="y", alpha=0.3)

    ax = axes[1]
    bars = ax.bar(labels, npv_mln, color="#1f77b4", alpha=0.85)
    for b, v in zip(bars, npv_mln):
        ax.text(b.get_x() + b.get_width()/2, v, f"{v:,.0f}\nmln rub",
                ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylabel("5-year NPV @ 14 %, mln rub")
    ax.set_title("5-year scaled NPV (sublinear CAPEX, 0.7)")
    ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Grid Guardian — scaling to 35 kV+ network "
                 "(avoidance 65 %, base scenario)", fontsize=12)
    plt.tight_layout()
    plt.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


# ---------- main ----------

def main():
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    pessimistic = pilot_scenario(
        PARAMS["avoidance_scenarios"]["pessimistic"], PARAMS["discount_rate"]["base"])
    base = pilot_scenario(
        PARAMS["avoidance_scenarios"]["base"], PARAMS["discount_rate"]["base"])
    optimistic = pilot_scenario(
        PARAMS["avoidance_scenarios"]["optimistic"], PARAMS["discount_rate"]["base"])

    grid = sensitivity_grid()
    scaling = scaling_estimate()

    # ---- compare base PP/DPP against Rosseti target 5-10 years
    target = PARAMS["rosseti_targets_for_reference"]["target_payback_years_digital_projects"]
    base_pp = base["pp_simple_years"]
    base_dpp = base["dpp_years"]
    pp_vs_target = {
        "pilot_pp_years": base_pp,
        "pilot_dpp_years": base_dpp,
        "target_low_years": target["low"],
        "target_high_years": target["high"],
        "verdict": (
            "pilot PP and DPP are MATERIALLY BELOW the 5-10-year target band "
            f"({base_pp:.2f} y / {base_dpp:.2f} y vs {target['low']}-{target['high']} y) "
            "— strong argument that Grid Guardian outperforms the corporate "
            "expectation for digital-project payback."
            if base_pp is not None and base_pp < target["low"]
            else "pilot PP is within or above target band — review parameters."
        ),
    }

    out = {
        "horizon_years": HORIZON_YEARS,
        "params": PARAMS,
        "pilot_scenarios": {
            "pessimistic_avoidance_45pct": pessimistic,
            "base_avoidance_65pct": base,
            "optimistic_avoidance_80pct": optimistic,
        },
        "sensitivity_grid_3x3": grid,
        "scaling_estimate_35kv_plus": scaling,
        "payback_vs_rosseti_target": pp_vs_target,
        "emergency_repair_breakdown": PARAMS["emergency_repair_cost_rub"]["breakdown"],
        "key_positioning": PARAMS["pilot_investment_rub"]["key_positioning"],
        "avoidance_rationale": PARAMS["avoidance_scenarios"]["avoidance_rationale"],
        "parameters_to_refine_with_real_data": [
            "base_failure_rate_per_year (currently 2.5%/y PoC estimate)",
            "substations_35kV_and_above_share (currently 1.2-3.0% expert range)",
            "discount rate page references in source PDFs",
        ],
        "notes_on_sources": (
            "Sources were read directly from references/ folder. Page numbers and "
            "exact_quote fields verified against actual PDFs:\n"
            "  - 13.71 % discount rate: RSBU 2024 p. 41 (verified)\n"
            "  - 17.10 % WACD-portfolio: Annual Report 2024 p. 59 (verified — "
            "note: this is the portfolio-wide weighted average rate at year-end, "
            "NOT specifically 'new debt' as paraphrased in the brief)\n"
            "  - 593 k total substations, 40.1 k digitally-controlled: AR 2024 p. 10 (verified)\n"
            "  - 5-10 year digital-project payback: ЦТ-2030 p. 15 (verified)\n"
            "  - External-factor disturbances: AR 2024 p. 35 (verified)\n"
            "Жилкина methodology is NOT in references/; cited as in the thesis bibliography."
        ),
    }
    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=float)
    print(f"[economics] wrote {OUT_JSON}")

    plot_cashflow(base, OUT_CASHFLOW)
    print(f"[economics] wrote {OUT_CASHFLOW}")
    plot_sensitivity(grid, OUT_SENS)
    print(f"[economics] wrote {OUT_SENS}")
    plot_scaling(scaling, OUT_SCALING)
    print(f"[economics] wrote {OUT_SCALING}")

    # ---- console summary ----
    print()
    print("=" * 78)
    print("BASE SCENARIO (avoidance 65%, discount 14%, OPEX 12.5%)")
    print("=" * 78)
    print(f"  Annual savings (50 units):  {base['annual_savings_total_rub']/MILLION:>8.3f} mln rub")
    print(f"  Annual OPEX:                {base['annual_opex_rub']/MILLION:>8.3f} mln rub")
    print(f"  Annual net cashflow:        {base['annual_net_cashflow_rub']/MILLION:>8.3f} mln rub")
    print(f"  Investment (year 0):        {PARAMS['pilot_investment_rub']['value']/MILLION:>8.3f} mln rub")
    print()
    print(f"  ROI (5 y, simple):          {base['roi_simple']*100:>8.2f} %")
    print(f"  Payback (simple):           {base['pp_simple_years']:>8.2f} years")
    print(f"  NPV (5 y @ 14%):            {base['npv_rub']/MILLION:>8.3f} mln rub")
    print(f"  IRR:                        {base['irr']*100:>8.2f} %")
    print(f"  DPP (5 y @ 14%):            {base['dpp_years']:>8.2f} years")

    print()
    print("=" * 78)
    print("SENSITIVITY GRID — NPV in mln rub (rows: avoidance, cols: rate)")
    print("=" * 78)
    print(f"  {'':>15s}  " + "  ".join(f"{c:>10s}" for c in grid["col_labels_rate"]))
    for ri, av_label in enumerate(grid["row_labels_avoidance"]):
        row = "  ".join(f"{v/MILLION:>10.3f}" for v in grid["npv_grid_rub"][ri])
        print(f"  avoidance {av_label:>4s}: {row}")

    print()
    print("=" * 78)
    print("SCALING — annual savings if rolled out to 35 kV+ network")
    print("=" * 78)
    for level in ["low", "midpoint", "high"]:
        save = scaling[f"annual_saving_{level}_rub"]
        n_sub = scaling["n_substations_in_scope"][level]
        n_tx = scaling["n_transformers_in_scope"][level]
        inv = scaling["scaled_investment_rub"][level]
        npv_ = scaling["scaled_npv_5y_rub"][level]
        print(f"  {level:>9s}: {n_sub:>7,.0f} subs x {n_tx:>9,.0f} tx -> "
              f"save {save/MILLION:>8,.0f} mln rub/y, invest {inv/MILLION:>6.0f}, "
              f"5y NPV {npv_/MILLION:>9,.0f} mln rub")

    print()
    print("=" * 78)
    print("vs Rosseti ЦТ-2030 target payback band 5-10 years:")
    print("=" * 78)
    print(f"  pilot PP  = {base_pp:.2f} y   (target band: 5-10 y)")
    print(f"  pilot DPP = {base_dpp:.2f} y   (target band: 5-10 y)")
    print(f"  verdict: {'WELL BELOW target — STRONG' if base_pp < target['low'] else 'within/above target'}")


if __name__ == "__main__":
    main()
