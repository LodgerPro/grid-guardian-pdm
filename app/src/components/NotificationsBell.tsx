import { useEffect, useRef, useState } from "react";

interface AlertItem {
  id: string;
  substation: string;
  reason: string;
  probability_pct: number;
  level: "crit" | "warn" | "ok" | "info";
}

interface HomeData {
  alerts?: AlertItem[];
}

export default function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/home.json`)
      .then((r) => r.json() as Promise<HomeData>)
      .then((d) => setAlerts(d?.alerts ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, []);

  const unread = alerts.filter((a) => !readIds.has(a.id));
  const markAllRead = () => setReadIds(new Set(alerts.map((a) => a.id)));
  const markOne = (id: string) => setReadIds((s) => new Set([...s, id]));

  const iconFor = (lvl: AlertItem["level"]) => {
    if (lvl === "crit") return "i-warn";
    if (lvl === "warn") return "i-pulse";
    return "i-check";
  };

  return (
    <div className={`notif-wrap ${open ? "is-open" : ""}`} ref={wrapRef}>
      <button
        className="icon-btn"
        aria-label="Уведомления"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <svg>
          <use href="#i-bell" />
        </svg>
        {unread.length > 0 && <span className="badge-dot" />}
      </button>
      <div className="notif-pop" role="dialog" aria-label="Уведомления">
        <div className="notif-head">
          <div className="notif-title">
            Уведомления
            {unread.length > 0 && <span className="notif-count">{unread.length} нов.</span>}
          </div>
          {unread.length > 0 && (
            <button className="notif-mark" onClick={markAllRead}>
              Прочитано
            </button>
          )}
        </div>
        <div className="notif-list">
          {alerts.length === 0 && (
            <div style={{ padding: "20px", color: "var(--fg-3)", fontSize: 13 }}>
              Нет уведомлений
            </div>
          )}
          {alerts.map((a) => (
            <div
              key={a.id}
              className={`notif-item ${readIds.has(a.id) ? "" : "is-unread"}`}
              onClick={() => markOne(a.id)}
            >
              <div className={`notif-icon ${a.level}`}>
                <svg>
                  <use href={`#${iconFor(a.level)}`} />
                </svg>
              </div>
              <div className="notif-body">
                <div className="notif-msg">{a.reason}</div>
                <div className="notif-meta">
                  <b>{a.id}</b> · {a.substation} · вероятность {a.probability_pct}%
                </div>
              </div>
              <div className="notif-time">сейчас</div>
            </div>
          ))}
        </div>
        <div className="notif-foot">
          <span className="status-dot">Поток телеметрии · 9 824 изм/час</span>
          <a href="#/predictions">Все события →</a>
        </div>
      </div>
    </div>
  );
}
