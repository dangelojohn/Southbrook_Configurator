# BASE Corner Cabinet Taxonomy — Engineering Reference

**Scope:** Every commercially real BASE (lower) cabinet corner-condition type used in North American residential kitchen cabinetry, with construction, dimensional, mechanism-envelope, and placement data suitable for driving a pure-Python layout/placement engine.

**Method note on confidence:** Numbers tagged `verified` were read directly out of a manufacturer spec book, hardware-vendor product spec sheet, or a standards body PDF (source URL given inline and in the Sources list). Numbers tagged `ESTIMATE (basis: …)` are inferred from practitioner discussion (WoodWeb, forums), cross-referenced adjacent products, or general pattern-matching across multiple retail listings — they are directionally reliable but not manufacturer-certified for any specific SKU. No number in this document was invented without a stated basis.

Two spec-book primary sources anchor most of the verified dimensions:
- **Wellborn Cabinet Inc.**, *Select & Premier Specification & Price Catalog* (03/27/2023 edition), a face-frame manufacturer — PDF: https://s3.amazonaws.com/wellbornmedia/cms/63cae0d5a0040.pdf
- **KraftMaid**, *Momentum Spec Book* (frameless/full-access construction) — https://s3.amazonaws.com/FlippingBookStorage/KraftMaid%20Momentum%20Spec%20Book/files/assets/basic-html/page87.html

These two let every type below be checked against **both** face-frame and frameless construction where the product line overlaps.

---

## 1. Blind Corner Base Cabinet (basic — door/shelf only, no pullout)

The default, lowest-cost solution to a 90° inside corner: a single box that occupies the full run on one wall (the "open" or "hinge" leg) and extends its depth into the return wall, leaving a wedge of cabinet interior ("the blind") that is only reachable by kneeling and reaching past the door opening.

Wellborn's own installation diagram is explicit about the geometry: the door/opening sits at the front on the **hinge leg**; the box's blind portion runs back along the **return leg**; a filler strip is required at the boundary with the adjoining run on the return leg so its doors/drawers can clear the blind box's face frame.

| Property | Value | Confidence |
|---|---|---|
| Nominal box widths (hinge leg) | 33, 36, 39, 42, 45, 48 in (Wellborn BBC36–BBC48; general retail range 33–42 in) | verified |
| Standard depth | 23⅝ in face-of-frame (Wellborn), nominal 24 in industry-wide | verified |
| Standard height | 34½ in (30 in fixed-height / ADA "Active Living" variant: 32½ in) | verified |
| Door opening width (usable, hinge side) | 9 in (BBC36) up to 19½ in (BBC48), scaling with nominal width | verified |
| Door width, top-overlay (TOL) style | 10–20½ in across BBC36–BBC48 | verified |
| Door width, full-overlay (FOL) style | 11½–22 in across BBC36–BBC48 | verified |
| Max door "pull" (swing clearance along hinge-leg wall) | 40½ in (BBC36) to 51 in (BBC48) | verified |
| Min door pull, with 1½" hardware projection | 37½–48 in across sizes | verified |
| Min door pull, no hardware | 36–48 in across sizes | verified |
| Center stile (face-frame blind-side stile) | 6 in wide | verified |
| Filler required, adjoining cabinet (return leg) | 1 in minimum (no door/drawer hardware) / 2½ in minimum (with hardware pulls) | verified |
| Frameless (KraftMaid) equivalent | Base Corner Angle "BCA24 BUTT": 34½"H × 24"W × 24"D, single door, 45° hinge, 143° opening angle | verified |
| Blind cavity depth (unreachable-by-sight zone) | ~24–27 in behind the door opening | ESTIMATE (basis: nominal width minus opening width) |

**Prose.** This is the cabinetmaker's fallback: cheapest hardware (a single ordinary 45°-mount hinge or, in frameless lines, a 143°-opening hinge), simplest carcass (still a rectangular box — no mitered/diagonal panel needed), and it is the type every other corner solution in this document exists to improve on. Its principal defect is the "blind" zone: roughly two-thirds of the box's interior volume is inaccessible without kneeling and reaching in past a 9–19½ in door opening, and anything stored past ~20 in of reach is effectively lost. It is nearly always retrofitted or upgraded with a swing-out shelf kit, Magic Corner unit, or LeMans mechanism (see below) rather than sold empty in a new install, though budget/RTA lines still ship it bare with a single fixed shelf.

**Placement facts.** Consumes its full nominal width (33–48 in) along the hinge-leg wall as usable frontage but only 9–19½ in of that is *operable*; consumes only its depth (24 in) along the return-leg wall, where a mandatory 1–2½ in filler must separate it from the next cabinet's door/drawer swing. Must not be placed directly adjacent (blind side) to another blind corner, a dishwasher, or anything requiring hinge clearance on the return leg without the filler.

---

## 2. Blind Corner with Swing-Out Shelves (pullout variant)

Same box envelope as the basic blind corner, but the interior blind cavity gets a piano-hinge-mounted shelf frame (wood or wire) attached to the door or to a center mullion so that opening the door drags the shelving out of the blind zone into reach.

| Property | Value | Confidence |
|---|---|---|
| Box widths | 45, 48 in in Wellborn's ADA "Active Living" swing-out line (ACBBC45SOS / ACBBC48SOS); general market also builds 36–42 in swing-out blind corners (KraftMaid "Base Blind Corner with Chrome Swing-Outs") | verified (Wellborn) / verified product exists (KraftMaid) but dims not published on the fetched page |
| Height | 32½ in (Wellborn Active Living / ADA line) or 34½ in standard-height equivalent | verified |
| Depth | 24 in | verified |
| TOL door dimension | 25¼ in (45 box) / 28¼ in (48 box) | verified |
| FOL door dimension | 24 3/16 in (45 box) / 27 3/16 in (48 box) | verified |
| Max pull | 49½ in (45 box) / 51 in (48 box) | verified |
| Min pull w/ hardware | 46½ in (45) / 48 in (48) | verified |
| Min pull w/o hardware | 45 in (45) / 48 in (48) | verified |
| Mechanism | 1 door, 2 swing-out shelves (steel bar frame, one "bottom shelf slides out" separately) | verified |
| Adjacent tall-pantry analog (NOT base height, cross-reference only) | Hardware Resources PSO45: fits 36 in pantry column, min opening 33 in wide, swing-out wing 25 15/16 in W × 8 in D, 10 total shelves (birch/birch-ply) | verified (different product class — full-height pantry, cited only to bound shelf-wing envelope) |
| Filler | Same 1 in / 2½ in rule as basic blind corner | verified |

**Prose.** This is the most common "upgrade" a homeowner actually buys over the bare blind corner: roughly double the hardware cost of a plain hinge, no rotation, no diagonal cut needed in the box — just a piano-hinged shelf frame bolted inside a stock blind-corner carcass. Access is still single-swing (shelves move only as far as the door opens, not fully independent of the door), so it does not reach 100% of the blind cavity, but it substantially outperforms the bare box.

**Placement facts.** Identical wall-consumption footprint to the basic blind corner (same box). The added swing arc requires the same or slightly larger *door* swing clearance in the room (170°-class swings are common on the upgraded hardware) — confirm no island/peninsula edge intrudes into the door's open arc within roughly one door-width of the corner.

---

## 3. Diagonal / Angle Corner Cabinet — Full-Round Lazy Susan (independent rotation)

A cabinet whose face frame is mitered/cut on a 45° diagonal so it presents a single door (or a bifold pair) square to the room, with equal box legs on both walls. Behind the door sits a full-round rotating shelf assembly that spins independently of the door.

