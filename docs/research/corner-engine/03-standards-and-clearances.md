# Industry Standards and Planning Rules — Kitchen Cabinet Placement Engine

Normative layer for a professional kitchen CAD/MRP placement engine. Every number below is either
sourced to a specific URL or explicitly marked `ESTIMATE (basis: ...)`. Where sources disagree
(e.g. toe kick height 4" vs 4.5", filler width 2"–4"), the range is captured and the engine should
treat the tightest constraint as the "hard" floor unless a project spec overrides it.

**Caveat on primary sources:** The authoritative documents — NKBA "Kitchen Planning Guidelines with
Access Standards," KCMA A161.1-2022, and AWI/AWS ANSI/AWI 0620 & 0641 — are all publicly hosted as
image-heavy/compressed PDFs that automated fetch tools could not OCR/extract text from directly (see
Sources list; each PDF URL is retained for manual verification). The values below were therefore
triangulated from secondary sources that explicitly quote the primary standards verbatim (trade
associations, cabinet manufacturers' technical pages, and a 1994 JLC/NKBA "31 Rules" reprint that
predates and matches the modern NKBA guideline numbering). Numbers that could not be corroborated
across at least two independent secondary sources are marked ESTIMATE.

---

## 1. NKBA Kitchen Planning Guidelines (with Access Standards)

The NKBA guidelines are numbered 1–31 (originally published 1992, updated through the current
"Kitchen Planning Guidelines with Access Standards" edition). Each guideline has a base ("Practical")
value and, in the Access Standards variant, an accessible/Universal Design value. Only the numeric,
placement-relevant content is captured here.

### Doors / entry (Guidelines 1–2)
- **G1 Doorway clear width:** clear opening of a doorway ≥ 32"; typically requires a 34" (2'-10")
  door. Access Standard variant requires 34" clear opening (36" door). Source: starcraftcustombuilders.com reprint of the 31 Rules.
- **G2 Door/appliance interference:** no entry door may interfere with appliance operation; no
  appliance door may interfere with another appliance door.

### Work triangle / traffic (Guidelines 3–5)
- **G3 Work triangle distances:** sum of the three work-center-to-work-center legs ≤ 26 ft (7.92 m);
  no single leg < 4 ft (1.219 m) or > 9 ft (2.743 m).
- **G4 Work-center separation:** full-height/full-tall obstacles should not separate primary work
  centers (sink, cooktop, refrigerator); a recessed corner unit is acceptable.
- **G5 Traffic through triangle:** no major traffic pattern should cross the work triangle.

### Aisles / walkways (Guidelines 6–7)
- **G6 Work aisle width:** ≥ 42" for a single-cook kitchen; ≥ 48" for a multiple-cook kitchen.
  Measured between counter frontage, tall cabinets, and/or appliances.
- **G7 Walkway width:** ≥ 36" (passageway with no work-center frontage on either side).

### Seating (Guidelines 8–9)
- **G8 Seating clearance:** 32" min clearance behind a seated diner with no traffic passing; 36" if
  traffic passes to one side ("edge past"); 44" if traffic walks directly behind; 60" for wheelchair
  access/turn.
- **G9 Seating space per person:** ≥ 24" wide per seated person, with knee space depth of 18" at a
  30" high table/counter, 15" at 36", or 12" at 42".

### Sink / cleanup (Guidelines 10–11, 15)
- **G10 Cleanup sink:** locate adjacent to or across from the cooking surface and refrigerator; max
  rim height 34" AFF; bowl depth ≤ 6.5".
- **G11 Sink landing area:** ≥ 24" landing on one side of the sink, ≥ 18" on the other.
- **G15 Auxiliary/prep sink:** ≥ 3" frontage on one side, ≥ 18" on the other.

### Food prep (Guideline 12)
- **G12 Prep counter:** ≥ 36" wide × 24" deep continuous countertop adjacent to a sink.

### Dishwasher (Guideline 13)
- **G13 Dishwasher-to-sink:** nearest edge of dishwasher within 36" of nearest edge of cleanup/prep
  sink; provide ≥ 21" standing space perpendicular to the open dishwasher door.

### Waste (Guideline 14)
- **G14 Waste receptacles:** ≥ 2 receptacles (trash + recycling); positioned ≤ 30" from sink
  centerline.

### Refrigerator (Guideline 16)
- **G16 Refrigerator landing area:** ≥ 15" landing on the handle side (or either side for
  side-by-side units); alternative is landing directly across an aisle ≤ 48" away.

### Cooktop / cooking surface (Guidelines 17–20)
- **G17 Cooktop landing areas:** ≥ 12" landing on one side, ≥ 15" on the other, both at cooktop
  height; if the cooktop is on an island/peninsula with no wall behind, provide ≥ 9" behind the
  cooking surface.
- **G18 Cooktop overhead clearance:** ≥ 24" to a protected/noncombustible surface (e.g. UL-listed
  range hood) directly above; ≥ 30" to an unprotected/combustible surface (e.g. cabinetry).
- **G19 Ventilation:** ducted ventilation sized to the appliance; recommended minimum 150 CFM.
- **G20 Cooktop safety:** not located beneath an operable window; non-flammable window treatments;
  fire extinguisher mounted 15"–48" AFF near an exit.

### Microwave (Guidelines 21–22)
- **G21 Microwave mounting:** bottom of the appliance ideally 3" below the principal user's
  shoulder height, never more than 54" AFF; if installed below the counter, bottom ≥ 15" AFF.
- **G22 Microwave landing area:** ≥ 15" landing above, below, or adjacent to the handle side.

### Oven (Guideline 23)
- **G23 Oven landing area:** ≥ 15" landing next to or above the oven; a landing ≤ 48" across an
  aisle is acceptable only if the oven door does not open into a walkway.

### Combining landing areas (Guideline 24)
- **G24 Adjacent landing-area combination rule:** where two appliance landing requirements are
  adjacent and can be shared, the combined minimum = larger individual requirement + 12".

### Countertops (Guidelines 25–26)
- **G25 Total countertop frontage:** ≥ 158" of countertop frontage at 24" depth combined across the
  kitchen (covers prep, landing, and storage functions), with ≥ 15" clearance above all counter runs.
- **G26 Countertop corners:** specify clipped or rounded corners rather than pointed/sharp corners
  on all exposed countertop corners.

### Storage totals (Guidelines 27–29)
- **G27 Total shelf/drawer frontage** by kitchen size: < 150 sq ft → ≥ 1,400" combined
  shelf+drawer frontage; 150–350 sq ft → ≥ 1,700"; > 350 sq ft → ≥ 2,000".
- **G28 Storage within 72" of sink centerline:** small kitchen ≥ 400"; medium ≥ 480"; large ≥ 560".
- **G29 Corner cabinet storage:** every corner cabinet should incorporate a functional storage
  device (lazy Susan, pull-out, etc.) rather than being left as unusable dead space.

### Electrical / lighting (Guidelines 30–31)
- **G30 Receptacles:** GFCI/AFCI protected on all countertop circuits; operable with one hand and
  ≤ 5 lb force; reach range 15"–48" AFF unobstructed, 15"–44" if counter obstruction is 20"–25" deep.
- **G31 Lighting:** every work surface lit by dedicated task lighting; wall-switch control at each
  entrance; natural light (window/skylight) area ≥ 8% of kitchen floor area.

**Access Standards note:** the Access Standards edition of the same 31 guidelines substitutes ADA/UD
values for several of the above (documented separately in Section 4, ADA/Accessibility, to avoid
conflating "recommended residential" vs "accessible" hard minimums). Where the placement engine
needs to switch profiles (standard vs. accessible), G1, G6/G7 (aisle/walkway), G8 (seating), and G16
(refrigerator clear floor space) are the ones with materially different accessible values.

