/* @odoo-module **/
//
// W039 (R8.1, 2026-06-27) — shop-floor density toggle.
//
// Adds / removes body.sb-shopfloor-dense based on:
//   1. URL query param ?shopfloor=1 / ?shopfloor=0  (highest precedence,
//      bookmarkable; writes to localStorage so the choice survives
//      reload without the query string).
//   2. localStorage key `sb.shopfloor.dense` ("1"/"0").
//   3. Default: OFF (planners / office must not see jumbo controls).
//
// The companion SCSS (shopfloor_dense.scss) is body-class-scoped so
// when the body class is absent ZERO css rules apply — non-shopfloor
// users see no visual change.
//
// Runs in both backend (web.assets_backend) and frontend
// (web.assets_frontend) bundles so the tablet workspace and the
// portal scan UI both honour the same toggle.

(function () {
    "use strict";

    const STORAGE_KEY = "sb.shopfloor.dense";
    const BODY_CLASS = "sb-shopfloor-dense";

    function applyDensity(on) {
        const body = document.body;
        if (!body) {
            // DOM not ready — retry after DOMContentLoaded.
            document.addEventListener("DOMContentLoaded", function () {
                applyDensity(on);
            }, { once: true });
            return;
        }
        if (on) {
            body.classList.add(BODY_CLASS);
        } else {
            body.classList.remove(BODY_CLASS);
        }
    }

    function readURLOverride() {
        try {
            const params = new URLSearchParams(window.location.search);
            const v = params.get("shopfloor");
            if (v === "1" || v === "true") return true;
            if (v === "0" || v === "false") return false;
            return null;
        } catch (_e) {
            return null;
        }
    }

    function readStoredPreference() {
        try {
            const v = window.localStorage.getItem(STORAGE_KEY);
            if (v === "1") return true;
            if (v === "0") return false;
            return null;
        } catch (_e) {
            return null;
        }
    }

    function writeStoredPreference(on) {
        try {
            window.localStorage.setItem(STORAGE_KEY, on ? "1" : "0");
        } catch (_e) {
            // Private mode / quota — silently swallow; URL param is
            // still honoured for this page load.
        }
    }

    // Expose a tiny global so devs / power-users can flip from the
    // console: sbShopfloorDense.on() / off() / toggle().
    window.sbShopfloorDense = {
        on() { writeStoredPreference(true); applyDensity(true); },
        off() { writeStoredPreference(false); applyDensity(false); },
        toggle() {
            const next = !document.body.classList.contains(BODY_CLASS);
            writeStoredPreference(next);
            applyDensity(next);
            return next;
        },
        isOn() {
            return document.body.classList.contains(BODY_CLASS);
        },
    };

    // -------- Decide initial state on script load. --------
    const fromURL = readURLOverride();
    if (fromURL !== null) {
        // URL is explicit — persist it then apply.
        writeStoredPreference(fromURL);
        applyDensity(fromURL);
    } else {
        const fromStore = readStoredPreference();
        applyDensity(fromStore === true);
    }
})();
