import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useEffect, useRef } from "react";
import L from "leaflet";
import { useData } from "../lib/useData";
import NotificationsBell from "../components/NotificationsBell";
function makeIcon(status) {
    return L.divIcon({
        className: "",
        html: `<div class="gg-marker ${status}" style="position:relative"></div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
    });
}
export default function MapsPage() {
    const { data } = useData("maps.json");
    const containerRef = useRef(null);
    const mapRef = useRef(null);
    const markerById = useRef({});
    useEffect(() => {
        if (!containerRef.current || !data)
            return;
        if (mapRef.current)
            return; // already initialised
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
                .bindPopup(`<div style="font-family:Inter,sans-serif;color:#0a0e16;">
            <div style="font-weight:600;font-size:13px">${s.name}</div>
            <div style="font-size:11px;color:#444;margin-top:2px">${s.city} · ${s.voltage}</div>
            <div style="font-size:11px;color:#444">Единиц: ${s.n_units}</div>
            <div style="font-family:JetBrains Mono,monospace;font-size:12px;margin-top:6px;font-weight:600;color:${s.status === "crit" ? "#c43328" : s.status === "warn" ? "#a37500" : "#1f8f54"}">Риск 72ч: ${s.max_probability_pct.toFixed(1)}%</div>
          </div>`);
            markerById.current[s.id] = mk;
        });
        if (data.suggested_route.length >= 2) {
            const latlngs = data.suggested_route.map((r) => [r.lat, r.lon]);
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
    const focus = (s) => {
        const m = mapRef.current;
        if (!m)
            return;
        m.flyTo([s.lat, s.lon], 5, { duration: 0.6 });
        const mk = markerById.current[s.id];
        if (mk)
            mk.openPopup();
    };
    return (_jsxs(_Fragment, { children: [_jsxs("div", { className: "topbar", children: [_jsxs("div", { className: "topbar-title", children: [_jsx("div", { className: "page-eyebrow", children: "\u041A\u0430\u0440\u0442\u0430 \u00B7 10 \u043F\u043E\u0434\u0441\u0442\u0430\u043D\u0446\u0438\u0439 \u043F\u0438\u043B\u043E\u0442\u0430" }), _jsx("h1", { className: "page-title", children: "\u0413\u0435\u043E\u0433\u0440\u0430\u0444\u0438\u044F \u0440\u0438\u0441\u043A\u0430" }), _jsx("div", { className: "page-sub", children: "\u0442\u0451\u043C\u043D\u0430\u044F \u043A\u0430\u0440\u0442\u0430 CartoDB \u00B7 \u043C\u0430\u0440\u043A\u0435\u0440\u044B \u043F\u043E \u0443\u0440\u043E\u0432\u043D\u044E \u0440\u0438\u0441\u043A\u0430 \u00B7 \u043C\u0430\u0440\u0448\u0440\u0443\u0442 \u0431\u0440\u0438\u0433\u0430\u0434\u044B \u043F\u043E \u043A\u0440\u0438\u0442\u0438\u0447\u0435\u0441\u043A\u0438\u043C \u0443\u0437\u043B\u0430\u043C" })] }), _jsxs("div", { className: "topbar-actions", children: [_jsx(NotificationsBell, {}), _jsxs("button", { className: "btn-primary", children: [_jsx("svg", { style: { width: 14, height: 14 }, children: _jsx("use", { href: "#i-route" }) }), "\u041D\u0430\u0437\u043D\u0430\u0447\u0438\u0442\u044C \u043C\u0430\u0440\u0448\u0440\u0443\u0442"] })] })] }), _jsxs("div", { className: "map-shell", children: [_jsx("div", { className: "card map-card", children: _jsx("div", { ref: containerRef, style: { height: 540, width: "100%" } }) }), _jsxs("div", { className: "card", children: [_jsx("div", { className: "card-head", children: _jsxs("div", { children: [_jsx("div", { className: "card-title", children: "\u041C\u0430\u0440\u0448\u0440\u0443\u0442 \u0431\u0440\u0438\u0433\u0430\u0434\u044B" }), _jsx("div", { className: "card-sub", children: data?.route_strategy })] }) }), (!data || data.suggested_route.length === 0) && (_jsx("div", { style: { color: "var(--fg-3)", fontSize: 13 }, children: "\u041D\u0435\u0442 \u043A\u0440\u0438\u0442\u0438\u0447\u0435\u0441\u043A\u0438\u0445 \u043F\u043E\u0434\u0441\u0442\u0430\u043D\u0446\u0438\u0439 \u2014 \u0432\u044B\u0435\u0437\u0434 \u043D\u0435 \u0442\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044F." })), _jsx("div", { className: "route-list", children: data?.suggested_route.map((s) => (_jsxs("div", { className: "route-item", onClick: () => focus(s), children: [_jsx("div", { className: "route-num", children: s.order }), _jsxs("div", { children: [_jsx("div", { className: "route-name", children: s.id }), _jsx("div", { className: "route-sub", children: s.name })] }), _jsxs("div", { style: { fontFamily: "JetBrains Mono, monospace", fontWeight: 600, color: "var(--crit)" }, children: [s.max_probability_pct.toFixed(1), "%"] })] }, s.id))) }), data && (_jsxs(_Fragment, { children: [_jsx("div", { className: "card-head", style: { marginTop: 18 }, children: _jsxs("div", { children: [_jsx("div", { className: "card-title", children: "\u0421\u0432\u043E\u0434\u043A\u0430 \u043F\u043E \u043F\u043E\u0434\u0441\u0442\u0430\u043D\u0446\u0438\u044F\u043C" }), _jsx("div", { className: "card-sub", children: "10 \u0443\u0437\u043B\u043E\u0432 \u043F\u0438\u043B\u043E\u0442\u043D\u043E\u0433\u043E \u0440\u0430\u0437\u0432\u0451\u0440\u0442\u044B\u0432\u0430\u043D\u0438\u044F" })] }) }), _jsx("div", { style: { display: "flex", flexDirection: "column", gap: 6 }, children: data.substations.map((s) => (_jsxs("div", { style: {
                                                display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center",
                                                padding: "6px 8px", borderRadius: 8, fontSize: 12.5,
                                                background: s.status === "crit" ? "var(--crit-soft)" : s.status === "warn" ? "var(--warn-soft)" : "transparent",
                                            }, children: [_jsxs("div", { children: [_jsx("span", { style: { fontFamily: "JetBrains Mono, monospace", fontWeight: 600 }, children: s.id }), _jsxs("span", { style: { color: "var(--fg-3)", marginLeft: 6 }, children: [s.city, " \u00B7 ", s.voltage] })] }), _jsxs("span", { className: `tag ${s.status}`, children: [_jsx("span", { className: "dot" }), s.max_probability_pct.toFixed(0), "%"] })] }, s.id))) })] }))] })] })] }));
}