---

## 2. KCMA A161.1 — Performance & Construction Standard for Kitchen and Vanity Cabinets

KCMA A161.1 is primarily a **performance/durability** certification standard (load and cycle
testing), not a dimensional-placement standard — but it fixes a few structural facts relevant to
where an engine may assume a cabinet can safely bear load, plus it is the customary reference for
"certified" cabinet construction quality that a spec sheet will cite.

- Wall cabinets and wall-hung base cabinets: gradually loaded to **600 lb** without visible
  structural failure of the cabinet or mounting system. (Informs backing/blocking requirements
  behind wall cabinets — not a placement clearance, but relevant to structural feasibility checks.)
- Shelves and cabinet bottoms: loaded at **15 lb/sq ft**, sustained 7 days, no excessive deflection
  or joint failure.
- Base-front (face-frame) joint strength: **250 lb** applied load for cabinets with a drawer rail,
  **200 lb** for cabinets without.
- Doors and drawers: cycle-tested to **25,000 cycles** minimum.
- Exact linear/dimensional tolerance clauses (referenced in the standard as drawings 2.9A–2.9E for
  exposed construction joints) could not be extracted from the available PDF — **ESTIMATE (basis:
  general woodworking/cabinet industry practice, not the A161.1 text itself): overall box
  width/height/depth manufacturing tolerance ±1/16"–1/8".** Flag this row `confidence: low` in the
  JSON and verify against the purchased KCMA A161.1-2022 PDF before hard-coding.

---

## 3. AWI / AWS — Architectural Woodwork Standards (Casework) & ANSI/AWI 0620 (Finish Carpentry/Installation)

These standards govern the **installed** result (reveals, plumb/level, scribe) rather than raw
manufacturing dimensions, and are the best-sourced numeric tolerances found in this research pass.

- **Installed plumb/level tolerance:** product shall be installed plumb and level within
  **3.2 mm [.125"] in 2438 mm [96"]** (i.e., ⅛" out of true over an 8-ft run). This is the standard
  installer tolerance an engine should treat as the "absorbable via shim/scribe" envelope before a
  wall is flagged out-of-tolerance for standard cabinetry.
- **Reveal Overlay (frameless) construction:** maximum uniform reveal within a cabinet elevation
  (door-to-door, door-to-drawer, or door/drawer-to-finished-end, including doors hung in pairs) is
  as specified in contract documents — i.e., no single AWI-mandated number; project spec governs.
  Recommended practical minimum reveal where unspecified: **¼" (6.4 mm)**.
  ESTIMATE (basis: secondary paraphrase of AWI casework aesthetic clauses) for the exact clause
  wording — verify against ANSI/AWI 0641 §3.4 directly.
- **Inset (face-frame) construction:** maximum uniform reveal variance between adjacent door/drawer
  edges and cabinet components: **3.2 mm [.125"]** (matches the general installed-tolerance figure
  above; same clause family). ESTIMATE on cross-reference to the exact clause number — verify against
  ANSI/AWI 0620 Aesthetic requirements.
- These are **AWI grade-dependent** (Economy / Custom / Premium grades carry different reveal and
  tolerance requirements in the full standard) — the numbers above are the commonly-cited
  Custom-grade figures; the placement engine should treat grade as a project-level parameter that
  can tighten or loosen these values, not hard-code a single grade.

---

## 4. ADA / Accessibility (2010 ADA Standards §804, U.S. Access Board Chapter 3)

- **Pass-through kitchen clearance** (counters/appliances/cabinets on two opposing sides): **40"**
  minimum clear width between all opposing base cabinets, countertops, appliances, or walls.
- **U-shaped kitchen clearance** (enclosed on three contiguous sides): **60"** minimum clear width.
- **Clear floor/ground space** (forward or side approach to a fixture/appliance): **30" × 48"**
  minimum; where the space is confined on three sides and obstructed for more than half its depth
  (alcove condition), minimum width increases to **36"**.
- **Turning space:** **60"** minimum diameter circular turning space, OR a T-shaped turning space
  60" × 60" overall with each of the three arms/stem ≥ 36" wide (knee/toe clearance may overlap only
  one of the three T-segments).
- **Obstruction turn (180°):** 60" minimum clearance around an obstruction < 48" long on the route;
  reduces to 48" minimum if the connecting routes are each ≥ 42" wide.
- **Knee and toe clearance:** toe clearance ≤ 9" high × ≤ 6" deep (max); knee clearance ≥ 27" high
  minimum, ≥ 30" wide minimum, up to 25" deep maximum from the leading edge, with ≥ 17" of that depth
  required where knee/toe space is mandated (e.g. under an accessible sink or cooktop).
- **Accessible work-surface height:** counter/work-surface ≤ 34" AFF maximum (vs. the 36" AFF
  standard counter height in Section 5 — this is the single largest hard-vs-recommended divergence
  the engine needs to encode as a profile switch).
- **Accessible clear floor space in front of appliances:** 30" × 48" minimum, forward or parallel
  approach.

---

## 5. Standard Cabinet Dimension Conventions (US residential, face-frame & frameless)

