import { useMemo, useState } from "react";
import { useData } from "../lib/useData";
import NotificationsBell from "../components/NotificationsBell";

interface PredItem {
  id: string;
  substation: string;
  voltage: string;
  city: string;
  probability_72h_pct: number;
  status: "crit" | "warn" | "ok";
  is_degraded_unit: boolean;
  factors: {
    c2h2: number;
    temperature: number;
    vibration: number;
    humidity: number;
    tan_delta: number;
    service_age: number;
  };
}

interface PredData {
  horizon_hours: number;
  n_total: number;
  n_critical: number;
  n_warning: number;
  n_ok: number;
  items: PredItem[];
}

interface HorizonRow {
  horizon_hours: number;
  model_recall_high: number;
  baseline_recall_high: number;
  delta_recall_high: number;
}
interface HorizonData {
  rows: HorizonRow[];
}

const FACTOR_LABELS: Record<string, string> = {
  c2h2: "C₂H₂ (DGA)",
  temperature: "T° обмотки",
  vibration: "Вибрация",
  humidity: "Влага",
  tan_delta: "tan δ",
  service_age: "Наработка",
};

export default function Predictions() {
  const { data } = useData<PredData>("predictions.json");
  const { data: horizon } = useData<HorizonData>("horizon.json");
  const [filter, setFilter] = useState<"all" | "crit" | "warn" | "ok">("all");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const visible = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    return data.items.filter((it) => {
      if (filter !== "all" && it.status !== filter) return false;
      if (q && !(it.id.toLowerCase().includes(q) || it.substation.toLowerCase().includes(q))) return false;
      return true;
    });
  }, [data, filter, search]);

  const selected = useMemo(() => {
    if (!data) return null;
    if (selectedId) {
      const found = data.items.find((x) => x.id === selectedId);
      if (found) return found;
    }
    return visible[0] ?? data.items[0];
  }, [data, visible, selectedId]);

  if (!data) return <div style={{ color: "var(--fg-3)" }}>Загрузка…</div>;

  return (
    <>
      <div className="topbar">
        <div className="topbar-title">
          <div className="page-eyebrow">Прогноз риска · {data.horizon_hours} ч вперёд</div>
          <h1 className="page-title">Прогноз отказов оборудования</h1>
          <div className="page-sub">
            {data.n_total} единиц · {data.n_critical} критичных, {data.n_warning} предупреждений, {data.n_ok} в норме
          </div>
        </div>
        <div className="topbar-actions">
          <span className="pill"><span className="dot"></span>Модель GG-ML v2.4</span>
          <NotificationsBell />
          <button className="btn-primary">
            <svg style={{ width: 14, height: 14 }}><use href="#i-export" /></svg>
            Экспорт CSV
          </button>
        </div>
      </div>

      <div className="pred-shell">
        <div>
          <div className="toolbar">
            <button className="btn-ghost"><svg style={{ width: 14, height: 14 }}><use href="#i-filter" /></svg>Регион</button>
            <button className="btn-ghost"><svg style={{ width: 14, height: 14 }}><use href="#i-filter" /></svg>Тип</button>
            <button className="btn-ghost"><svg style={{ width: 14, height: 14 }}><use href="#i-filter" /></svg>Год выпуска</button>
            <input
              className="gg-input"
              placeholder="Поиск по ID или подстанции…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ flex: 1, minWidth: 200, maxWidth: 320 }}
            />
            <div className="seg" role="tablist">
              {(["all", "crit", "warn", "ok"] as const).map((k) => (
                <button key={k} className={filter === k ? "is-on" : ""} onClick={() => setFilter(k)}>
                  {k === "all" ? "Все" : k === "crit" ? "Критично" : k === "warn" ? "Предупр." : "Норма"}
                </button>
              ))}
            </div>
          </div>

          <div className="tbl-wrap">
            <div className="tbl-head">
              <div>ID</div>
              <div>Подстанция</div>
              <div className="voltage">кВ</div>
              <div>Статус</div>
              <div style={{ textAlign: "right" }}>Риск 72 ч</div>
            </div>
            {visible.map((it) => (
              <div
                key={it.id}
                className={`tbl-row ${selected?.id === it.id ? "is-selected" : ""}`}
                onClick={() => setSelectedId(it.id)}
              >
                <div className="id">{it.id}</div>
                <div className="sub-cell">
                  {it.substation}
                  <div className="small city">{it.city}</div>
                </div>
                <div className="v voltage">{it.voltage}</div>
                <div>
                  <span className={`tag ${it.status}`}>
                    <span className="dot" />
                    {it.status === "crit" ? "Критично" : it.status === "warn" ? "Внимание" : "Норма"}
                  </span>
                </div>
                <div className="v" style={{ textAlign: "right" }}>{it.probability_72h_pct.toFixed(1)}%</div>
              </div>
            ))}
            {visible.length === 0 && (
              <div style={{ padding: 24, textAlign: "center", color: "var(--fg-3)" }}>
                По фильтрам ничего не нашлось
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="card" style={{ marginBottom: 14 }}>
            <div className="card-head">
              <div>
                <div className="card-title">Разложение по факторам риска</div>
                <div className="card-sub">{selected?.id} · {selected?.substation}</div>
              </div>
            </div>
            {selected && (
              <>
                <div style={{
                  fontFamily: "Space Grotesk, sans-serif", fontSize: 44, fontWeight: 600,
                  color: selected.status === "crit" ? "var(--crit)" : selected.status === "warn" ? "var(--warn)" : "var(--ok)",
                  letterSpacing: "-0.015em", marginBottom: 4,
                }}>
                  {selected.probability_72h_pct.toFixed(1)}%
                </div>
                <div style={{ fontSize: 12, color: "var(--fg-3)", marginBottom: 14 }}>
                  Вероятность критического состояния через 72 ч
                </div>
                {Object.entries(selected.factors).map(([k, v]) => (
                  <div key={k} className="factor-row">
                    <span className="k">{FACTOR_LABELS[k] ?? k}</span>
                    <div className="factor-bar">
                      <i style={{ width: `${Math.min(100, v * 200)}%` }} />
                    </div>
                    <span className="v">{(v * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </>
            )}
          </div>

          <div className="card">
            <div className="card-head">
              <div>
                <div className="card-title">Чувствительность к горизонту</div>
                <div className="card-sub">recall класса High · модель vs no-ML</div>
              </div>
            </div>
            {horizon?.rows?.map((r) => (
              <div key={r.horizon_hours} style={{
                display: "grid", gridTemplateColumns: "60px 1fr 1fr 60px",
                gap: 8, padding: "8px 0", fontSize: 12.5, alignItems: "center",
                borderTop: "1px solid oklch(0.28 0.025 250 / 0.4)",
              }}>
                <div className="mono" style={{ color: "var(--fg-1)" }}>{r.horizon_hours} ч</div>
                <div className="mono" style={{ color: "var(--accent)" }}>ML {(r.model_recall_high * 100).toFixed(2)}%</div>
                <div className="mono" style={{ color: "var(--fg-3)" }}>BL {(r.baseline_recall_high * 100).toFixed(2)}%</div>
                <div className="mono" style={{
                  textAlign: "right",
                  color: r.delta_recall_high > 0.005 ? "var(--ok)" : "var(--fg-2)",
                }}>
                  {r.delta_recall_high > 0 ? "+" : ""}{(r.delta_recall_high * 100).toFixed(2)}
                </div>
              </div>
            ))}
            <div style={{ fontSize: 11.5, color: "var(--fg-3)", marginTop: 10, lineHeight: 1.55 }}>
              На горизонте 168 ч модель опережает no-ML правило на 1.08 п.п. recall — основной аргумент ценности ML.
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
