import { NavLink, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import NotificationsBell from "./NotificationsBell";
import type { ReactNode } from "react";

interface NavItem {
  to: string;
  icon: string;
  label: string;
  badgeKey?: "critical_units";
}

const NAV: NavItem[] = [
  { to: "/", icon: "i-home", label: "Главная" },
  { to: "/predictions", icon: "i-pred", label: "Прогноз риска", badgeKey: "critical_units" },
  { to: "/financial", icon: "i-money", label: "Финансы" },
  { to: "/maps", icon: "i-map", label: "Карта" },
  { to: "/monitoring", icon: "i-pulse", label: "Мониторинг" },
];

interface HomeData {
  kpi?: { critical_units?: { value: number } };
}

export default function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const [criticalCount, setCriticalCount] = useState<number | null>(null);

  // Load critical_units count once so the sidebar badge matches reality.
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/home.json`)
      .then((r) => r.json() as Promise<HomeData>)
      .then((d) => setCriticalCount(d?.kpi?.critical_units?.value ?? null))
      .catch(() => setCriticalCount(null));
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <svg>
              <use href="#i-bolt" />
            </svg>
          </div>
          <div>
            <div className="brand-name">Grid Guardian</div>
            <div className="brand-sub">Страж сети · v2.4</div>
          </div>
        </div>

        <div>
          <div className="nav-section-label">Раздел</div>
          <nav className="nav">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                className={({ isActive }) => (isActive ? "active" : "")}
              >
                <svg className="nav-icon">
                  <use href={`#${n.icon}`} />
                </svg>
                <span>{n.label}</span>
                {n.badgeKey === "critical_units" && criticalCount != null && criticalCount > 0 && (
                  <span className="nav-badge">{criticalCount}</span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="sidebar-footer">
          <div className="avatar">АИ</div>
          <div className="user-meta">
            <div className="user-name">Аналитик</div>
            <div className="user-role">Центр управления сетями</div>
          </div>
        </div>
      </aside>

      <header className="mobile-header">
        <div className="brand">
          <div className="brand-mark">
            <svg>
              <use href="#i-bolt" />
            </svg>
          </div>
          <div>
            <div className="brand-name">Grid Guardian</div>
          </div>
        </div>
        <NotificationsBell />
      </header>

      <main className="main">{children}</main>

      <nav className="mobile-bar">
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === "/"}
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            <svg>
              <use href={`#${n.icon}`} />
            </svg>
            <span>{n.label.split(" ")[0]}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