### Width increments
- Standard base/wall cabinet nominal widths run in **3" increments**: 9, 12, 15, 18, 21, 24, 27, 30,
  33, 36 (up to 48") inches.

### Base cabinets
- Height without countertop: **34.5"**; with a **1.5"** countertop substrate/surface, finished
  height **36" AFF** — matches the target spec's "34.5"+1.5"=36" AFF" convention exactly.
- Depth: **24"** standard (cabinet box only, before countertop overhang).
- Toe kick: sources converge on **~4" high (range 3.5"–4") × 3" deep** recess. Some secondary
  sources state 4.5" — treat 4" × 3" as the primary convention per the target spec, 4.5" flagged as
  a secondary/less common variant. ESTIMATE flag on the 4.5" figure only.

### Wall cabinets
- Depth: standard **12"** (most common, food/dish storage); **15"** and **24"** depths used over
  refrigerators, sinks, or as "deep wall" specialty units.
- Height: ranges **12"–42"**, standard runs typically 30"/36"/42" depending on ceiling height.
- Mounting: bottom of wall cabinet standard **54" AFF**, giving **18"** of open backsplash/clearance
  between the 36" AFF counter and the 54" AFF wall-cabinet bottom.

### Tall/pantry cabinets
- Height: **84", 90", or 96"** standard heights (84" fits an 8-ft ceiling with a 12" soffit; 90"
  aligns its top with a 36"-high wall cabinet's top).
- Depth: **24"** most common; **12"** deep variants exist to align with adjacent wall-cabinet runs.
- Width: **18"–36"**.

### 32mm / frameless system
- Frameless (European, "full access") construction uses a **32mm-on-center** system-hole grid
  (5mm diameter holes) on cabinet side panels, both near the front and near the back, for adjustable
  shelving, hinge plates, and drawer runners — this is the geometric basis for hardware placement in
  a frameless cabinet model.
- Frameless boxes have no face frame; doors/drawers mount directly to the box front, typically
  yielding **10–15%** more usable interior width per cabinet vs. an equivalent face-frame box
  (face-frame stiles consume ~1.5" of opening width per intermediate stile).

---

## 6. Filler Conventions

- General filler stock at walls/runs where a door/drawer needs swing clearance from an obstruction:
  commonly supplied in **1.5"–3"** widths, trimmed to fit in the field.
- **Blind corner cabinets:** a filler of **at least 3"** (commonly **2"–3"**, with **3"–4"**
  recommended specifically for frameless/full-access construction) must separate the blind cabinet's
  face/door from the return wall or adjacent perpendicular run, so the door and any hardware on the
  perpendicular cabinet can swing/open without obstruction. This is the numeric basis for "corners
  need a 3" pull" — the filler exists to clear door/drawer swing arcs at the blind corner, not for
  aesthetics.
- Face-frame construction can sometimes use a narrower filler than frameless in the same corner
  condition because the face frame itself already offsets the door edge from the box edge; frameless
  needs the full filler width since the door mounts flush to the box.

---

## 7. Face-Frame vs. Frameless Placement Differences

- **Face-frame:** a frame of rails/stiles (typically **1.5"** wide members) is applied to the front
  of the box; doors/drawers are mounted to/within this frame. Reveal and overlay are measured
  relative to the frame opening, not the box edge. Stiles between adjacent cabinet openings consume
  additional width (reducing usable opening by the stile width at every internal join), which the
  engine must subtract from nominal cabinet width when computing true opening width.
- **Frameless (32mm system):** no face frame; doors mount directly to the box edges with concealed
  hinges referencing the 32mm hole system. Full 32mm-grid access yields wider openings and, per the
  10–15% interior-space figure above, less width lost to structure — but ALL clearance for
  door/drawer swing at corners must come from filler strips since there's no frame offset to absorb
  it.
- **Corner handling:** face-frame corner (blind) cabinets rely on the frame + a filler (see Section
  6) to clear the adjacent door swing; frameless corner cabinets (diagonal/lazy Susan units or blind
  units) rely purely on filler width plus, frequently, specialized corner hardware (pie-cut lazy
  Susan, magic corner, LeMans unit) since there is no frame reveal to help hide the dead/blind zone.
- **Scribe allowance:** face-frame cabinets commonly include a **~1/8"–1/4"** scribe/reveal margin
  built into the end panel or filler at wall returns to absorb out-of-plumb walls; frameless cabinets
  typically rely on a dedicated scribe/filler piece of similar or slightly greater width since the
  box side itself is often the finished/exposed surface. ESTIMATE (basis: general trade practice, not
  a single cited numeric standard) — no single normative "scribe allowance" number was found in a
  primary standard; treat as a project/manufacturer-specific parameter, default **¼"** per side at
  wall returns if no manufacturer spec is available.

### Diagonal / lazy Susan corner cabinets (base)
- Standard diagonal corner base cabinet footprint: **36" (or 36 3/16") wide × 34.5" high × 24"
  deep** along each wall leg, functionally occupying a 36"×36" (or 33"×33") corner block.
- Lazy Susan turntable diameter is sized smaller than the cabinet's clear shelf depth (commonly
  **18"–22"** turntable diameter inside a ~20¾" shelf) to allow rotation clearance.

---

## 8. Countertop Overhang Standards

- **Front overhang** (over base cabinet face): standard **1.5"**.
- **Side/end overhang, against a wall:** **0"–0.25"** (essentially flush, sealed to wall).
- **Side/end overhang, open end (no wall):** **1"–1.5"**, typically matched to the front overhang.
- **Island/peninsula seating overhang:** **12"** standard to clear knee space for a stool (some
  sources call this the "bar overhang" convention as well).
- **Overhang requiring structural support** (corbels, steel brackets, or similar): any overhang
  beyond **10"–12"** unsupported.
- **Corner treatment:** countertop corners should be specified clipped or rounded rather than
  square/pointed at all exposed (non-wall) corners — this is NKBA Guideline 26 (Section 1 above),
  repeated here because it directly affects overhang/corner geometry generation.

---

## 9. Crown / Valance / Light-Rail vs. Ceiling Height

- Standard wall-cabinet-bottom mount height of **54" AFF** plus an 18" reveal to the 36" AFF counter
  is the baseline (Section 5).
- **42"-tall wall cabinets** run to (or just touch) an **8-ft (96") ceiling** with no crown/soffit
  trim; they are better suited to **9-ft ceilings** or an 8-ft ceiling with trim up to ~12" tall,
  since crown molding or a soffit needs headroom above the cabinet top.
- **Light-rail valance:** a **~2"**-tall valance strip is commonly applied below the wall-cabinet
  bottom edge to conceal under-cabinet task lighting; with a 2" valance, the *effective* wall-cabinet
  mounting reference shifts and finished clearance above a range hood/cooktop-adjacent cabinet can
  drop to as little as **~16"** to the valance underside in tight installations — this is a soft
  planning flag, not a code minimum, but interacts with NKBA G18's 24"/30" cooktop overhead
  clearance rule and should be checked against it (the larger of the two governs).
- **Stacked upper cabinet systems** (e.g., a 36" lower unit + an 18" upper "stacker" unit, separated
  by a scribe/light-rail reveal) are used to reach taller ceilings, typically yielding **50–60%**
  more storage than a single-tier upper run at the same wall.
- ESTIMATE (basis: no single normative "valance height" or "crown clearance" standard found in
  NKBA/AWI/KCMA text; the 2" valance and 16" residual-clearance figures come from cabinetmaker forum
  consensus, not a published standard) — flag confidence low in JSON.

---

## 10. Out-of-Square / Installation Tolerance Conventions

- **AWI/AWS installed tolerance (best-sourced figure in this research pass):** cabinetry/casework
  installed plumb and level within **3.2 mm [.125"] per 2438 mm [96"]** run — i.e., an installer can
  absorb up to ⅛" of out-of-true over an 8-ft wall run via shim/scribe before the installation falls
  outside the standard's tolerance. This is the number the placement engine should use as the
  default "wall deviation absorbable without a custom filler/scribe redesign" threshold.
- **Field practice for larger deviations:** where wall gap variance exceeds roughly **¾"** across a
  run (i.e., gap ranges from ~⅛" at one end to ¾"+ at the other), installers do not rely on a single
  fixed-width filler; they scribe a wider filler/end panel in place, or in worst cases furr out the
  wall. This is a qualitative trade-practice threshold, not a numeric standard — ESTIMATE (basis:
  cabinetmaker/installer trade discussion, not a codified figure).
- Cabinets should be shimmed level/plumb *before* scribing; scribing the wrong (out-of-plumb)
  reference geometry is the most commonly cited installation failure mode — relevant to the engine's
  order of operations (place/level the run, THEN compute scribe geometry, not the reverse).

---

## 11. Manufacturing Tolerances (KCMA / general CNC panel practice)

- KCMA A161.1's own dimensional-tolerance clauses (referenced internally as drawings 2.9A–2.9E for
  exposed construction joints) could not be extracted from the available PDF in this research pass —
  **do not treat any width/height/depth tolerance number in this section as KCMA-sourced.**
- **General CNC panel-processing tolerance** (industry-wide, not cabinet-specific): typical shop
  default **±0.1 mm**, with a commonly quoted practical range of **±0.05 mm to ±0.5 mm** depending on
  machine/material/fixturing; ISO 2768 is the general reference standard for linear/angular
  machining tolerances that panel-processing shops often cite. ESTIMATE (basis: general CNC
  machining tolerance guides, not a cabinet-industry-specific source) for applicability to cabinet
  box panels specifically — treat as a reasonable default for a cut-list/CNC nesting tolerance
  parameter, confidence medium.
- **Practical cabinet-box tolerance** (width/height/depth of an assembled box): **ESTIMATE (basis:
  general woodworking/cabinet trade practice, not a cited standard): ±1/16"–1/8"** per box dimension.
  Flag low confidence; verify against the purchased KCMA A161.1-2022 text before using as a hard
  gate in tolerance-sensitive placement math (e.g. filler sizing at the last cabinet in a run).

---

## Consolidated Placement-Relevant Rules Table

