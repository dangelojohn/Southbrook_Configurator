/** @odoo-module **/
// SPDX-License-Identifier: LGPL-3.0-only
//
// W037 (R8.4, 2026-06-27) — Offline scan queue, client-side glue.
//
// Responsibilities:
//   1. Register the Service Worker at `/southbrook_qr_kit/static/src/js/offline_scan_sw.js`
//      scoped to `/sb/qr/`.
//   2. Mint + attach `client_uuid` (uuid v4) to every outgoing
//      `/sb/qr/*` POST so the controller can dedup on replay.
//   3. Render a small status badge in the corner of the screen
//      reflecting queue depth and drain state. Three states:
//        * `online_synced`  — green dot, hidden when count=0
//        * `queued_offline` — yellow badge, "N QUEUED"
//        * `draining`       — blue spinner badge, "Syncing N…"
//   4. Push a `sb-drain` message to the SW on `online` events at
//      the page level (the SW's own `online` listener is best-effort
//      across browsers).
//
// Compatibility: bails out gracefully on browsers without
// `serviceWorker` (e.g. old Safari in private mode) — caller still
// works, just without offline queueing.
//
// Mount: a tiny IIFE runs on import. The badge attaches to
// document.body once at first DOM-ready.

const SW_PATH = "/southbrook_qr_kit/static/src/js/offline_scan_sw.js";
const SW_SCOPE = "/sb/qr/";
const STORAGE_UUID_KEY = "southbrook.qr_kit.client_uuid";
const SCAN_URL_FRAGMENTS = [
    "/sb/qr/scan",
    "/sb/qr/shipping/load-unit",
    "/sb/qr/inventory/bin-scan",
    "/sb/qr/pod/submit",
];

