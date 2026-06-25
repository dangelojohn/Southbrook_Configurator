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
**information-complete** for downstream consumption. Checklist:

- [x] Panel dimensions (length × width × thickness) — present
- [x] Edge-banding per edge (top/bottom/left/right) — present, boolean
- [x] Quantity per panel — present
- [ ] **Material identification** (which sheet stock / which panel
      from the cutlist row) — `panel_name` is descriptive ("side_L")
      but the underlying material/board ref is NOT in the envelope.
      Likely needed for nesting.
- [ ] **Grain direction** — not in envelope; required for grain-matched
      cabinets
- [ ] **Banding tape SKU** (not just boolean) — needed for the right
      tape to feed in
- [ ] **Bore positions** (drawer slide holes, hinge cups) — fully absent;
      Homag CNC needs these as a separate file or embedded
- [ ] **Reference origin** (which corner is 0,0) — not declared in
      envelope; consumer has to assume

**Recommendation:** before any partner conversation, extend
`to_nesting_envelope` to add material identification, grain direction,
banding tape SKU, and a `bore_positions` array. These are universal to
ANY nesting downstream, regardless of which path we go.

## Tracking

Update this file as the answers land:

- Path chosen: _TBD_
- Partner contact (Lignumiq or Accucutt): _TBD_
- Sample file received: _TBD_
- Generator implementation PR: _TBD_
- First successful real-cut: _TBD_