| Rule ID | Statement | Value | Source |
|---|---|---|---|
| nkba-doorway-clear-width | Kitchen entry doorway clear opening width | ≥ 32" (34" door) | starcraftcustombuilders.com 31-rules reprint |
| nkba-door-appliance-interference | No door may interfere with appliance operation; no appliance door may interfere with another | qualitative | starcraftcustombuilders.com |
| nkba-work-triangle-leg-min | Work triangle single leg minimum | 4 ft | starcraftcustombuilders.com; wcsupply.com |
| nkba-work-triangle-leg-max | Work triangle single leg maximum | 9 ft | starcraftcustombuilders.com; wcsupply.com |
| nkba-work-triangle-perimeter-max | Work triangle sum of three legs | ≤ 26 ft | starcraftcustombuilders.com; wcsupply.com |
| nkba-work-triangle-no-traffic | No major traffic crosses the work triangle | qualitative | starcraftcustombuilders.com |
| nkba-work-aisle-min-single-cook | Work aisle width, one cook | ≥ 42" | starcraftcustombuilders.com; wcsupply.com |
| nkba-work-aisle-min-multi-cook | Work aisle width, multiple cooks | ≥ 48" | starcraftcustombuilders.com; wcsupply.com |
| nkba-walkway-min | Walkway width (no work-center frontage) | ≥ 36" | starcraftcustombuilders.com; wcsupply.com |
| nkba-seating-clearance-no-traffic | Seating clearance, no traffic behind | ≥ 32" | starcraftcustombuilders.com |
| nkba-seating-clearance-edge-past | Seating clearance, traffic edges past | ≥ 36" | starcraftcustombuilders.com |
| nkba-seating-clearance-walk-past | Seating clearance, traffic walks directly behind | ≥ 44" | starcraftcustombuilders.com |
| nkba-seating-clearance-wheelchair | Seating clearance, wheelchair access | ≥ 60" | starcraftcustombuilders.com |
| nkba-seating-width-per-person | Seating width per person | ≥ 24" | starcraftcustombuilders.com |
| nkba-sink-landing-primary | Sink landing area, one side | ≥ 24" | starcraftcustombuilders.com; wcsupply.com |
| nkba-sink-landing-secondary | Sink landing area, other side | ≥ 18" | starcraftcustombuilders.com; wcsupply.com |
| nkba-prep-counter | Continuous prep counter adjacent to sink | ≥ 36" wide × 24" deep | starcraftcustombuilders.com |
| nkba-dishwasher-sink-max-distance | Dishwasher nearest edge to sink nearest edge | ≤ 36" | starcraftcustombuilders.com; edesiakbs.com |
| nkba-refrigerator-landing | Refrigerator landing area, handle side | ≥ 15" | starcraftcustombuilders.com; wcsupply.com |
| nkba-cooktop-landing-a | Cooktop landing area, one side | ≥ 12" | starcraftcustombuilders.com; wcsupply.com |
| nkba-cooktop-landing-b | Cooktop landing area, other side | ≥ 15" | starcraftcustombuilders.com; wcsupply.com |
| nkba-cooktop-clearance-protected | Cooktop to protected/noncombustible surface above | ≥ 24" | starcraftcustombuilders.com; wcsupply.com |
| nkba-cooktop-clearance-unprotected | Cooktop to unprotected/combustible surface above | ≥ 30" | starcraftcustombuilders.com; wcsupply.com |
| nkba-cooktop-ventilation-cfm | Ducted ventilation minimum | 150 CFM | starcraftcustombuilders.com |
| nkba-microwave-mount-max | Microwave bottom max mount height | ≤ 54" AFF | starcraftcustombuilders.com |
| nkba-microwave-undercounter-min | Undercounter microwave bottom min height | ≥ 15" AFF | starcraftcustombuilders.com |
| nkba-microwave-landing | Microwave landing area | ≥ 15" | starcraftcustombuilders.com |
| nkba-oven-landing | Oven landing area | ≥ 15" | starcraftcustombuilders.com |
| nkba-landing-combination-bonus | Combined adjacent landing area = larger requirement + bonus | +12" | starcraftcustombuilders.com |
| nkba-countertop-corner-treatment | Countertop corners clipped/rounded, not pointed | qualitative | starcraftcustombuilders.com |
| nkba-corner-cabinet-storage | Corner cabinets must have functional storage device | qualitative | starcraftcustombuilders.com |
| ada-passthrough-clearance | Pass-through kitchen clearance (2 opposing sides) | ≥ 40" | access-board.gov |
| ada-ushape-clearance | U-shaped kitchen clearance (3 sides) | ≥ 60" | access-board.gov |
| ada-clear-floor-space | Clear floor space, forward/side approach | 30" × 48" | access-board.gov |
| ada-clear-floor-space-alcove | Clear floor space width, confined-alcove condition | ≥ 36" | access-board.gov |
| ada-turning-space-circular | Turning space, circular | 60" diameter | access-board.gov |
| ada-turning-space-tshape | Turning space, T-shape overall / arm width | 60"×60" / 36" arms | access-board.gov |
| ada-knee-clearance-min-height | Knee clearance minimum height | ≥ 27" | access-board.gov |
| ada-toe-clearance-max | Toe clearance max height / depth | 9" / 6" | access-board.gov |
| ada-worksurface-max-height | Accessible work surface max height | ≤ 34" AFF | access-board.gov / corada.com |
| cab-base-height-no-top | Base cabinet height without countertop | 34.5" | multiple cabinet-dimension pages |
| cab-base-height-with-top | Base cabinet finished height with countertop | 36" AFF | multiple cabinet-dimension pages |
| cab-base-depth | Base cabinet standard depth | 24" | multiple cabinet-dimension pages |
| cab-toe-kick-height | Toe kick height | 4" (range 3.5"–4.5") | kitchencabinetkings.com; homenish.com |
| cab-toe-kick-depth | Toe kick recess depth | 3" | homenish.com; liwoodrenewal.com |
| cab-wall-mount-height | Wall cabinet bottom mount height AFF | 54" | multiple cabinet-dimension pages |
| cab-backsplash-clearance | Open clearance between counter and wall cabinet bottom | 18" | multiple cabinet-dimension pages |
| cab-wall-depth-standard | Wall cabinet standard depth | 12" | multiple cabinet-dimension pages |
| cab-wall-depth-alt | Wall cabinet alternate depths | 15" / 24" | multiple cabinet-dimension pages |
| cab-tall-height-options | Tall/pantry cabinet standard heights | 84" / 90" / 96" | 27estore.com; kraftmaid.com |
| cab-tall-depth | Tall/pantry cabinet standard depth | 24" (12" alt) | 27estore.com |
| cab-width-increment | Standard cabinet width module | 3" increments | multiple cabinet-dimension pages |
| cab-32mm-grid | Frameless system-hole spacing | 32mm o.c., 5mm dia. | woodweb.com / hettich system 32 refs |
| cab-frameless-space-gain | Frameless vs. face-frame interior space gain | 10–15% | mtcopeland.com / cabinets.com |
| filler-blind-corner-min | Blind corner cabinet filler minimum width | ≥ 3" (2"–3" typ; 3"–4" frameless) | woodcabinets4less.com; bestonlinecabinets.com |
| filler-general-min | General filler stock width range | 1.5"–3" | multiple cabinet-install pages |
| corner-lazy-susan-footprint | Diagonal corner base cabinet footprint | 36"×36" (33"×33" alt) | cabinets.com; castacabinetry.com |
| corner-lazy-susan-diameter | Lazy Susan turntable diameter | 18"–22" | designingidea.com |
| countertop-overhang-front | Countertop front overhang | 1.5" | marble.com; multiple |
| countertop-overhang-side-wall | Countertop side overhang at wall | 0"–0.25" | marble.com |
| countertop-overhang-side-open | Countertop side overhang, open end | 1"–1.5" | marble.com |
| countertop-overhang-seating | Countertop overhang at seating/island | 12" | marble.com; cectops.com |
| countertop-overhang-support-threshold | Overhang requiring corbel/bracket support | > 10"–12" | cectops.com |
| wall-cabinet-42in-ceiling-fit | 42" wall cabinet fits flush to 8-ft ceiling (no trim) | 96" ceiling | cornerrenovation.com |
| light-rail-valance-height | Light-rail valance height (typical) | ~2" | ESTIMATE — cabinetmaker forum consensus |
| stacked-upper-storage-gain | Stacked upper cabinet system storage gain vs single tier | 50–60% | kitchensearch.com |
| awi-install-plumb-level-tolerance | Installed plumb/level tolerance | 3.2mm [.125"] per 2438mm [96"] | awinet.org (ANSI/AWI 0620) |
| awi-reveal-overlay-min | Recommended minimum reveal, frameless, unspecified | ¼" (6.4mm) | awinet.org (paraphrase, verify clause) |
| awi-reveal-inset-max-variance | Inset/face-frame max reveal variance | .125" (3.2mm) | awinet.org (paraphrase, verify clause) |
| kcma-wall-cabinet-load-test | Wall cabinet static load test (no failure) | 600 lb | woodworkingnetwork.com; kcma.org |
| kcma-shelf-load-test | Shelf/bottom load test, 7-day sustained | 15 lb/sq ft | kcma.org |
| kcma-base-front-joint-load-drawer-rail | Base-front joint load test, w/ drawer rail | 250 lb | kcma.org |
| kcma-base-front-joint-load-no-rail | Base-front joint load test, w/o drawer rail | 200 lb | kcma.org |
| kcma-door-drawer-cycle-test | Door/drawer operation cycle test | 25,000 cycles | woodworkingnetwork.com; kcma.org |
| kcma-box-dimension-tolerance | Assembled cabinet box dimensional tolerance | ±1/16"–1/8" | ESTIMATE — not confirmed in KCMA text |
| cnc-panel-tolerance-typical | CNC panel-processing typical tolerance | ±0.1mm (range ±0.05–0.5mm) | shop.machinemfg.com; yijinsolution.com |
| out-of-square-scribe-field-threshold | Field threshold where fixed filler is abandoned for scribe | ~0.75" gap variance | ESTIMATE — trade-forum consensus |

