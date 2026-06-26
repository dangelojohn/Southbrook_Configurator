# Homag BTL/MPR Export — Source-Verify Audit

**Date:** 2026-06-25
**PRD reference:** SAMI v1.0 §4.9 IOT-05 ("Nesting plan export — Odoo → Homag BTL/MPR/XML")
**Production plan reference:** Wave 3 #14 (BLOCKER for SAMI go-live)
**Status:** ❌ **Gap larger than PRD claim** — see findings.

## What we have today

### `sb.cutlist.to_nesting_envelope()`
Defined in `addons/southbrook_kitchen_mrp/models/sb_cutlist.py`. Produces a
custom JSON envelope schema `southbrook.nesting.v1`:

```json
{
  "schema": "southbrook.nesting.v1",
  "cutlist_id": <int>,
  "panels": [
    {
      "panel_name": "side_L" | "side_R" | "top" | "bottom" | "back" | "door" | ...,
      "qty": <int>,
      "length_mm": <float>,
      "width_mm": <float>,
      "thickness_mm": <float>,
      "edge_banding": {"top": bool, "bottom": bool, "left": bool, "right": bool}
    },
    ...
  ]
}
```

Round-trip tested in `addons/southbrook_kitchen_mrp/tests/test_nesting_io.py`.
JSON-serializable, deterministic, versioned. ✅ This part works.

## What Homag iX actually needs

Homag iX cells (specifically the Sawteq/Bargstedt cutting + storage line in
the SAMI factory) consume one of:

1. **BTL (Borer Transfer Language)** — Homag's column-oriented text file
   for cut + bore + edge-banding instructions. Pattern: one row per panel
   operation, columns for X/Y/Z, tool, depth, edge tape code. Used by
   Format4 cells.
2. **MPR (Maschinen Programm)** — Homag's macro language for routing /
   boring operations on the CNC. Less applicable for sheet-cutting; more
   for the bore step.
3. **XML envelope** (proprietary) — newer Homag CAM accepts an XML
   variant. Spec is gated behind Homag NDA / partner program.

The PRD §4.9 IOT-05 says "**PARTIAL** — Export endpoint exists; needs
source-verify on actual Homag file format." The gap analysis confirms:
**no BTL/MPR/XML generator exists in the codebase today.**

The JSON envelope is an intermediate format. To reach Homag, one of:

- **A. Homag accepts JSON via a custom partner adapter** (Lignumiq is the
  Canadian Homag dealer; they sometimes supply CAM adapters). Need
  vendor confirmation.
- **B. We write the BTL generator ourselves** against the Homag schema
  (requires the Homag CAM SDK + an NDA-gated spec).
- **C. We pipe through Accucutt** (the optimization service that already
  understands BTL) — the JSON envelope becomes input to Accucutt, which
  emits BTL to Homag. Memory `[[sami_southbrook_full_platform_build]]`
  hints that Accucutt was the planned path.

## Risk profile

| Risk | Severity |
|------|----------|
| Cut spec pipeline currently a paper claim — never tested against real Homag hardware | **HIGH** |
| BTL format spec is NDA-gated; can't be written without partner access | **HIGH** |
| Accucutt-as-translator assumed in roadmap but not confirmed end-to-end | **MEDIUM** |
| When SAMI deploys, surprise gap forces last-minute integration work | **HIGH** |

## What we can do now

I cannot validate end-to-end without:

1. **Access to a real Homag iX machine** (or a vendor-provided CAM
   simulator). Without it, any BTL we generate is unverified.
2. **The Homag CAM SDK / format spec.** This requires a partner-channel
   request — Lignumiq is the Canadian Homag dealer; their integration
   team would supply BTL format docs under NDA.
3. **Accucutt's input format spec** (if Path C is chosen) — should be
   easier to obtain since Accucutt is Southbrook's existing partner.

## Concrete next steps (in order)

1. **[Owner action]** Confirm with John which path Southbrook is on:
   - Path A (Lignumiq partner adapter) — JSON envelope is enough; we
     hand off and they translate
   - Path B (Direct BTL generator) — we need the Homag SDK + spec
   - Path C (Accucutt as middleware) — we need Accucutt's input spec
2. **[If Path A or C]** Request the partner's expected input schema +
   one or two sample files
3. **[If Path B]** Engage Lignumiq under NDA for the BTL/MPR spec
4. **Once schema known:** add a `to_homag_btl()` method (or
   `to_accucutt_csv()`) to `sb.cutlist`, mirroring `to_nesting_envelope`
5. **End-to-end validation:** stand at the Homag iX with one of the
   exported files, run it through CAM, verify a real panel cuts to spec

## Source-verify against the JSON envelope today

What I CAN do without partner access — verify the JSON envelope is
**information-complete** for downstream consumption. Re-audited 2026-06-25
after writing the v2 envelope bump (correcting my initial scan):

- [x] Panel dimensions (length × width × thickness) — present (v1)
- [x] Edge-banding per edge (top/bottom/left/right) — present, boolean (v1)
- [x] Quantity per panel — present (v1)
- [x] **Material identification** — present in v1 as `substrate`
      (selection: melamine_white_5_8, etc.). My initial audit pass
      missed this; corrected here.
- [x] **Grain direction** — present in v1 as `grain_dir`
      (with_grain / cross_grain / no_grain). Also missed initially.
- [x] **Reference origin** — added in v2 as `reference_origin`
      (`bottom_front_left`, x_axis=width, y_axis=height, z_axis=depth).
- [x] **Units declaration** — added in v2 as top-level `units: "mm"`.
- [x] **MO metadata** (name + product code) — added in v2 as `mo: {...}`
      object alongside the legacy `mo_id` integer (v1 backcompat).
- [ ] **Banding tape SKU** (not just boolean) — reserved field
      `edge_banding_tape_skus: null` in v2; needs banding-product
      taxonomy first.
- [ ] **Bore positions** (drawer slide holes, hinge cups) — reserved
      field `bore_positions: null` in v2; needs a `sb.cutlist.bore`
      sub-model or per-line bore-spec JSON. Phase 3.5.

**Schema bump:** `southbrook.nesting.v1` → `southbrook.nesting.v2`
landed in `addons/southbrook_kitchen_mrp/models/sb_cutlist.py` 2026-06-25.
v2 is additive over v1 — all v1 fields preserved. v1 consumers reading
the v2 envelope by schema name will see the bump and either upgrade or
ignore unknown fields. Test in `test_nesting_io.py:test_envelope_is_deterministic_and_versioned`
asserts the v2 shape end-to-end.

## Tracking

Update this file as the answers land:

- Path chosen: _TBD_
- Partner contact (Lignumiq or Accucutt): _TBD_
- Sample file received: _TBD_
- Generator implementation PR: _TBD_
- First successful real-cut: _TBD_
