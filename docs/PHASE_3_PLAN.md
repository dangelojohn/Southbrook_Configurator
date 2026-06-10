# Phase 3 Polish — Implementation Plan

**Drafted:** 2026-06-10
**Author:** Claude (engineering session)
**Status:** Draft — not authorized to start; awaiting Phase 2 Track 2 gate sign-off per `CLAUDE.md` §7.3.
**Source:** Backlog rows in `docs/PHASE_2_TRACK_2_GATE.md` lines 350-362.

This document orders the 13 Phase-3-polish backlog items into 4 themed
sprints, calls out cross-item dependencies, and gives an effort estimate
per item. It is a *plan*, not an implementation — no code in this
phase touches `addons/` until John signs off the Track 2 gate.

---

## Why a plan first

Phase 3 polish bundles items that span two surfaces (Track 1 full-screen
SPA + Track 2 portal Order Builder), two render layers (Three.js
viewport + OWL DOM), and two backend subsystems (rule engine + BoM
rollup). Sprinting through them in commit order without grouping
would re-touch the same files 3-4 times. Grouping them lets each
sprint land as a coherent commit set.

The brief (`CLAUDE.md` §7.3) requires John reviews on a live Odoo
instance at the end of each phase. Phase 3 has enough surface area
that a single end-of-phase review is too coarse — the plan below
proposes a mid-phase checkpoint after Sprint B, so the rule-engine
and BoM-breakdown work (the riskiest items) can be validated before
the lower-risk a11y/touch sprint runs.

---

## Sprint A — Visual & font polish *(safe, parallelizable, ~3 days)*

The lowest-risk items: pure asset/shader changes, no model edits,
no rule-engine entanglement. Land first so the Three.js scene
visually matches the Prodboard manifest reference *before* John
sees Sprint B's rule output.

| # | Item | Files | Effort | Notes |
|---|---|---|---:|---|
| A1 | Custom font vendoring (woff2 @font-face) | `static/src/scss/planner.scss`, `static/src/fonts/` | 0.5d | Roboto Flex woff2 vendored; no CDN; `@font-face` declaration with `font-display: swap` |
| A2 | HDRI environment lighting | `static/src/js/kitchen_viewport.esm.js`, `static/src/assets/hdri/` | 1d | RGBE Equirectangular HDRI (Polyhaven-licensed studio_small_03 1k, ~512 KB). PMREMGenerator + scene.environment. Replaces the 4-point lighting rig from Phase 2. |
| A3 | Outline post-process around hovered cabinet | `static/src/js/kitchen_viewport.esm.js` | 1d | EffectComposer + OutlinePass from three/examples/jsm/postprocessing/. Replace the emissive material hack from Phase 2. Hover state already lifts via `_onPointerMove`. |
| A4 | In-page PDF preview | `static/src/js/portal_boot.esm.js`, new `pdf_preview.esm.js` | 0.5d | `<iframe srcdoc>` loading the spec-sheet PDF blob URL. Mobile fallback = open in new tab (iOS blocks iframe PDF). |

**Land cadence:** one commit per item, A1 → A4 in order.

**Risk:** HDRI texture size. Polyhaven 1k Equirectangular HDR is ~512 KB
unzipped, which doubles the initial scene load. Mitigation: lazy-load
the HDRI after first render; show the Phase-2 4-point lighting for the
first paint, then upgrade.

---

## Sprint B — Rule engine + BoM rollup *(risky, single-threaded, ~5 days)*

The two highest-risk items. Both touch backend models AND the OWL
viewport reads. Land together so the ValidationStrip and the per-line
BoM breakdown can share a single data round-trip.

| # | Item | Files | Effort | Notes |
|---|---|---|---:|---|
| B1 | Real rule engine output → ValidationStrip | `models/product_config_session.py`, `controllers/main.py`, `static/src/js/portal_boot.esm.js` | 2d | Today's ValidationStrip is empty for demo orders (Phase 1 limitation per `PHASE_2_TRACK_2_GATE.md` line 53). The rule engine exists in `addons/southbrook_estimating/data/config_rules.xml`; this sprint exposes its output via a new `/southbrook/order/<id>/validation` endpoint and renders the rule reasons inline. |
| B2 | Per-line BoM breakdown + cut diagrams | `models/sale_order_line.py`, new `controllers/bom_breakdown.py`, OWL `BomBreakdown.esm.js` | 3d | Per `PHASE_2_TRACK_2_GATE.md` line 53: demo variants have empty BoM rollup because they were created bare (not through configurator session). This sprint either (a) re-seeds demo orders through real config sessions, OR (b) computes the BoM rollup live from `product.config.session._SKU_DEFAULTS` for lines that lack a session. Both produce the panel/edge-banding/hardware rollup; cut diagrams use the existing `southbrook_dims` constants. |

**Mid-phase checkpoint:** after B1 + B2 ship, John reviews on the live
QNAP stack against `S00235` (the canonical demo order from the Track 2
gate). The MAPLE badge and channel-discount math should now light up
on real data, not zeros.

