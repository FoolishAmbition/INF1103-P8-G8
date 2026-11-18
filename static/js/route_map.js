/* Current itinerary only. No coordinates are written to browser storage. */
const EventWiseMap = (() => {
    let map = null;
    let layers = [];
    let markers = [];
    let routePoints = [];
    let legs = [];
    let onSelect = () => {};
    const byId = (id) => document.getElementById(id);
    const valid = (leg) =>
        leg &&
        Array.isArray(leg.geometry) &&
        leg.geometry.length >= 2 &&
        leg.geometry.every(
            (p) =>
                Array.isArray(p) &&
                p.length === 2 &&
                Number.isFinite(p[0]) &&
                Number.isFinite(p[1]) &&
                p[0] >= 1 &&
                p[0] <= 1.7 &&
                p[1] >= 103.4 &&
                p[1] <= 104.6,
        );
    function color(leg) {
        const rail = {
            EW: "#087b40",
            NS: "#c62828",
            NE: "#813bad",
            CC: "#b77600",
            DT: "#1662b5",
            TE: "#8a5533",
        };
        if (leg.mode === "WALK") return "#4c5967";
        if (leg.mode === "BUS") return "#b45100";
        return (
            rail[leg.route] ||
            (["SUBWAY", "RAIL"].includes(leg.mode) ? "#1858b0" : "#7940a1")
        );
    }
    function clear() {
        if (map) {
            map.remove();
            map = null;
        }
        layers = [];
        markers = [];
        routePoints = [];
        legs = [];
        byId("geo-route-map").replaceChildren();
        byId("geo-show-all").onclick = null;
        byId("geo-show-all").disabled = true;
    }
    function showAll() {
        if (!map || !routePoints.length) return;
        layers.forEach((layer) =>
            layer.line.setStyle({ opacity: 0.95, weight: 6 }),
        );
        markers.forEach((marker) => {
            if (marker) {
                marker.setZIndexOffset(0);
                marker.closeTooltip();
            }
        });
        onSelect(-1);
        map.fitBounds(L.latLngBounds(routePoints), {
            padding: [28, 28],
            maxZoom: 16,
        });
        byId("geo-map-message").textContent =
            layers.length < legs.length
                ? "Partial route: some steps have no map geometry. Gaps are not connected."
                : "Whole journey. Select a numbered step or route section for a closer look.";
    }
    function selectStep(index) {
        onSelect(index);
        if (!map) return;
        markers.forEach((marker) => {
            if (marker) marker.closeTooltip();
        });
        const leg = legs[index];
        if (!valid(leg)) {
            byId("geo-map-message").textContent =
                `Step ${index + 1}: map geometry is unavailable. Follow the written directions.`;
            layers.forEach((layer) =>
                layer.line.setStyle({ opacity: 0.4, weight: 5 }),
            );
            return;
        }
        layers.forEach((layer) => {
            const selected = layer.index === index;
            layer.line.setStyle({
                opacity: selected ? 1 : 0.25,
                weight: selected ? 8 : 5,
            });
            if (selected) {
                layer.outline.bringToFront();
                layer.line.bringToFront();
            }
        });
        markers.forEach((marker, i) => {
            if (marker) marker.setZIndexOffset(i === index ? 1000 : 0);
        });
        if (markers[index]) markers[index].openTooltip();
        map.fitBounds(L.latLngBounds(leg.geometry), {
            padding: [40, 40],
            maxZoom: 17,
        });
        const mode =
            {
                WALK: "Walk",
                BUS: "Bus",
                SUBWAY: "MRT",
                RAIL: "Rail",
                TRAM: "Tram",
                FERRY: "Ferry",
            }[leg.mode] || "Travel";
        byId("geo-map-message").textContent =
            `Step ${index + 1}: ${mode}${leg.route ? " " + leg.route : ""} · ${leg.from_name || "Start"} → ${leg.to_name || "End"}`;
    }
    function render(travel, callback = () => {}) {
        clear();
        onSelect = callback;
        const section = byId("geo-map-section");
        const container = byId("geo-route-map");
        const message = byId("geo-map-message");
        section.hidden = !travel || travel.status !== "AVAILABLE";
        container.hidden = true;
        message.textContent = "";
        if (section.hidden) return;
        legs = Array.isArray(travel.legs) ? travel.legs : [];
        if (!legs.some(valid)) {
            message.textContent =
                "Route geometry is unavailable. Use the written directions.";
            return;
        }
        if (typeof L === "undefined") {
            message.textContent =
                "The map library could not load. Your written directions are still available.";
            return;
        }
        try {
            container.hidden = false;
            map = L.map(container, { scrollWheelZoom: false });
            const tiles = L.tileLayer(
                "https://www.onemap.gov.sg/maps/tiles/GreyLite/{z}/{x}/{y}.png",
                {
                    minZoom: 11,
                    maxZoom: 19,
                    attribution:
                        '<img src="https://www.onemap.gov.sg/web-assets/images/logo/om_logo.png" alt="OneMap" style="height:20px;width:20px;"> <a href="https://www.onemap.gov.sg/" target="_blank" rel="noopener noreferrer">OneMap</a> &copy; contributors | <a href="https://www.sla.gov.sg/" target="_blank" rel="noopener noreferrer">Singapore Land Authority</a>',
                },
            );
            tiles.on("tileerror", () => {
                message.textContent =
                    "Some map tiles could not load. Route lines and written directions remain available.";
            });
            tiles.addTo(map);
            legs.forEach((leg, index) => {
                if (!valid(leg)) return;
                const outline = L.polyline(leg.geometry, {
                    color: "#fff",
                    weight: 10,
                    opacity: 0.9,
                    interactive: false,
                }).addTo(map);
                const line = L.polyline(leg.geometry, {
                    color: color(leg),
                    weight: 6,
                    opacity: 0.95,
                    dashArray: leg.mode === "WALK" ? "4 9" : null,
                }).addTo(map);
                line.on("click", () => selectStep(index));
                layers.push({ index, line, outline });
                routePoints.push(...leg.geometry);
                const marker = L.marker(leg.geometry[0], {
                    icon: L.divIcon({
                        className: "geo-map-number",
                        html: `<span>${index + 1}</span>`,
                        iconSize: [28, 28],
                        iconAnchor: [14, 14],
                    }),
                    title: `Step ${index + 1}`,
                    keyboard: true,
                })
                    .addTo(map)
                    .bindTooltip(`Step ${index + 1}`);
                marker.on("click", () => selectStep(index));
                markers[index] = marker;
            });
            const last = legs[legs.length - 1];
            if (valid(last))
                L.marker(last.geometry[last.geometry.length - 1], {
                    icon: L.divIcon({
                        className: "geo-map-finish",
                        html: "<span>End</span>",
                        iconSize: [40, 26],
                        iconAnchor: [20, 13],
                    }),
                    title: "Event destination",
                    keyboard: true,
                })
                    .addTo(map)
                    .bindTooltip("Event destination");
            byId("geo-show-all").onclick = showAll;
            byId("geo-show-all").disabled = false;
            showAll();
            if (layers.length < legs.length)
                message.textContent =
                    "Partial route: some steps have no map geometry. Gaps are not connected.";
            map.invalidateSize();
        } catch (error) {
            clear();
            container.hidden = true;
            message.textContent =
                "The map could not be displayed. Your written directions are still available.";
        }
    }
    return { render, selectStep, showAll };
})();
