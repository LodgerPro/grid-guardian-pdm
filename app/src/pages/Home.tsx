import { useData } from "../lib/useData";
import NotificationsBell from "../components/NotificationsBell";

interface KpiCell { value: number; delta: number; delta_label: string; sub: string; }
interface Alert { id: string; substation: string; reason: string; probability_pct: number; level: "crit" | "warn" | "ok"; }

interface HomeData {
  kpi: {
    n_units: KpiCell;
    mean_risk_pct: KpiCell;
    active_warnings: KpiCell;
    critical_units: KpiCell;
  };
  risk_distribution: {
    low:    { count: number; pct: number };
    medium: { count: number; pct: number };
    high:   { count: number; pct: number };
    total:  number;
  };
  alerts: Alert[];
  model_card: { recall_high: number; horizon_hours: number; n_features_used: number };
  updated_at: string;
  period_days: number;
  degraded_units_total: number;
}

function Donut({ low, medium, high }: { low: number; medium: number; high: number }) {
  // Donut with three concentric arcs sized by share. Total circumference 2*pi*78 ≈ 490.09.
  const C = 2 * Math.PI * 78;
  const sLow = (low * C) / 100;
  const sMed = (medium * C) / 100;
  const sHigh = (high * C) / 100;
  return (
    <div className="donut-wrap" aria-label="Распределение рисков">
      <svg width={200} height={200} viewBox="0 0 200 200">
        <circle cx={100} cy={100} r={78} stroke="oklch(0.28 0.025 250)" strokeWidth={22} fill="none" />
        <g fill="none" strokeWidth={22} strokeLinecap="butt" transform="rotate(-90 100 100)">
          <circle cx={100} cy={100} r={78} stroke="oklch(0.74 0.15 155)"
                  strokeDasharray={`${sLow} ${C - sLow}`} strokeDashoffset={0} />
          <circle cx={100} cy={100} r={78} stroke="oklch(0.80 0.15 80)"
                  strokeDasharray={`${sMed} ${C - sMed}`} strokeDashoffset={-sLow} />
          <circle cx={100} cy={100} r={78} stroke="oklch(0.66 0.20 25)"
                  strokeDasharray={`${sHigh} ${C - sHigh}`} strokeDashoffset={-(sLow + sMed)} />
        </g>
      </svg>
      <div className="donut-center">
        <div>
          <div className="v mono">{low.toFixed(1)}%</div>
          <div className="l">норма</div>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const { data, err } = useData<HomeData>("home.json");
  if (err) return <div style={{ color: "var(--crit)" }}>Ошибка загрузки данных: {err}</div>;
  if (!data) return <div style={{ color: "var(--fg-3)" }}>Загрузка…</div>;

  const k = data.kpi;
  const rd = data.risk_distribution;

  return (
    <>
      <div className="topbar">
        <div className="topbar-title">
          <div className="page-eyebrow">Главная · Сводка по парку</div>
          <h1 className="page-title">Состояние оборудования</h1>
          <div className="page-sub">
            Обновлено {data.updated_at} · период наблюдения {data.period_days} дней · модель GG-ML v2.4
          </div>
        </div>
        <div className="topbar-actions">
          <span className="pill"><span className="dot"></span>Поток данных активен</span>
          <button className="icon-btn" aria-label="Поиск"><svg><use href="#i-search" /></svg></button>
          <NotificationsBell />
          <button className="btn-primary">
            <svg style={{ width: 14, height: 14 }}><use href="#i-export" /></svg>
            Экспорт отчёта
          </button>
        </div>
      </div>

      <section className="kpi-grid">
        <div className="kpi is-accent">
          <div className="kpi-glyph"><svg><use href="#i-transformer" /></svg></div>
          <div className="kpi-label">Всего единиц оборудования</div>
          <div className="kpi-value mono">{k.n_units.value.toLocaleString("ru-RU")}</div>
          <div className="kpi-foot">
            <span className="delta neutral">{k.n_units.delta_label}</span>
            <span>{k.n_units.sub}</span>
          </div>
        </div>
        <div className="kpi">
          <div className="kpi-glyph"><svg><use href="#i-sensor" /></svg></div>
          <div className="kpi-label">Средняя вероятность отказа</div>
          <div className="kpi-value mono">
            {k.mean_risk_pct.value.toFixed(1)}<span className="unit">%</span>
          </div>
          <div className="kpi-foot">
            <span className="delta down">{k.mean_risk_pct.delta_label}</span>
            <span>{k.mean_risk_pct.sub}</span>
          </div>
        </div>
        <div className="kpi is-warn">
          <div className="kpi-glyph" style={{ color: "var(--warn)" }}><svg><use href="#i-warn" /></svg></div>
          <div className="kpi-label">Активные предупреждения</div>
          <div className="kpi-value mono">{k.active_warnings.value}</div>
          <div className="kpi-foot">
            <span className="delta up">{k.active_warnings.delta_label}</span>
            <span>{k.active_warnings.sub}</span>
          </div>
        </div>
        <div className="kpi is-crit">
          <div className="kpi-glyph" style={{ color: "var(--crit)" }}><svg><use href="#i-warn" /></svg></div>
          <div className="kpi-label">Критические единицы</div>
          <div className="kpi-value mono">{k.critical_units.value}</div>
          <div className="kpi-foot">
            <span className="delta up">{k.critical_units.delta_label}</span>
            <span>{k.critical_units.sub}</span>
          </div>
        </div>
      </section>

      <section className="content-grid">
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Распределение по уровням риска</div>
              <div className="card-sub">{rd.total.toLocaleString("ru-RU")} ч-измерений · прогноз на 72 ч вперёд</div>
            </div>
            <div className="seg" role="tablist">
              <button className="is-on">Парк</button>
              <button>По регионам</button>
            </div>
          </div>
          <div className="risk-body">
            <Donut low={rd.low.pct} medium={rd.medium.pct} high={rd.high.pct} />
            <div className="legend">
              <div className="legend-row is-ok">
                <span className="legend-dot" />
                <div>
                  <div className="legend-name">Норма (Low)</div>
                  <div className="legend-sub">{rd.low.count.toLocaleString("ru-RU")} наблюдений</div>
                </div>
                <div className="legend-val">{rd.low.pct.toFixed(2)}%</div>
              </div>
              <div className="legend-row is-warn">
                <span className="legend-dot" />
                <div>
                  <div className="legend-name">Предупреждение (Medium)</div>
                  <div className="legend-sub">{rd.medium.count.toLocaleString("ru-RU")} наблюдений</div>
                </div>
                <div className="legend-val">{rd.medium.pct.toFixed(2)}%</div>
              </div>
              <div className="legend-row is-crit">
                <span className="legend-dot" />
                <div>
                  <div className="legend-name">Критический (High)</div>
                  <div className="legend-sub">{rd.high.count.toLocaleString("ru-RU")} наблюдений</div>
                </div>
                <div className="legend-val">{rd.high.pct.toFixed(2)}%</div>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Активные предупреждения</div>
              <div className="card-sub">по прогнозу модели на ближайшие 72 ч</div>
            </div>
            <span className="pill">{data.alerts.length} событий</span>
          </div>
          <div className="alerts-list">
            {data.alerts.map((a) => (
              <div key={a.id} className={`alert-item is-${a.level}`}>
                <span className="alert-dot" />
                <div className="alert-meta">
                  <div className="alert-id">{a.id}</div>
                  <div className="alert-sub">{a.substation} · {a.reason}</div>
                </div>
                <div className="alert-prob">
                  <span className="lbl">риск 72ч</span>
                  {a.probability_pct.toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <div>
            <div className="card-title">Модель прогноза</div>
            <div className="card-sub">XGBoost · класс High recall на горизонте 72 ч</div>
          </div>
        </div>
        <div className="risk-body">
          <div style={{ fontFamily: "Space Grotesk, sans-serif", fontSize: 56, fontWeight: 600, color: "var(--accent)" }}>
            {data.model_card.recall_high.toFixed(2)}<span style={{ fontSize: 24, color: "var(--fg-2)", marginLeft: 4 }}>%</span>
          </div>
          <div style={{ flex: 1, color: "var(--fg-2)", fontSize: 13.5, lineHeight: 1.55 }}>
            На тестовой выборке за последние ~5 месяцев двухгодичного периода модель распознала
            {" "}{data.model_card.recall_high.toFixed(2)}% будущих критических состояний
            (горизонт {data.model_card.horizon_hours} ч). Использовано {data.model_card.n_features_used} признаков
            (исключены 7 признаков-«индикаторов порогов» во избежание тавтологической утечки).
            Замеры воспроизводимы — random seed 42.
          </div>
        </div>
      </section>
    </>
  );
}