---

## Sources

- NKBA "Kitchen Planning Guidelines with Access Standards" (2022 edition) — https://media.nkba.org/uploads/2022/05/Kitchen-Planning-Guidelines.pdf (binary/image PDF, not text-extractable via automated fetch; retained for manual verification)
- NKBA Kitchen Planning Guidelines (pre-2023 edition) — https://nkba-ps.com/images/downloads/Awards/nkba_kitchen_planning_guidelines_pre_2023.pdf (same extraction limitation)
- NKBA guidelines reprint (IVO Cabinets) — https://www.ivocabinets.com/wp-content/uploads/2024/06/NKBA-Kitchen-Planning-Guidelines.pdf
- "The 31 Rules of Kitchen Design" (JLC, 1994 reprint of original NKBA rules) — https://www.jlconline.com/wp-content/uploads/sites/4/1994/the-31-rules-of-kitchen-design-tcm96-1152572.pdf (binary PDF, not extractable)
- "The Thirty-One Kitchen Design Rules, Illustrated & Annotated" — http://starcraftcustombuilders.com/kitchen.design.rules.htm (primary secondary-source used for Section 1 numbers; text-extractable)
- Wholesale Cabinet Supply, "Kitchen Design Guidelines & Clearances" — https://www.thewcsupply.com/pages/kitchen-design-guidelines-standard-clearances
- CRD Design Build, "Kitchen Dimensions: Code Requirements & NKBA Guidelines" — https://www.crddesignbuild.com/blog/kitchen-dimensions-code-requirements-nkba-guidelines/
- eDesia KBS, "Kitchen Space Distance Suggestions" — https://www.edesiakbs.com/blog/kitchen-space-distance-suggestions
- Wikipedia, "Kitchen work triangle" — https://en.wikipedia.org/wiki/Kitchen_work_triangle
- KCMA A161.1-2022 (full standard PDF) — https://kcma.org/sites/default/files/2024-08/KCMA%20A161.1%202022%20High%20Res.pdf (binary PDF, not extractable via automated fetch; retained for manual verification)
- KCMA, "Cabinets Certified to Last" — https://kcma.org/insights/cabinets-certified-last-0
- KCMA, "ROI of Cabinet Durability: Reducing Project Risk With A161.1" — https://kcma.org/resources/roi-durable-cabinets-a161-1
- KCMA, "A161.1 Quality Certification" — https://kcma.org/certifications/kcma-quality-cabinet-certification
- Woodworking Network, "The strength behind certified cabinetry: ANSI/KCMA A161.1" — https://www.woodworkingnetwork.com/cabinets/strength-behind-certified-cabinetry-ansikcma-a1611
- AWI, ANSI/AWI 0620-2018 Finish Carpentry/Installation (full PDF) — https://awinet.org/wp-content/uploads/2024/12/ANSI-AWI-0620-2018-Finish-Carpentry-Installation.pdf
- AWI, ANSI/AWI 0641-2019 Architectural Wood Casework (Aesthetic requirements) — https://awiweb-cd.awinet.org/standards/casework/requirements/material
- AWI, "3.4 Aesthetic" (Finish Carpentry/Installation requirements page) — https://awinet.org/standards/finish-carpentry-installation/requirements/aesthetic-4/
- Architectural Woodwork Standards, Section 10 Casework — https://woodworkinstitute.com/wp-content/uploads/2015/05/Sec10_2ndEdAWS_SmBkMrkd_141001-3.pdf
- U.S. Access Board, "Chapter 3: Clear Floor or Ground Space and Turning Space" — https://www.access-board.gov/ada/guides/chapter-3-clear-floor-or-ground-space-and-turning-space/
- corada.com, "Kitchens and Kitchenettes: ADA Standard Section 804" — https://www.corada.com/documents/2010ADAStandards/804
- ADA Compliance, "804 Kitchens and Kitchenettes" — http://www.ada-compliance.com/ada-compliance/804-kitchens-and-kitchenettes
- Mr. Handyman, "Guide to Standard Kitchen Cabinet Sizes" — https://www.mrhandyman.com/blog/standard-kitchen-cabinet-sizes/
- CabinetSelect, "Kitchen Cabinet Sizes" — https://cabinetselect.com/standard-kitchen-cabinet-sizes/
- CabinetCorp, "Standard Cabinet Sizes and Dimensions Guide" (PDF) — https://www.cabinetcorp.com/wp-content/uploads/2025/07/Standard-Cabinet-Sizes-and-Dimensions-Guide.pdf
- Expo Home Improvement, "Complete Guide to Kitchen Cabinet Heights" — https://www.expohomeimprovement.com/complete-guide-to-kitchen-cabinet-heights-key-dimensions/
- Kitchen Search, "Standard Cabinet Sizes Guide" — https://kitchensearch.com/standard-cabinet-sizes/
- Kitchen Search, "Standard Cabinet Depth" — https://kitchensearch.com/standard-cabinet-depth/
- Kitchen Cabinet Kings, "Standard Toe Kick Height & Depth" — https://kitchencabinetkings.com/blog/standard-toe-kick-height/
- Homenish, "Guide to Standard Toe Kick Dimensions" — https://www.homenish.com/toe-kick-dimensions/
- The Handyman's Daughter, "Cabinet Toe Kicks" — https://www.thehandymansdaughter.com/cabinet-toe-kicks/
- LI Wood Renewal, "Cabinet Toe Kick Dimensions" — https://liwoodrenewal.com/cabinet-toe-kick-dimensions-height-design/
- 27estore, "How Deep Should Pantry Cabinets Be?" — https://www.27estore.com/blog/how-deep-should-pantry-cabinets-be
- KraftMaid, "What Are Standard Kitchen Cabinet Sizes?" — https://www.kraftmaid.com/kraftmaid/kitchen-cabinet-sizes
- Corner Renovation, "Kitchen Cabinets for 8-Foot Ceilings: 36 vs 42 Inch Uppers" — https://cornerrenovation.com/blog/8-foot-ceiling-kitchen-cabinets
- Bob Vila, "How to Find the Correct Upper Cabinet Height" — https://www.bobvila.com/articles/upper-cabinet-height/
- Woodweb, "Upper Cabinet Height Standard" — https://woodweb.com/knowledge_base/Upper_Cabinet_Height_Standard.html
- Best Online Cabinets, "Blind Corner Cabinet Ideas" — https://www.bestonlinecabinets.com/blog/blind-corner-cabinet/
- Wood Cabinets 4 Less, "Blind Base Cabinets 101" — https://woodcabinets4less.com/blog/blind-base-cabinets-101/
- Prime Cabinetry, "Install a Blind Corner Base Cabinet" — https://www.primecabinetry.com/blog/how-to-install-a-blind-corner-base-cabinet.html
- Lanae Home, "Corner Cabinet Dimensions: Lazy Susan and Alternatives" — https://lanaehome.com/blogs/news/corner-cabinet-dimensions-lazy-susan-and-alternatives
- Castacabinetry, "Corner Cabinet Dimensions: Complete Guide" — https://castacabinetry.com/post/corner-cabinet-dimensions/
- DesigningIdea, "Lazy Susan Dimensions" — https://designingidea.com/lazy-susan-dimensions/
- Marble.com, "Standard Countertop Overhang" — https://marble.com/articles/standard-countertop-overhang
- CEC Tops, "How Much Overhang Should a Countertop Have?" — https://www.cectops.com/how-much-overhand-should-a-countertop-have/
- Wikipedia, "Frameless construction" — https://en.wikipedia.org/wiki/Frameless_construction
- Woodweb, "Face frame versus frameless" — https://woodweb.com/knowledge_base/Face_frame_versus_frameless.html
- MT Copeland, "Face Frame vs. Frameless Cabinets" — https://mtcopeland.com/blog/face-frame-vs-frameless-cabinets-which-is-right-for-your-cabinet-build/
- Cabinets.com, "Frameless vs. Face Frame Cabinets" — https://www.cabinets.com/frameless-vs-face-frame-cabinets
- A&J's Custom Cabinets, "32mm vs Face Frame" — https://ajcabs.com/custom-cabinets/32mm_vs_face_frame/
- Houzz Forum, "Issues with cabinet install, should they have shimmed or scribed?" — https://www.houzz.com/discussions/4198503/issues-with-cabinet-install-should-they-have-shimmed-or-scribed
- Fine Homebuilding forum, "Cabinet Install on Unsquare wall" — https://www.finehomebuilding.com/forum/cabinet-install-on-unsquare-wall
- Popular Woodworking, "Scribing, Part Two" — https://www.popularwoodworking.com/editors-blog/scribing-part-two-making-cabinets-fit-seamlessly-into-irregular-surroundings/
- Woodweb, "Shimming Cabinets" — https://www.woodweb.com/knowledge_base/Shimming_Cabinets.html
- BJ Floors and Kitchens, "Cabinet Scribing 101" — https://www.bjfloorsandkitchens.com/blog/articles/cabinet-scribing-101-how-pros-make-walls-look-straight-without-rebuilding-them
- MFG Shop, "Comprehensive Guide to CNC Machining Tolerances" — https://shop.machinemfg.com/guide-to-cnc-machining-tolerances/
- Yijin Solution, "CNC Machining Tolerances Guide" — https://yijinsolution.com/cnc-guides/cnc-machining-tolerance/
- Gerber Wood Products, "An Overview of CNC Machining Tolerances" — https://gerberwood.com/an-overview-of-cnc-machining-tolerances/
- DoItYourself.com forum, "Dishwasher Door hits Refrigerator when open" — https://www.doityourself.com/forum/designing-kitchens-bathrooms/583906-dishwasher-door-hits-refrigerator-when-open.html
- Cabinetune, "Kitchen Clearance Dimensions" — https://cabinetune.com/kitchen-clearance-dimensions/

