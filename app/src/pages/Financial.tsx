import { useMemo, useState } from "react";
import { useData } from "../lib/useData";
import NotificationsBell from "../components/NotificationsBell";

interface FinData {
  inputs: {
    n_units: number;
    investment_mln: number;
    discount_rate: number;
    avoidance: number;
    base_failure_rate: number;
    emergency_repair_mln: number;
    planned_repair_mln: number;
    opex_pct: number;
    horizon_years: number;
  };
  inputs_min_max: Record<string, { min: number; max: number; step: number }>;
  kpi_at_base: {
    roi_pct: number; pp_years: number; npv_mln: number;
    irr_pct: number; dpp_years: number;
    annual_savings_mln: number; annual_opex_mln: number;
  };
  sensitivity_3x3: {
    rates: number[]; avoidances: number[]; npv_mln: number[][];
  };
  scaling_35kv_plus: {
    n_substations_in_scope: { low: number; midpoint: number; high: number };
    annual_saving_mln: { low: number; midpoint: number; high: number };
    scaled_npv_mln: { low: number; midpoint: number; high: number };
  };
  target_payback_band_years: { low: number; high: number; source: string };
}

// Identical formula to economics.py — kept client-side so sliders recompute live.
function compute(p: FinData["inputs"]) {
  const savePerAvoidance = p.emergency_repair_mln - p.planned_repair_mln;
  const failuresPerUnit = p.base_failure_rate * p.avoidance;
  const annualSavings = failuresPerUnit * savePerAvoidance * p.n_units;
  const annualOpex = p.investment_mln * p.opex_pct;
  const net = annualSavings - annualOpex;
  const cfs: number[] = [-p.investment_mln];
  for (let t = 0; t < p.horizon_years; t++) cfs.push(net);

  const npv = (r: number) =>
    cfs.reduce((acc, c, t) => acc + c / Math.pow(1 + r, t), 0);

  const npvVal = npv(p.discount_rate);

  // Bisection IRR
  let lo = -0.99, hi = 10;
  for (let i = 0; i < 80; i++) {
    const mid = (lo + hi) / 2;
    const fm = npv(mid);
    if (Math.abs(fm) < 1e-9) { lo = hi = mid; break; }
    if (npv(lo) * fm < 0) hi = mid; else lo = mid;
  }
  const irr = (lo + hi) / 2;

  const pp = net > 0 ? p.investment_mln / net : null;

  let cum = 0; let dpp: number | null = null;
  for (let t = 0; t < cfs.length; t++) {
    const pv = cfs[t] / Math.pow(1 + p.discount_rate, t);
    const prev = cum;
    cum += pv;
    if (cum >= 0 && t > 0 && dpp == null) {
      dpp = (t - 1) + (-prev) / pv;
    }
  }

  const roi = (net * p.horizon_years - p.investment_mln) / p.investment_mln;
  return { annualSavings, annualOpex, net, cfs, npv: npvVal, irr, pp, dpp, roi };
}

function npvColor(v: number, scale: { min: number; max: number }): string {
  if (v < 0) {
    const t = Math.min(1, Math.abs(v) / Math.max(1, Math.abs(scale.min)));
    const l = 60 + (1 - t) * 20;
    return `oklch(${l}% 0.20 25)`;
  }
  const t = Math.min(1, v / Math.max(1, scale.max));
  const l = 80 - t * 15;
  return `oklch(${l}% 0.15 155)`;
}

