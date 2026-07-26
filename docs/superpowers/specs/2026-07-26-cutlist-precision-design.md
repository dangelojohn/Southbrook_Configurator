# Cutlist Precision — Design Spec

**Date:** 2026-07-26
**Status:** Approved (direction + all open questions settled with John, 2026-07-26). Ready for implementation planning.
**Deploy target:** Live Southbrook v19 CE (`southbrook`, system-docker). Modules: `sb_material_core`, `sb_material_mrp` (both LIVE); geometry from `southbrook_estimating` (unchanged).

## Goal

Replace the current **estimation-grade** per-line material demand/weight (a qty-weighted share of the whole cabinet carcass) with an **exact** per-line number derived from the actual panels each BoM line's material represents — so `material_demand_qty`, `component_weight_kg`, and the Phase-2 `suggested_purchase_qty` reflect the real panels, not a statistical allocation.

## Background — why today is estimation-grade

`sb_material_mrp/models/mrp_bom.py`:
- `_panel_volume_mm3(line)` sums the **whole** carcass (side_L + side_R + top + bottom + back + shelf×count) from `_compute_panel_dimensions`; it has no knowledge of *which* panel(s) the calling line represents. Doors are excluded entirely; `back` is pinned to a cut-constant thickness.
- `_sb_component_share_volume_mm3(line)` (2026-07-26 fix) divides that carcass total by the qty-weighted sum of **all** `density_volume` sibling lines on the BoM. Correct in aggregate ("carcass counted once"), but the per-line number is a statistical split across *all* materials, not a fact about that line's panels.

Live BoMs have two shapes (verified on prod 2026-07-26):
- **One line per material** (BoMs 280/283/285): 1× melamine = the whole carcass, 1× hardboard = the back, 1× ply = another group.
- **N lines, same material** (BoM 256): 7× MEL34, 2× PLY12, 1× PLY14BACK — roughly one line per physical panel.

The one-line-per-material shape is the key insight: a line already means "all panels of this material." So the precision primitive is **assign panel roles to materials**, then a line's exact demand = the summed area of the panels its material owns.

The codebase already holds three disconnected panel-aware structures (carcass math in `sb_material_mrp`; a per-panel 3D-render payload with a rendering-slug "material" in `product_config_line.py`; and the post-MO `sb.cutlist.line` with `panel_name` + `substrate` in `southbrook_kitchen_mrp`). This design introduces the first *real* material↔panel-role link and deliberately reuses `sb.cutlist.PANEL_NAMES`' vocabulary so the post-MO cutlist can converge later at no cost now.

## Design

### 1. Panel-role vocabulary
Reuse the roles already defined in `sb.cutlist.PANEL_NAMES` (`southbrook_kitchen_mrp/models/sb_cutlist.py`): `side_L`, `side_R`, `top`, `bottom`, `back`, `shelf`, `door`. Define them as a shared constant in `sb_material_core` (single source), and have the two modules reference the same list so the vocabularies can never drift.

### 2. Material → panel-role assignment
Add `panel_role_ids` to `southbrook.kitchen.material` — the set of panel roles this material can serve, expressed as a small tag model `sb.panel.role` (Many2many) whose records are the seven role names above (seeded, `noupdate`). Examples: a carcass melamine → {side_L, side_R, top, bottom}; a back material → {back}; shelf material → {shelf}; door stock → {door}. Low-cardinality: curated once per material, not per BoM line.

Rationale for a tag model over a comma-Selection: a material serves *multiple* roles (carcass = 4 box panels), and roles must be reused verbatim by `sb.cutlist` later — a real model with stable xml_ids is the clean shared vocabulary.

