# Southbrook Production Media (DMS) — Design Spec

**Date:** 2026-07-25
**Status:** Approved (design) — ready for implementation planning
**Deploy target:** Live Southbrook v19 CE instance (`southbrook` DB, `southbrook-odoo` under system-docker on QNAP)

## Goal

Give Southbrook a Community-Edition document-management system for **photos and videos of manufactured parts**, organized **by Product and by Manufacturing Order (MO)**, by porting **OCA `dms` 18.0 → 19.0 CE** as the source and adding a thin Southbrook bridge. v1 is the **foundation**: ported DMS + product/MO organization + manual upload + in-Odoo viewing (photos and video). Live cameras and automated capture come later.

## Why this source

- Porterly's v16 "DMS" is a bought **Synconics `res_documents`** module (+ OCA `document_page`, which is a wiki, not a file store) — porting bought code forward is a rewrite and conflicts with the CE-native-replacement doctrine.
- Odoo's Enterprise **Documents** app is not available in CE (not installed on prod; Enterprise-only).
- OCA **`dms`** is purpose-built for binary file storage (folders, tags, categories, per-record embedding), **LGPL-3**, and community-maintained. Its `19.0` branch currently exists but is an **empty stub** (scaffolding only, "Initial commit" 2025-09-30), so v19 must be **ported from 18.0** (`dms` core = `18.0.1.1.1`).

## Locked decisions

