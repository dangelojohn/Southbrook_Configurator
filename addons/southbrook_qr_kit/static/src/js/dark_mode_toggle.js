/* @odoo-module **/
//
// W038 (R8.5, 2026-06-27) — Night-shift dark mode.
//
// JTBD: "When my shift is 10pm-6am and the bright white UI burns my
// eyes, I want a dark mode that auto-engages or persists across
// sessions."
//
// Adds / removes body.sb-dark-mode based on:
//   1. URL query param ?theme=dark / ?theme=light (highest precedence,
//      bookmarkable; writes to localStorage so the choice survives).
//   2. localStorage key `sb.dark.mode` ("1"/"0").
//   3. Time-of-day auto-engage window (default 22:00 - 06:00 local)
//      — ONLY if (a) no explicit URL or stored preference is set AND
//      (b) the ICP `southbrook.dark_mode.auto_engage` is "1".
//   4. Default: OFF. Day-shift users see ZERO change.
//
// The companion SCSS (dark_mode.scss) is body-class-scoped so when
// the class is absent no rules apply — non-night users see the
// stock light UI.
//
// Runs in both backend (web.assets_backend) and frontend
// (web.assets_frontend) bundles so kanban, scan modal, POD page,
// and traveler-print preview all honour the same toggle.

(function () {
    "use strict";

    const STORAGE_KEY = "sb.dark.mode";
    const BODY_CLASS = "sb-dark-mode";
    // Auto-engage window in local hours: dark from 22:00 inclusive
    // through 06:00 exclusive. Constants here so the test harness can
    // import + assert against the same numbers.
    const AUTO_START_HOUR = 22;
    const AUTO_END_HOUR = 6;

    function applyTheme(on) {
        const body = document.body;
        if (!body) {
            document.addEventListener("DOMContentLoaded", function () {
                applyTheme(on);
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
            const v = params.get("theme");
            if (v === "dark") return true;
            if (v === "light") return false;
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

    function isAutoEngageHour(now) {
        // Returns true when `now`'s local hour falls in the
        // night-shift window (22:00 - 06:00). Pure function so tests
        // can pin a deterministic Date instance.
        const h = now.getHours();
        // 22, 23, 0, 1, 2, 3, 4, 5 are dark; 6..21 are light.
        return h >= AUTO_START_HOUR || h < AUTO_END_HOUR;
    }

    function shouldAutoEngage() {
        // Two-source check, OR'd:
        //   (a) localStorage `sb.dark.auto` === "1" — per-tablet
        //       opt-in. Set via console (`sbDarkMode.enableAuto()`)
        //       or via a future settings UI.
        //   (b) <meta name="sb-dark-auto" content="1"> — optional
        //       server-side hint surfaced by an upstream layout
        //       inherit when the addon owner wants site-wide
        //       auto-engage (gated on the
        //       southbrook.dark_mode.auto_engage ICP).
        // Both default to OFF so day-shift users never get surprised.
        try {
            const local = window.localStorage.getItem("sb.dark.auto");
            if (local === "1") return true;
        } catch (_e) {
            // continue to meta-tag fallback
        }
        try {
            const tag = document.querySelector("meta[name=\"sb-dark-auto\"]");
            if (!tag) return false;
            const v = (tag.getAttribute("content") || "").toLowerCase();
            return v === "1" || v === "true" || v === "yes";
        } catch (_e) {
            return false;
        }
    }

    // Expose a tiny global so devs / power-users can flip from the
    // console: sbDarkMode.on() / off() / toggle() / enableAuto().
    window.sbDarkMode = {
        on() { writeStoredPreference(true); applyTheme(true); },
        off() { writeStoredPreference(false); applyTheme(false); },
        toggle() {
            const next = !document.body.classList.contains(BODY_CLASS);
            writeStoredPreference(next);
            applyTheme(next);
            return next;
        },
        isOn() {
            return document.body.classList.contains(BODY_CLASS);
        },
        enableAuto() {
            try {
                window.localStorage.setItem("sb.dark.auto", "1");
            } catch (_e) {
                /* swallow — private mode */
            }
        },
        disableAuto() {
            try {
                window.localStorage.setItem("sb.dark.auto", "0");
            } catch (_e) {
                /* swallow */
            }
        },
        // Exposed for tests + the smoke harness.
        _internal: {
            STORAGE_KEY,
            BODY_CLASS,
            AUTO_START_HOUR,
            AUTO_END_HOUR,
            isAutoEngageHour,
        },
    };

    // -------- Decide initial state on script load. --------
    const fromURL = readURLOverride();
    if (fromURL !== null) {
        // URL is explicit — persist it then apply.
        writeStoredPreference(fromURL);
        applyTheme(fromURL);
    } else {
        const fromStore = readStoredPreference();
        if (fromStore !== null) {
            // Stored preference wins over auto-engage.
            applyTheme(fromStore);
        } else if (shouldAutoEngage() && isAutoEngageHour(new Date())) {
            // No URL, no stored preference, ICP says auto-engage,
            // and it's currently night-shift hours.
            applyTheme(true);
            // Don't persist — let day-shift users see light when
            // they pick up the tablet at 7am without manual reset.
        } else {
            applyTheme(false);
        }
    }
})();
