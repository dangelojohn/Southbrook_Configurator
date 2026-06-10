/* SPDX-License-Identifier: LGPL-3.0-only
 *
 * Phase 3 Sprint A4 — progressive in-page PDF preview.
 *
 * Looks for any element marked `data-pdf-preview-src="<url>"`.
 * On desktop + Android Chrome/Firefox: replaces it with an inline
 * <iframe> rendering the PDF.
 *
 * On iOS Safari: silently no-ops. Mobile Safari treats PDF in <iframe>
 * as either a blank box or a "download this file" intent, neither of
 * which is what the user wants. The page's existing "Download PDF"
 * button stays visible above us and handles iOS by opening in a new
 * tab (which iOS routes to its native PDF preview).
 *
 * No framework dependency — runs on plain DOMContentLoaded so it
 * works on portal pages that don't load the OWL bundle.
 */
(function () {
    "use strict";

    function isIosSafari() {
        const ua = navigator.userAgent || "";
        // Catches iPhone + iPad including modern "iPad pretends to be Mac"
        // mode where the UA reads as Macintosh but maxTouchPoints > 0.
        const iOS = /iP(ad|hone|od)/.test(ua) ||
                    (ua.includes("Mac") && navigator.maxTouchPoints > 1);
        const safari = /Safari/.test(ua) && !/Chrome|CriOS|FxiOS/.test(ua);
        return iOS && safari;
    }

    function mountPreviews() {
        if (isIosSafari()) return;
        const slots = document.querySelectorAll(
            "[data-pdf-preview-src]",
        );
        slots.forEach((slot) => {
            const src = slot.getAttribute("data-pdf-preview-src");
            if (!src || slot.dataset.pdfPreviewMounted === "1") {
                return;
            }
            const title = slot.getAttribute("data-pdf-preview-title")
                || "Document preview";
            const iframe = document.createElement("iframe");
            iframe.src = src;
            iframe.title = title;
            iframe.loading = "lazy";
            iframe.setAttribute("aria-label", title);
            iframe.style.width = "100%";
            iframe.style.height = "70vh";
            iframe.style.minHeight = "500px";
            iframe.style.border = "1px solid rgba(0,0,0,0.1)";
            iframe.style.borderRadius = "6px";
            iframe.style.background = "#f8f6f0";
            slot.appendChild(iframe);
            slot.dataset.pdfPreviewMounted = "1";
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", mountPreviews);
    } else {
        mountPreviews();
    }
})();