**Risk:** B2's two approaches have different downstream consequences.
Re-seeding demos (option a) is simpler but invalidates the
e2e walkthrough screenshots. Live computation (option b) is correct
in production but adds a JSON-RPC round-trip per line render. Decide
at sprint kickoff; my recommendation is (b) because Production orders
won't go through demo-seed paths anyway.

---

## Sprint C — Interaction & functional polish *(~3 days)*

User-facing functional items that depend on B1/B2 having landed
(rule output + BoM data) but don't themselves touch backend models.

| # | Item | Files | Effort | Notes |
|---|---|---|---:|---|
| C1 | Inline add-line flow on the portal | `static/src/js/portal_boot.esm.js`, controller `_add_line` JSON-RPC | 1d | Replaces the existing "navigate to backend to add a line" hop. The drawer-driven config UX from Track 2 is the natural insertion point. |
| C2 | Full attribute pickers in ConfigDrawer | `static/src/js/portal_boot.esm.js` | 1d | Today's ConfigDrawer reads the existing attribute values from the variant; this sprint surfaces the attribute *picker* with rule-blocked options visibly disabled (per `CLAUDE.md` §5 acceptance criteria). |
| C3 | History panel parent-order chain | `models/sale_order.py` (add `_compute_history`), OWL `HistoryPanel.esm.js` | 0.5d | The data already exists on `sale.order` via `parent_id` (revision-versioning). This sprint adds a UI panel that walks the chain. |
| C4 | Cancel order button | `static/src/js/portal_boot.esm.js`, controller `_cancel_order` | 0.5d | Simple state transition; the pipeline already has a `cancelled` state. |

---

## Sprint D — Accessibility & realtime *(~2 days)*

The remaining items. Land last because they touch the broadest set
of components and benefit from A/B/C being stable.

| # | Item | Files | Effort | Notes |
|---|---|---|---:|---|
| D1 | Keyboard nav (arrow keys for tabs, lines) | `static/src/js/portal_boot.esm.js`, ARIA attribute pass | 0.5d | Arrow keys + Enter/Space + Esc per WAI-ARIA Authoring Practices grid pattern. |
| D2 | Touch / mobile breakpoint tuning | `static/src/scss/planner.scss`, OWL responsive props | 1d | The 3-pane layout collapses to a single-column stack below 768px (already partly works); this sprint hardens the touch targets, scroll behavior, and the drawer-pane handoff on small screens. |
| D3 | Bus.bus subscription for live multi-user updates | `static/src/js/portal_boot.esm.js`, `models/sale_order.py` (bus notification trigger) | 0.5d | When two designers have the same order open, edits from one propagate to the other in <2s. Odoo 19's `bus.bus` is the channel. |

---

## Out-of-Phase-3 backlog (deferred to Phase 4+)

| Item | Phase | Why not in Phase 3 |
|---|---|---|
| Send-to-manufacturing button | Phase 4 | Triggers MO creation; depends on Phase 4 cut-list bridge being stable. |
| Multi-currency awareness | Phase 4 | Cross-cuts pricelists, BoM, and the Accucutt envelope; sized as its own sprint. |

These are not Phase 3 polish — they're Phase 4 architectural items
from the same gate-doc table. Listed here so the reader doesn't
expect them to land in Phase 3.

---

## Commit + branch strategy

- One feature branch per sprint: `feature/phase-3-sprint-a`, etc.
- Sprints A, C, D land as squash-merge PRs (small, reviewable).
- Sprint B lands as a multi-commit merge (the rule engine work + the
  BoM rework are distinct enough to read separately in history).
- Every sprint adds tests with the
  `@tagged("post_install", "-at_install", "southbrook", "phase-3")`
  tag so the suite can be filtered per-sprint during gate review.
- No memory-only changes; every Phase 3 decision lands in this doc
  + commit messages, not in side conversations.

## Estimate roll-up

| Sprint | Days | Risk |
|---|---:|---|
| A — Visual / font | 3 | Low |
| B — Rule + BoM | 5 | High (single-threaded; mid-phase checkpoint) |
| C — Functional | 3 | Low/medium |
| D — A11y / realtime | 2 | Low |
| **Total** | **13 days** | |

Two-week sprint cadence with one engineer; one-week with two
engineers if Sprints A and B run in parallel (A has no dependency
on B).

## Pre-conditions before kickoff

1. Phase 2 Track 2 gate **signed off** (this plan does not authorize
   any Phase 3 code).
2. The bridge container's elevation render is live in production
   (closed today via commits `531a371` and `f9cab1b`) — Sprint A's
   in-page PDF preview reads the installation PDF endpoint that
   now embeds elevations.
3. John picks Sprint B option (a) re-seed vs (b) live-compute. The
   recommendation here is (b).

If any pre-condition slips, the plan still holds — just the
calendar slides.
