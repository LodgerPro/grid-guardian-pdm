import { useData } from "../lib/useData";
import {
  LineChart, Line, XAxis, YAxis, ReferenceLine, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import NotificationsBell from "../components/NotificationsBell";

interface Pt { t: string; v: number; }
interface UnitSeries {
  id: string;
  substation: string;
  series: { temperature_top: Pt[]; gas_c2h2: Pt[]; vibration_x: Pt[] };
}
interface MonData {
  window_days: number;
  downsample: string;
  healthy: UnitSeries;
  degraded: UnitSeries;
  thresholds: {
    temperature_top: { warn: number; crit: number };
    gas_c2h2:        { warn: number; crit: number };
    vibration_x:     { warn: number; crit: number };
  };
}

interface ChartProps {
  title: string;
  unit: string;
  data: Pt[];
  warn: number;
  crit: number;
  color: string;
}

function MiniChart({ title, unit, data, warn, crit, color }: ChartProps) {
  const last = data[data.length - 1]?.v ?? 0;
  return (
    <div className="mon-chart">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <span className="title">{title}</span>
        <span className="v">{last.toFixed(2)} {unit}</span>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <LineChart data={data} margin={{ top: 6, right: 6, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="oklch(0.28 0.025 250 / 0.4)" vertical={false} />
          <XAxis dataKey="t" hide />
          <YAxis
            stroke="oklch(0.52 0.02 250)"
            tick={{ fontSize: 10, fill: "oklch(0.68 0.015 250)" }}
            width={36}
          />
          <Tooltip
            contentStyle={{ background: "oklch(0.10 0.02 250 / 0.96)", border: "1px solid oklch(0.40 0.03 250)", color: "oklch(0.97 0.005 250)", fontSize: 12 }}
            formatter={(v: unknown) => `${typeof v === "number" ? v.toFixed(2) : v} ${unit}`}
          />
          <ReferenceLine y={warn} stroke="oklch(0.80 0.15 80)" strokeDasharray="4 4" strokeWidth={1} />
          <ReferenceLine y={crit} stroke="oklch(0.66 0.20 25)" strokeDasharray="4 4" strokeWidth={1} />
          <Line type="monotone" dataKey="v" stroke={color} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function Monitoring() {
  const { data } = useData<MonData>("monitoring.json");
  if (!data) return <div style={{ color: "var(--fg-3)" }}>Загрузка…</div>;
  const th = data.thresholds;

  return (
    <>
      <div className="topbar">
        <div className="topbar-title">
          <div className="page-eyebrow">Мониторинг · сравнение «здоровый vs проблемный»</div>
          <h1 className="page-title">Эволюция параметров за {data.window_days} дней</h1>
          <div className="page-sub">даунсэмплинг {data.downsample} · пороги предупреждения и критики подсвечены пунктиром</div>
        </div>
        <div className="topbar-actions">
          <span className="pill"><span className="dot"></span>Окно {data.window_days} дней</span>
          <NotificationsBell />
        </div>
      </div>

      <div className="mon-grid">
        <div className="card mon-card">
          <div className="card-head">
            <div>
              <div className="card-title" style={{ color: "var(--ok)" }}>Здоровый трансформатор</div>
              <div className="mon-tag">
                <span className="nm">{data.healthy.id}</span>·<span>{data.healthy.substation}</span>
              </div>
            </div>
            <span className={`tag ok`}><span className="dot"></span>Норма</span>
          </div>
          <MiniChart title="Температура верхнего слоя масла"
                     unit="°C" data={data.healthy.series.temperature_top}
                     warn={th.temperature_top.warn} crit={th.temperature_top.crit}
                     color="oklch(0.74 0.15 155)" />
          <MiniChart title="C₂H₂ (ацетилен)"
                     unit="ppm" data={data.healthy.series.gas_c2h2}
                     warn={th.gas_c2h2.warn} crit={th.gas_c2h2.crit}
                     color="oklch(0.74 0.15 155)" />
          <MiniChart title="Вибрация (ось X)"
                     unit="мм/с" data={data.healthy.series.vibration_x}
                     warn={th.vibration_x.warn} crit={th.vibration_x.crit}
                     color="oklch(0.74 0.15 155)" />
        </div>

        <div className="card mon-card">
          <div className="card-head">
            <div>
              <div className="card-title" style={{ color: "var(--crit)" }}>Деградирующий трансформатор</div>
              <div className="mon-tag">
                <span className="nm">{data.degraded.id}</span>·<span>{data.degraded.substation}</span>
              </div>
            </div>
            <span className={`tag crit`}><span className="dot"></span>Критично</span>
          </div>
          <MiniChart title="Температура верхнего слоя масла"
                     unit="°C" data={data.degraded.series.temperature_top}
                     warn={th.temperature_top.warn} crit={th.temperature_top.crit}
                     color="oklch(0.66 0.20 25)" />
          <MiniChart title="C₂H₂ (ацетилен)"
                     unit="ppm" data={data.degraded.series.gas_c2h2}
                     warn={th.gas_c2h2.warn} crit={th.gas_c2h2.crit}
                     color="oklch(0.66 0.20 25)" />
          <MiniChart title="Вибрация (ось X)"
                     unit="мм/с" data={data.degraded.series.vibration_x}
                     warn={th.vibration_x.warn} crit={th.vibration_x.crit}
                     color="oklch(0.66 0.20 25)" />
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div style={{ color: "var(--fg-2)", fontSize: 13.5, lineHeight: 1.6 }}>
          <b style={{ color: "var(--fg-0)" }}>Цель раздела</b> — наглядно показать, что система видит деградацию.
          У здорового юнита все три параметра колеблются строго ниже warn-порогов. У деградирующего за последние ~10 дней
          температура и C₂H₂ выходят за критический порог, вибрация подбирается к 8 мм/с. Именно такие траектории
          модель XGBoost обучилась распознавать <i>за 72 часа до</i> попадания в High-класс.
        </div>
      </div>
    </>
  );
}
