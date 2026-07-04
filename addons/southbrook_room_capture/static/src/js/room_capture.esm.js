/** @odoo-module **/
// SPDX-License-Identifier: LGPL-3.0-only
/*
 * southbrook_room_capture — frontend.
 *
 * This addon adds an "AI room capture" entry point to the customer
 * Order Builder portal: a customer photographs/uploads a kitchen,
 * the photos are sent to this addon's server endpoint
 * (POST /southbrook/api/order/<id>/room/analyze-photos), and the
 * returned geometry estimate PRE-FILLS the EXISTING "Set Up Your
 * Room" wizard (RoomSetupWizard, southbrook_estimating_website) for
 * MANDATORY human review. No southbrook.room / .wall / .constraint
 * record is ever created from the AI output directly — the user
 * still edits + saves normally through the wizard, which validates
 * via southbrook.room.validate_geometry server-side exactly as for
 * hand-typed geometry.
 *
 * WHAT LIVES IN THIS FILE vs. WHAT DOESN'T (read before editing):
 *
 * RoomSetupWizard (below) is `export`ed from room_setup_wizard.esm.js
 * with a stable, file-based qweb template name
 * ("southbrook_estimating_website.RoomSetupWizard") — a normal,
 * supported cross-addon patch()/t-inherit target. This file patches
 * it to (a) fix create-vs-edit detection for an AI-prefilled-but-
 * unsaved room, and (b) surface the "these are estimates, review
 * them" banner (added via room_capture.xml's t-inherit).
 *
 * OrderBuilder (the component with the "Set Up Room" / "Edit Room"
 * CTAs) is NOT patched from here. It is declared
 * `class OrderBuilder extends Component` (no `export`) with
 * `static template = TEMPLATE`, where TEMPLATE is an inline owl
 * `xml\`...\`` tagged-template literal. Odoo's `xml()` helper
 * (odoo/addons/web/static/lib/owl/owl.js) auto-generates an unstable
 * per-page-load template name (`__template__<n>`) for such literals —
 * there is no stable qweb template name for t-inherit to target, and
 * no exported class reference for patch() to target. Forcing this
 * open (exporting the class + duplicating/forking its entire template
 * in this addon) would be fragile: any future edit to that template
 * would silently desync from the fork. Per the brief's own escape
 * hatch for exactly this situation, the "Capture room from photos"
 * button, its hidden file input, and the handlers that call this
 * addon's analyze-photos endpoint are instead a small, clearly
 * commented, additive edit made DIRECTLY in
 * southbrook_estimating_website/static/src/js/portal_boot.esm.js
 * (search that file for "AI ROOM CAPTURE"). That edit only calls the
 * endpoint by URL string — it does not import anything from this
 * addon, and this addon does not import anything from it either, so
 * southbrook_estimating_website keeps working standalone whether or
 * not southbrook_room_capture is installed (the button simply falls
 * back to the "couldn't read the room, enter manually" path if the
 * route 404s). All AI/API surface (the endpoint, the vision-model
 * call, the response contract) is 100% owned by this addon; only that
 * thin UI hook lives in the other file. The visual styling of that
 * button/spinner/error (the .sb-capture-* classes) is still owned
 * here, in room_capture.scss.
 */
import { patch } from "@web/core/utils/patch";
import { RoomSetupWizard } from "@southbrook_estimating_website/js/room_setup_wizard.esm";

patch(RoomSetupWizard.prototype, {
    setup() {
        super.setup();

        const existingRoom = this.props.existingRoom || null;

        // ------------------------------------------------------------
        // id-aware isEdit fix + AI-estimate detection.
        //
        // The base setup() sets:
        //   isEdit: !!existingRoom
        //   roomId: existingRoom ? existingRoom.id : null
        //
        // That's correct for the two cases it was written for (no
        // existingRoom = fresh create; existingRoom with an id = edit
        // a saved room) but wrong for a THIRD case this addon
        // introduces: existingRoom present but WITHOUT an id — the
        // shape returned by /room/analyze-photos' `existing_room` key
        // (explicitly documented as "NO id fields"). Today, the ONLY
        // way this component receives a truthy existingRoom with no
        // `.id` is the AI-capture path (a real saved-room edit always
        // carries existingRoom.id; a real fresh-create click always
        // passes existingRoom=null). That makes
        // "existingRoom truthy && !existingRoom.id" an exact, robust
        // signal for "this came from the AI estimate" — no extra prop
        // or cross-addon singleton needed, and no way for it to
        // misfire on the two pre-existing cases.
        //
        // For that case we correct isEdit/roomId/maxStepReached back
        // to "create" semantics (nothing is persisted yet — the user
        // must still complete + submit the wizard, which calls
        // /room/create, not /room/<id>/update) and flag state so the
        // template can show the "review before saving" banner.
        // ------------------------------------------------------------
        const aiPrefill = !!(existingRoom && !existingRoom.id);

        if (aiPrefill) {
            this.state.isEdit = false;
            this.state.roomId = null;
            this.state.maxStepReached = 1;
        }

        this.state.aiEstimated = aiPrefill;
        this.state.aiAssumptions = (aiPrefill && Array.isArray(existingRoom.assumptions))
            ? existingRoom.assumptions
            : [];
        this.state.aiWarnings = (aiPrefill && Array.isArray(existingRoom.warnings))
            ? existingRoom.warnings
            : [];
        this.state.aiBannerDismissed = false;
    },

    // Dismiss control for the banner injected by room_capture.xml.
    _sbDismissAiBanner() {
        this.state.aiBannerDismissed = true;
    },
});
