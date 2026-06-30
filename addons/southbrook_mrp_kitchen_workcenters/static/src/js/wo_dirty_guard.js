/** @odoo-module **/
// W075 (R8.12, 2026-06-27) — onbeforeunload guard on dirty WO form.
//
// Tablet operators on the shop floor accidentally swipe-back (Android
// gesture nav) or tap the browser back button mid-edit on an
// in-progress mrp.workorder and lose every field they touched (lot
// scan, qty produced, MI check answers). The native Odoo "Discard?"
// dialog only fires for in-app navigation — it does NOT intercept
// browser-level navigation, page reloads, or the OS back gesture.
//
// Solution: a global beforeunload listener that:
//   1. Looks for a form view whose record has unsaved edits
//      (`.o_form_dirty` is the well-known marker Odoo adds to the
//      <div class="o_form_view"> root when the record is modified).
//   2. Fires the native browser "are you sure?" dialog ONLY when
//      that marker is present.
//   3. Stays silent on read-only forms, clean forms, and non-form
//      pages (kanban / list / dashboards).
//
// Browser behavior:
//   * The exact dialog text is browser-controlled (security: the
//     page cannot customize the string in Chrome/Edge/Safari since
//     2017). Setting `event.returnValue` to any non-empty string
//     triggers the prompt; the browser shows its own copy.
//   * `preventDefault()` plus `returnValue` is the canonical
//     cross-browser idiom — covered for both Chromium and WebKit.
//
// Why not OWL-specific: hooking the form controller would couple us
// to Odoo's internal hook API. The DOM marker `o_form_dirty` is
// public and stable since v14 — far safer for a tiny utility.

(function () {
    "use strict";

    if (window.__sbk_wo_dirty_guard_installed) {
        return;
    }
    window.__sbk_wo_dirty_guard_installed = true;

    function isAnyFormDirty() {
        // Odoo tags the open form's root element with `o_form_dirty`
        // whenever the user has typed in any field on an editable
        // record. The class is removed on save / discard.
        const forms = document.querySelectorAll(".o_form_view");
        for (const f of forms) {
            if (f.classList.contains("o_form_dirty")) {
                return true;
            }
        }
        return false;
    }

    function onBeforeUnload(event) {
        if (!isAnyFormDirty()) {
            return undefined;
        }
        // Triggers the native prompt. Modern browsers ignore the
        // custom string for security but still need a truthy value.
        const msg = "You have unsaved changes on this work order. "
                  + "Leave the page and lose them?";
        event.preventDefault();
        event.returnValue = msg;
        return msg;
    }

    window.addEventListener("beforeunload", onBeforeUnload);
})();
