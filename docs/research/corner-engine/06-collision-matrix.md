# Kitchen Element Collision / Interference Matrix

Purpose: a working reference for the corner/placement engine's constraint solver — every
documented pairwise interference between cabinet doors, drawers, corner mechanisms, and
appliances, with the geometric condition that triggers the clash and the clearance number
(where a source actually publishes one) that resolves it.

Confidence key: **DOCUMENTED** = a manufacturer spec, code clearance, or planning-guideline
number found in a citable source. **ESTIMATE** = a number reported consistently across
practitioner/forum sources but not tied to a single authoritative spec sheet — treat as a
reasonable default, not a code minimum. **RULE-ONLY** = the geometric principle is well
established but no source publishes a universal inches figure (it is model/hinge-dependent).

---

## 1. Matrix Overview

| # | Pair | Failure mode | Hard number found? | Typical resolution |
|---|------|--------------|---------------------|---------------------|
| 1 | Door vs door, inside corner (two full-height doors hinged to meet at 90°) | Door faces/edges collide before either reaches usable open angle | Yes — 1.5"–3" filler (ESTIMATE, consistent) | filler + corner/bi-fold hinge |
| 2 | Door vs adjacent drawer front/handle | Door's swept arc (door width + handle projection) strikes neighboring drawer face or pull | Yes — 3" filler for drawer-adjacent case (ESTIMATE, consistent) | filler; angle-restrictor clip |
| 3 | Drawer vs perpendicular drawer at corner | Both fully extended fronts collide at the corner post/stile | Partial — no universal inches; 3" filler + 6" cabinet offset reported in one case (ESTIMATE) | filler; sequencing/interlock; reduced-depth corner drawer |
| 4 | Handle projection norms (knob vs bar pull) | Oversized projection turns a marginal clearance into a collision | Yes — knob 1"–1.5" dia.; pull projection avg 1.5", range 1"–2.5" (DOCUMENTED, industry norm) | spec low-projection pulls near corners |
| 5 | Pullout vs adjacent dishwasher | Blind-corner pullout mechanism or its door can't clear an open dishwasher door/handle; heat/moisture proximity | Yes — 2" min corner clearance (DOCUMENTED, appliance mfr norm); 21" standing clearance (DOCUMENTED, NKBA) | 2"–3" filler between appliance and corner cabinet |
| 6 | Corner door vs tall pantry box | Door swings into an adjoining tall cabinet before reaching 90° | Yes — 1.5" (doors-only) to 3" (drawers present) filler (ESTIMATE) | filler; 170°+ hinge |
| 7 | Upper corner door vs range hood | Diagonal/bi-fold upper corner door swing interferes with hood body or duct chase | Rule-only — no single inches figure; governed by hood clearance zone (24"–30" above cooktop) (DOCUMENTED for hood-to-cooktop, not door-to-hood) | reduced door width; hood offset; open-shelf corner |
| 8 | Refrigerator door swing vs opposite counter/run | Door swept arc blocks aisle or crisper-drawer removal envelope | Yes — 90° min for basic access, 100°–120° for full drawer/shelf removal (DOCUMENTED, Sub-Zero); 36"–48" aisle (DOCUMENTED, NKBA) | counter-depth model; swing-side reversal; walk-in clearance |
| 9 | Lazy Susan rotation envelope vs door position | Kidney/pie tray rotates into the door swing path or a door closes on a rotated tray | Rule-only — bearing "stop" hardware is the documented mitigation, no inches figure | stop-pin bearing; independent (non-door-attached) tray |
| 10 | LeMans arm sweep beyond door opening | Articulated arm/tray needs door open past a minimum angle or it fouls the door or neighbor | Yes — 85° min door opening; ~30 cm (11.8") side clearance for full extension (DOCUMENTED, Kesseböhmer) | angle-restrictor removed; adjacent cabinet spacing |
| 11 | Magic Corner full-extension envelope | Pull-out frame needs full door swing + minimum cabinet interior height or shelves foul door/box | Yes — min. 525 mm (20.7") clear interior height; door width range 450–600 mm (17.7"–23.6") (DOCUMENTED, Kesseböhmer) | box sized to spec; no undersized custom corner boxes |
| 12 | Dishwasher corner/appliance clearance | Door swing hits corner wall/cabinet | Yes — 2" minimum (DOCUMENTED, multiple mfr installation guides) | 2"–3" filler |
| 13 | Range side clearance | Cabinet or combustible surface too close to burners/controls | Yes — 6" min side clearance to wall cabinets at/above counter height in the 36" zone typical (DOCUMENTED, GE); 0" allowed to combustible sidewall below cooktop on many models (DOCUMENTED, Maytag) | 6" min side clearance rule of thumb; verify per model |
| 14 | Range-to-upper-cabinet vertical | Cabinet bottom too close to burners — heat/grease | Yes — 30" min unprotected / 24" min with protection above cooktop; 18" absolute min in all cases (DOCUMENTED, GE) | vent hood in place of cabinet, or raise cabinet |
| 15 | Wall-oven door drop envelope | Open door blocks aisle / adjacent corner or drawer | Yes — ~31 1/8" min clearance in front when open (DOCUMENTED, mfr spec); 30"–36" general work clearance (ESTIMATE/DOCUMENTED blend) | position away from traffic corner; adjacent drawer stack instead of door |
| 16 | Fridge ventilation + 90°+ door swing for crisper removal | Insufficient door angle prevents drawer withdrawal along its rails | Yes — 90° stop supports drawer removal on most Sub-Zero units; 120° recommended for full-shelf cleaning (DOCUMENTED, Sub-Zero) | corner filler so door reaches ≥90°; swing-reversal hinge |
| 17 | Filler-as-solution ("3-inch corner filler") | Any of the above — the generic fix | Yes — 3" for drawer-adjacent corners, 1.5" for door-only corners, 2"–3" for appliance-adjacent corners (ESTIMATE, converges across multiple independent sources) | standardize 3" filler as default corner allowance |

---

## 2. Door vs Door — Inside Corner Clash

**Geometry.** Two full-overlay doors hinged on adjoining faces of an inside corner (either two
base cabinets or two wall cabinets meeting at 90°) sweep arcs that originate from each door's
hinge line. Because the doors are mounted flush to the corner, the leading top/bottom corners
of each door occupy the same physical space during part of their swing — the classic "corner
door clash."

```
 plan view, closed:              plan view, opening (clash zone shaded):
 ┌────┬────┐                     ┌────┬────┐
 │    │    │                     │    │╲▓▓╱│   <- door edges sweep
 │ A  │ B  │                     │ A  │▓╳▓│  B │    into shared corner
 │    │    │                     │    │╱▓▓╲│    volume
 └────┴────┘                     └────┴────┘
        corner
```

Failure mode: door A's leading edge (thickness ~3/4") strikes door B's face or leading edge
before either reaches a usable opening angle, often well short of 90°.

Geometric condition (prose formula): *collision occurs when the swept radius of door A
(≈ door_width_A) intersects the static bounding box of door B's closed position, i.e. when
the corner setback (filler + reveal) is less than the door's stile-side clearance requirement
for the hinge system in use.* Corner/bi-fold hinges (e.g., Blum 170°, or paired 45°/60°
Clip Top bi-fold hinges) change the pivot geometry so the doors fold rather than rotate flat,
which is the standard resolution rather than pure filler in many builds.

Documented numbers: rule-of-thumb inside-corner filler is **3"** when the adjacent cabinet
run includes drawers, reducible to **~1.5"** for door-only runs (consistently reported,
ESTIMATE — not a single Blum spec page, but converges across cabinet-industry sources).
Minimum gap between two adjoining door edges commonly cited as **2mm** reveal at minimum,
though this is a fabrication tolerance, not a swing-clearance number.

Resolution: filler strip sized to hinge system; or corner/bi-fold (pie-cut) hinge that folds
both leaves back against the corner instead of swinging flat.

Sources:
- [Unequally Sized Doors on a Corner Cabinet — WoodWeb](https://woodweb.com/knowledge_base/Unequally_Sized_Doors_on_a_Corner_Cabinet.html)
- [Corner Cabinet Filler: Everything You Need to Know](https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler)
- [Blum Clip Top Bi-Fold Hinges, Inside Corner 60° — Woodcraft](https://www.woodcraft.com/products/blum-60-clip-top-bi-fold-hinge-inside-corner-pair)
- [Can anyone help me determine my filler width for blind corner wall cab? — LumberJocks](https://www.lumberjocks.com/threads/can-anyone-help-me-determine-my-filler-width-for-blind-corner-wall-cab.308550/)

---

## 3. Door vs Adjacent Drawer Front/Handle

**Geometry.** A hinged door mounted immediately beside a bank of drawers sweeps an arc whose
radius equals door width; if a drawer pull on the neighboring cabinet projects past the face
by more than the available reveal, the door edge (or door + handle, if the door itself has a
handle near that edge) strikes the pull mid-swing.

```
 plan view:
 ┌──────┐┌───┐
 │ DOOR │ │ D │  <- pull projects 1"-1.5" past drawer face
 │  ↺   │ │ R │
 │  arc │ │ A │
 └──────┘└───┘
     ^ door leading edge sweeps outward through
       the drawer's pull-projection zone if reveal < projection
```

Geometric condition: *collision if (door_thickness + door_edge_reveal) < handle_projection of
the adjacent drawer, evaluated at the door's fully-open position (typically 90°–115° depending
on hinge).* This is the same "door swept past a fixed obstruction" pattern as door-vs-door but
the obstruction is now a rigid protruding handle rather than another door face — meaning even
a well-fillered corner can still clash if the neighboring pull is a deep bar pull rather than a
knob.

Documented numbers: 3" filler recommended specifically to clear a neighboring drawer/door
handle at a blind corner (ESTIMATE, consistent across multiple sources); handle/pull
projection itself typically 1"–2.5", averaging ~1.5" (DOCUMENTED, hardware industry norm).

Resolution: 3" filler; or specify low-projection pulls (recessed/pocket handles) on cabinets
adjacent to door swings; or restrict door opening angle with a Blum-style angle stop (86°–110°
stops are sold specifically "to prevent collision with neighboring handles").

Sources:
- [Corner Cabinet Filler — unfinished-kitchen-cabinets.net](https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler)
- [Cabinet Hardware Placement & Sizing Guide — DK Hardware](https://www.dkhardware.com/blog/cabinet-hardware-placement-sizing-guide/)
- [Multi-Use Restriction Clip, 110° on 155° / 92° on 125° Blum Hinges — CabinetParts.com](https://www.cabinetparts.com/p/blum-hinges-european-cabinet-hinges-BHB70T7553-p131715)
- [Opening angle stops 155° hinges — Blum EASY ASSEMBLY Blog](https://ea.blum.com/en/opening-angle-stops-155-hinges/)

---

## 4. Drawer vs Perpendicular Drawer at Corner

**Geometry.** Two drawer banks on perpendicular runs meeting at an outside or inside corner:
when both drawers are pulled to full extension, their fronts (which are wider than the box to
achieve reveal/overlay) occupy the same corner airspace.

```
 plan view, both extended:
                 ┌─────────────┐
                 │  drawer B   │  extends toward corner
                 └─────────────┘
 ┌───┐
 │ A │  <- drawer A front also
 │front│   extends toward same
 └───┘    corner volume -> clash
```

Geometric condition: *collision if front_overhang_A (front width − box width, typically
0.5"–0.75" per side for full overlay) plus front_overhang_B, measured from the corner
intersection, exceeds the corner setback provided by fillers/stiles.* Unlike the door cases,
this failure is purely about the **front panel**, not an arc — drawers travel straight out, so
the interference zone is static once you know both fully-open positions.

Documented numbers: no universal inches figure exists (highly dependent on overlay style and
box construction). One resolved case reports the base cabinet run pulled out 6" from the wall
with a 3" filler to the center stile, which cleared the perpendicular drawer opening
(ESTIMATE, single documented case — not a code minimum).

Resolution options reported in practice: 3" (or larger) corner filler; sequencing hardware or
manual habit (open one at a time); shortened/half-depth corner drawer; or eliminate the
perpendicular-drawer-at-corner condition entirely by routing a blind-corner or Lazy-Susan unit
into that position instead of stacked drawers.

Sources:
- [Drawers are hitting each other and cabinet maker blames install — Houzz](https://www.houzz.com/discussions/2665020/drawers-are-hitting-each-other-and-cabinet-maker-blames-install)
- [Drawer pulls obstructing each other — DoItYourself.com](https://www.doityourself.com/forum/carpentry-cabinetry-interior-woodworking/647516-drawer-pulls-obstructing-each-other.html)
- [Blind Corner Cabinet Ideas To Maximize Corner Space](https://www.bestonlinecabinets.com/blog/blind-corner-cabinet/)

Note: the Houzz case investigated directly was actually a **manufacturing tolerance** failure
(slab fronts oversized relative to box opening, drawers touching at <1/16" gap when both
closed/near-closed) rather than a full-extension geometric clash — included here because it
illustrates that "drawer vs drawer" failures have two distinct root causes: (a) static
front-to-front tolerance at rest, and (b) dynamic full-extension corner collision. The engine
should model both.

---

## 5. Handle Projection Norms (Knob vs Bar Pull)

Documented figures (DOCUMENTED, hardware industry consensus across multiple retailer/mfr
guides):

| Hardware type | Typical size/projection |
|---|---|
| Knob diameter | 1"–1.5" |
| Pull projection (from door/drawer face) | 1"–2.5", average ~1.5" |
| Bar pull length rule | should not exceed ~1/3 of door height or drawer width |
| Pull length by door height | <24" tall door → 3"–7" pull; 24"–36" tall door → 7"–12" pull |

Design implication for the collision engine: knobs (≤1.5" projection) rarely create clearance
problems beyond the door-thickness envelope; bar/appliance-style pulls (up to 2.5" projection,
and dishwasher integrated handles which can project further still) are the dominant driver of
corner-filler sizing. Any interference calculation that assumes a flat door thickness without
adding handle projection will systematically under-detect corner clashes.

Sources:
- [Cabinet Hardware Placement & Sizing Guide — DK Hardware](https://www.dkhardware.com/blog/cabinet-hardware-placement-sizing-guide/)
- [What Does Pull Projection Mean Cabinet Hardware — GripfastHardware](https://gripfasthardware.com/2025/12/04/what-does-pull-projection-mean-cabinet-hardware-2/)
- [Ultimate Cabinet Hardware Size Guide 2026 — Cast A Cabinetry](https://castacabinetry.com/post/cabinet-hardware-size-guide/)

---

## 6. Pullout vs Adjacent Appliance (Dishwasher / Range)

**Geometry.** A blind-corner pullout mechanism (LeMans, Magic Corner, or a simple wire pullout)
sitting beside a dishwasher or range faces two independent problems: (1) the appliance door,
when open, physically occupies space the pullout's face frame or door needs to swing through;
(2) for ranges specifically, sustained heat/radiant exposure to an adjacent cabinet face is a
building-code and product-safety issue, not just a geometric one.

Documented numbers:
- Dishwasher-to-corner minimum clearance: **2"** between the side of the open dishwasher door
  and the wall/adjacent cabinet (DOCUMENTED, consistent across multiple installation guides —
  e.g., Lowes/manufacturer install instructions; verify per-model since integrated bar handles
  can require more).
- NKBA standing clearance: at least **21"** of standing space between the dishwasher edge and
  any countertop frontage/appliance/cabinet set at a right angle to it; **30" × 48"** clear
  floor space positioned adjacent to the dishwasher door (DOCUMENTED, NKBA Kitchen & Bath
  Planning Guidelines).
- Range side clearance: **6"** minimum to a side wall is a commonly cited figure, though many
  ranges are UL-listed for 0" clearance to combustible construction below the cooktop deck —
  the number is genuinely model-dependent and the installation manual for the specific unit is
  authoritative (DOCUMENTED for the specific Maytag/GE models checked, not universal).

Practitioner failure mode: "dishwasher handle stood out way further than a normal knob" —
several forum threads describe under-sizing the corner filler because the designer used
generic handle-projection assumptions instead of the actual (often much deeper) integrated
dishwasher handle depth, then having to retrofit a wider filler.

Resolution: size the filler to the specific appliance handle depth (not a generic pull
assumption) plus mechanism swing clearance; treat dishwasher/range adjacency to a corner
pullout as a "verify actual handle depth" flag in the engine rather than trusting a generic
1"–1.5" handle default.

Sources:
- [Bosch Dishwasher Corner Clearance — Houzz](https://www.houzz.com/discussions/6403387/bosch-dishwasher-corner-clearance)
- [Dishwasher in Corner: The #1 Kitchen Design Mistake — Fix It In The Home](https://fixitinthehome.com/dishwasher-in-corner_gem1/)
- [Kitchen & Bath Planning Guidelines — NKBA](https://kb.nkba.org/uploads/2023/05/2023-DC-Guidelines-1.pdf)
- [Kitchen Planning Guidelines With Access Standards — NKBA](https://media.nkba.org/uploads/2022/05/Kitchen-Planning-Guidelines.pdf)
- [Corner Cabinet Filler: Everything You Need to Know](https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler)

---

## 7. Corner Door vs Tall Pantry/Cabinet

**Geometry.** A hinged door on a cabinet immediately adjacent to a tall pantry box (which
presents a full-height obstruction, unlike a countertop-height base cabinet) cannot swing past
the point where its outer edge contacts the pantry's side panel.

Geometric condition: *max_open_angle = arccos(setback / door_width)* where setback is the gap
between the hinge-side cabinet face and the pantry's leading face. Below a critical setback,
the door physically cannot reach 90°, which is often the minimum angle needed for full drawer
or shelf access behind it.

Documented numbers: **1.5"** filler sufficient for a door-only adjacent run to reach a full
90°; **3"** recommended when the pantry run has drawers or the design wants swing past 90°
(ESTIMATE, converges across multiple cabinetry-industry sources — not a single code citation).

Resolution: filler sized per above; or 170°+ opening hinge to recover functional access even
with a tighter setback; or reverse the pantry door swing so its face doesn't compete with the
neighboring door's arc.

Sources:
- [Corner Cabinet Filler — unfinished-kitchen-cabinets.net](https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler)
- [How to fix these corner cabinet doors? — DoItYourself.com](https://www.doityourself.com/forum/furniture-wood-cabinetry-finishing/623891-how-fix-these-corner-cabinet-doors.html)
- [Question for cabinet makers, adjacent wall clearance for cabinet doors to open — LumberJocks](https://www.lumberjocks.com/threads/question-for-cabinet-makers-adjacent-wall-clearance-for-cabinet-doors-to-open.98658/)

---

## 8. Upper Corner Door vs Range Hood

**Geometry.** A diagonal or bi-fold upper corner cabinet next to (or partially behind) a range
hood: the hood's body/duct chase occupies wall-cabinet-height space that the corner door's
swing radius may need. This pairing is the least numerically documented of the set — sources
consistently describe it as a layout constraint to check case-by-case rather than publish a
governing clearance figure.

What IS documented (RULE-ONLY plus adjacent hard numbers):
- Hood-to-cooktop vertical clearance: **24"–30"** typical range (electric ~24" min, gas ~27"
  min) — this constrains where the hood *bottom* sits, which in turn determines how much of
  the upper-cabinet run near a corner is actually available before the hood volume starts
  (DOCUMENTED for hood-to-cooktop, but this is a different pair than door-to-hood).
- No source found publishes a "door-to-hood-body" minimum clearance in inches; the failure
  mode is described qualitatively ("cabinet door clearance issues with vent hoods" as a
  planning concern) without a number.

Geometric condition (engine formula, RULE-ONLY, no cited constant): *collision if the corner
door's swept arc intersects the hood's projected footprint + duct chase width; since hood
placement is itself constrained by the 24"–30" cooktop clearance, model the hood as a fixed
obstruction volume and treat the corner door swing exactly as in the door-vs-tall-cabinet case
above (§7), substituting the hood body for the pantry box.*

Resolution observed in practice: narrow the corner door width, switch to open shelving at that
corner, or offset the hood to clear the door swing envelope — decided at the design stage, not
solved with a filler.

Sources:
- [Kitchen Cabinet Clearance Above Stove Top — WoodWeb](https://woodweb.com/knowledge_base/Kitchen_Cabinet_Clearance.html)
- [5 Tips for Designing a Range Hood Wall — Carla Aston](https://carlaaston.com/designed/5-tips-for-designing-range-hood-wall-in-kitchen)
- [How to Plan Cabinet Door Swing Direction in Your Kitchen — Bradco](https://bradcokitchen.com/blog/how-to-determine-kitchen-cabinet-door-swing-direction/)

---

## 9. Refrigerator Door Swing vs Adjacent Counter/Run

**Geometry.** The refrigerator door sweeps a large arc (door width often 24"–36" on
double-door units) that must clear both the aisle in front and, in a galley layout, an
opposing counter run. A second, independent condition governs whether the door angle achieved
is sufficient to slide crisper drawers/shelves out along their rails without the door itself
blocking the withdrawal path.

Documented numbers:
- Minimum door-open angle for basic drawer/shelf access: **90°** (DOCUMENTED, Sub-Zero: "all
  drawers can be fully accessed or removed with the door opening restricted to 90°," though
  shelves above may need removal first).
- Recommended angle for full cleaning/shelf removal: **~120°** (DOCUMENTED, Sub-Zero/general
  appliance guidance).
- Corner installation filler: **2" minimum, 3" preferred** to prevent hand/finger pinch between
  handle and adjacent wall when door is near-fully open (DOCUMENTED, Sub-Zero corner
  installation guidance).
- Aisle/walkway clearance: **36"** minimum transit path, **42"** work aisle (one cook),
  **48"** for a galley aisle used by two people or with appliance doors opening into it
  (DOCUMENTED, NKBA planning guidelines).
- Landing space adjacent to the refrigerator: **15"** minimum on the handle side (DOCUMENTED,
  NKBA).

Geometric condition: *collision if door_swept_radius (≈ door_width, pivoting at the hinge
side) intersects the opposing counter/island edge before reaching the angle required for
shelf/drawer withdrawal (90°–120° depending on model); separately, verify aisle_width −
door_open_depth_at_90° ≥ NKBA walkway minimum for the aisle's usage class.*

Resolution: counter-depth or cabinet-depth models to reduce swept radius; swing-side reversal
so the door opens away from the tightest run; corner filler per Sub-Zero guidance if the unit
sits in or near a corner.

Sources:
- [Sub-Zero Door and Drawer Clearance — Sub-Zero/Wolf](https://www.subzero-wolf.com/assistance/answers/sub-zero/common/sub-zero-door-and-drawer-clearance)
- [Sub-Zero Refrigerator Drawer Removal and Reinstallation](https://www.subzero-wolf.com/assistance/answers/sub-zero/common/refrigerator-storage-drawer-removal-and-reinstallation)
- [Fridge in a Corner: The Critical 4-Inch Clearance Rule — homeappliances.blog](https://homeappliances.blog/fridge-corner-installation-clearance)
- [Kitchen & Bath Planning Guidelines — NKBA](https://kb.nkba.org/uploads/2023/05/2023-DC-Guidelines-1.pdf)

Note: one secondary source titled the corner rule as a "4-inch" clearance (vs. Sub-Zero's own
2"–3" guidance) — flagged as a discrepancy; treat Sub-Zero's own support page as authoritative
for Sub-Zero units and verify per manufacturer for others.

---

## 10. Lazy Susan Rotation Envelope vs Door Position

**Geometry.** Two distinct lazy-susan architectures behave differently:
- **Pie-cut / dependent tray**, attached directly to the door: opening the door rotates the
  tray with it (single-piece), so the "envelope vs door" problem is inherent to the mechanism
  — the tray sweep IS the door sweep, by design.
- **Kidney-shaped / independent tray** (not attached to the door): the tray rotates on its own
  post independent of the door. The documented failure mode here is a tray left rotated to an
  arbitrary position, then the door closed onto it, jamming the door or bending the tray
  support.

Geometric condition: *for independent trays, collision if tray_rotational_position at the time
of door closing places any stored item or the tray's own bearing arm within the door's closed
envelope; mitigated by a mechanical bearing stop that only allows the tray to come to rest in
positions compatible with door closure.*

Documented numbers: none found in inches/degrees for a generic rotation-vs-door-clearance
figure; the mitigation is entirely mechanical (a keyed/stop bearing), not a spacing number.

Resolution: specify independent kidney-shelf systems with a stop-bearing (Rev-A-Shelf and
similar), which mechanically limits rest position so the door always clears; for pie-cut
systems, the door-swing analysis IS the mechanism analysis (see §1/§7 arc math).

Sources:
- [Solid Bottom Kidney-Shaped Lazy Susan — Rev-A-Shelf](https://rev-a-shelf.com/53-401-series)
- [Lazy Susans Info — Rev-A-Shelf](https://rev-a-shelf.com/lazy-susans-info)
- [Corner Cabinet Lazy Susan — George Cabinetry](https://georgecabinetry.com/blog/corner-cabinet-lazy-susan/)

---

## 11. LeMans Arm Sweep Beyond the Door Opening

**Geometry.** The LeMans mechanism's four-arm articulated frame is physically linked to the
door: pulling the door open drives the arms, which sweep the shelves out of the blind cavity
and rotate them into the main cabinet opening. The mechanism requires the door to reach a
minimum angle before the shelves clear the door swing path; if the door is restricted (by an
angle stop, or by a neighboring obstruction limiting how far it can open), the shelves cannot
fully present.

Documented numbers (DOCUMENTED, Kesseböhmer):
- **85°** minimum door opening angle required for the shelves to fully extend.
- **~30 cm (11.8")** of extra side clearance needed for full access when trays are extended.
- An opening-angle limiter is offered specifically "to prevent damage to the fronts of
  adjacent components" — i.e., the manufacturer explicitly documents the arm-sweep-vs-neighbor
  collision risk and sells a mechanical fix for it.

Geometric condition: *collision/non-function if achievable_door_angle < 85°; separate
collision if adjacent_cabinet_clearance < ~11.8" and the angle limiter is not installed.*

Resolution: ensure the corner cabinet has an unobstructed door swing to at least 85° (verify
against §1/§6 corner-adjacency constraints); install the angle limiter when the adjacent
run is tight enough that full arm sweep would strike a neighboring door/drawer front.

Sources:
- [LeMans kitchen corner unit solution — Kesseböhmer](https://www.kesseboehmer.com/en/storage-solutions/kitchen/corner-units/lemans)
- [LeMans: Maximize Your Blind Corner Cabinet Storage — Kesseböhmer US](https://www.kesseboehmer.us/kitchen/corner-cabinets/lemans)
- [Kesseböhmer LeMans II Set — Häfele](https://www.hafele.com/us/en/product/lemans-ii-set-for-blind-corner-cabinets/P-00856493/)

---

## 12. Magic Corner Full-Extension Envelope

**Geometry.** The Magic Corner system splits into a front shelf frame and a rear shelf frame;
opening the door drives the front frame sideways, which in turn drags the rear frame forward
into the main cabinet opening. Both frames must have unobstructed travel for their full stroke,
and the cabinet box itself must meet minimum dimensions or the mechanism cannot be installed at
spec.

Documented numbers (DOCUMENTED, Kesseböhmer / cabinetparts.com install docs):
- Fits base cabinets with outer dimensions of **500 × 900 mm or 500 × 1000 mm**.
- Suitable for **door widths 450–600 mm (17.7"–23.6")**.
- Requires **minimum clear interior height of 525 mm (20.7")**.
- Front shelf: 295 × 470 × 88 mm, 14 kg capacity; rear shelf: 390 × 470 × 88 mm, 18 kg
  capacity — these footprints define the swept envelope inside the box, i.e. the minimum
  interior clearances the corner cabinet box must provide.

Geometric condition: *non-function/collision if cabinet_interior_height < 525 mm, or if
door_width falls outside 450–600 mm, or if the box's inner depth is insufficient for the front
(88 mm) + rear (88 mm) frame stack to clear each other during the sideways-then-forward
extension stroke.*

Resolution: this is a "build to spec" case rather than a filler-based fix — treat the
Magic Corner as a hard constraint on corner-box dimensions in the engine (reject/flag any
corner box configuration that falls outside the documented envelope rather than trying to
resolve with spacing).

Sources:
- [Magic Corner Standard installation PDF — cabinetparts.com](https://downloads.cabinetparts.com/auto/MagicCornerIInstallation.pdf)
- [Magic Corner Kitchen corner unit solution — Kesseböhmer US](https://www.kesseboehmer.us/kitchen/corner-cabinets/magic-corner)
- [Kessebohmer KS-MC1 Kit — Ferguson Home](https://www.fergusonhome.com/kessebohmer-mc1-l-kit/s1766224)

---

## 13. Standard Appliance Clearances (Reference Set)

Consolidated hard numbers for the engine's constraint table:

| Clearance | Value | Confidence | Source |
|---|---|---|---|
| Dishwasher, corner/side minimum | 2" | DOCUMENTED | multiple mfr install guides |
| Dishwasher, NKBA standing clearance | 21" | DOCUMENTED | NKBA |
| Dishwasher, clear floor space | 30" × 48" | DOCUMENTED | NKBA |
| Range, side clearance to wall | 6" (typ.); 0" combustible-rated on some models below cooktop deck | DOCUMENTED (model-dependent) | GE, Maytag install docs |
| Range-to-wall-cabinet, unprotected | 30" min | DOCUMENTED | GE |
| Range-to-wall-cabinet, protected | 24" min | DOCUMENTED | GE |
| Range-to-wall-cabinet, absolute floor | 18" min | DOCUMENTED | GE |
| Range hood to cooktop, electric | ~24" min | DOCUMENTED | industry consensus (KitchenAid/Whirlpool) |
| Range hood to cooktop, gas | ~27"–30" min | DOCUMENTED | industry consensus |
| Wall oven, door-open clearance | ~31 1/8" min | DOCUMENTED | mfr install spec |
| Wall oven, general work clearance | 30"–36" | ESTIMATE | Town Appliance / general guidance |
| Refrigerator, door angle for drawer access | 90° min | DOCUMENTED | Sub-Zero |
| Refrigerator, door angle for full shelf removal | ~120° | DOCUMENTED | Sub-Zero |
| Refrigerator, corner filler | 2" min, 3" preferred | DOCUMENTED | Sub-Zero |
| Refrigerator, front clearance/aisle | 30"–48" (usage-dependent) | DOCUMENTED (range) | NKBA |
| Refrigerator, landing space | 15" min | DOCUMENTED | NKBA |
| Handle/pull projection | 1"–2.5" (avg 1.5") | DOCUMENTED | hardware industry |
| Knob diameter | 1"–1.5" | DOCUMENTED | hardware industry |
| Corner filler, door-only run | 1.5" | ESTIMATE | multiple cabinetry sources |
| Corner filler, drawer-adjacent run | 3" | ESTIMATE | multiple cabinetry sources |
| Corner filler, appliance-adjacent (dishwasher/fridge) | 2"–3" | DOCUMENTED (fridge)/ESTIMATE (dishwasher) | Sub-Zero + industry |
| LeMans, min door opening angle | 85° | DOCUMENTED | Kesseböhmer |
| LeMans, side clearance for full extension | ~11.8" (30 cm) | DOCUMENTED | Kesseböhmer |
| Magic Corner, min interior height | 20.7" (525 mm) | DOCUMENTED | Kesseböhmer |
| Magic Corner, door width range | 17.7"–23.6" (450–600 mm) | DOCUMENTED | Kesseböhmer |

---

## 14. Filler-as-Solution: Why the "3-Inch Corner Filler" Rule Exists

The recurring 3" figure is not arbitrary — it is the smallest allowance that simultaneously
satisfies the two dominant corner failure modes documented above:

1. **Handle-projection clearance.** A drawer/door pull projects up to ~1.5"–2.5" past the
   cabinet face (§5). A perpendicular door or drawer swinging/extending toward that corner
   needs its own edge to clear that projection *plus* a working reveal (~1/8"–1/4"). Summing a
   worst-case pull projection (2.5") with a margin for stile/reveal and fabrication tolerance
   lands close to 3" — which is why sources converge on "3-inch filler clears the handle" as a
   practical rule even though no single code cites the arithmetic explicitly.

2. **Door-arc vs. box-corner geometry.** For a door to open past 90° (needed for most
   European/Blum hinge systems to reach their stable "rest open" detent, and needed for
   pull-out mechanisms like LeMans that require ≥85° travel), the door's leading top corner
   must clear the perpendicular cabinet's front face. For typical 3/4" door stock hinged near
   the corner, a 1.5" setback is sufficient to reach 90° cleanly (door-only, no handle in the
   way) — hence the smaller 1.5" figure for door-only runs — but once a handle is added to the
   equation (either on the door itself or on a neighboring drawer), the same arc analysis pushes
   the required setback toward 3".

In short: **1.5" solves the pure door-swing-vs-box-corner geometry; 3" additionally solves the
handle-projection-vs-perpendicular-element geometry.** The engine should therefore not treat
"corner filler" as a single constant — it should compute filler width as
`max(door_arc_clearance, handle_projection_clearance + reveal_margin)` per corner instance,
using the specific door thickness, hinge opening angle, and actual (not assumed) handle
projection of both adjoining elements. Defaulting to a flat 3" is a safe but sometimes
over-generous heuristic; defaulting to 1.5" is unsafe whenever either adjoining element has a
projecting pull.

Sources:
- [Corner Cabinet Filler: Everything You Need to Know](https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler)
- [BASE CORNER BLIND CABINET spec sheet — cabinets.com](https://www.cabinets.com/media/download/euro-base-blind-details.pdf)
- [Filler size for corner cabinets? — Houzz](https://www.houzz.com/discussions/2695209/filler-size-for-corner-cabinets)

---

## Sources (consolidated)

- Bosch Dishwasher Corner Clearance — https://www.houzz.com/discussions/6403387/bosch-dishwasher-corner-clearance
- Lowes dishwasher installation instructions (PDF, binary/unparseable at fetch time) — http://pdf.lowes.com/installationguides/883049292700_install.pdf
- Fix It In The Home, "Dishwasher in Corner" — https://fixitinthehome.com/dishwasher-in-corner_gem1/
- Whirlpool dishwasher dimensions — https://www.whirlpool.com/blog/kitchen/dishwasher-dimensions.html
- KitchenAid dishwasher size guide — https://www.kitchenaid.com/pinch-of-help/major-appliances/how-to-choose-the-right-dishwasher-size.html
- Garage Journal forum, dishwasher-to-cabinet pull tightness — https://www.garagejournal.com/forum/threads/how-tight-should-i-pull-kitchen-cabinets-to-dishwasher.487428/
- WoodWeb, Unequally Sized Doors on a Corner Cabinet — https://woodweb.com/knowledge_base/Unequally_Sized_Doors_on_a_Corner_Cabinet.html
- Sawmill Creek, Pie Corner door layout — https://sawmillcreek.org/threads/how-to-layout-door-dimensions-for-pie-corner.291443/
- Corner Cabinet Filler — https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler
- HardwareSource, Blum Corner Hinge Bundle — https://www.hardwaresource.com/products/blum-corner-hinge-bundle
- LumberJocks, filler width for blind corner wall cab (pt.1 & 2) — https://www.lumberjocks.com/threads/can-anyone-help-me-determine-my-filler-width-for-blind-corner-wall-cab.308550/
- Sawmill Creek, 45° upper corner hinge — https://sawmillcreek.org/archive/index.php/t-275341.html
- Woodcraft, Blum 60° Clip Top Bi-Fold Hinge — https://www.woodcraft.com/products/blum-60-clip-top-bi-fold-hinge-inside-corner-pair
- DK Hardware, Cabinet Hardware Placement & Sizing Guide — https://www.dkhardware.com/blog/cabinet-hardware-placement-sizing-guide/
- Top Knobs, Decorative Hardware Size Selection — https://blog.topknobs.com/decoraive-hardware-sizing-guide/
- GripfastHardware, Pull Projection Meaning — https://gripfasthardware.com/2025/12/04/what-does-pull-projection-mean-cabinet-hardware-2/
- Wayfair, How to Measure Drawer Pulls & Cabinet Pulls — https://www.wayfair.com/sca/ideas-and-advice/renovation/how-to-measure-drawer-pulls-and-cabinet-pulls-T5263
- Cast A Cabinetry, Cabinet Hardware Size Guide 2026 — https://castacabinetry.com/post/cabinet-hardware-size-guide/
- Maytag range installation instructions (PDF) — https://www.maytag.com/content/dam/global/documents/200803/installation-instructions-8101P624-60.pdf
- GE Appliances, Range Minimum Clearance Requirements — https://products.geappliances.com/appliance/gea-support-search-content?contentId=16627
- GE Appliances, General List of Minimum Air Clearance Requirements — https://products.geappliances.com/appliance/gea-support-search-content?contentId=21841
- AJ Madison, proximity to side cabinet spec sheet (PDF) — https://assets.ajmadison.com/ajmadison/itemdocs/m40079_vdsc_specs.pdf
- Fine Homebuilding forum, Cabinet Clearance Around Range Top — https://www.finehomebuilding.com/forum/cabinet-clearance-around-range-top
- Town Appliance, How Much Clearance Does a Wall Oven Need? — https://www.townappliance.com/blogs/town-appliance-official/how-much-clearance-does-a-wall-oven-need
- Electric wall oven installation instructions (PDF) — https://content.syndigo.com/asset/538414e3-f0bc-4ba9-97ea-03f93f94c417/original.pdf
- Home Depot appliance repair manual (wall oven, PDF) — https://www.appliancerepair.homedepot.com/assets/manuals/D9DD768F202D0752459CC94C5B92EAB9C857DBEA.pdf
- Sub-Zero, Refrigerator Storage Drawer Removal and Reinstallation — https://www.subzero-wolf.com/assistance/answers/sub-zero/common/refrigerator-storage-drawer-removal-and-reinstallation
- Sub-Zero, Classic Crisper Shelf Removal & Installation — https://www.subzero-wolf.com/assistance/answers/sub-zero/classic/built-in-series-crisper-shelf-removal-amp-installation
- Sub-Zero, Door and Drawer Clearance — https://www.subzero-wolf.com/assistance/answers/sub-zero/common/sub-zero-door-and-drawer-clearance
- homeappliances.blog, Fridge in a Corner: The Critical 4-Inch Clearance Rule — https://homeappliances.blog/fridge-corner-installation-clearance
- Rev-A-Shelf, Kidney Lazy Susan series — https://rev-a-shelf.com/53-401-series
- Rev-A-Shelf, Lazy Susans Info — https://rev-a-shelf.com/lazy-susans-info
- George Cabinetry, Corner Cabinet Lazy Susan — https://georgecabinetry.com/blog/corner-cabinet-lazy-susan/
- Kesseböhmer, LeMans corner unit solution — https://www.kesseboehmer.com/en/storage-solutions/kitchen/corner-units/lemans
- Kesseböhmer US, LeMans — https://www.kesseboehmer.us/kitchen/corner-cabinets/lemans
- Häfele, Kesseböhmer LeMans II Set — https://www.hafele.com/us/en/product/lemans-ii-set-for-blind-corner-cabinets/P-00856493/
- Kesseböhmer US, Magic Corner — https://www.kesseboehmer.us/kitchen/corner-cabinets/magic-corner
- cabinetparts.com, Magic Corner Standard installation PDF — https://downloads.cabinetparts.com/auto/MagicCornerIInstallation.pdf
- Ferguson Home, Kessebohmer KS-MC1 Kit — https://www.fergusonhome.com/kessebohmer-mc1-l-kit/s1766224
- NKBA, Kitchen & Bath Planning Guidelines With Support Spaces and Accessibility (PDF) — https://kb.nkba.org/uploads/2023/05/2023-DC-Guidelines-1.pdf
- NKBA, Kitchen Planning Guidelines With Access Standards (PDF) — https://media.nkba.org/uploads/2022/05/Kitchen-Planning-Guidelines.pdf
- CRD Design Build, Kitchen Dimensions: Code Requirements & NKBA Guidelines — https://www.crddesignbuild.com/blog/kitchen-dimensions-code-requirements-nkba-guidelines/
- CabinetParts.com, Blum Multi-Use Restriction Clip (110°/92°) — https://www.cabinetparts.com/p/blum-hinges-european-cabinet-hinges-BHB70T7553-p131715
- Blum EASY ASSEMBLY Blog, Opening angle stops 155° hinges — https://ea.blum.com/en/opening-angle-stops-155-hinges/
- Blum EASY ASSEMBLY Blog, Opening angle stops 110°/107° hinges — https://ea.blum.com/en/opening-angle-stops-for-110-and-107-hinges/
- Houzz, Drawers are hitting each other and cabinet maker blames install — https://www.houzz.com/discussions/2665020/drawers-are-hitting-each-other-and-cabinet-maker-blames-install
- DoItYourself.com, Drawer pulls obstructing each other — https://www.doityourself.com/forum/carpentry-cabinetry-interior-woodworking/647516-drawer-pulls-obstructing-each-other.html
- bestonlinecabinets.com, Blind Corner Cabinet Ideas — https://www.bestonlinecabinets.com/blog/blind-corner-cabinet/
- WoodWeb, Kitchen Cabinet Clearance Above Stove Top — https://woodweb.com/knowledge_base/Kitchen_Cabinet_Clearance.html
- Carla Aston, 5 Tips for Designing a Range Hood Wall — https://carlaaston.com/designed/5-tips-for-designing-range-hood-wall-in-kitchen
- Bradco Kitchen, How to Plan Cabinet Door Swing Direction — https://bradcokitchen.com/blog/how-to-determine-kitchen-cabinet-door-swing-direction/
- cabinets.com, Base Corner Blind Cabinet spec sheet (PDF) — https://www.cabinets.com/media/download/euro-base-blind-details.pdf
- Houzz, Filler size for corner cabinets? — https://www.houzz.com/discussions/2695209/filler-size-for-corner-cabinets
- DoItYourself.com, How to fix these corner cabinet doors? — https://www.doityourself.com/forum/furniture-wood-cabinetry-finishing/623891-how-fix-these-corner-cabinet-doors.html
- LumberJocks, adjacent wall clearance for cabinet doors to open — https://www.lumberjocks.com/threads/question-for-cabinet-makers-adjacent-wall-clearance-for-cabinet-doors-to-open.98658/

---

```json
[
  {
    "pair_id": "corner-door-vs-door",
    "element_a": "hinged_door",
    "element_b": "hinged_door",
    "failure_mode": "Two full-overlay doors hinged to meet at an inside 90° corner strike each other's leading edge/face before reaching a usable opening angle",
    "geometric_condition": "collision if corner_setback (filler + reveal) < required_setback(door_thickness, hinge_opening_angle); required_setback derived from door_width * (1 - cos(opening_angle)) approx for the leading-edge travel",
    "min_clearance_in": 1.5,
    "resolution": "filler",
    "source_url": "https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler",
    "confidence": "ESTIMATE"
  },
  {
    "pair_id": "corner-door-vs-door-bifold-hinge",
    "element_a": "hinged_door",
    "element_b": "hinged_door",
    "failure_mode": "Same as above but resolved via mechanism instead of spacing",
    "geometric_condition": "no arc collision if hinge_type == corner_bifold (170° or paired 45/60 Clip Top), since doors fold against the corner rather than sweeping flat",
    "min_clearance_in": null,
    "resolution": "hinge-restrictor",
    "source_url": "https://www.woodcraft.com/products/blum-60-clip-top-bi-fold-hinge-inside-corner-pair",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "corner-door-vs-drawer-handle",
    "element_a": "hinged_door",
    "element_b": "drawer_front_with_pull",
    "failure_mode": "Door's swept edge strikes the projecting pull of an adjacent drawer before completing its opening arc",
    "geometric_condition": "collision if (door_edge_reveal) < handle_projection of adjacent drawer, evaluated at the door's fully-open position",
    "min_clearance_in": 3,
    "resolution": "filler",
    "source_url": "https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler",
    "confidence": "ESTIMATE"
  },
  {
    "pair_id": "drawer-vs-perpendicular-drawer-corner",
    "element_a": "drawer_front",
    "element_b": "drawer_front",
    "failure_mode": "Two perpendicular drawer banks at a corner both extend fully and their overhanging fronts collide in the shared corner airspace",
    "geometric_condition": "collision if front_overhang_A + front_overhang_B (measured from corner intersection) exceeds available corner setback from fillers/stiles",
    "min_clearance_in": 3,
    "resolution": "filler",
    "source_url": "https://www.houzz.com/discussions/2665020/drawers-are-hitting-each-other-and-cabinet-maker-blames-install",
    "confidence": "ESTIMATE"
  },
  {
    "pair_id": "drawer-front-static-tolerance",
    "element_a": "drawer_front",
    "element_b": "drawer_front",
    "failure_mode": "Adjacent slab fronts oversized relative to box opening touch/rub even at rest (not a full-extension issue)",
    "geometric_condition": "collision if gap_between_fronts_at_rest < fabrication_tolerance (~1/16in observed failure case)",
    "min_clearance_in": 0.125,
    "resolution": "spacing",
    "source_url": "https://www.houzz.com/discussions/2665020/drawers-are-hitting-each-other-and-cabinet-maker-blames-install",
    "confidence": "ESTIMATE"
  },
  {
    "pair_id": "handle-projection-knob",
    "element_a": "cabinet_door_or_drawer",
    "element_b": "knob_hardware",
    "failure_mode": "N/A - reference geometry constant, not itself a collision",
    "geometric_condition": "knob_diameter in range 1.0-1.5in; treat as fixed projection depth ~= radius for arc-sweep calculations",
    "min_clearance_in": 1.5,
    "resolution": "spacing",
    "source_url": "https://www.dkhardware.com/blog/cabinet-hardware-placement-sizing-guide/",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "handle-projection-bar-pull",
    "element_a": "cabinet_door_or_drawer",
    "element_b": "bar_pull_hardware",
    "failure_mode": "N/A - reference geometry constant, not itself a collision",
    "geometric_condition": "pull_projection in range 1.0-2.5in, average 1.5in; use actual spec value, not default, for any adjacent arc-sweep or extension calculation",
    "min_clearance_in": 2.5,
    "resolution": "spacing",
    "source_url": "https://gripfasthardware.com/2025/12/04/what-does-pull-projection-mean-cabinet-hardware-2/",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "blind-pullout-vs-dishwasher",
    "element_a": "blind_corner_pullout",
    "element_b": "dishwasher",
    "failure_mode": "Pullout mechanism/door and open dishwasher door occupy the same corner floor space; integrated dishwasher handles often project further than assumed generic pulls, causing under-filled corners",
    "geometric_condition": "collision if corner_filler_width < actual_dishwasher_handle_depth + pullout_door_swing_clearance (do not assume generic 1-1.5in handle; verify actual appliance spec)",
    "min_clearance_in": 2,
    "resolution": "filler",
    "source_url": "https://www.houzz.com/discussions/6403387/bosch-dishwasher-corner-clearance",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "dishwasher-standing-clearance",
    "element_a": "dishwasher",
    "element_b": "perpendicular_countertop_or_cabinet",
    "failure_mode": "Insufficient standing/floor space in front of an open dishwasher door adjacent to a perpendicular run",
    "geometric_condition": "collision/ergonomic-failure if standing_clearance < 21in (NKBA) or clear_floor_space < 30in x 48in",
    "min_clearance_in": 21,
    "resolution": "spacing",
    "source_url": "https://kb.nkba.org/uploads/2023/05/2023-DC-Guidelines-1.pdf",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "corner-door-vs-tall-pantry",
    "element_a": "hinged_door",
    "element_b": "tall_pantry_cabinet",
    "failure_mode": "Door cannot reach 90° (or the hinge's stable open detent) because its outer edge contacts the full-height adjacent pantry box",
    "geometric_condition": "max_open_angle = arccos(setback / door_width); collision/restricted-function if max_open_angle < 90 (or < hinge's rated minimum, e.g. 85 for mechanism-linked doors)",
    "min_clearance_in": 1.5,
    "resolution": "filler",
    "source_url": "https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler",
    "confidence": "ESTIMATE"
  },
  {
    "pair_id": "upper-corner-door-vs-range-hood",
    "element_a": "upper_corner_cabinet_door",
    "element_b": "range_hood",
    "failure_mode": "Diagonal/bi-fold upper corner door swing interferes with the hood body or duct chase volume",
    "geometric_condition": "model hood as fixed obstruction volume positioned per its own cooktop-clearance constraint (24-30in above cooktop); collision if corner door's swept arc intersects hood_footprint + duct_chase_width",
    "min_clearance_in": null,
    "resolution": "reorder",
    "source_url": "https://woodweb.com/knowledge_base/Kitchen_Cabinet_Clearance.html",
    "confidence": "ESTIMATE"
  },
  {
    "pair_id": "refrigerator-door-swing-vs-opposite-run",
    "element_a": "refrigerator_door",
    "element_b": "opposite_counter_or_island",
    "failure_mode": "Refrigerator door's swept arc blocks the aisle or collides with an opposing counter/island edge before reaching the angle needed for shelf/drawer withdrawal",
    "geometric_condition": "collision if aisle_width - door_swept_depth_at_required_angle(90-120deg) < NKBA_minimum_for_aisle_usage_class(36/42/48in)",
    "min_clearance_in": 36,
    "resolution": "spacing",
    "source_url": "https://kb.nkba.org/uploads/2023/05/2023-DC-Guidelines-1.pdf",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "refrigerator-crisper-drawer-vs-door-angle",
    "element_a": "refrigerator_door",
    "element_b": "crisper_drawer",
    "failure_mode": "Door restricted below 90° prevents crisper/shelf withdrawal along its rails",
    "geometric_condition": "function fails if achievable_door_angle < 90 (basic access) or < 120 (full shelf removal/cleaning)",
    "min_clearance_in": null,
    "resolution": "reorder",
    "source_url": "https://www.subzero-wolf.com/assistance/answers/sub-zero/common/sub-zero-door-and-drawer-clearance",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "refrigerator-vs-corner-wall",
    "element_a": "refrigerator_door",
    "element_b": "adjacent_wall_or_cabinet",
    "failure_mode": "Handle/hand pinches between the door and an adjacent wall/cabinet when the unit sits in or near a corner",
    "geometric_condition": "collision/pinch-risk if corner_filler_width < 2in (minimum), < 3in (preferred, Sub-Zero)",
    "min_clearance_in": 2,
    "resolution": "filler",
    "source_url": "https://www.subzero-wolf.com/assistance/answers/sub-zero/common/sub-zero-door-and-drawer-clearance",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "lazy-susan-tray-vs-door-close",
    "element_a": "independent_kidney_tray",
    "element_b": "hinged_door",
    "failure_mode": "Tray left rotated to an arbitrary position jams the door on closing or bends the tray support arm",
    "geometric_condition": "collision if tray_rest_position (unconstrained) does not fall within the subset of rotational positions compatible with the door's closed envelope",
    "min_clearance_in": null,
    "resolution": "hinge-restrictor",
    "source_url": "https://rev-a-shelf.com/53-401-series",
    "confidence": "ESTIMATE"
  },
  {
    "pair_id": "lemans-arm-sweep-vs-door-angle",
    "element_a": "lemans_articulated_arm",
    "element_b": "cabinet_door",
    "failure_mode": "Mechanism cannot fully present shelves because the linked door is restricted below the mechanism's required opening angle",
    "geometric_condition": "non-function if achievable_door_angle < 85 degrees",
    "min_clearance_in": null,
    "resolution": "reorder",
    "source_url": "https://www.kesseboehmer.com/en/storage-solutions/kitchen/corner-units/lemans",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "lemans-arm-sweep-vs-adjacent-cabinet",
    "element_a": "lemans_articulated_arm",
    "element_b": "adjacent_cabinet_front",
    "failure_mode": "Fully extended arm/tray sweep strikes a neighboring cabinet's door/drawer front",
    "geometric_condition": "collision if adjacent_side_clearance < ~11.8in (30cm) and no angle limiter installed",
    "min_clearance_in": 11.8,
    "resolution": "hinge-restrictor",
    "source_url": "https://www.kesseboehmer.us/kitchen/corner-cabinets/lemans",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "magic-corner-vs-cabinet-box",
    "element_a": "magic_corner_mechanism",
    "element_b": "corner_cabinet_box",
    "failure_mode": "Front/rear shelf frames cannot complete their sideways-then-forward stroke because the box is undersized",
    "geometric_condition": "non-function if cabinet_interior_height < 20.7in (525mm), or door_width outside 17.7-23.6in (450-600mm) range, or box outer dims not 500x900/1000mm",
    "min_clearance_in": 20.7,
    "resolution": "reorder",
    "source_url": "https://downloads.cabinetparts.com/auto/MagicCornerIInstallation.pdf",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "dishwasher-corner-clearance",
    "element_a": "dishwasher",
    "element_b": "corner_wall_or_cabinet",
    "failure_mode": "Open dishwasher door strikes the adjacent wall or cabinet at a corner installation",
    "geometric_condition": "collision if corner_clearance < 2in between side of open dishwasher door and wall/cabinet",
    "min_clearance_in": 2,
    "resolution": "filler",
    "source_url": "https://www.houzz.com/discussions/6403387/bosch-dishwasher-corner-clearance",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "range-side-clearance",
    "element_a": "range",
    "element_b": "adjacent_wall_cabinet",
    "failure_mode": "Cabinet or combustible surface positioned too close to burners/controls; heat/safety issue rather than pure geometry",
    "geometric_condition": "violation if side_clearance < 6in typical rule of thumb at/above counter height (model-dependent; some ranges UL-listed for 0in to combustible sidewall below cooktop deck)",
    "min_clearance_in": 6,
    "resolution": "spacing",
    "source_url": "https://products.geappliances.com/appliance/gea-support-search-content?contentId=16627",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "range-vs-wall-cabinet-vertical",
    "element_a": "range_cooktop",
    "element_b": "wall_cabinet_above",
    "failure_mode": "Cabinet bottom positioned too close to burners causing heat/grease damage risk",
    "geometric_condition": "violation if vertical_clearance < 30in (unprotected) or < 24in (protected), absolute floor 18in",
    "min_clearance_in": 18,
    "resolution": "spacing",
    "source_url": "https://products.geappliances.com/appliance/gea-support-search-content?contentId=21841",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "wall-oven-door-drop-envelope",
    "element_a": "wall_oven_door",
    "element_b": "adjacent_aisle_or_corner",
    "failure_mode": "Open oven door blocks the aisle or an adjacent corner/drawer stack",
    "geometric_condition": "collision if front_clearance < 31.125in (mfr spec) measured to corners, drawers, walls when door is open",
    "min_clearance_in": 31.125,
    "resolution": "reorder",
    "source_url": "https://content.syndigo.com/asset/538414e3-f0bc-4ba9-97ea-03f93f94c417/original.pdf",
    "confidence": "DOCUMENTED"
  },
  {
    "pair_id": "filler-corner-generic-rule",
    "element_a": "generic_cabinet_element",
    "element_b": "generic_perpendicular_element",
    "failure_mode": "Generic corner interference from combined door-arc geometry and handle-projection geometry",
    "geometric_condition": "required_filler = max(door_arc_clearance(door_thickness, hinge_open_angle), handle_projection_of_adjacent_element + reveal_margin); door-only case solves near 1.5in, handle-adjacent case solves near 3in",
    "min_clearance_in": 3,
    "resolution": "filler",
    "source_url": "https://www.unfinished-kitchen-cabinets.net/blog/corner-cabinet-filler",
    "confidence": "ESTIMATE"
  }
]
```