### 3. Exact per-line resolution (`_sb_line_panel_area_mm2` / volume)
For a BoM line resolving to `material_id` on a cabinet with resolved geometry (`_sb_resolve_geo`, already live):
1. Compute the cabinet's per-panel dimensions once (`_compute_panel_dimensions`, cached per compute pass).
2. Determine which panel roles this line's material **owns on this BoM**: the roles in `material_id.panel_role_ids` that are **claimed by exactly one line's material** on this BoM (unambiguous ownership).
3. This line's exact panel set = the panels whose role the line owns. Its exact volume/area = the sum of those panels' `(L × W × thickness)` (thickness from `material_id.thickness_mm` when set, else the panel's cut-constant — existing behaviour).
4. **Material-scoped share** for the N-lines-same-material case: if K lines on the BoM share the same `material_id`, split that material's owned-panel total among them by `product_qty` (reusing the existing share mechanic, but scoped to the material's own panels — not the whole carcass).

### 4. Honesty fallback (unchanged contract, extended)
A line falls back to today's `_sb_component_share_volume_mm3` estimate when its role ownership is **unresolvable**: the material has no `panel_role_ids`, or a role it claims is also claimed by another line's material on the same BoM (ambiguous), or the panel geometry is absent. Never fabricated. Ambiguous/estimated lines are visibly flagged (a computed boolean, e.g. `material_demand_is_exact`) so a buyer can tell an exact number from an estimate.

### 5. Back and door become first-class (closes two documented gaps)
- `back` is a real role: a line whose material owns `back` gets the back panel's exact area with its own material thickness (no longer pinned to `BACK_TH`).
- `door` is a real role: door panels are included when a line's material owns `door` (previously excluded from every line → silent 0). When no material owns `door`, doors remain excluded exactly as today (honesty).

### 6. Configurator auto-stamp (future BoMs)
Where the configurator materializes a BoM (`kitchen_design._ensure_kitchen_bom` / the Hermes apply path), no per-line tagging is needed under this model — resolution is automatic from each line's `material_id` + the material's `panel_role_ids`. The configurator's existing per-panel material intent (the 3D payload slug) is the natural place to *seed* each material's `panel_role_ids` correctly; wiring that is in scope as data/seed, not new per-BoM writes.

### 7. Recompute / rollout
- All new fields default empty → **no live number changes on install**. Numbers become exact only as materials get `panel_role_ids` assigned.
- Seed the seven `sb.panel.role` records and assign `panel_role_ids` to the standard seeded materials (MDF/MEL/PLY/back/door families) with sensible defaults (`noupdate`, correctable).
- An explicit, idempotent post-migrate recomputes `material_demand_qty`/`component_weight_kg` after the seed assignment (mirrors the proven 19.0.1.1.1 / 19.0.1.6.0 recompute idiom).
- `@api.depends` on the exact-demand computes extended to include `material_id.panel_role_ids` and the sibling-material set.

## Out of scope (deferred)
- **Converging `sb.cutlist`** (post-MO) onto this material↔role link, and unifying the two panel-geometry engines (`_compute_panel_dimensions` vs `shared/southbrook_dims.py`) — later phase; vocabulary is shared now so it's free.
- **`density_area` materials** (tile/drywall/stone) — still the Phase-1 0-weight stub; not mapped here.
- **Multi-role-per-line with different dims on a *single* line** — not needed (the material-ownership model handles the real BoM shapes); revisit only if a real BoM requires it.
- **Nesting / offcut optimization** and cross-BoM sheet batching — materially harder, separate project.

## Success criteria
- A one-line-per-material BoM (280/283/285) reports each line's demand as the **exact** summed area of that material's panels (verifiable against hand math), not a whole-carcass share.
- A back-material line reports the exact back-panel area (was cut-constant); a door-material line reports the exact door area (was 0).
- N-lines-same-material (256) split that material's panel total among themselves; the BoM total still counts each material's panels exactly once.
- Unmapped/ambiguous lines are unchanged (today's estimate) and flagged non-exact — honesty contract intact.
- Additive/backcompat; no live number moves until roles are assigned; recompute is explicit.