| Property | Value | Confidence |
|---|---|---|
| Nominal box (both legs equal) | 36 in × 36 in (Wellborn BLS36); market range 33–42 in | verified (Wellborn) |
| Height | 34½ in | verified |
| Susan shelf diameter (Wellborn BLS36, door-attached/dependent style) | 28 in, white polymer, all door styles | verified |
| Full-round independent susan diameters (Rev-A-Shelf 6072/3071/LD series) | 18, 20, 24, 28, 32 in | verified |
| Door config (Wellborn BLS36) | Double doors attached to the rotary shelves (i.e., dependent — see Type 4 below for the distinct bifold mechanism) | verified |
| Filler required | Not standard — diagonal box legs are cut to the corner and abut adjoining cabinets directly | ESTIMATE (basis: no filler note in Wellborn diagonal-cabinet section, unlike the blind-corner section which explicitly calls one out) |

**Prose.** WoodWeb's practitioner consensus ranks the full-round "super susan" (adjustable center shelf riding a fixed pole) as the storage-efficiency winner among simple diagonal solutions, because a single center post prevents the alignment drift that plagues cheap two-shelf clip-together lazy susans. The tradeoff flagged repeatedly by installers: real usable storage gain over a blind corner is smaller than it looks once you subtract the corner geometry lost to the pole and bearing hub, and cheap plastic susans (vs $350+ premium units with metal bearings) wobble and jam over time.

**Placement facts.** Consumes its full nominal width on *both* legs (33–42 in each, typically equal), unlike the blind corner which only fully consumes one leg. No filler is generally needed since both adjoining runs land flush with the diagonal box's mitered ends. Requires door swing clearance in front of the corner point equal to roughly the door's own width (single door) or ~½ that per leaf (bifold pair).

---

## 4. Pie-Cut / Bifold-Door Lazy Susan (dependent rotation)

The historically dominant American corner solution: two door leaves hinged together at 90° (joined by a 90° cabinet-to-cabinet hinge) and hinged to the cabinet at the outer edges (typically a 170° Euro-style hinge), with a pie-shaped ("pie-cut") shelf bolted to the back of the doors so the whole assembly — doors and shelves — rotates together as one piece when opened.

| Property | Value | Confidence |
|---|---|---|
| Cabinet box, back-measured width → shelf size | 36 or 39 in box → 31 in pie-cut shelf; 33 in box → 28 in pie-cut shelf; 24 in box → used in wall (not base) corners | verified (Rev-A-Shelf / CabinetParts pie-cut sizing guide) |
| Clearance around shelf perimeter | 1–2 in all around, inside the cabinet | verified |
| Cabinet-side hinge | 170° Euro hinge | verified |
| Door-to-door hinge | 90° pie-cut/lazy-susan specialty hinge (also made in 135° variant for bay-window/non-square corners) | verified |
| Door-edge gap | ⅛ in between the two door panels when closed | verified |
| Height / depth | Same as host diagonal box: 34½ in H, 24 in D nominal | ESTIMATE (basis: inherits standard base-cabinet envelope; no dedicated pie-cut box spec found independent of Type 3) |

**Prose.** Because the shelf is door-mounted, opening either leaf immediately exposes the full pie-cut shelf with no separate rotation step — the classic "grandma's lazy susan" experience. Downsides documented across install guides: the door-to-door hinge is a common failure/misalignment point over years of use, and because the shelf rotates *with* the doors rather than independently, the door swing radius must be fully unobstructed (nothing — no appliance handle, no adjacent pulled-out drawer — can intrude into the full bifold arc).

**Placement facts.** Same footprint as Type 3 (equal-leg diagonal box, 33–39 in typical). Requires an unobstructed bifold swing arc through roughly 170° in front of the corner apex — larger operational clearance than the fixed-door full-round susan (Type 3), where only the single door, not the whole mechanism, swings.

---

## 5. Easy Reach Corner (wide-door single-swing susan)

Marketed as a friendlier alternative to the standard diagonal susan: a single, large door (not a bifold pair) hinged to open ~170°, with independently-rotating pie-cut shelves behind it. Distinct from Type 4 because the door does not carry the shelf/rotate with it, and distinct from a plain wall "Easy Reach" (which is the far more common usage of this term, in wall/upper cabinets, with fixed angled shelving rather than a susan) — the base-cabinet product below is a real stocked SKU, not a hypothetical.

| Property | Value | Confidence |
|---|---|---|
| Box (example: Home Decorators/Newport EZR33SSL) | 33 in W × 33 in D × 34½ in H | verified |
| Door | Single door, left-hinged in the cited SKU, opens 170° | verified |
| Interior mechanism | 2 adjustable pie-cut shelves, independently rotating ("Super Lazy Susan"), soft-close door | verified |
| Construction | Framed (face-frame) plywood box, factory-assembled | verified |

**Prose.** The 170° single-door swing is the defining placement-relevant fact: it needs meaningfully more open-door floor clearance directly in front of the corner than a blind corner's ~115–143° swing, but *less* rotational-arc clearance than the bifold pie-cut (Type 4) since only one leaf moves. Marketed as reducing "lost corner" perception because the opening is visually much larger than a standard diagonal cabinet's door.

**Placement facts.** Same equal-leg diagonal footprint as Types 3–4 (33 in × 33 in in the cited SKU). Door swing clearance zone in front of the corner must accommodate a full 170° single-leaf arc — check for peninsula ends or islands intruding on that arc.

---

## 6. Magic Corner I (Kesseböhmer / Häfele)

A door-mounted pull-out frame (usually wire baskets) linked mechanically to a second, independent shelf unit fixed inside the blind cavity: opening the door drags the front basket frame out, and a connecting arm/track simultaneously swings the rear shelf set out of the blind zone into the door opening. This is the entry-level (single-stage) version of the mechanism; Magic Corner II (Type 7) is the larger two-stage version.

