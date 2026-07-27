# Corner Cabinetry Knowledge Engine — Research Corpus
### Deep-research deliverables for the Southbrook parametric kitchen placement engine
*Produced 2026-07-27 by an 8-agent parallel research fleet + codebase-grounded synthesis. 221 machine-readable entries total; every document ends with a validated ```json block for direct ingestion.*

| Doc | Domain | Entries | Key primary sources |
|---|---|---|---|
| [01-base-corner-taxonomy.md](01-base-corner-taxonomy.md) | 18 base corner cabinet types — construction, dims, wall consumption | 18 | Wellborn spec book (pdftotext), KraftMaid Momentum, Kesseböhmer/Häfele, NKBA G29 |
| [02-wall-corner-taxonomy.md](02-wall-corner-taxonomy.md) | 11 wall corner types + mounting conventions | 11 | CabinetCorp/Barker specs, KraftMaid 3″/1.5″ blind filler rule, Blum 170° bi-fold |
| [03-standards-and-clearances.md](03-standards-and-clearances.md) | NKBA 31 guidelines, ADA §804, KCMA, AWI, dimension conventions | 66 | NKBA, ADA, AWI ⅛″/96″; ⚠ KCMA triangulated — verify vs. purchased standard |
| [04-hardware-envelopes.md](04-hardware-envelopes.md) | 23 corner mechanisms — motion envelopes, min openings, clearances | 23 | Blum CLIP top/SPACE CORNER PDFs, Hettich Design Collection drawings, Kesseböhmer, Rev-A-Shelf, Vauth-Sagel, Ninka |
| [05-installation-practice.md](05-installation-practice.md) | Install sequencing, corner-first rationale, tolerance absorption | 37 | MasterBrand/KraftMaid/IKEA manuals, FHB/JLC, installer forums; disagreements preserved |
| [06-collision-matrix.md](06-collision-matrix.md) | Complete interference matrix with documented clearances | 23 | Blum planning manuals, appliance install manuals (GE/Bosch/Sub-Zero), NKBA |
| [07-cad-math-architecture.md](07-cad-math-architecture.md) | How 2020/Cabinet Vision/Microvellum model walls, corners, constraints | 12 | Cabinet Vision UCS internals, Microvellum, Chief Architect, Ericson RTCD, IFC, Merrell SIGGRAPH'11 |
| [08-manufacturing-intelligence.md](08-manufacturing-intelligence.md) | 32mm system, panel genealogy, corner-deck CNC, BOM/routing patterns | 31 | Euro32, Cabinet Vision S2M, Microvellum BOM/routes, WoodWeb |
| [09-rule-engine-spec.md](09-rule-engine-spec.md) | **Synthesis** — Phase 8 rule schema + Phase 9 Odoo model + migration plan M1–M6 grounded in `kitchen_layout_engine` | — | docs 01–08 + live codebase/DB |

## How to consume
- **Engine work** starts at 09 §7 (migration steps M1–M6); each step cites the
  research entries it implements.
- **Rule authoring**: instantiate 09 §3 schema records; pull numbers ONLY from
  the JSON blocks (each entry carries `sources` + `confidence`); `estimate`
  entries must surface a UI warning, never a silent hard gate.
- **Test authoring**: the 23 `pair_id`s in doc 06 are the collision acceptance
  matrix; docs 01/02 `type_id`s enumerate the fixture space.

## Known verification debt (carried forward from the fleet's own flags)
1. KCMA A161.1 + NKBA primary PDFs resisted text extraction — numbers
   triangulated from secondary sources (docs 02/03/08).
2. Kesseböhmer/Vauth-Sagel/Ninka factory datasheets sit behind dealer portals —
   reseller-sourced dims marked medium/low confidence (doc 04).
3. No codified standard exists for: light-rail height, field scribe threshold,
   drawer-vs-drawer corner spec, upper-corner-door-vs-hood clearance — modeled
   as geometric rules, not constants (docs 03/06).
4. Live catalog data bugs found during synthesis (09 §1): `SB-CORNER-BLIND/
   -DIAG/-LSUSAN` lack `southbrook_cabinet_type`/dims; the 33″ corner variant
   reads template width 36.
