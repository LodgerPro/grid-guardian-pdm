import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { NavLink, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import NotificationsBell from "./NotificationsBell";
const NAV = [
    { to: "/", icon: "i-home", label: "Главная" },
    { to: "/predictions", icon: "i-pred", label: "Прогноз риска", badgeKey: "critical_units" },
    { to: "/financial", icon: "i-money", label: "Финансы" },
    { to: "/maps", icon: "i-map", label: "Карта" },
    { to: "/monitoring", icon: "i-pulse", label: "Мониторинг" },
];
export default function Shell({ children }) {
    const { pathname } = useLocation();
    const [criticalCount, setCriticalCount] = useState(null);
    // Load critical_units count once so the sidebar badge matches reality.
    useEffect(() => {
        fetch(`${import.meta.env.BASE_URL}data/home.json`)
            .then((r) => r.json())
            .then((d) => setCriticalCount(d?.kpi?.critical_units?.value ?? null))
            .catch(() => setCriticalCount(null));
    }, []);
    return (_jsxs("div", { className: "app", children: [_jsxs("aside", { className: "sidebar", children: [_jsxs("div", { className: "brand", children: [_jsx("div", { className: "brand-mark", children: _jsx("svg", { children: _jsx("use", { href: "#i-bolt" }) }) }), _jsxs("div", { children: [_jsx("div", { className: "brand-name", children: "Grid Guardian" }), _jsx("div", { className: "brand-sub", children: "\u0421\u0442\u0440\u0430\u0436 \u0441\u0435\u0442\u0438 \u00B7 v2.4" })] })] }), _jsxs("div", { children: [_jsx("div", { className: "nav-section-label", children: "\u0420\u0430\u0437\u0434\u0435\u043B" }), _jsx("nav", { className: "nav", children: NAV.map((n) => (_jsxs(NavLink, { to: n.to, end: n.to === "/", className: ({ isActive }) => (isActive ? "active" : ""), children: [_jsx("svg", { className: "nav-icon", children: _jsx("use", { href: `#${n.icon}` }) }), _jsx("span", { children: n.label }), n.badgeKey === "critical_units" && criticalCount != null && criticalCount > 0 && (_jsx("span", { className: "nav-badge", children: criticalCount }))] }, n.to))) })] }), _jsxs("div", { className: "sidebar-footer", children: [_jsx("div", { className: "avatar", children: "\u0410\u0418" }), _jsxs("div", { className: "user-meta", children: [_jsx("div", { className: "user-name", children: "\u0410\u043D\u0430\u043B\u0438\u0442\u0438\u043A" }), _jsx("div", { className: "user-role", children: "\u0426\u0435\u043D\u0442\u0440 \u0443\u043F\u0440\u0430\u0432\u043B\u0435\u043D\u0438\u044F \u0441\u0435\u0442\u044F\u043C\u0438" })] })] })] }), _jsxs("header", { className: "mobile-header", children: [_jsxs("div", { className: "brand", children: [_jsx("div", { className: "brand-mark", children: _jsx("svg", { children: _jsx("use", { href: "#i-bolt" }) }) }), _jsx("div", { children: _jsx("div", { className: "brand-name", children: "Grid Guardian" }) })] }), _jsx(NotificationsBell, {})] }), _jsx("main", { className: "main", children: children }), _jsx("nav", { className: "mobile-bar", children: NAV.map((n) => (_jsxs(NavLink, { to: n.to, end: n.to === "/", className: ({ isActive }) => (isActive ? "active" : ""), children: [_jsx("svg", { children: _jsx("use", { href: `#${n.icon}` }) }), _jsx("span", { children: n.label.split(" ")[0] })] }, n.to))) })] }));
}
