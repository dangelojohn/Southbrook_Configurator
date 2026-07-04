# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook Room Capture (AI)",
    "summary": "AI-assisted room capture: photograph a kitchen, get a "
               "vision-model estimate that pre-fills the existing "
               "\"Set Up Your Room\" wizard for mandatory human review.",
    "description": """
Southbrook Room Capture
========================

A customer photographs a kitchen (1-5 photos); a vision-capable Claude
model (Sonnet 5) estimates room geometry (layout shape, walls, ceiling
height, constraints such as windows/sinks/appliances) from the photos.

The estimate is NEVER used to create records directly. It is
normalized and handed back to the frontend, which pre-fills the
EXISTING "Set Up Your Room" wizard (southbrook_estimating_website's
RoomSetupWizard) for mandatory human review. Every geometry value
still passes through southbrook.room.validate_geometry before
persistence, exactly as if a human had typed it in — this addon adds
no new persistence path for southbrook.room / .wall / .constraint.

Privacy (test-enforced): images are transient, request-scoped only.
This addon never writes image bytes to ir.attachment, the filestore,
or disk, and never logs image data. Images are downscaled server-side
before the AI call to control cost/tokens.

Components:
* southbrook.room.capture (AbstractModel) — validates/downscales
  images, builds the Anthropic Messages API request, calls it (or
  returns a mock estimate when southbrook_room_capture.use_mock is
  True, the default so cold installs and CI never touch the network),
  and normalizes the response defensively.
* controllers/main.py — one JSON-RPC route:
  POST /southbrook/api/order/<id>/room/analyze-photos.

Frontend (2026-07-04): a "Capture room from photos" / "Re-scan from
photos" entry point on the Order Builder's Room Setup tab, wired to
the endpoint above. A successful, high-enough-confidence estimate
pre-fills RoomSetupWizard (patched to detect the idless "AI prefill"
case and show a dismissible "review before saving" banner); any
failure or low-confidence-with-no-walls response opens the wizard
BLANK for manual entry — the AI output is never trusted to prefill
without that check. See static/src/js/room_capture.esm.js's top-of-
file comment for exactly which file owns which piece of the UI and
why (OrderBuilder's inline-template constraint pushed the button
markup itself into a small, documented, additive edit in
southbrook_estimating_website/static/src/js/portal_boot.esm.js).
""",
    "author": "Southbrook Cabinetry",
    "license": "LGPL-3",
    "category": "Website/eCommerce",
    "version": "19.0.1.0.0",
    "depends": [
        "southbrook_estimating",
        "southbrook_estimating_website",
    ],
    # httpx is imported lazily inside southbrook.room.capture._call_anthropic
    # (guarded exactly like addons/southbrook_ai_design/models/
    # southbrook_gemini_client.py's _call_gemini_real) so the addon installs
    # fine without it — southbrook_room_capture.use_mock defaults to True,
    # so mock mode (no httpx needed) is what cold installs/CI exercise.
    # Pillow is used for server-side image downscaling; it is already a
    # transitive dependency of this codebase (see southbrook_api,
    # southbrook_kitchen_mrp) and is pre-installed on the Odoo 19 image.
    "data": [
        "security/ir.model.access.csv",
    ],
    # 2026-07-04 — frontend assets. Registered in THIS addon's own
    # manifest (not southbrook_estimating_website's) even though this
    # addon `depends` on it — Odoo assembles a shared bundle like
    # web.assets_frontend by walking installed addons in dependency
    # order and concatenating each addon's own asset list, so these
    # entries load AFTER southbrook_estimating_website's
    # room_setup_wizard.esm.js / .xml without any manual ordering
    # trick. room_capture.esm.js patches the (exported, stably-named-
    # template) RoomSetupWizard; room_capture.xml t-inherits that same
    # stable template name. Neither file touches OrderBuilder — that
    # component's inline-template constraint made a cross-addon
    # patch()/t-inherit infeasible, so the "Capture room from photos"
    # button + its handlers are a small additive edit directly in
    # southbrook_estimating_website/static/src/js/portal_boot.esm.js
    # (search that file for "AI ROOM CAPTURE"); this addon's
    # room_capture.scss still owns that button's visual styling via
    # the .sb-capture-* class contract.
    "assets": {
        "web.assets_frontend": [
            "southbrook_room_capture/static/src/js/room_capture.esm.js",
            "southbrook_room_capture/static/src/xml/room_capture.xml",
            "southbrook_room_capture/static/src/scss/room_capture.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