| Property | Value | Confidence |
|---|---|---|
| Min. cabinet/door opening (Würth "MC 15.625" variant) | 19⅜ in | verified |
| Min. door opening (Barker "Magic Corner" RTA cabinet, using Häfele Magic Corner I) | 15⅝ in (396 mm) | verified |
| Host box (Barker's stocked Magic Corner cabinet) | 46 in W × 24 in D × 34½ in H, blind side 24 in | verified |
| Frame style | Frameless, full-overlay European construction (Barker's implementation); Blum soft-close hinges | verified |
| Filler | None — Barker's packaged unit ships with no additional filler required | verified |
| Load rating | Wire basket frames, several kg per shelf | ESTIMATE (basis: comparable Kesseböhmer wire-basket load ratings; exact figure not confirmed for Magic Corner I specifically) |

**Prose.** Magic Corner I is the hardware most often specified when a designer wants "some" corner extraction without the larger footprint/cost premium of a LeMans or Magic Corner II. It requires a wider physical box (46 in in the sourced retail SKU) than a bare blind corner of similar nominal opening, because the wire-frame carriage needs side clearance to travel.

**Placement facts.** Consumes ~46 in on the hinge leg (per the sourced retail SKU — verify against the specific Kesseböhmer catalog size chosen, as narrower cabinet-specific kits exist down to ~19⅜ in minimum opening) and standard 24 in depth on the return leg. No filler required per the Barker packaged spec. Confirm door swing (full basket-extraction pull) has unobstructed floor space in front of the corner at least equal to the basket's extension length.

---

## 7. Magic Corner II (Kesseböhmer / Häfele)

The larger-capacity, two-tier evolution of Magic Corner I: adds a second set of shelves/baskets so the total extracted storage roughly doubles, at the cost of a larger minimum cabinet envelope.

| Property | Value | Confidence |
|---|---|---|
| Min. cabinet opening depth | 19⅝ in | verified |
| Min. cabinet opening width | 20½ in | verified |
| Min. opening height | 21⅞ in | verified |
| Min. cabinet interior width | 37⅞ in | verified |
| Load capacity | Up to 32 kg (pots/dishes/appliances) | verified |
| Häfele metric sizing note | Minimum interior cabinet width 900–1000 mm; a 1000 mm-wide variant exists for 1000 mm base units only | verified |
| Door opening required | 20½ in (520 mm) minimum, plus hinge clearance | verified |
| Frame style | Frameless (European carcass) is the native format; face-frame installs require an additional reveal/filler allowance not separately quantified in sourced material | ESTIMATE (basis: mechanism is a frameless-cabinet hardware product; face-frame adaptation is a common but non-catalog practice) |

**Prose.** Magic Corner II is the step up from Type 6 when the corner box itself is sized ≥37⅞ in wide — below that width, Magic Corner I (or LeMans, Type 8) is the only mechanically compatible option. Both Magic Corner variants attach directly to the door, so the mechanism's reliability is tied to door/hinge condition over the cabinet's life; heavy door sag or misaligned hinges are the most common field-service issue reported by installers for this hardware family.

**Placement facts.** Requires the widest hinge-leg box of any door-mounted corner mechanism in this document short of LeMans (≥37⅞ in interior, meaning ~39–42 in nominal box width once face-frame/side-panel thickness is added). Return-leg (depth) consumption ≥19⅝ in interior, i.e. ≥21–24 in nominal depth.

---

## 8. LeMans Corner Unit (Kesseböhmer / Häfele)

A patented four-arm articulated pull-out: opening the door to roughly 85° causes two organically-shaped trays to swing fully out of the cabinet into the room on a fixed-axle four-bar linkage, fully independent of anything remaining in the blind cavity — widely regarded as the most complete-extraction corner mechanism short of full custom drawer banks.

| Property | Value | Confidence |
|---|---|---|
| Series / tray size | Series 40/45/50/60 → 12 in / 15 in / 18 in / 21 in trays respectively | verified |
| Min. cabinet opening — Series 45 | 16½ in W × 21 in H | verified |
| Min. face-frame opening — Series 50 | 17¾ in W × 21½ in H | verified |
| Door opening angle required for full tray extension | 85° | verified |
| Weight capacity | 25 kg (55 lb) per tray; up to 50 kg (110 lb) total unit | verified |
| Storage-space claim (mfr marketing) | "Up to 70% more storage" vs. an unfitted corner cabinet | verified (manufacturer claim, not independently measured) |
| Host box nominal width, by series | ESTIMATE 33 in (Series 40) up to ESTIMATE 45 in (Series 60), scaling with tray size | ESTIMATE (basis: proportional to min. opening width figures across the series; exact host-box widths per series not published in sourced material) |

**Prose.** LeMans is the premium-tier hardware answer to the corner problem — a four-arm linkage (not a simple pivot or door-mounted frame) that fully clears the blind cavity on a single door-opening motion. It is priced and positioned above Magic Corner I/II and well above a swing-out shelf kit; several trade sources note it commonly appears as the "upgrade" pitch in kitchen showrooms specifically because the fully-independent tray motion (vs. Magic Corner's door-linked motion) reads as the more dramatic demo.

**Placement facts.** Needs the door to swing to 85° for full tray travel — confirm no appliance, peninsula edge, or adjacent open door intrudes into an 85°+ door arc directly in front of the corner. Minimum openings run 16½–17¾ in depending on series, translating to nominal host boxes in the low-to-mid 30s of inches on the hinge leg (see estimate row above) and standard 24 in depth on the return leg.

---

## 9. Kidney / D-Shape Lazy Susan

A shelf shaped like a kidney bean or "D" rather than a full circle, designed to nest into corner cabinets whose door is likewise cut to a rounded/D profile rather than a straight diagonal — maximizes shelf area within a rounded-front cabinet silhouette.

| Property | Value | Confidence |
|---|---|---|
| Available diameters (2-shelf sets, Rev-A-Shelf 3472/5472/4WLS/LD-2472 families) | 24, 28, 32 in | verified |
| Bearing | Aluminum swivel bearing with built-in rotation stop | verified |
| Mount options | Bottom-mount fixed post or telescoping "Twist-n-Lock" post (accommodates cabinet height variance) | verified |
| Independent vs. dependent | Independently rotating (shelf spins free of the door) | verified |
| Host box | Same diagonal 33–36 in equal-leg footprint as Type 3 | ESTIMATE (basis: kidney susans are a drop-in shelf replacement for the same diagonal-corner box family, not a distinct carcass) |

**Prose.** Functionally a drop-in alternative to the full-round susan (Type 3) inside the same diagonal corner box — the kidney/D shape trades a small amount of swept storage area for a shelf silhouette that better matches a rounded door front and reduces the "dead sliver" at the shelf's outer edge that a full circle leaves in a square-ish cabinet corner.

**Placement facts.** Identical wall-consumption profile to Type 3 (equal legs, 33–36 in typical nominal box). No additional clearance beyond the host diagonal cabinet's own door swing.

---

## 10. Swing-Out Corner (base-height, non-Kesseböhmer swing-out shelf hardware)

Distinguished here from Type 2 (which is Wellborn's specific ADA/Active-Living blind-corner-plus-swing-out SKU) to capture the broader hardware category: aftermarket and other-manufacturer swing-out shelf kits (chrome wire or wood) retrofitted into an otherwise standard blind corner box, sold by KraftMaid ("Base Blind Corner with Chrome Swing-Outs"), Rev-A-Shelf, and others.

| Property | Value | Confidence |
|---|---|---|
| Host box | Standard blind corner box, 36–45 in nominal (Type 1 dimensions apply) | verified (box) / product confirmed to exist (KraftMaid) but full dims not retrieved |
| Mechanism | Chrome wire or wood shelf frame, piano-hinged, door-linked swing | verified (existence + general description) |
| Adjacent full-height (non-base) cross-reference | Rev-A-Shelf 4WP series and Hardware Resources PSO45: fit 36 in **pantry** columns (tall, not base height), min. opening 33 in W, wing envelope 25 15/16 in W × 8 in D, 10 shelves, birch/birch-ply construction, industrial piano hinge | verified (different product class, cited to bound plausible shelf-wing dimensions for the mechanism family) |

**Prose.** This entry exists to flag that "swing-out shelves in a corner" is a hardware *category* spanning multiple manufacturers and both base-height and full-pantry-height carcasses — a placement engine should treat "swing-out corner" as a mechanism attribute layered onto the Type-1 blind-corner box envelope, not a differently-shaped box.

**Placement facts.** Same as Type 1 (basic blind corner) for wall consumption; add door-swing clearance sufficient for the shelf wing to fully travel (≈26 in wing width, ≈8 in depth, per the cross-referenced pantry-class hardware — treat as an upper-bound estimate for base-height equivalents).

---

## 11. Corner Drawer System (45° drawer stack)

Replaces the rotating-susan approach entirely with true full-extension drawers built on a 45°-angled carcass — pie/trapezoid-shaped drawer boxes running on corner-specific (often proprietary-angle) slides, giving top-down visibility and full extension instead of a rotating or swinging mechanism.

| Property | Value | Confidence |
|---|---|---|
| Typical drawer-stack depth | ~30 in deep, 4-drawer stack, turned 45° into the corner | ESTIMATE (basis: WoodWeb practitioner "Inside Corner Drawers" discussion) |
| Depth premium vs. straight-run drawer bank | "Around 35% deeper than other drawer banks in the same kitchen" | ESTIMATE (basis: same WoodWeb discussion; practitioner estimate, not a manufacturer spec) |
| Outer stile treatment | Angled ("mitered"/beveled) outer stiles required for door/drawer-front clearance at the 45° turn | verified (construction technique, WoodWeb) |
| Retail drawer-replacement product (KraftMaid "corner drawers") | 3 full-width drawers replacing a lazy susan in a corner base cabinet | verified existence; no published dims retrieved |
| Barker "1 door/1 drawer" hybrid corner base | Door pulls open to the left; blind on the right side (drawer + door combo, not a full drawer stack) | verified existence; full dims not retrieved |

**Prose.** This is the most manufacturing-complex corner solution in this taxonomy: every drawer box is a non-rectangular (trapezoidal or pie-shaped) carcass, requiring either proprietary corner-drawer slide hardware or a shop-fabricated angled sub-frame, and the face frame/door fronts must be scribed to a 45° miter. WoodWeb's cabinetmakers explicitly flag the wasted volume at the very back point of the drawer (the acute corner of the trapezoid is unusable) and the extra depth required — the practical payoff is full-extension, eye-level access with zero rotating parts to fail, which is why it commands the highest cost tier of any type in this document.

**Placement facts.** Consumes both legs at the box's nominal diagonal width (similar footprint to Types 3/4) but requires **more physical depth into the room** than a susan-based diagonal cabinet of the same nominal width (≈35% more, per the WoodWeb estimate) because the angled drawer boxes need the extra depth to clear the 45° turn — a placement engine must not assume the same depth-into-corner value used for susan-type diagonal cabinets.

---

## 12. Corner Sink Base

A double-door (occasionally single-door) diagonal cabinet sized and reinforced to accept an inset or undermount sink and its plumbing/disposal, with no drawer (the sink bowl occupies the space a drawer would use) and typically no rotating mechanism.

| Property | Value | Confidence |
|---|---|---|
| Wellborn CSB36 | Double doors, 1 adjustable shelf, full top, "fits through a standard-size door" for delivery, natural-maple end panels | verified |
| Barker B45SINK2DM | 42–46 in box (both legs equal, 0.25 in increments), 45° specialty hinge (no soft-close), left/right return sides 20–24 in | verified |
| Sink-size fit, at 42×42 in box | Max recommended sink width ≈ 28 in | verified |
| Sink-size fit, at 46×46 in box | Max recommended sink width ≈ 33 in | verified |
| Practitioner custom sizing (WoodWeb) | 41 in cabinet with 24 in face fits a 33 in sink set back 3–4 in from the front; mitred return fillers can drop the apparent face back ~6 in to reduce visual bulk | verified (practitioner report, not a catalog SKU) |
| Standard height | 34½ in (implied, matches host base-cabinet line) | ESTIMATE (basis: no height explicitly stated in the Wellborn CSB entry; inherited from the surrounding base-cabinet section, which is uniformly 34½ in) |

**Prose.** Corner sink bases skip drawers by necessity (plumbing/disposal occupy the interior) and frequently use a non-soft-close 45° specialty hinge because standard soft-close mechanisms are not rated for the odd hinge geometry. Cabinetmakers consistently warn that the *practical* sink-width ceiling is well under the nominal box width — a 46 in box tops out around a 33 in sink — and recommend mocking the layout up in kraft paper at full scale before committing, since doorway pass-through width for delivery/installation of a fully-assembled unit is a frequent overlooked constraint.

**Placement facts.** Both legs consumed equally by the box's nominal width (typically 36–46 in). Must be planned with the sink model's actual footprint plus 3–6 in setback allowance in mind — do not treat the nominal box width as the usable sink envelope. No adjacent-cabinet filler noted as required (Wellborn CSB entry does not carry the blind-corner filler note), but return-side depth (20–24 in) must match the flanking run's depth or a scribe/filler is needed.

---

## 13. Open Corner Shelf (no door, static shelves)

The simplest possible corner treatment: the same diagonal-cut box as Type 3, but with fixed open shelves and no door at all — effectively a built-in corner display/utility shelf unit.

| Property | Value | Confidence |
|---|---|---|
| Box footprint | Same as Type 3 diagonal corner: 33–42 in nominal, both legs equal, 34½ in H, 24 in D | ESTIMATE (basis: shares the diagonal-corner carcass family; no dedicated open-shelf SKU spec found) |
| Mechanism | None — fixed shelves | verified (as a described option; WoodWeb: "Full diagonal with open shelves — simplest but difficult to access items") |
| Accessibility | Ranked as the *worst* for deep-shelf accessibility among diagonal-corner practitioner options, precisely because nothing rotates or swings | verified (practitioner assessment) |

**Prose.** WoodWeb's own six-option comparison of corner solutions ranks this dead last on accessibility despite being cheapest to build — no rotating hardware, no special hinge, just a mitered box with shelf pins. It survives commercially mainly as a low-cost builder-grade option or, in higher-end kitchens, as an intentional open display shelf (matching open shelving used decoratively elsewhere in the kitchen) rather than as active working storage.

**Placement facts.** Same footprint as Type 3. No door swing clearance required at all (a genuine placement-engine advantage — it can sit adjacent to fixed obstructions that a hinged corner cabinet could not).

---

## 14. Dead / Void Corner (with filler return)

Not a cabinet at all — the deliberate decision to leave the corner as unused volume, closing it off with a filler panel/return rather than installing any corner-specific box. The two flanking cabinet runs simply stop short of the true corner, each capped with a filler.

| Property | Value | Confidence |
|---|---|---|
| Typical filler-return width per leg | ~3 in (each run starts 24 in from the corner wall behind a 3 in filler, or the corner-turn filler itself is ~3 in) | ESTIMATE (basis: general retail/installation guidance; not a single manufacturer standard) |
| Minimum practical dead-space to preserve door/drawer clearance | ~6 in minimum, per general industry guidance | ESTIMATE (basis: aggregated retail/installation sources; no single authoritative citation found) |
| Mechanism / hardware | None | verified (by definition) |

**Prose.** Explicitly endorsed by some practitioners for very large kitchens with storage to spare, where the labor/hardware cost of any corner mechanism isn't worth the marginal storage gained. This is the placement engine's "valid null" state for a corner — it should be modeled as a legitimate output (a filler + two capped runs), not an error condition, whenever available corner-cabinet stock doesn't cleanly fit the remaining run length.

**Placement facts.** Wall consumption on each leg reduces to whatever filler width is chosen (~3 in typical, ESTIMATE) plus the last few inches of each flanking cabinet's clearance-only zone (up to ~6 in per leg combined, ESTIMATE) — no functional storage envelope to plan around at all.

---

## 15. 45°/135° Non-Square Corner Condition (bay windows, canted walls)

Not a single cabinet type but a *site condition* that forces custom treatment of whichever corner-cabinet type would otherwise be used: bay windows and canted/non-90° walls create 135° (obtuse) or 45° (acute) corners instead of the standard 90°, and none of the stock 90°-cornerdesigns above drop in without modification.

| Property | Value | Confidence |
|---|---|---|
| Susan diameter commonly used at these non-square corners | 18–20 in (smaller than the 28–32 in used at true 90° corners) | verified (WoodWeb "45-Degree Corner Cabinet Options" discussion) |
| Angled filler standard angles | 22.5° or 45° | verified |
| Face-frame extension technique for 45°-turn cabinets | Shops build extended face frames with 22½° bevels | verified |
| Back-panel relief cut (even at true 90° corners, to accommodate non-square drywall) | Back cut at 45° angle, 4–8 in in from the true back corner | verified |
| Recommended approach, inside (acute/135°) corners | Fixed narrow shelf + prioritize drawers in flanking runs over expanding cabinet depth ("all those 135° turns will make for wasted space regardless of approach") | verified (practitioner recommendation) |
| Recommended approach, outside (135°, e.g. bay window apex) corners | Round-shelf solutions favored | verified (practitioner recommendation) |

**Prose.** Every practitioner source consulted agrees this condition inherently wastes more volume than a true 90° corner, regardless of which hardware family is applied, and that the correct engineering response is to shrink expectations (smaller susan, simpler shelf) rather than force a full-size mechanism into a non-square opening. For a placement engine, this should be modeled as a **corner-angle parameter** on the corner-condition object (45°, 90°, 135°) that constrains which of Types 1–13 are even eligible, and derates susan/mechanism envelope sizes when angle ≠ 90°.

**Placement facts.** No fixed wall-consumption figures — dimensions are inherently site-specific/custom. Treat susan/shelf diameter as capped at ~18–20 in (vs. 28–32 in at square corners) as a conservative default when angle ≠ 90°.

---

## 16. Outside (Convex/Clipped) Corner Cabinet

The mirror-image problem to an inside corner: where a cabinet run turns *outward* (e.g., a peninsula's leading edge, or a kitchen island corner exposed to a walkway), a sharp 90° box corner is a collision/injury hazard and reads as visually blunt — shops instead clip or angle the corner.

| Property | Value | Confidence |
|---|---|---|
| Clipped-end example spec | 12 in × 12 in "Right Clipped End Cabinet" with a 6 in (or 26.56°) clip | verified (shop-catalog example, unfinished-kitchen-cabinets.net) |
| Angle-corner example spec | 25 in × 25 in "Angle Corner Cabinet" with 12 in left and right ends | verified (same source) |
| Common clip angles | 30° or 45° | verified |
| Panel/back thickness | ¼ in flush backs, ¾ in end panels and face-frame stock (shop standard) | verified |
| Mechanism | Typically none (fixed shelf, sometimes an open display shelf or narrow wine-rack insert given the shallow point) | ESTIMATE (basis: shallow trapezoidal interior at the clipped point is a poor fit for a door/drawer; no manufacturer-catalog SKU with active hardware found) |

**Prose.** Unlike every inside-corner type above, this condition is overwhelmingly shop-built to order rather than sold as a stocked SKU from a major national manufacturer — none of KraftMaid, Wellborn, Fabuwood, or Barker's fetched catalogs list an "outside corner" product line, only inside-corner families. Treat this as a custom/shop-fabrication category in a placement engine: eligible whenever a run's leading edge is convex and exposed to traffic, but without a standard nominal-size table to draw from.

**Placement facts.** The clip removes a fixed depth from the box corner (6 in in the sourced 12×12 example) rather than consuming additional wall length — net effect on the placement engine is a *reduction* of usable countertop at the clipped point, not a wall-consumption addition on either leg.

---

## 17. Peninsula / Island Corner Condition

Where a peninsula run meets a perpendicular wall run, or where an island's own corner needs a finished treatment, the "corner cabinet" question becomes about the *transition and termination* of the run rather than a single boxed mechanism — often paired with one of Types 1–10 at the actual wall-meeting corner, plus a separate finished end treatment where the peninsula/island run terminates in open space.

| Property | Value | Confidence |
|---|---|---|
| Peninsula base cabinet width range | 12–48 in, 24 in standard depth (custom depths available) | verified (27estore peninsula-cabinet line) |
| Configuration options | 2, 3, or 4 doors; optional drawers; blind-corner options available specifically for L-shaped/transitional layouts | verified |
| Finished-end treatments | Decorative side/end panels, wainscot panels, applied doors, double-sided (see-through) door access for peninsulas facing a family room | verified |
| Example single unit | "Base Peninsula Cabinet 15 in for Two Doors" | verified (product listing) |

**Prose.** This entry is deliberately a *condition*, not a fixed-dimension cabinet family: at the wall-meeting corner, specify one of Types 1–10 based on desired storage/mechanism tier; at the peninsula/island's exposed terminating end, specify a finished end panel (and, if the end faces a seating area, consider double-sided/see-through cabinet doors). A placement engine should model "peninsula corner" as a composite: {wall-corner cabinet type} + {termination end-panel treatment}, not as its own single box type.

**Placement facts.** No independent wall-consumption figure — inherits whatever cabinet type is placed at the actual wall corner (see that type's entry) plus the termination end panel, which typically consumes 0.75–1.5 in of additional length at the open end for the panel material itself (ESTIMATE, basis: standard cabinet end-panel stock thickness).

---

## 18. Transition Cabinet (depth-step / "Base End Angle")

Handles the case where a cabinet run must step down in depth — e.g., a 24 in-deep run needs to meet a 12 in-deep run (common next to a shallow appliance, a reduced-depth peninsula return, or where cabinetry must clear a window/door casing) — via an angled-face cabinet rather than an abrupt 90° step.

| Property | Value | Confidence |
|---|---|---|
| KraftMaid Base End Angle "BEA12" | 34½ in H; depth transitions from 24 in (standard) down to 12 in across the cabinet's angled face; 2 adjustable shelves; ordered as R or L hand | verified |
| Construction note | The 24 in-deep end "is not designed to be exposed" — must always land against another cabinet or a wall, never as a finished/visible end | verified |
| Availability | Both APC (all-plywood construction) and CFO (cabinet-front-only) options | verified |

**Prose.** This is technically a *depth transition*, not an angle-of-wall corner, but manufacturers group it in the same product family as corner cabinets because it solves the same underlying problem — a run of cabinets can't simply be square-cut where box depths change — using the identical angled-face-frame technique as a 45° diagonal corner cabinet. Its one hard constraint (the deep end must never be exposed) is a placement-engine-relevant invariant: never place this type as a run terminus with its 24 in end facing open space.

**Placement facts.** Consumes 12 in on the shallow leg/wall and 24 in on the deep leg/wall (by definition, since the cabinet *is* the depth transition). The 24 in-deep end must always abut another cabinet, appliance, or wall — never left exposed.

---

## Cross-Cutting Placement Rules (synthesized across all types)

1. **Filler minimums are real and load-bearing for placement, not cosmetic.** Wellborn's blind-corner filler rule (1 in without hardware / 2½ in with hardware pulls) recurs verbatim across every blind-corner SKU size (BBC36–48, ACBBC36, ACBBC45/48-SOS) — treat it as a structural constant for any blind-corner-type box, not a per-SKU variable.
2. **NKBA Guideline 29 (Corner Cabinet Storage):** "At least one corner cabinet should include a functional storage device… This guideline does not apply if there are no corner cabinets." (Source: NKBA Kitchen Planning Guidelines.) A placement engine targeting NKBA compliance should flag — but not hard-fail — a layout where every corner resolves to a Type 14 (dead/void) or Type 13 (open shelf, no mechanism) treatment.
3. **NKBA Guideline 4 (Separating Work Centers):** "A full-height, full-depth, tall obstacle should not separate two primary work centers… A properly recessed tall corner unit will not interrupt the workflow and is acceptable." Relevant when a corner condition sits between two of the kitchen's primary work centers (sink/cooktop/refrigerator).
4. **Door-swing arcs vary by an order of magnitude across types** — from 0° (Type 13, open shelf; Type 14, dead corner) up to a full bifold ~170° (Type 4) or an 85°-minimum four-arm mechanism (Type 8, LeMans). A placement engine must carry door-swing-angle as a first-class per-type attribute when checking for peninsula/island/appliance-door collisions near a corner — nominal box width alone is insufficient.
5. **Depth-into-room is not uniform across the diagonal-cabinet family.** Susan-based diagonal cabinets (Types 3, 4, 5, 9) share the standard ~24 in base depth; the 45° corner-drawer system (Type 11) needs materially more (≈+35%, per WoodWeb) because of the angled drawer-box geometry — do not reuse one depth constant across all diagonal-corner types.
6. **Non-90° corners (Type 15) cap mechanism size.** Default susan/mechanism diameter should step down from the 28–32 in square-corner default to 18–20 in whenever the corner-condition angle parameter is not 90°.

---

## Sources

- Wellborn Cabinet Inc., *Select & Premier Specification & Price Catalog*, 03/27/2023 — https://s3.amazonaws.com/wellbornmedia/cms/63cae0d5a0040.pdf
- KraftMaid *Momentum Spec Book*, page 87 (Base Corner Angle / Base End Corner / Base End Angle) — https://s3.amazonaws.com/FlippingBookStorage/KraftMaid%20Momentum%20Spec%20Book/files/assets/basic-html/page87.html
- KraftMaid corner-drawer product page — https://www.kraftmaid.com/corner-drawers/
- KraftMaid pantry swing-out product page — https://www.kraftmaid.com/pantry-swing-out/
- Barker Modern, 1-door 45° base corner cabinet (B451DM) — https://www.barkermodern.com/product-p/b451dm.htm
- Barker Modern, 2-door 45° base corner cabinet (B452DM) — https://www.barkermodern.com/product-p/b452dm.htm
- Barker Modern, 2-door 45° base corner SINK cabinet (B45SINK2DM) — https://www.barkermodern.com/product-p/b45sink2dm.htm
- Barker Modern, Magic Corner base cabinet (Häfele Magic Corner I) — https://www.barkermodern.com/product-p/b1d1drmagiccornerrightm.htm
- NKBA, *Kitchen Planning Guidelines with Access Standards* — https://nkba-ps.com/images/downloads/Awards/nkba_kitchen_planning_guidelines_pre_2023.pdf
- Kesseböhmer, LeMans corner-unit solution page — https://www.kesseboehmer.com/en/storage-solutions/kitchen/corner-units/lemans
- Kesseböhmer, Magic Corner solution page — https://www.kesseboehmer.com/en/storage-solutions/kitchen/corner-units/magic-corner
- CabinetParts.com, Kessebohmer 541.32.745 LeMans II Series 45 — https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132745-p24164
- CabinetParts.com, Kessebohmer 541.32.150 LeMans II Series 50 — https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132150-p24145
- CabinetParts.com, Kessebohmer 548.10.240/241 Magic Corner Two — https://www.cabinetparts.com/g/magic-corner-ii-kessebohmer-g13662
- Würth Baer Supply, Magic Corner I (15.625 MCO) — https://wurthbaersupply.com/product/755631/MAGIC-CORNER-15.625-MCO-RIGHT-CP-MP-BOMMC1562RCP-MP
- Häfele US product page, Kesseböhmer LeMans II Set — https://www.hafele.com/us/en/product/kesseboehmer-lemans-ii-set-for-blind-corner-cabinets/P-00856493/
- Advance Design Hardware, Magic Corner II by Häfele — https://advancedesignhardware.com/collections/kitchen-organization-1/products/magic-corner-ii-by-hafele
- Rev-A-Shelf, kidney-shape lazy susans category — https://rev-a-shelf.com/kitchen/lazy-susans/kidney-shape
- Rev-A-Shelf, pie-cut lazy susans category — https://rev-a-shelf.com/kitchen/lazy-susans/pie-cut
- Rev-A-Shelf 3472/5472/LD series product listings (Home Depot / CabinetParts / WoodworkerExpress) — https://www.homedepot.com/p/Rev-A-Shelf-32-in-Almond-Polymer-Kidney-Lazy-Susan-Set-3472-32-15-52/304893143 ; https://www.cabinetparts.com/p/revashelf-organizers-kitchen-organizers-RV6072281152-p37622
- CabinetParts.com, Pie-Cut Lazy Susan installation help — https://www.cabinetparts.com/how-to/pie-cut-cabinet-lazy-susan-installation-help/p184
- Hardware Resources, PSO45 Wood Pantry Swingout — https://www.hardwareresources.com/organizers/cabinet-organizers/pantry-organizers/pso45.html
- Home Decorators Cabinetry, Newport Easy Reach corner base (EZR33SSL) — https://homedecoratorscabinetry.homedepot.com/products/ezr33ssl-ndo
- 27estore, Base Diagonal Corner Cabinet 42 in (BDC-42) — https://www.27estore.com/base-diagonal-corner-cabinet-wide-42
- 27estore, Peninsula Cabinets category — https://www.27estore.com/kitchen-cabinets/peninsula-cabinets
- WoodWeb Knowledge Base, "45-Degree Corner Cabinet Options" — https://woodweb.com/knowledge_base/45Degree_Corner_Cabinet_Options.html
- WoodWeb Knowledge Base, "Corner Sink Base Ideas" — https://woodweb.com/knowledge_base/Corner_Sink_Base_Ideas.html
- WoodWeb Knowledge Base, "Kitchen Corner Cabinets" — https://woodweb.com/knowledge_base/Kitchen_Corner_Cabinets.html
- WoodWeb Knowledge Base, "Inside Corner Drawers" — https://woodweb.com/knowledge_base/Inside_Corner_Drawers.html
- WoodWeb Knowledge Base, "Joining cabinets at a 45 degree angle" — https://woodweb.com/knowledge_base/Joining_cabinets__at_a_45_degree_angle.html
- unfinished-kitchen-cabinets.net, "Angled Base Cabinets" (clipped/angle-corner shop specs) — https://www.unfinished-kitchen-cabinets.net/angle-base
- Fabuwood Cabinetry, Standard Kitchen Cabinet Size Guide (LSB36 lazy susan corner base) — https://www.fabuwood.com/blog/standard-kitchen-cabinet-size-and-dimension-guide
- KCMA / ANSI A161.1-2017 overview (performance & construction standard; general construction requirements only — no corner-specific dimensional data located) — https://www.woodworkingnetwork.com/cabinets/strength-behind-certified-cabinetry-ansikcma-a1611

---

```json
[
  {
    "type_id": "blind-corner-basic",
    "display_name": "Blind Corner Base Cabinet (basic)",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 33, "typ": 39, "max": 48 },
    "wall_b_consumed_in": { "min": 23.625, "typ": 24, "max": 24 },
    "box_width_in": 39,
    "box_depth_in": 24,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": 1, "wall_b": null },
    "door_config": "single door, hinge on blind side, opening 9-19.5in scaling with nominal width",
    "mechanism": "none (fixed shelf)",
    "mechanism_envelope_note": "blind cavity ~24-27in deep behind opening is reachable only by kneeling and reaching in; no rotating or sliding hardware",
    "min_adjacent_clearance_in": 2.5,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 2,
    "cost_tier": 1,
    "sources": [
      "https://s3.amazonaws.com/wellbornmedia/cms/63cae0d5a0040.pdf",
      "https://s3.amazonaws.com/FlippingBookStorage/KraftMaid%20Momentum%20Spec%20Book/files/assets/basic-html/page87.html"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "blind-corner-swingout",
    "display_name": "Blind Corner with Swing-Out Shelves",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 36, "typ": 45, "max": 48 },
    "wall_b_consumed_in": { "min": 24, "typ": 24, "max": 24 },
    "box_width_in": 45,
    "box_depth_in": 24,
    "height_in": 32.5,
    "filler_required_in": { "wall_a": 1, "wall_b": null },
    "door_config": "single door, hinge on blind side; door dims 24.1875-28.25in TOL/FOL depending on box size",
    "mechanism": "piano-hinge-mounted swing-out shelf frame (steel/wood), 2 shelves per side, door-linked",
    "mechanism_envelope_note": "max pull 49.5-51in; min pull w/hardware 46.5-48in; shelf wing envelope (cross-referenced pantry-class analog) ~25.9in W x 8in D",
    "min_adjacent_clearance_in": 2.5,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 3,
    "cost_tier": 2,
    "sources": [
      "https://s3.amazonaws.com/wellbornmedia/cms/63cae0d5a0040.pdf",
      "https://www.hardwareresources.com/organizers/cabinet-organizers/pantry-organizers/pso45.html"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "diagonal-corner-lazy-susan",
    "display_name": "Diagonal/Angle Corner — Full-Round Lazy Susan",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 33, "typ": 36, "max": 42 },
    "wall_b_consumed_in": { "min": 33, "typ": 36, "max": 42 },
    "box_width_in": 36,
    "box_depth_in": 24,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "double doors attached to rotary shelves (dependent) or single/double fixed door with independent susan behind, varies by SKU",
    "mechanism": "full-round rotating lazy susan",
    "mechanism_envelope_note": "susan diameter 28in (Wellborn BLS36, dependent style); independent full-round susans available 18/20/24/28/32in diameter",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 3,
    "cost_tier": 2,
    "sources": [
      "https://s3.amazonaws.com/wellbornmedia/cms/63cae0d5a0040.pdf",
      "https://rev-a-shelf.com/kitchen/lazy-susans/kidney-shape"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "pie-cut-bifold-susan",
    "display_name": "Pie-Cut Bifold-Door Lazy Susan",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 33, "typ": 36, "max": 39 },
    "wall_b_consumed_in": { "min": 33, "typ": 36, "max": 39 },
    "box_width_in": 36,
    "box_depth_in": 24,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "two door leaves hinged together at 90 degrees (or 135 for non-square corners), doors rotate with the shelf",
    "mechanism": "pie-cut shelf bolted to back of bifold doors (dependent rotation)",
    "mechanism_envelope_note": "36/39in box -> 31in shelf; 33in box -> 28in shelf; 1-2in clearance required around shelf perimeter; 170 degree cabinet-side hinge + 90 degree door-to-door hinge; 0.125in gap between door panels",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 3,
    "cost_tier": 2,
    "sources": [
      "https://rev-a-shelf.com/kitchen/lazy-susans/pie-cut",
      "https://www.cabinetparts.com/how-to/pie-cut-cabinet-lazy-susan-installation-help/p184"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "easy-reach-corner",
    "display_name": "Easy Reach Corner (wide single-door susan)",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 33, "typ": 33, "max": 36 },
    "wall_b_consumed_in": { "min": 33, "typ": 33, "max": 36 },
    "box_width_in": 33,
    "box_depth_in": 33,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "single door, 170 degree opening, soft-close",
    "mechanism": "2 independently-rotating pie-cut shelves",
    "mechanism_envelope_note": "170 degree single-leaf door swing required, larger open-door floor clearance than standard blind/diagonal doors but less rotational arc than bifold pie-cut",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["face-frame"],
    "complexity": 3,
    "cost_tier": 3,
    "sources": [
      "https://homedecoratorscabinetry.homedepot.com/products/ezr33ssl-ndo"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "magic-corner-i",
    "display_name": "Magic Corner I (Kesseböhmer/Häfele)",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 36, "typ": 46, "max": 46 },
    "wall_b_consumed_in": { "min": 24, "typ": 24, "max": 24 },
    "box_width_in": 46,
    "box_depth_in": 24,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": 0, "wall_b": null },
    "door_config": "single door, frameless full-overlay, Blum soft-close hinge",
    "mechanism": "door-mounted wire basket pull-out frame linked to independent swinging rear shelf",
    "mechanism_envelope_note": "min door opening 15.625in (396mm) in the sourced retail SKU; other catalog variants min opening 19.375in",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["frameless"],
    "complexity": 4,
    "cost_tier": 3,
    "sources": [
      "https://www.barkermodern.com/product-p/b1d1drmagiccornerrightm.htm",
      "https://wurthbaersupply.com/product/755631/MAGIC-CORNER-15.625-MCO-RIGHT-CP-MP-BOMMC1562RCP-MP"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "magic-corner-ii",
    "display_name": "Magic Corner II (Kesseböhmer/Häfele)",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 39, "typ": 40, "max": 42 },
    "wall_b_consumed_in": { "min": 21, "typ": 22, "max": 24 },
    "box_width_in": 40,
    "box_depth_in": 22,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "single door, frameless, min door opening 20.5in (520mm)",
    "mechanism": "two-tier door-mounted pull-out basket frame linked to independent swinging rear shelf set",
    "mechanism_envelope_note": "min cabinet opening depth 19.625in, width 20.5in, height 21.875in; min cabinet interior width 37.875in; load capacity up to 32kg",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["frameless"],
    "complexity": 4,
    "cost_tier": 4,
    "sources": [
      "https://www.cabinetparts.com/g/magic-corner-ii-kessebohmer-g13662",
      "https://advancedesignhardware.com/collections/kitchen-organization-1/products/magic-corner-ii-by-hafele"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "lemans-corner",
    "display_name": "LeMans Corner Unit (Kesseböhmer/Häfele)",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 33, "typ": 39, "max": 45 },
    "wall_b_consumed_in": { "min": 24, "typ": 24, "max": 24 },
    "box_width_in": 39,
    "box_depth_in": 24,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "single door, must open to 85 degrees for full tray extension",
    "mechanism": "four-arm articulated linkage, two organically-shaped trays swing fully independent of door/blind cavity",
    "mechanism_envelope_note": "Series 40/45/50/60 -> 12/15/18/21in trays; min opening Series45 16.5x21in, Series50 17.75x21.5in; 25kg per tray, 50kg total",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 5,
    "cost_tier": 5,
    "sources": [
      "https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132745-p24164",
      "https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132150-p24145",
      "https://www.kesseboehmer.com/en/storage-solutions/kitchen/corner-units/lemans"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "kidney-susan",
    "display_name": "Kidney/D-Shape Lazy Susan",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 33, "typ": 36, "max": 36 },
    "wall_b_consumed_in": { "min": 33, "typ": 36, "max": 36 },
    "box_width_in": 36,
    "box_depth_in": 24,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "single or double door matched to rounded/D-shaped susan profile",
    "mechanism": "independently-rotating kidney/D-shaped shelf, aluminum swivel bearing with rotation stop",
    "mechanism_envelope_note": "diameters available: 24, 28, 32in; bottom-mount fixed post or telescoping Twist-n-Lock post",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 3,
    "cost_tier": 2,
    "sources": [
      "https://rev-a-shelf.com/kitchen/lazy-susans/kidney-shape",
      "https://www.homedepot.com/p/Rev-A-Shelf-32-in-Almond-Polymer-Kidney-Lazy-Susan-Set-3472-32-15-52/304893143"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "swing-out-corner",
    "display_name": "Swing-Out Corner (generic hardware category)",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 33, "typ": 39, "max": 48 },
    "wall_b_consumed_in": { "min": 24, "typ": 24, "max": 24 },
    "box_width_in": 39,
    "box_depth_in": 24,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": 1, "wall_b": null },
    "door_config": "single door, hinge on blind side, door-linked shelf-wing swing",
    "mechanism": "chrome wire or wood swing-out shelf frame, piano-hinged",
    "mechanism_envelope_note": "shelf wing envelope ~25.9in W x 8in D, 10 shelves (cross-referenced from tall-pantry-class hardware; base-height dims not independently published)",
    "min_adjacent_clearance_in": 2.5,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 3,
    "cost_tier": 2,
    "sources": [
      "https://www.kraftmaid.com/base-blind-corner-with-chrome-swing-outs/",
      "https://www.hardwareresources.com/organizers/cabinet-organizers/pantry-organizers/pso45.html"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "corner-drawer-45",
    "display_name": "Corner Drawer System (45-degree drawer stack)",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 33, "typ": 36, "max": 42 },
    "wall_b_consumed_in": { "min": 33, "typ": 36, "max": 42 },
    "box_width_in": 36,
    "box_depth_in": 39,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "no door; drawer fronts only, or 1 door + 1 drawer hybrid (Barker style)",
    "mechanism": "trapezoidal/pie-shaped full-extension drawer boxes on corner-specific angled slides",
    "mechanism_envelope_note": "typical stack ~30in deep, 4 drawers, turned 45 degrees; requires ~35% more depth than a straight-run drawer bank of equal width; angled outer stiles required",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 5,
    "cost_tier": 5,
    "sources": [
      "https://woodweb.com/knowledge_base/Inside_Corner_Drawers.html",
      "https://www.kraftmaid.com/corner-drawers/",
      "https://www.barkermodern.com/product-p/b1d1drmagiccornerrightm.htm"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "corner-sink-base",
    "display_name": "Corner Sink Base",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 36, "typ": 39, "max": 46 },
    "wall_b_consumed_in": { "min": 36, "typ": 39, "max": 46 },
    "box_width_in": 39,
    "box_depth_in": 24,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "double doors (occasionally single), often 45 degree specialty hinge with no soft-close",
    "mechanism": "none (open cavity for sink/plumbing/disposal); full top",
    "mechanism_envelope_note": "practical sink-width ceiling well under nominal box width: 42in box -> max ~28in sink; 46in box -> max ~33in sink, sink typically set back 3-6in from front",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 2,
    "cost_tier": 2,
    "sources": [
      "https://s3.amazonaws.com/wellbornmedia/cms/63cae0d5a0040.pdf",
      "https://www.barkermodern.com/product-p/b45sink2dm.htm",
      "https://woodweb.com/knowledge_base/Corner_Sink_Base_Ideas.html"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "open-corner-shelf",
    "display_name": "Open Corner Shelf (no door, static)",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 33, "typ": 36, "max": 42 },
    "wall_b_consumed_in": { "min": 33, "typ": 36, "max": 42 },
    "box_width_in": 36,
    "box_depth_in": 24,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "none (open front)",
    "mechanism": "none (fixed shelves)",
    "mechanism_envelope_note": "no rotating or sliding hardware; ranked worst for accessibility among diagonal-corner practitioner options per WoodWeb",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 1,
    "cost_tier": 1,
    "sources": [
      "https://woodweb.com/knowledge_base/45Degree_Corner_Cabinet_Options.html"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "dead-void-corner",
    "display_name": "Dead/Void Corner (filler return, no cabinet)",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 3, "typ": 6, "max": 24 },
    "wall_b_consumed_in": { "min": 3, "typ": 6, "max": 24 },
    "box_width_in": null,
    "box_depth_in": null,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": 3, "wall_b": 3 },
    "door_config": "none",
    "mechanism": "none",
    "mechanism_envelope_note": "no functional storage envelope; models as a valid null placement state, not an error",
    "min_adjacent_clearance_in": 6,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 1,
    "cost_tier": 1,
    "sources": [
      "https://woodweb.com/knowledge_base/Kitchen_Corner_Cabinets.html",
      "https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "angle-corner-45-135",
    "display_name": "45/135-Degree Non-Square Corner Condition",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": null, "typ": null, "max": null },
    "wall_b_consumed_in": { "min": null, "typ": null, "max": null },
    "box_width_in": null,
    "box_depth_in": null,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "varies; typically single door or fixed narrow shelf on acute (135 degree interior) legs",
    "mechanism": "reduced-diameter susan or fixed shelf",
    "mechanism_envelope_note": "susan diameter capped at 18-20in (vs 28-32in at 90 degree corners); angled fillers standard at 22.5 or 45 degrees; face frames extended with 22.5 degree bevels",
    "min_adjacent_clearance_in": null,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 5,
    "cost_tier": 4,
    "sources": [
      "https://woodweb.com/knowledge_base/45Degree_Corner_Cabinet_Options.html"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "outside-corner-clipped",
    "display_name": "Outside (Convex/Clipped) Corner Cabinet",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 12, "typ": 12, "max": 25 },
    "wall_b_consumed_in": { "min": 12, "typ": 12, "max": 25 },
    "box_width_in": 12,
    "box_depth_in": 12,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "none typical (open display shelf or narrow insert)",
    "mechanism": "none",
    "mechanism_envelope_note": "clip removes a fixed depth (e.g. 6in) from the box corner at 30 or 45 degrees rather than consuming additional wall length; shop-fabricated, no major-manufacturer catalog SKU found",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 3,
    "cost_tier": 2,
    "sources": [
      "https://www.unfinished-kitchen-cabinets.net/angle-base"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "peninsula-corner",
    "display_name": "Peninsula/Island Corner Condition",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 12, "typ": 24, "max": 48 },
    "wall_b_consumed_in": { "min": null, "typ": null, "max": null },
    "box_width_in": null,
    "box_depth_in": 24,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "composite: inherits door config of whichever type-1-10 cabinet sits at the wall corner, plus a finished end-panel treatment at the open terminus",
    "mechanism": "none inherent (see paired wall-corner type)",
    "mechanism_envelope_note": "not an independent box type; models as {wall-corner cabinet type} + {termination end-panel}; end panel consumes ~0.75-1.5in additional length",
    "min_adjacent_clearance_in": null,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 2,
    "cost_tier": 2,
    "sources": [
      "https://www.27estore.com/kitchen-cabinets/peninsula-cabinets"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "transition-cabinet",
    "display_name": "Transition Cabinet (Base End Angle / depth-step)",
    "category": "base-corner",
    "wall_a_consumed_in": { "min": 12, "typ": 12, "max": 12 },
    "wall_b_consumed_in": { "min": 24, "typ": 24, "max": 24 },
    "box_width_in": null,
    "box_depth_in": null,
    "height_in": 34.5,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "single door, angled face, R or L hand ordering; 2 adjustable shelves",
    "mechanism": "none",
    "mechanism_envelope_note": "depth steps from 24in (standard, this end must never be exposed) to 12in across the angled face; hard invariant: 24in end must always abut another cabinet/appliance/wall, never a run terminus",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["face-frame", "frameless"],
    "complexity": 3,
    "cost_tier": 2,
    "sources": [
      "https://s3.amazonaws.com/FlippingBookStorage/KraftMaid%20Momentum%20Spec%20Book/files/assets/basic-html/page87.html"
    ],
    "confidence": "verified"
  }
]
```
