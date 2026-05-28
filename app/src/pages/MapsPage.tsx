import { useEffect, useRef } from "react";
import L from "leaflet";
import { useData } from "../lib/useData";
import NotificationsBell from "../components/NotificationsBell";

interface SubstationItem {
  id: string;
  name: string;
  city: string;
  voltage: string;
  lat: number;
  lon: number;
  n_units: number;
  status: "crit" | "warn" | "ok";
  max_probability_pct: number;
}
interface RouteStop {
  order: number;
  id: string;
  name: string;
  lat: number;
  lon: number;
  max_probability_pct: number;
}
interface MapsData {
  substations: SubstationItem[];
  suggested_route: RouteStop[];
  route_strategy: string;
}

function makeIcon(status: SubstationItem["status"]): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div class="gg-marker ${status}" style="position:relative"></div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

export default function MapsPage() {
  const { data } = useData<MapsData>("maps.json");
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerById = useRef<Record<string, L.Marker>>({});

  useEffect(() => {
    if (!containerRef.current || !data) return;
    if (mapRef.current) return; // already initialised

    const m = L.map(containerRef.current, {
      center: [60, 65],
      zoom: 3,
      minZoom: 3,
      maxZoom: 7,
      zoomControl: true,
      attributionControl: true,
    });
    mapRef.current = m;

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OSM</a> · CartoDB',
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(m);

    data.substations.forEach((s) => {
      const mk = L.marker([s.lat, s.lon], { icon: makeIcon(s.status) })
        .addTo(m)
        .bindPopup(
          `<div style="font-family:Inter,sans-serif;color:#0a0e16;">
            <div style="font-weight:600;font-size:13px">${s.name}</div>
            <div style="font-size:11px;color:#444;margin-top:2px">${s.city} · ${s.voltage}</div>
            <div style="font-size:11px;color:#444">Единиц: ${s.n_units}</div>
            <div style="font-family:JetBrains Mono,monospace;font-size:12px;margin-top:6px;font-weight:600;color:${
              s.status === "crit" ? "#c43328" : s.status === "warn" ? "#a37500" : "#1f8f54"
            }">Риск 72ч: ${s.max_probability_pct.toFixed(1)}%</div>
          </div>`
        );
      markerById.current[s.id] = mk;
    });

    if (data.suggested_route.length >= 2) {
      const latlngs = data.suggested_route.map((r) => [r.lat, r.lon] as [number, number]);
      L.polyline(latlngs, {
        color: "#36d6e0",
        weight: 2.5,
        opacity: 0.85,
        dashArray: "6 6",
      }).addTo(m);
    }

    return () => {
      m.remove();
      mapRef.current = null;
    };
  }, [data]);

  const focus = (s: RouteStop) => {
    const m = mapRef.current;
    if (!m) return;
    m.flyTo([s.lat, s.lon], 5, { duration: 0.6 });
    const mk = markerById.current[s.id];
    if (mk) mk.openPopup();
  };

  return (
    <>
      <div className="topbar">
        <div className="topbar-title">
          <div className="page-eyebrow">Карта · 10 подстанций пилота</div>
          <h1 className="page-title">География риска</h1>
          <div className="page-sub">тёмная карта CartoDB · маркеры по уровню риска · маршрут бригады по критическим узлам</div>
        </div>
        <div className="topbar-actions">
          <NotificationsBell />
          <button className="btn-primary">
            <svg style={{ width: 14, height: 14 }}><use href="#i-route" /></svg>
            Назначить маршрут
          </button>
        </div>
      </div>

      <div className="map-shell">
        <div className="card map-card">
          <div ref={containerRef} style={{ height: 540, width: "100%" }} />
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Маршрут бригады</div>
              <div className="card-sub">{data?.route_strategy}</div>
            </div>
          </div>
          {(!data || data.suggested_route.length === 0) && (
            <div style={{ color: "var(--fg-3)", fontSize: 13 }}>Нет критических подстанций — выезд не требуется.</div>
          )}
          <div className="route-list">
            {data?.suggested_route.map((s) => (
              <div key={s.id} className="route-item" onClick={() => focus(s)}>
                <div className="route-num">{s.order}</div>
                <div>
                  <div className="route-name">{s.id}</div>
                  <div className="route-sub">{s.name}</div>
                </div>
                <div style={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 600, color: "var(--crit)" }}>
                  {s.max_probability_pct.toFixed(1)}%
                </div>
              </div>
            ))}
          </div>

          {data && (
            <>
              <div className="card-head" style={{ marginTop: 18 }}>
                <div>
                  <div className="card-title">Сводка по подстанциям</div>
                  <div className="card-sub">10 узлов пилотного развёртывания</div>
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {data.substations.map((s) => (
                  <div key={s.id} style={{
                    display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center",
                    padding: "6px 8px", borderRadius: 8, fontSize: 12.5,
                    background: s.status === "crit" ? "var(--crit-soft)" : s.status === "warn" ? "var(--warn-soft)" : "transparent",
                  }}>
                    <div>
                      <span style={{ fontFamily: "JetBrains Mono, monospace", fontWeight: 600 }}>{s.id}</span>
                      <span style={{ color: "var(--fg-3)", marginLeft: 6 }}>{s.city} · {s.voltage}</span>
                    </div>
                    <span className={`tag ${s.status}`}><span className="dot" />{s.max_probability_pct.toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
