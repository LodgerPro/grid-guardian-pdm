import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useMemo, useState } from "react";
import { useData } from "../lib/useData";
import NotificationsBell from "../components/NotificationsBell";
const FACTOR_LABELS = {
    c2h2: "C₂H₂ (DGA)",
    temperature: "T° обмотки",
    vibration: "Вибрация",
    humidity: "Влага",
    tan_delta: "tan δ",
    service_age: "Наработка",
};
export default function Predictions() {
    const { data } = useData("predictions.json");
    const { data: horizon } = useData("horizon.json");
    const [filter, setFilter] = useState("all");
    const [search, setSearch] = useState("");
    const [selectedId, setSelectedId] = useState(null);
    const visible = useMemo(() => {
        if (!data)
            return [];
        const q = search.trim().toLowerCase();
        return data.items.filter((it) => {
            if (filter !== "all" && it.status !== filter)
                return false;
            if (q && !(it.id.toLowerCase().includes(q) || it.substation.toLowerCase().includes(q)))
                return false;
            return true;
        });
    }, [data, filter, search]);
    const selected = useMemo(() => {
        if (!data)
            return null;
        if (selectedId) {
            const found = data.items.find((x) => x.id === selectedId);
            if (found)
                return found;
        }
        return visible[0] ?? data.items[0];
    }, [data, visible, selectedId]);
    if (!data)
        return _jsx("div", { style: { color: "var(--fg-3)" }, children: "\u0417\u0430\u0433\u0440\u0443\u0437\u043A\u0430\u2026" });
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "topbar", children: [_jsxs("div", { className: "topbar-title", children: [_jsxs("div", { className: "page-eyebrow", children: ["\u041F\u0440\u043E\u0433\u043D\u043E\u0437 \u0440\u0438\u0441\u043A\u0430 \u00B7 ", data.horizon_hours, " \u0447 \u0432\u043F\u0435\u0440\u0451\u0434"] }), _jsx("h1", { className: "page-title", children: "\u041F\u0440\u043E\u0433\u043D\u043E\u0437 \u043E\u0442\u043A\u0430\u0437\u043E\u0432 \u043E\u0431\u043E\u0440\u0443\u0434\u043E\u0432\u0430\u043D\u0438\u044F" }), _jsxs("div", { className: "page-sub", children: [data.n_total, " \u0435\u0434\u0438\u043D\u0438\u0446 \u00B7 ", data.n_critical, " \u043A\u0440\u0438\u0442\u0438\u0447\u043D\u044B\u0445, ", data.n_warning, " \u043F\u0440\u0435\u0434\u0443\u043F\u0440\u0435\u0436\u0434\u0435\u043D\u0438\u0439, ", data.n_ok, " \u0432 \u043D\u043E\u0440\u043C\u0435"] })] }), _jsxs("div", { className: "topbar-actions", children: [_jsxs("span", { className: "pill", children: [_jsx("span", { className: "dot" }), "\u041C\u043E\u0434\u0435\u043B\u044C GG-ML v2.4"] }), _jsx(NotificationsBell, {}), _jsxs("button", { className: "btn-primary", children: [_jsx("svg", { style: { width: 14, height: 14 }, children: _jsx("use", { href: "#i-export" }) }), "\u042D\u043A\u0441\u043F\u043E\u0440\u0442 CSV"] })] })] }), _jsxs("div", { className: "pred-shell", children: [_jsxs("div", { children: [_jsxs("div", { className: "toolbar", children: [_jsxs("button", { className: "btn-ghost", children: [_jsx("svg", { style: { width: 14, height: 14 }, children: _jsx("use", { href: "#i-filter" }) }), "\u0420\u0435\u0433\u0438\u043E\u043D"] }), _jsxs("button", { className: "btn-ghost", children: [_jsx("svg", { style: { width: 14, height: 14 }, children: _jsx("use", { href: "#i-filter" }) }), "\u0422\u0438\u043F"] }), _jsxs("button", { className: "btn-ghost", children: [_jsx("svg", { style: { width: 14, height: 14 }, children: _jsx("use", { href: "#i-filter" }) }), "\u0413\u043E\u0434 \u0432\u044B\u043F\u0443\u0441\u043A\u0430"] }), _jsx("input", { className: "gg-input", placeholder: "\u041F\u043E\u0438\u0441\u043A \u043F\u043E ID \u0438\u043B\u0438 \u043F\u043E\u0434\u0441\u0442\u0430\u043D\u0446\u0438\u0438\u2026", value: search, onChange: (e) => setSearch(e.target.value), style: { flex: 1, minWidth: 200, maxWidth: 320 } }), _jsx("div", { className: "seg", role: "tablist", children: ["all", "crit", "warn", "ok"].map((k) => (_jsx("button", { className: filter === k ? "is-on" : "", onClick: () => setFilter(k), children: k === "all" ? "Все" : k === "crit" ? "Критично" : k === "warn" ? "Предупр." : "Норма" }, k))) })] }), _jsxs("div", { className: "tbl-wrap", children: [_jsxs("div", { className: "tbl-head", children: [_jsx("div", { children: "ID" }), _jsx("div", { children: "\u041F\u043E\u0434\u0441\u0442\u0430\u043D\u0446\u0438\u044F" }), _jsx("div", { className: "voltage", children: "\u043A\u0412" }), _jsx("div", { children: "\u0421\u0442\u0430\u0442\u0443\u0441" }), _jsx("div", { style: { textAlign: "right" }, children: "\u0420\u0438\u0441\u043A 72 \u0447" })] }), visible.map((it) => (_jsxs("div", { className: `tbl-row ${selected?.id === it.id ? "is-selected" : ""}`, onClick: () => setSelectedId(it.id), children: [_jsx("div", { className: "id", children: it.id }), _jsxs("div", { className: "sub-cell", children: [it.substation, _jsx("div", { className: "small city", children: it.city })] }), _jsx("div", { className: "v voltage", children: it.voltage }), _jsx("div", { children: _jsxs("span", { className: `tag ${it.status}`, children: [_jsx("span", { className: "dot" }), it.status === "crit" ? "Критично" : it.status === "warn" ? "Внимание" : "Норма"] }) }), _jsxs("div", { className: "v", style: { textAlign: "right" }, children: [it.probability_72h_pct.toFixed(1), "%"] })] }, it.id))), visible.length === 0 && (_jsx("div", { style: { padding: 24, textAlign: "center", color: "var(--fg-3)" }, children: "\u041F\u043E \u0444\u0438\u043B\u044C\u0442\u0440\u0430\u043C \u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u043D\u0430\u0448\u043B\u043E\u0441\u044C" }))] })] }), _jsxs("div", { children: [_jsxs("div", { className: "card", style: { marginBottom: 14 }, children: [_jsx("div", { className: "card-head", children: _jsxs("div", { children: [_jsx("div", { className: "card-title", children: "\u0420\u0430\u0437\u043B\u043E\u0436\u0435\u043D\u0438\u0435 \u043F\u043E \u0444\u0430\u043A\u0442\u043E\u0440\u0430\u043C \u0440\u0438\u0441\u043A\u0430" }), _jsxs("div", { className: "card-sub", children: [selected?.id, " \u00B7 ", selected?.substation] })] }) }), selected && (_jsxs(_Fragment, { children: [_jsxs("div", { style: {
                                                    fontFamily: "Space Grotesk, sans-serif", fontSize: 44, fontWeight: 600,
                                                    color: selected.status === "crit" ? "var(--crit)" : selected.status === "warn" ? "var(--warn)" : "var(--ok)",
                                                    letterSpacing: "-0.015em", marginBottom: 4,
                                                }, children: [selected.probability_72h_pct.toFixed(1), "%"] }), _jsx("div", { style: { fontSize: 12, color: "var(--fg-3)", marginBottom: 14 }, children: "\u0412\u0435\u0440\u043E\u044F\u0442\u043D\u043E\u0441\u0442\u044C \u043A\u0440\u0438\u0442\u0438\u0447\u0435\u0441\u043A\u043E\u0433\u043E \u0441\u043E\u0441\u0442\u043E\u044F\u043D\u0438\u044F \u0447\u0435\u0440\u0435\u0437 72 \u0447" }), Object.entries(selected.factors).map(([k, v]) => (_jsxs("div", { className: "factor-row", children: [_jsx("span", { className: "k", children: FACTOR_LABELS[k] ?? k }), _jsx("div", { className: "factor-bar", children: _jsx("i", { style: { width: `${Math.min(100, v * 200)}%` } }) }), _jsxs("span", { className: "v", children: [(v * 100).toFixed(1), "%"] })] }, k)))] }))] }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-head", children: _jsxs("div", { children: [_jsx("div", { className: "card-title", children: "\u0427\u0443\u0432\u0441\u0442\u0432\u0438\u0442\u0435\u043B\u044C\u043D\u043E\u0441\u0442\u044C \u043A \u0433\u043E\u0440\u0438\u0437\u043E\u043D\u0442\u0443" }), _jsx("div", { className: "card-sub", children: "recall \u043A\u043B\u0430\u0441\u0441\u0430 High \u00B7 \u043C\u043E\u0434\u0435\u043B\u044C vs no-ML" })] }) }), horizon?.rows?.map((r) => (_jsxs("div", { style: {
                                            display: "grid", gridTemplateColumns: "60px 1fr 1fr 60px",
                                            gap: 8, padding: "8px 0", fontSize: 12.5, alignItems: "center",
                                            borderTop: "1px solid oklch(0.28 0.025 250 / 0.4)",
                                        }, children: [_jsxs("div", { className: "mono", style: { color: "var(--fg-1)" }, children: [r.horizon_hours, " \u0447"] }), _jsxs("div", { className: "mono", style: { color: "var(--accent)" }, children: ["ML ", (r.model_recall_high * 100).toFixed(2), "%"] }), _jsxs("div", { className: "mono", style: { color: "var(--fg-3)" }, children: ["BL ", (r.baseline_recall_high * 100).toFixed(2), "%"] }), _jsxs("div", { className: "mono", style: {
                                                    textAlign: "right",
                                                    color: r.delta_recall_high > 0.005 ? "var(--ok)" : "var(--fg-2)",
                                                }, children: [r.delta_recall_high > 0 ? "+" : "", (r.delta_recall_high * 100).toFixed(2)] })] }, r.horizon_hours))), _jsx("div", { style: { fontSize: 11.5, color: "var(--fg-3)", marginTop: 10, lineHeight: 1.55 }, children: "\u041D\u0430 \u0433\u043E\u0440\u0438\u0437\u043E\u043D\u0442\u0435 168 \u0447 \u043C\u043E\u0434\u0435\u043B\u044C \u043E\u043F\u0435\u0440\u0435\u0436\u0430\u0435\u0442 no-ML \u043F\u0440\u0430\u0432\u0438\u043B\u043E \u043D\u0430 1.08 \u043F.\u043F. recall \u2014 \u043E\u0441\u043D\u043E\u0432\u043D\u043E\u0439 \u0430\u0440\u0433\u0443\u043C\u0435\u043D\u0442 \u0446\u0435\u043D\u043D\u043E\u0441\u0442\u0438 ML." })] })] })] })] }));
}