// ----------------------------------------------------------------------
// uuid v4 — RFC 4122 §4.4. Uses crypto.getRandomValues when available,
// falls back to Math.random (acceptable for dedup key uniqueness; not
// security-critical).
// ----------------------------------------------------------------------
function uuidv4() {
    const bytes = new Uint8Array(16);
    if (window.crypto && window.crypto.getRandomValues) {
        window.crypto.getRandomValues(bytes);
    } else {
        for (let i = 0; i < 16; i++) {
            bytes[i] = Math.floor(Math.random() * 256);
        }
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0"));
    return (
        hex.slice(0, 4).join("") +
        "-" +
        hex.slice(4, 6).join("") +
        "-" +
        hex.slice(6, 8).join("") +
        "-" +
        hex.slice(8, 10).join("") +
        "-" +
        hex.slice(10, 16).join("")
    );
}

// One UUID per outgoing scan, NOT per device — the per-device uuid is
// just used as a debug-correlation aid in the User-Agent-ish slot.
// `client_uuid` per payload is what the server dedups on.
function scanUuid() {
    return uuidv4();
}

// ----------------------------------------------------------------------
// Patch the global fetch so every /sb/qr/* POST gets a `client_uuid`
// attached. We do this in addition to (not instead of) the SW
// interception so the dedup key is present even when the SW is asleep
// and the request goes direct.
// ----------------------------------------------------------------------
function patchFetch() {
    if (window.__sbScanFetchPatched) {
        return;
    }
    const orig = window.fetch.bind(window);
    window.fetch = async function (input, init) {
        try {
            const url = typeof input === "string" ? input : (input && input.url);
            const method = (init && init.method) || (input && input.method) || "GET";
            if (
                url &&
                method.toUpperCase() === "POST" &&
                SCAN_URL_FRAGMENTS.some((f) => url.includes(f))
            ) {
                init = init || {};
                init.headers = init.headers || {};
                let bodyObj = null;
                if (typeof init.body === "string" && init.body) {
                    try {
                        bodyObj = JSON.parse(init.body);
                    } catch (e) {
                        bodyObj = null;
                    }
                }
                if (bodyObj && typeof bodyObj === "object") {
                    // JSON-RPC envelope (Odoo type=json controllers)
                    // — payload lives under `params`.
                    if (bodyObj.params && typeof bodyObj.params === "object") {
                        if (!bodyObj.params.client_uuid) {
                            bodyObj.params.client_uuid = scanUuid();
                        }
                    } else if (!bodyObj.client_uuid) {
                        bodyObj.client_uuid = scanUuid();
                    }
                    init.body = JSON.stringify(bodyObj);
                }
            }
        } catch (e) {
            // Never let the patch break a real request.
        }
        return orig(input, init);
    };
    window.__sbScanFetchPatched = true;
}

// ----------------------------------------------------------------------
// Badge UI — single span + small CSS, no framework dep so it works
// inside both backend (OWL) and frontend (vanilla) bundles.
// ----------------------------------------------------------------------
function mountBadge() {
    if (document.getElementById("sb-offline-scan-badge")) {
        return;
    }
    if (!document.body) {
        // DOM not ready yet — defer.
        document.addEventListener("DOMContentLoaded", mountBadge, {once: true});
        return;
    }
    const css = document.createElement("style");
    css.textContent = (
        "#sb-offline-scan-badge {" +
        "  position: fixed; right: 12px; bottom: 12px; z-index: 9999;" +
        "  font-family: system-ui, -apple-system, sans-serif;" +
        "  font-size: 13px; font-weight: 600; padding: 6px 10px;" +
        "  border-radius: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.18);" +
        "  cursor: default; user-select: none;" +
        "}" +
        "#sb-offline-scan-badge.sb-hidden { display: none; }" +
        "#sb-offline-scan-badge.sb-state-queued {" +
        "  background: #fff3bf; color: #5c4400; border: 1px solid #ffd43b;" +
        "}" +
        "#sb-offline-scan-badge.sb-state-draining {" +
        "  background: #d0ebff; color: #0b4d8b; border: 1px solid #74c0fc;" +
        "}" +
        "#sb-offline-scan-badge.sb-state-online {" +
        "  background: #d3f9d8; color: #155724; border: 1px solid #69db7c;" +
        "}"
    );
    document.head.appendChild(css);
    const span = document.createElement("span");
    span.id = "sb-offline-scan-badge";
    span.className = "sb-hidden";
    span.setAttribute("aria-live", "polite");
    document.body.appendChild(span);
}

function renderBadge(state, size) {
    const el = document.getElementById("sb-offline-scan-badge");
    if (!el) {
        return;
    }
    el.classList.remove(
        "sb-state-online",
        "sb-state-queued",
        "sb-state-draining",
        "sb-hidden",
    );
    if (state === "queued") {
        el.classList.add("sb-state-queued");
        el.textContent = size + " QUEUED";
    } else if (state === "draining") {
        el.classList.add("sb-state-draining");
        el.textContent = size > 0 ? "Syncing " + size + "…" : "Syncing…";
    } else {
        // idle / online
        if (!size || size <= 0) {
            el.classList.add("sb-hidden");
            el.textContent = "";
        } else {
            el.classList.add("sb-state-online");
            el.textContent = size + " queued";
        }
    }
}

// ----------------------------------------------------------------------
// Service Worker registration + messaging.
// ----------------------------------------------------------------------
async function registerSw() {
    if (!("serviceWorker" in navigator)) {
        return null;
    }
    try {
        const reg = await navigator.serviceWorker.register(SW_PATH, {
            scope: SW_SCOPE,
        });
        navigator.serviceWorker.addEventListener("message", (event) => {
            const data = event.data || {};
            if (data.type === "sb-queue") {
                renderBadge(data.state, data.size);
            }
        });
        // Ask the SW for current queue depth so the badge is correct
        // even on a soft reload mid-outage.
        const send = (msg) => {
            const ctrl = navigator.serviceWorker.controller;
            if (ctrl) {
                ctrl.postMessage(msg);
            }
        };
        send({type: "sb-queue-size"});
        window.addEventListener("online", () => send({type: "sb-drain"}));
        return reg;
    } catch (e) {
        // SW registration fails on insecure origins (http:// non-localhost).
        // The patched-fetch dedup still works without it — the operator
        // just loses the offline queue.
        return null;
    }
}

// ----------------------------------------------------------------------
// Bootstrap.
// ----------------------------------------------------------------------
(function init() {
    try {
        // Ensure a persistent per-device UUID lands in localStorage —
        // some downstream tools (forensic correlation) want a stable
        // device id even though dedup is per-scan.
        if (!window.localStorage.getItem(STORAGE_UUID_KEY)) {
            window.localStorage.setItem(STORAGE_UUID_KEY, uuidv4());
        }
    } catch (e) {
        // localStorage unavailable in some private-browsing modes.
    }
    patchFetch();
    mountBadge();
    registerSw();
})();

// Expose a tiny test handle so manual smoke tests can poke the SW.
window.sbScanQueue = {
    uuidv4: uuidv4,
    drainNow: () => {
        const ctrl = navigator.serviceWorker && navigator.serviceWorker.controller;
        if (ctrl) {
            ctrl.postMessage({type: "sb-drain"});
        }
    },
};