| # | Decision |
|---|---|
| 1 | **Foundation first.** v1 = ported DMS + product/MO organization + manual upload + view (photos & video). Camera/auto-capture deferred. |
| 2 | **Storage nested, single source of truth:** `Products → [Product] → Orders → [MO]`. Files stored once, never duplicated. **Plus** a flat MO-centric access path (smart button on each MO + a top-level "Manufacturing Orders Media" listing) — satisfying "both" (co-location *and* direct as-built access). |
| 3 | **Forms:** inline gallery (via `dms_field`) **and** a header smart button "Photos/Videos (N)" — on both Product and MO forms. |
| 4 | **Video:** inline HTML5 playback in the gallery/preview; files stored in the **filestore (disk), not the DB**. |
| 5 | **Access:** internal-only. All staff view+upload; a new "Production Media Manager" group manages structure/deletions. No portal/external access in v1. |
| 6 | **Panel integration — REFINED by Addendum A (2026-07-25).** Originally deferred; the user then explicitly directed that capture/save/**view + interactivity** of QC media happen *inside* the Process Explorer Miller-column Media area. So v1 now adds **View / Capture / Annotate** modes to that panel (opt-in, read-only preserved by default). Deeper "twin" surfacing, live camera, and time-lapse remain deferred. See Addendum A. |
| 7 | **Shipping is in scope (Addendum A).** The system serves QC during manufacturing **and shipping**, so the bridge anchor accepts `stock.picking` in addition to `product.template` and `mrp.production`, with a "Shipping QC" node in the Miller tree. |
| 8 | **Generalized to all manufacturing (Addendum A).** All capture/annotate/view components are generic on `res_model`/`res_id` — no kitchen/cabinetry/product-category-specific logic anywhere in the code path. |

## Architecture & modules

Three modules, deployed together:

- **`dms`** — OCA core, **ported 18.0 → 19.0**, kept under the **same technical name** so we can later rebase onto OCA's official 19.0 with no rename migration. Minimal functional change — port only what v19 requires.
- **`dms_field`** — OCA (`18.0.1.2.2`), ported 18.0 → 19.0. Provides the embeddable "DMS folder inside a record" widget used for the inline gallery.
- **`sb_production_media`** — new Southbrook bridge (the only bespoke module). Owns folder auto-organization, Product/MO linkage, smart buttons, video inline preview, access group, and the forward-compat ingest API.

**Skipped for v1:** `dms_user_role` (pulls in `base_user_role`), `web_editor_media_dialog_dms` (website editor, AGPL), `dms_auto_classification` (rules engine).

**Dependencies (all CE, verified installed on prod):** `dms` depends on `mail, http_routing, onboarding, portal, base, web`. `sb_production_media` depends on `dms, dms_field, product, mrp`.

## Data model & folder structure

One DMS **storage** — "Southbrook Production Media", **filestore** backend.

Physical directory tree (single source of truth):
```
Products
 └─ [Product]                 ← reference/design media (drawings, reference 3D, spec photos)
     └─ Orders
         └─ [MO]              ← as-built finished-part photos/videos (this run)
Shipping                      ← (Addendum A) QC media captured at the shipping stage
 └─ [Delivery / stock.picking]  ← packing/condition-at-ship photos, damage evidence
```

**Bridge mechanism (refined by the dms_field analysis):** reuse `dms_field`'s
`dms.field.mixin` + `dms.field.template` rather than hand-rolling directory
records. Inherit `dms.field.mixin` onto `product.template`, `mrp.production`,
**and `stock.picking`** (Addendum A); add one `dms.field.template` per model
(which auto-creates the per-record directory *and* a per-record `dms.access.group`,
giving internal-only ACL and cascade cleanup for free — avoiding the Porterly-style
IDOR risk of hand-rolled directories). The base `dms.directory` already carries
generic `res_model`/`res_id`; we add `sb_dir_kind` (Selection: `product` / `mo`
/ `shipping` / `structural`) only to classify auto-managed folders and drive the
flat listing and the Miller-tree nodes.

**Folder lifecycle:** get-or-created **lazily** on first open/upload via helper methods:
- `product.template._get_media_directory()` → returns/creates the product's directory under the `Products` root.
- `mrp.production._get_media_directory()` → returns/creates the MO's directory under `[its product]/Orders`, creating the product dir + `Orders` intermediary as needed.
- An admin server action **"Backfill media folders"** to pre-create folders for existing products/MOs (optional; lazy creation covers normal use).

**Flat MO access:** a top-level menu **"Manufacturing Orders Media"** = an action on `dms.directory` filtered to `sb_dir_kind = 'mo'`, so every MO folder is reachable regardless of nesting depth.

## UX surfaces

- **Product form & MO form:** a **"Media" notebook tab** containing the **inline `dms_field` gallery** (thumbnails, drag-drop upload) bound to the record's directory, **plus** a header **smart button "Photos/Videos (N)"** (N = file count in the directory subtree) that opens the full DMS file view scoped to that folder.
- **Video:** the file preview widget renders an HTML5 `<video controls>` for `video/*` mimetypes (extends DMS's existing image/PDF preview); images keep the existing lightbox/preview.
- **DMS app:** the ported standard DMS UI (kanban/list file manager, search panel, upload) for bulk work, plus the flat "Manufacturing Orders Media" listing.
- **Process Explorer Media area (Addendum A):** the Miller-column Media panel gains **View / Capture / Annotate** modes — native-camera capture, Canvas-2D defect annotation, per-media QC status, and inline `<video>` playback — with a chatter-backed audit trail. See Addendum A for the full v1/phase2 split.

## Access & security (internal-only v1)

- New group **`sb_production_media.group_media_manager`** ("Production Media Manager"): manages storage/directory structure and deletions.
- All internal users (`base.group_user`): view + upload files, create MO/product folders via the lazy helpers.
- No portal/public access; DMS share-links disabled in v1.
- DMS's `dms_security_mixin` / access-groups drive record rules; the bridge seeds sane defaults so auto-created folders inherit internal-only visibility.

## Port approach & risks

Port faithfully, applying the catalogued v19 deprecations (each already burned once and recorded):
- Asset-bundle declaration + cache-busting (restart bumps hash).
- `res.users` `groups_id` → `group_ids`; `res.groups.category_id` removed.
- `_sql_constraints` → `models.Constraint` (silently ignored in v19 otherwise).
- OWL/registry API drift in the **~615-line front-end** (custom kanban+list file views, controllers/renderers, `dms_file_upload` widget, `preview_binary` and `path_json` OWL fields) — **the single biggest risk**.
- `@api.depends` correctness (wrong field silently breaks the registry).
- View-validation traps (manual/`x_` fields, `column_invisible` parent resolution).

**Mitigations:** port on a branch; run OCA's own dms test suite (ported) + bridge tests on an isolated DB; a **staging soak** before prod; keep module names identical for a clean future rebase onto official OCA 19.0.

**Other constraints/risks:**
- Large video uploads can exceed Odoo's upload cap and the **Caddy request-body limit**. The network/proxy layer is owner-owned — v1 will **document a per-file size guidance** and surface a clear error, not modify the proxy.
- Confirm `onboarding` module behaves in v19 CE (dms depends on it); trim the DMS onboarding steps if they don't port cleanly.

## Testing

- **Ported `dms`/`dms_field`:** run the modules' bundled tests on an isolated DB (`test_sbdms`); the OWL file views verified rendering on staging.
- **`sb_production_media` bridge tests:** get-or-create product dir; get-or-create MO dir with `Orders` intermediary + product-dir auto-create; nesting correctness; smart-button count reflects subtree; `sb_dir_kind` classification; flat MO action domain; `video/*` file stored to filestore + preview mimetype branch; internal-only ACL (portal user denied); the forward-compat ingest API creates the right MO folder and drops a file.

## Deploy

Same safe pattern as the Materials module (gated on explicit go-ahead):
1. Pre-deploy DB backup (verified readable).
2. rsync `dms`, `dms_field`, `sb_production_media` to the host addons path.
3. Single consolidated `-i dms,dms_field,sb_production_media --stop-after-init --no-http` on live `southbrook`.
4. Restart `southbrook-odoo` (assets/menus changed).
5. Smoke test: modules `installed`; Media tab + smart button on a Product and an MO; upload a photo and a video; video plays inline.

## Addendum A (2026-07-25): QC media interactivity — blindspot + ReAct ≥7/10 pass

A multi-agent blindspot pass + ReAct completeness-critic loop investigated the best CE-native methods to **capture, save, and view interactive still/video media for QC during manufacturing and shipping, integrated into the Miller-column Process Explorer Media area, generalized across all manufacturing types**. 78 candidates were adversarially scored; **only ≥7/10 were kept** (4 survived). This addendum refines the v1 scope with their cheap, high-leverage subset and defers the risky remainder.

### Findings kept (≥7/10)
| Score | Finding | Kind | Disposition |
|---|---|---|---|
| 7 | **On-device / canvas photo annotation & defect markup** (two convergent findings) — mark circles/arrows/text on a still to pinpoint defects | capture/qc | **v1** (native Canvas 2D, JSON strokes) |
| 7 | **Routing-step media checklist template** — enforce required media per step before completion | integration | **v1** as *generic* MO/picking-level required-media flag; discrete routing-step version → phase2 |
| 7 | **Time-lapse video recording** (getUserMedia/MediaRecorder) for process observation (curing, assembly) | capture | **phase2** (periodic-frame approach; gated on ACL audit + resumable upload + codec detection) |

### v1 additions (foundation preserved; these are the cheap, high-value pulls)
1. **Native-camera still capture** — add `capture="environment"` to the media panel's file-input, so "Add Media" on a phone/tablet opens the camera directly. Pure HTML attribute, no getUserMedia.
2. **Shipping anchor** — extend the bridge to accept **`stock.picking`** and add a **"Shipping QC"** node in the Miller tree (closes the manufacturing-only gap vs. the hard constraint).
3. **Non-destructive annotation overlay** — Canvas-2D (NOT fabric.js — avoids the flagged dependency-maintenance risk), basic shapes (circle/arrow/text), strokes stored as an `annotation_data` JSON field **separate from the untouched original** binary; small payloads (respects the Caddy body limit).
4. **Free audit trail** — every annotation save/clear posts a timestamped, user-attributed chatter note on the parent MO/picking via the panel's *existing* chatter write path (no new audit model; append-only).
5. **Generic required-media checklist** — an MO-level *and* picking-level `media_required` flag, independent of routing steps, so **discrete AND process/continuous** manufacturing get a basic compliance gate.
6. **HTML5 `<video controls>` playback** with a poster thumbnail (generated on upload) in the viewer pane for any filestore video — decoupled from capture, so phone-recorded/manually-uploaded clips are usable immediately.
7. **Per-media QC status** enum (Unreviewed / Pass / Flag-for-Review) settable inline from the viewer.
8. **Panel mode toggle** — View | Capture | Annotate in the panel header; read-only-plus-chatter preserved by default, new write surfaces opt-in.
9. **Pre-ship ACL audit** — because v1 adds write surfaces (upload, annotate, flag) beyond today's read-only panel, run the DMS record-rule/ACL audit (scope by MO/product/picking ownership + role) *before* v1 ships.
10. **Architecture guardrails** — all new widgets are OWL components reading/writing through the *existing* DMS-bridge RPC layer (no parallel API), and every component is generic on `res_model`/`res_id` (no kitchen-specific logic).

### Deferred to phase2 (real risk, not yet solved — do NOT ship early)
- Full getUserMedia + MediaRecorder **time-lapse** (periodic-frame pipeline) — gated on: completed DMS ACL audit, resumable/chunked upload, Safari-safe codec detection.
- **Storage retention/quota policy** (max-days, max-resolution, auto-archive) enforced by cron — filestore disk exhaustion is a real QNAP risk.
- **Touch-precision markup** (zoom-to-annotate, pinch-zoom, stylus) — validate on real iPad/phone before rollout.
- **Role-gated** annotation clear/overwrite (QC-manager can delete; any user can add).
- **Miller media-column lazy-load/pagination** past ~30–50 items.
- **Discrete routing-step (`mrp.routing.workcenter`-keyed) checklist** layer, and separate **process/continuous checklist semantics** (lot/batch or time-window keyed) — the "generalizes across ALL manufacturing" claim does not hold for the routing-step model without this rework.
- Time-lapse capture at the **shipping dock** (same phase2 pipeline).

## Deferred / roadmap (recorded so nothing is forgotten)

| Item | Notes |
|---|---|
| **Process Explorer panel — deep "twin" surfacing** | v1 now adds View/Capture/Annotate media modes to the Miller-column Media area (Addendum A). Still deferred: surfacing DMS media inside the legacy Drawing/3D "twin" tabs and a unified media-per-step twin view. |
| **Live camera feeds — Reolink RLC-820A (4K/8MP PoE)** | RTSP (H.264/H.265, ONVIF) → the deferred Process Explorer **Live tab** via an RTSP→HLS/WebRTC gateway. |
| **Automated capture & auto-routing** | Reolink **HTTP snapshot API** and/or **FTP/SMB push** on motion/AI-trigger → an ingest job files captures into the correct MO folder via the v1 forward-compat **ingest API** (`sb_production_media` exposes `get-or-create MO folder + drop file` server-side, so this is drop-in). Network/PoE/switch/gateway provisioning is owner-owned. |
| **Customer/portal share-links** | Expose selected finished-part media to customers via DMS share-links + per-directory access groups. |
| **Auto-classification rules** | OCA `dms_auto_classification` for rule-based filing. |
| **Rebase onto official OCA `dms` 19.0** | When OCA publishes the 19.0 modules, rebase our port (names kept identical for a clean swap). |

## Forward-compat guarantee for the camera phase

`sb_production_media` exposes a stable server-side API in v1 — `mrp.production._get_media_directory()` and a `_ingest_media(mo, filename, bytes, mimetype)` helper — so the later Reolink ingest can file captures **by MO** with zero rework. This is the one thing built now specifically to de-risk the deferred phase.