export default function Financial() {
  const { data } = useData<FinData>("financial.json");
  const [p, setP] = useState<FinData["inputs"] | null>(null);

  const inputs = p ?? data?.inputs ?? null;
  const result = useMemo(() => (inputs ? compute(inputs) : null), [inputs]);

  if (!data || !inputs || !result) return <div style={{ color: "var(--fg-3)" }}>Загрузка…</div>;

  const mm = data.inputs_min_max;
  const updateP = (k: keyof FinData["inputs"], v: number) =>
    setP((prev) => ({ ...(prev ?? data.inputs), [k]: v }));

  // Sensitivity grid color scale
  const flat = data.sensitivity_3x3.npv_mln.flat();
  const scale = { min: Math.min(...flat), max: Math.max(...flat) };

  return (
    <>
      <div className="topbar">
        <div className="topbar-title">
          <div className="page-eyebrow">Экономика проекта · пилот 50 единиц</div>
          <h1 className="page-title">Финансовая модель</h1>
          <div className="page-sub">
            Все параметры активны — двигайте ползунки, KPI и сетка чувствительности пересчитываются на лету
          </div>
        </div>
        <div className="topbar-actions">
          <NotificationsBell />
          <button className="btn-primary">
            <svg style={{ width: 14, height: 14 }}><use href="#i-export" /></svg>
            Экспорт обоснования
          </button>
        </div>
      </div>

      <section className="fin-grid">
        <div className="fin-card">
          <div className="label">ROI · {inputs.horizon_years} лет</div>
          <div className="value">{result.roi.toFixed(0)}<span className="unit">%</span></div>
          <div className="footnote">накопленная отдача от инвестиций</div>
        </div>
        <div className="fin-card">
          <div className="label">NPV · {(inputs.discount_rate * 100).toFixed(1)}%</div>
          <div className="value" style={{ color: result.npv >= 0 ? "var(--ok)" : "var(--crit)" }}>
            {result.npv >= 0 ? "+" : ""}{result.npv.toFixed(2)}<span className="unit"> млн ₽</span>
          </div>
          <div className="footnote">чистый дисконтированный поток</div>
        </div>
        <div className="fin-card">
          <div className="label">IRR</div>
          <div className="value">{(result.irr * 100).toFixed(1)}<span className="unit">%</span></div>
          <div className="footnote">внутренняя норма доходности</div>
        </div>
        <div className="fin-card">
          <div className="label">PP / DPP</div>
          <div className="value">
            {result.pp != null ? result.pp.toFixed(2) : "—"}
            <span className="unit"> / {result.dpp != null ? result.dpp.toFixed(2) : "—"} г</span>
          </div>
          <div className="footnote">
            цель ЦТ-2030: <b>{data.target_payback_band_years.low}–{data.target_payback_band_years.high} лет</b>
          </div>
        </div>
      </section>

      <div className="content-grid" style={{ gridTemplateColumns: "1fr 1.1fr" }}>
        {/* Sliders */}
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Параметры модели</div>
              <div className="card-sub">передвиньте ползунки для проверки сценариев</div>
            </div>
            <button className="btn-ghost" onClick={() => setP(data.inputs)}>
              <svg style={{ width: 14, height: 14 }}><use href="#i-refresh" /></svg>
              Сбросить
            </button>
          </div>

          <div className="slider-row">
            <span className="name">Снижение аварийности (avoidance)</span>
            <span className="val">{(inputs.avoidance * 100).toFixed(0)} %</span>
            <input
              type="range"
              min={mm.avoidance.min}
              max={mm.avoidance.max}
              step={mm.avoidance.step}
              value={inputs.avoidance}
              onChange={(e) => updateP("avoidance", Number(e.target.value))}
            />
          </div>
          <div className="slider-row">
            <span className="name">Ставка дисконтирования</span>
            <span className="val">{(inputs.discount_rate * 100).toFixed(2)} %</span>
            <input
              type="range"
              min={mm.discount_rate.min}
              max={mm.discount_rate.max}
              step={mm.discount_rate.step}
              value={inputs.discount_rate}
              onChange={(e) => updateP("discount_rate", Number(e.target.value))}
            />
          </div>
          <div className="slider-row">
            <span className="name">Базовая аварийность парка</span>
            <span className="val">{(inputs.base_failure_rate * 100).toFixed(2)} %/год</span>
            <input
              type="range"
              min={mm.base_failure_rate.min}
              max={mm.base_failure_rate.max}
              step={mm.base_failure_rate.step}
              value={inputs.base_failure_rate}
              onChange={(e) => updateP("base_failure_rate", Number(e.target.value))}
            />
          </div>

          <div style={{
            marginTop: 18, padding: 12, background: "var(--bg-2)",
            border: "1px solid var(--border)", borderRadius: 10, fontSize: 12.5, color: "var(--fg-2)", lineHeight: 1.55,
          }}>
            <div>Год. экономия: <b className="mono" style={{ color: "var(--fg-0)" }}>{result.annualSavings.toFixed(2)} млн ₽</b></div>
            <div>Год. OPEX: <b className="mono" style={{ color: "var(--fg-0)" }}>{result.annualOpex.toFixed(2)} млн ₽</b></div>
            <div>Чистый поток: <b className="mono" style={{ color: result.net > 0 ? "var(--ok)" : "var(--crit)" }}>{result.net.toFixed(2)} млн ₽/год</b></div>
          </div>
        </div>

        {/* Sensitivity heatmap */}
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Чувствительность NPV</div>
              <div className="card-sub">ставка дисконтирования × снижение аварийности</div>
            </div>
          </div>
          <table className="heatmap">
            <thead>
              <tr>
                <th></th>
                {data.sensitivity_3x3.rates.map((r) => (
                  <th key={r}>{(r * 100).toFixed(0)}%</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.sensitivity_3x3.avoidances.map((av, i) => (
                <tr key={av}>
                  <th>{(av * 100).toFixed(0)}%</th>
                  {data.sensitivity_3x3.npv_mln[i].map((v, j) => (
                    <td key={j} style={{ background: npvColor(v, scale) + "33" }}>
                      <b>{v >= 0 ? "+" : ""}{v.toFixed(2)}</b>
                      <span className="lbl">млн ₽</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ fontSize: 11.5, color: "var(--fg-3)", marginTop: 10, lineHeight: 1.55 }}>
            При <b>45 % avoidance</b> NPV становится отрицательным — нижняя граница, при которой пилот ещё имеет смысл.
            Базовый сценарий 65 % обеспечивает прочный запас.
          </div>
        </div>
      </div>

      {/* Cashflow visualisation */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <div>
            <div className="card-title">Денежный поток · {inputs.horizon_years} лет</div>
            <div className="card-sub">накопленный поток с дисконтированием при {(inputs.discount_rate * 100).toFixed(1)} %</div>
          </div>
        </div>
        {result.cfs.map((cf, year) => {
          const maxAbs = Math.max(...result.cfs.map(Math.abs));
          const pct = (Math.abs(cf) / maxAbs) * 100;
          return (
            <div key={year} className="cf-row">
              <div className="cf-year">{year === 0 ? "Год 0" : `Год ${year}`}</div>
              <div className="cf-track">
                {cf > 0 && <div className="cf-bar pos" style={{ width: `${pct / 2}%` }} />}
                {cf < 0 && <div className="cf-bar neg" style={{ width: `${pct / 2}%` }} />}
                <div className="cf-bar zero" />
              </div>
              <div className={`cf-val ${cf >= 0 ? "pos" : "neg"}`}>
                {cf >= 0 ? "+" : ""}{cf.toFixed(2)} млн
              </div>
            </div>
          );
        })}
      </div>

      {/* Scaling */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <div>
            <div className="card-title">Масштабирование на сеть 35 кВ+</div>
            <div className="card-sub">якорь — 40,1 тыс. подстанций с цифровым управлением, AR-2024 стр. 10</div>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
          {(["low", "midpoint", "high"] as const).map((tier) => (
            <div key={tier} style={{
              padding: 14, background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: 12,
            }}>
              <div style={{ fontSize: 11, color: "var(--fg-3)", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>
                {tier === "low" ? "Консерв." : tier === "midpoint" ? "База (40,1 тыс)" : "Амбициозно"}
              </div>
              <div style={{ fontFamily: "Space Grotesk, sans-serif", fontSize: 22, fontWeight: 600, color: "var(--fg-0)", marginTop: 6 }}>
                {data.scaling_35kv_plus.annual_saving_mln[tier].toLocaleString("ru-RU")} <span style={{ fontSize: 12, color: "var(--fg-2)" }}>млн ₽/год</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--accent)", marginTop: 4 }}>
                NPV 5 лет: {data.scaling_35kv_plus.scaled_npv_mln[tier].toLocaleString("ru-RU")} млн ₽
              </div>
              <div style={{ fontSize: 11, color: "var(--fg-3)", marginTop: 4 }}>
                {data.scaling_35kv_plus.n_substations_in_scope[tier].toLocaleString("ru-RU")} подстанций
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
