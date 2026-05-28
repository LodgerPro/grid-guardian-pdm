import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef, useState } from "react";
export default function NotificationsBell() {
    const [open, setOpen] = useState(false);
    const [alerts, setAlerts] = useState([]);
    const [readIds, setReadIds] = useState(new Set());
    const wrapRef = useRef(null);
    useEffect(() => {
        fetch(`${import.meta.env.BASE_URL}data/home.json`)
            .then((r) => r.json())
            .then((d) => setAlerts(d?.alerts ?? []))
            .catch(() => { });
    }, []);
    useEffect(() => {
        const onDocClick = (e) => {
            if (wrapRef.current && !wrapRef.current.contains(e.target))
                setOpen(false);
        };
        const onEsc = (e) => {
            if (e.key === "Escape")
                setOpen(false);
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
    const markOne = (id) => setReadIds((s) => new Set([...s, id]));
    const iconFor = (lvl) => {
        if (lvl === "crit")
            return "i-warn";
        if (lvl === "warn")
            return "i-pulse";
        return "i-check";
    };
    return (_jsxs("div", { className: `notif-wrap ${open ? "is-open" : ""}`, ref: wrapRef, children: [_jsxs("button", { className: "icon-btn", "aria-label": "\u0423\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u044F", "aria-haspopup": "true", "aria-expanded": open, onClick: () => setOpen((o) => !o), children: [_jsx("svg", { children: _jsx("use", { href: "#i-bell" }) }), unread.length > 0 && _jsx("span", { className: "badge-dot" })] }), _jsxs("div", { className: "notif-pop", role: "dialog", "aria-label": "\u0423\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u044F", children: [_jsxs("div", { className: "notif-head", children: [_jsxs("div", { className: "notif-title", children: ["\u0423\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u044F", unread.length > 0 && _jsxs("span", { className: "notif-count", children: [unread.length, " \u043D\u043E\u0432."] })] }), unread.length > 0 && (_jsx("button", { className: "notif-mark", onClick: markAllRead, children: "\u041F\u0440\u043E\u0447\u0438\u0442\u0430\u043D\u043E" }))] }), _jsxs("div", { className: "notif-list", children: [alerts.length === 0 && (_jsx("div", { style: { padding: "20px", color: "var(--fg-3)", fontSize: 13 }, children: "\u041D\u0435\u0442 \u0443\u0432\u0435\u0434\u043E\u043C\u043B\u0435\u043D\u0438\u0439" })), alerts.map((a) => (_jsxs("div", { className: `notif-item ${readIds.has(a.id) ? "" : "is-unread"}`, onClick: () => markOne(a.id), children: [_jsx("div", { className: `notif-icon ${a.level}`, children: _jsx("svg", { children: _jsx("use", { href: `#${iconFor(a.level)}` }) }) }), _jsxs("div", { className: "notif-body", children: [_jsx("div", { className: "notif-msg", children: a.reason }), _jsxs("div", { className: "notif-meta", children: [_jsx("b", { children: a.id }), " \u00B7 ", a.substation, " \u00B7 \u0432\u0435\u0440\u043E\u044F\u0442\u043D\u043E\u0441\u0442\u044C ", a.probability_pct, "%"] })] }), _jsx("div", { className: "notif-time", children: "\u0441\u0435\u0439\u0447\u0430\u0441" })] }, a.id)))] }), _jsxs("div", { className: "notif-foot", children: [_jsx("span", { className: "status-dot", children: "\u041F\u043E\u0442\u043E\u043A \u0442\u0435\u043B\u0435\u043C\u0435\u0442\u0440\u0438\u0438 \u00B7 9 824 \u0438\u0437\u043C/\u0447\u0430\u0441" }), _jsx("a", { href: "#/predictions", children: "\u0412\u0441\u0435 \u0441\u043E\u0431\u044B\u0442\u0438\u044F \u2192" })] })] })] }));
}