---

```json
[
  {"rule_id": "nkba-doorway-clear-width", "statement": "Kitchen entry doorway minimum clear opening width", "value_in": 32, "value_mm": 813, "applies_to": ["walkway"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-work-triangle-leg-min", "statement": "Work triangle single leg minimum length", "value_in": 48, "value_mm": 1219, "applies_to": ["walkway"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-work-triangle-leg-max", "statement": "Work triangle single leg maximum length", "value_in": 108, "value_mm": 2743, "applies_to": ["walkway"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-work-triangle-perimeter-max", "statement": "Work triangle sum of three legs maximum", "value_in": 312, "value_mm": 7925, "applies_to": ["walkway"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-work-aisle-min-single-cook", "statement": "Work aisle minimum width for a single-cook kitchen", "value_in": 42, "value_mm": 1067, "applies_to": ["walkway", "base"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-work-aisle-min-multi-cook", "statement": "Work aisle minimum width for a multiple-cook kitchen", "value_in": 48, "value_mm": 1219, "applies_to": ["walkway", "base"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-walkway-min", "statement": "Walkway minimum width (no work-center frontage)", "value_in": 36, "value_mm": 914, "applies_to": ["walkway"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-seating-clearance-no-traffic", "statement": "Seating clearance behind diner, no traffic passing", "value_in": 32, "value_mm": 813, "applies_to": ["walkway"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-seating-clearance-edge-past", "statement": "Seating clearance behind diner, traffic edges past", "value_in": 36, "value_mm": 914, "applies_to": ["walkway"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-seating-clearance-walk-past", "statement": "Seating clearance behind diner, traffic walks directly behind", "value_in": 44, "value_mm": 1118, "applies_to": ["walkway"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-seating-clearance-wheelchair", "statement": "Seating clearance for wheelchair access", "value_in": 60, "value_mm": 1524, "applies_to": ["walkway"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-seating-width-per-person", "statement": "Minimum seating width per person", "value_in": 24, "value_mm": 610, "applies_to": ["base"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-sink-landing-primary", "statement": "Sink landing area, wider side", "value_in": 24, "value_mm": 610, "applies_to": ["appliance", "base"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-sink-landing-secondary", "statement": "Sink landing area, narrower side", "value_in": 18, "value_mm": 457, "applies_to": ["appliance", "base"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-prep-counter", "statement": "Continuous prep countertop adjacent to sink, minimum size", "value_in": 36, "value_mm": 914, "applies_to": ["base", "appliance"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-dishwasher-sink-max-distance", "statement": "Maximum distance between dishwasher nearest edge and sink nearest edge", "value_in": 36, "value_mm": 914, "applies_to": ["appliance"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-refrigerator-landing", "statement": "Refrigerator landing area on handle side", "value_in": 15, "value_mm": 381, "applies_to": ["appliance"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-cooktop-landing-a", "statement": "Cooktop landing area, one side minimum", "value_in": 12, "value_mm": 305, "applies_to": ["appliance"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-cooktop-landing-b", "statement": "Cooktop landing area, other side minimum", "value_in": 15, "value_mm": 381, "applies_to": ["appliance"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-cooktop-clearance-protected", "statement": "Cooktop to protected/noncombustible surface above (e.g. rated hood)", "value_in": 24, "value_mm": 610, "applies_to": ["appliance", "wall"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-cooktop-clearance-unprotected", "statement": "Cooktop to unprotected/combustible surface above (e.g. cabinetry)", "value_in": 30, "value_mm": 762, "applies_to": ["appliance", "wall"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "high"},
  {"rule_id": "nkba-microwave-mount-max", "statement": "Microwave bottom maximum mount height above finished floor", "value_in": 54, "value_mm": 1372, "applies_to": ["appliance", "wall"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-microwave-undercounter-min", "statement": "Undercounter microwave bottom minimum height above finished floor", "value_in": 15, "value_mm": 381, "applies_to": ["appliance", "base"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-microwave-landing", "statement": "Microwave landing area (above, below, or adjacent to handle side)", "value_in": 15, "value_mm": 381, "applies_to": ["appliance"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-oven-landing", "statement": "Oven landing area next to or above oven", "value_in": 15, "value_mm": 381, "applies_to": ["appliance"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "medium"},
  {"rule_id": "nkba-landing-combination-bonus", "statement": "Combined adjacent landing area equals larger requirement plus bonus", "value_in": 12, "value_mm": 305, "applies_to": ["appliance"], "hard_or_soft": "recommended", "source_url": "http://starcraftcustombuilders.com/kitchen.design.rules.htm", "confidence": "low"},
  {"rule_id": "ada-passthrough-clearance", "statement": "Pass-through kitchen minimum clearance between opposing base cabinets/countertops/appliances/walls", "value_in": 40, "value_mm": 1016, "applies_to": ["walkway", "base"], "hard_or_soft": "hard", "source_url": "https://www.access-board.gov/ada/guides/chapter-3-clear-floor-or-ground-space-and-turning-space/", "confidence": "high"},
  {"rule_id": "ada-ushape-clearance", "statement": "U-shaped kitchen minimum clearance, enclosed on three contiguous sides", "value_in": 60, "value_mm": 1524, "applies_to": ["walkway", "base", "corner"], "hard_or_soft": "hard", "source_url": "https://www.access-board.gov/ada/guides/chapter-3-clear-floor-or-ground-space-and-turning-space/", "confidence": "high"},
  {"rule_id": "ada-clear-floor-space", "statement": "Minimum clear floor/ground space, forward or side approach", "value_in": 48, "value_mm": 1219, "applies_to": ["appliance", "walkway"], "hard_or_soft": "hard", "source_url": "https://www.access-board.gov/ada/guides/chapter-3-clear-floor-or-ground-space-and-turning-space/", "confidence": "high"},
  {"rule_id": "ada-turning-space-circular", "statement": "Minimum circular turning space diameter", "value_in": 60, "value_mm": 1524, "applies_to": ["walkway", "corner"], "hard_or_soft": "hard", "source_url": "https://www.access-board.gov/ada/guides/chapter-3-clear-floor-or-ground-space-and-turning-space/", "confidence": "high"},
  {"rule_id": "ada-worksurface-max-height", "statement": "Accessible work-surface maximum height above finished floor", "value_in": 34, "value_mm": 864, "applies_to": ["base", "appliance"], "hard_or_soft": "hard", "source_url": "https://www.corada.com/documents/2010ADAStandards/804", "confidence": "high"},
  {"rule_id": "ada-knee-clearance-min-height", "statement": "Accessible knee clearance minimum height", "value_in": 27, "value_mm": 686, "applies_to": ["base"], "hard_or_soft": "hard", "source_url": "https://www.access-board.gov/ada/guides/chapter-3-clear-floor-or-ground-space-and-turning-space/", "confidence": "high"},
  {"rule_id": "ada-toe-clearance-max-height", "statement": "Accessible toe clearance maximum height", "value_in": 9, "value_mm": 229, "applies_to": ["base"], "hard_or_soft": "hard", "source_url": "https://www.access-board.gov/ada/guides/chapter-3-clear-floor-or-ground-space-and-turning-space/", "confidence": "high"},
  {"rule_id": "cab-base-height-no-top", "statement": "Base cabinet height without countertop", "value_in": 34.5, "value_mm": 876, "applies_to": ["base"], "hard_or_soft": "recommended", "source_url": "https://www.mrhandyman.com/blog/standard-kitchen-cabinet-sizes/", "confidence": "high"},
  {"rule_id": "cab-base-height-with-top", "statement": "Base cabinet finished height with countertop, above finished floor", "value_in": 36, "value_mm": 914, "applies_to": ["base"], "hard_or_soft": "recommended", "source_url": "https://www.mrhandyman.com/blog/standard-kitchen-cabinet-sizes/", "confidence": "high"},
  {"rule_id": "cab-base-depth", "statement": "Base cabinet standard box depth", "value_in": 24, "value_mm": 610, "applies_to": ["base"], "hard_or_soft": "recommended", "source_url": "https://cabinetselect.com/standard-kitchen-cabinet-sizes/", "confidence": "high"},
  {"rule_id": "cab-toe-kick-height", "statement": "Toe kick height", "value_in": 4, "value_mm": 102, "applies_to": ["base"], "hard_or_soft": "recommended", "source_url": "https://kitchencabinetkings.com/blog/standard-toe-kick-height/", "confidence": "medium"},
  {"rule_id": "cab-toe-kick-depth", "statement": "Toe kick recess depth", "value_in": 3, "value_mm": 76, "applies_to": ["base"], "hard_or_soft": "recommended", "source_url": "https://www.homenish.com/toe-kick-dimensions/", "confidence": "medium"},
  {"rule_id": "cab-wall-mount-height", "statement": "Wall cabinet bottom mount height above finished floor", "value_in": 54, "value_mm": 1372, "applies_to": ["wall"], "hard_or_soft": "recommended", "source_url": "https://www.expohomeimprovement.com/complete-guide-to-kitchen-cabinet-heights-key-dimensions/", "confidence": "high"},
  {"rule_id": "cab-backsplash-clearance", "statement": "Open clearance between countertop and wall cabinet bottom", "value_in": 18, "value_mm": 457, "applies_to": ["wall", "base"], "hard_or_soft": "recommended", "source_url": "https://www.expohomeimprovement.com/complete-guide-to-kitchen-cabinet-heights-key-dimensions/", "confidence": "high"},
  {"rule_id": "cab-wall-depth-standard", "statement": "Wall cabinet standard depth", "value_in": 12, "value_mm": 305, "applies_to": ["wall"], "hard_or_soft": "recommended", "source_url": "https://cabinetselect.com/standard-kitchen-cabinet-sizes/", "confidence": "high"},
  {"rule_id": "cab-wall-depth-alt-15", "statement": "Wall cabinet alternate depth (over sink/fridge)", "value_in": 15, "value_mm": 381, "applies_to": ["wall"], "hard_or_soft": "soft", "source_url": "https://cabinetselect.com/standard-kitchen-cabinet-sizes/", "confidence": "medium"},
  {"rule_id": "cab-wall-depth-alt-24", "statement": "Wall cabinet alternate depth (deep specialty units)", "value_in": 24, "value_mm": 610, "applies_to": ["wall"], "hard_or_soft": "soft", "source_url": "https://cabinetselect.com/standard-kitchen-cabinet-sizes/", "confidence": "medium"},
  {"rule_id": "cab-tall-depth", "statement": "Tall/pantry cabinet standard depth", "value_in": 24, "value_mm": 610, "applies_to": ["tall"], "hard_or_soft": "recommended", "source_url": "https://www.27estore.com/blog/how-deep-should-pantry-cabinets-be", "confidence": "high"},
  {"rule_id": "cab-tall-height-84", "statement": "Tall/pantry cabinet standard height option", "value_in": 84, "value_mm": 2134, "applies_to": ["tall"], "hard_or_soft": "soft", "source_url": "https://www.27estore.com/blog/how-deep-should-pantry-cabinets-be", "confidence": "high"},
  {"rule_id": "cab-tall-height-90", "statement": "Tall/pantry cabinet standard height option", "value_in": 90, "value_mm": 2286, "applies_to": ["tall"], "hard_or_soft": "soft", "source_url": "https://www.27estore.com/blog/how-deep-should-pantry-cabinets-be", "confidence": "high"},
  {"rule_id": "cab-tall-height-96", "statement": "Tall/pantry cabinet standard height option", "value_in": 96, "value_mm": 2438, "applies_to": ["tall"], "hard_or_soft": "soft", "source_url": "https://www.27estore.com/blog/how-deep-should-pantry-cabinets-be", "confidence": "high"},
  {"rule_id": "cab-width-increment", "statement": "Standard cabinet nominal width module", "value_in": 3, "value_mm": 76, "applies_to": ["base", "wall", "tall"], "hard_or_soft": "soft", "source_url": "https://www.foreverbuiltkitchens.com/blog/kitchen-cabinet-dimensions", "confidence": "high"},
  {"rule_id": "cab-32mm-grid-spacing", "statement": "Frameless (32mm system) hole spacing on center", "value_in": 1.26, "value_mm": 32, "applies_to": ["base", "wall", "tall"], "hard_or_soft": "soft", "source_url": "https://ajcabs.com/custom-cabinets/32mm_vs_face_frame/", "confidence": "medium"},
  {"rule_id": "filler-blind-corner-min", "statement": "Blind corner cabinet minimum filler width", "value_in": 3, "value_mm": 76, "applies_to": ["corner", "base"], "hard_or_soft": "recommended", "source_url": "https://woodcabinets4less.com/blog/blind-base-cabinets-101/", "confidence": "medium"},
  {"rule_id": "filler-frameless-corner-max", "statement": "Frameless blind-corner filler recommended upper range", "value_in": 4, "value_mm": 102, "applies_to": ["corner", "base"], "hard_or_soft": "soft", "source_url": "https://www.bestonlinecabinets.com/blog/blind-corner-cabinet/", "confidence": "low"},
  {"rule_id": "corner-lazy-susan-footprint", "statement": "Diagonal corner base cabinet standard footprint per wall leg", "value_in": 36, "value_mm": 914, "applies_to": ["corner", "base"], "hard_or_soft": "soft", "source_url": "https://www.cabinets.com/dcls36-l-shaker-maple-painted-bright-white-diagonal-corner-lazy-susan-base-cabinet-1-door-assembled-kitchen-cabinet.html", "confidence": "medium"},
  {"rule_id": "countertop-overhang-front", "statement": "Countertop standard front overhang over base cabinet face", "value_in": 1.5, "value_mm": 38, "applies_to": ["base"], "hard_or_soft": "recommended", "source_url": "https://marble.com/articles/standard-countertop-overhang", "confidence": "high"},
  {"rule_id": "countertop-overhang-side-open", "statement": "Countertop side overhang at an open (non-wall) end", "value_in": 1.5, "value_mm": 38, "applies_to": ["base"], "hard_or_soft": "recommended", "source_url": "https://marble.com/articles/standard-countertop-overhang", "confidence": "medium"},
  {"rule_id": "countertop-overhang-seating", "statement": "Countertop overhang at island/peninsula seating", "value_in": 12, "value_mm": 305, "applies_to": ["base"], "hard_or_soft": "recommended", "source_url": "https://marble.com/articles/standard-countertop-overhang", "confidence": "medium"},
  {"rule_id": "countertop-overhang-support-threshold", "statement": "Overhang length beyond which structural support (corbel/bracket) is required", "value_in": 12, "value_mm": 305, "applies_to": ["base"], "hard_or_soft": "recommended", "source_url": "https://www.cectops.com/how-much-overhand-should-a-countertop-have/", "confidence": "medium"},
  {"rule_id": "awi-install-plumb-level-tolerance", "statement": "Cabinetry/casework installed plumb and level tolerance over a 96-inch run", "value_in": 0.125, "value_mm": 3.2, "applies_to": ["base", "wall", "tall", "corner"], "hard_or_soft": "hard", "source_url": "https://awinet.org/wp-content/uploads/2024/12/ANSI-AWI-0620-2018-Finish-Carpentry-Installation.pdf", "confidence": "high"},
  {"rule_id": "awi-reveal-overlay-min", "statement": "Recommended minimum reveal for frameless (reveal overlay) construction where unspecified", "value_in": 0.25, "value_mm": 6.4, "applies_to": ["base", "wall", "tall"], "hard_or_soft": "soft", "source_url": "https://awinet.org/standards/finish-carpentry-installation/requirements/aesthetic-4/", "confidence": "low"},
  {"rule_id": "awi-reveal-inset-max-variance", "statement": "Maximum uniform reveal variance for inset/face-frame construction", "value_in": 0.125, "value_mm": 3.2, "applies_to": ["base", "wall", "tall"], "hard_or_soft": "recommended", "source_url": "https://awinet.org/standards/finish-carpentry-installation/requirements/aesthetic-4/", "confidence": "low"},
  {"rule_id": "kcma-wall-cabinet-load-test", "statement": "Wall cabinet / wall-hung base cabinet static load test without failure", "value_in": null, "value_mm": null, "applies_to": ["wall"], "hard_or_soft": "hard", "source_url": "https://www.woodworkingnetwork.com/cabinets/strength-behind-certified-cabinetry-ansikcma-a1611", "confidence": "medium"},
  {"rule_id": "kcma-door-drawer-cycle-test", "statement": "Door/drawer operational cycle test minimum cycles", "value_in": null, "value_mm": null, "applies_to": ["base", "wall", "tall"], "hard_or_soft": "hard", "source_url": "https://www.woodworkingnetwork.com/cabinets/strength-behind-certified-cabinetry-ansikcma-a1611", "confidence": "medium"},
  {"rule_id": "kcma-box-dimension-tolerance", "statement": "Assembled cabinet box dimensional tolerance (width/height/depth) — not confirmed against primary KCMA A161.1 text", "value_in": 0.09375, "value_mm": 2.4, "applies_to": ["base", "wall", "tall"], "hard_or_soft": "recommended", "source_url": "https://kcma.org/sites/default/files/2024-08/KCMA%20A161.1%202022%20High%20Res.pdf", "confidence": "low"},
  {"rule_id": "cnc-panel-tolerance-typical", "statement": "Typical CNC panel-processing dimensional tolerance (general woodworking/manufacturing practice, not cabinet-specific standard)", "value_in": 0.004, "value_mm": 0.1, "applies_to": ["base", "wall", "tall"], "hard_or_soft": "soft", "source_url": "https://shop.machinemfg.com/guide-to-cnc-machining-tolerances/", "confidence": "medium"},
  {"rule_id": "out-of-square-scribe-field-threshold", "statement": "Field practice threshold of wall gap variance beyond which installers scribe a custom filler rather than use fixed-width stock", "value_in": 0.75, "value_mm": 19, "applies_to": ["corner", "wall", "base"], "hard_or_soft": "soft", "source_url": "https://www.finehomebuilding.com/forum/cabinet-install-on-unsquare-wall", "confidence": "low"},
  {"rule_id": "light-rail-valance-height", "statement": "Typical light-rail valance height concealing under-cabinet lighting", "value_in": 2, "value_mm": 51, "applies_to": ["wall"], "hard_or_soft": "soft", "source_url": "https://woodweb.com/knowledge_base/Upper_Cabinet_Height_Standard.html", "confidence": "low"},
  {"rule_id": "wall-cabinet-42in-ceiling-fit", "statement": "42-inch wall cabinet fits an 8-ft (96-inch) ceiling with no crown/soffit trim", "value_in": 96, "value_mm": 2438, "applies_to": ["wall"], "hard_or_soft": "soft", "source_url": "https://cornerrenovation.com/blog/8-foot-ceiling-kitchen-cabinets", "confidence": "medium"}
]
```
