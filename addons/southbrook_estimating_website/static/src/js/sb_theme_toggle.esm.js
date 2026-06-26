/** @odoo-module **/
/*
 * Stage 3a of the 2026-06-26 Trade Portal Design System.
 *
 * Injects the theme toggle button (gold-ring focus, .sb-btn--ghost
 * styling) into a fixed-position slot top-right of every portal page,
 * and wires it to flip [data-theme] on <html> + persist the user's
 * preference to localStorage('sb-theme').
 *
 * Pairs with views/design_system_chrome.xml (which inlines the anti-
 * FOUC <script> in <head> so the first paint already reflects the
 * stored or OS-preferred theme).
 *
 * Cross-tab sync via the 'storage' event so the toggle stays in lock-
 * step across multiple Order Builder tabs.
 *
 * Idempotent: re-running this script (e.g. on hot-reload) replaces the
 * existing toggle rather than duplicating it.
 */

(function () {
    "use strict";
    var KEY = "sb-theme";
    var root = document.documentElement;
    var mql = window.matchMedia ? window.matchMedia("(prefers-color-scheme:dark)") : null;

    function resolve() {
        // Light by default; dark only when the user has explicitly opted in
        // via the toggle (which writes 'dark' to localStorage). OS-level
        // prefers-color-scheme is intentionally ignored — the site is a
        // light-mode product first, dark is an opt-in feature.
        var s;
        try { s = localStorage.getItem(KEY); } catch (e) { s = null; }
        return s === "dark" ? "dark" : "light";
    }

    function apply(theme) {
        root.setAttribute("data-theme", theme);
        var toggles = document.querySelectorAll("#sb-theme-toggle");
        for (var i = 0; i < toggles.length; i++) {
            var b = toggles[i];
            var dark = theme === "dark";
            b.setAttribute("aria-pressed", String(dark));
            var icon = b.querySelector(".sb-theme-icon");
            var label = b.querySelector(".sb-theme-label");
            if (icon) icon.textContent = dark ? "☀️" : "🌙";
            if (label) label.textContent = dark ? "Light" : "Dark";
        }
    }

    function injectButton() {
        // Idempotency: drop any existing toggle (e.g. from a prior
        // bundle load on the same page) before re-injecting.
        var existing = document.getElementById("sb-theme-toggle-wrapper");
        if (existing) existing.remove();

        var wrapper = document.createElement("div");
        wrapper.id = "sb-theme-toggle-wrapper";
        // Top: 70px clears the Odoo website header band (~60px tall) and
        // the "Contact Us" CTA that lives at top-right on every portal
        // page, per Claude Chrome's 2026-06-26 visual QA report.
        wrapper.style.cssText =
            "position: fixed; top: 70px; right: 12px; z-index: 1050; " +
            "font-family: 'Inter', sans-serif;";

        var btn = document.createElement("button");
        btn.id = "sb-theme-toggle";
        btn.className = "sb-btn sb-btn--ghost sb-theme-toggle";
        btn.setAttribute("type", "button");
        btn.setAttribute("aria-label", "Toggle dark mode");
        btn.setAttribute("aria-pressed", "false");
        btn.innerHTML =
            '<span class="sb-theme-icon" aria-hidden="true">🌙</span>' +
            '<span class="sb-theme-label">Dark</span>';

        wrapper.appendChild(btn);
        document.body.appendChild(wrapper);

        btn.addEventListener("click", function () {
            var current = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
            try { localStorage.setItem(KEY, current); } catch (e) { /* ignore */ }
            apply(current);
        });
    }

    function init() {
        apply(resolve());
        injectButton();
        // re-apply once button exists so aria-pressed + icon/label sync
        apply(resolve());
    }

    // OS-pref listener removed: site defaults to light regardless of OS pref.
    // Dark is opt-in only via the toggle. Cross-tab sync (below) handles the
    // case where the user toggles in another tab.
    window.addEventListener("storage", function (e) {
        if (e.key === KEY) apply(resolve());
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
