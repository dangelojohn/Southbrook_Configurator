# CAD Math & Architecture Survey — Commercial Kitchen Design Systems

Research pass for the corner-placement engine. Focus: how commercial cabinet/kitchen
CAD systems (Microvellum, Cabinet Vision, Mozaik, 2020 Design, ProKitchen, KCD,
Winner/Compusoft) and adjacent general-purpose CAD/BIM/graphics literature model
walls, anchor cabinets, parameterize corners, chain transforms, detect collisions,
and drive placement — with concrete math and pseudocode wherever a primary or
credible secondary source exposes it. Where vendor internals are not public
(true for most of the consumer-facing kitchen-design tools), that gap is called
out explicitly rather than papered over with generic CAD folklore.

---

## 1. Wall & Room Modeling

### 1.1 Walls as first-class objects with local frames

Every system surveyed — from IFC-compliant BIM tools to Cabinet Vision — models a
wall not as a passive backdrop but as an object with its own local coordinate
system, from which everything attached to it (cabinets, moldings, soffits) derives
its placement.

The clearest public specification of this is **IFC (buildingSMART)**:

- `IfcWallStandardCase` requires a wall axis that is a straight line (or arc)
  **parallel to the local x-axis** of the wall's object coordinate system
  (`IfcAxis2Placement3D`), with the wall extruded along the local **+z axis**
  (vertical), and the local coordinate system itself placed into the world via
  a `LocalPlacement` transform relative to the building/storey.
- Material layers (the wall's physical construction — stud, sheathing, etc.) are
  applied **perpendicular to the axis**, via `IfcMaterialLayerSetUsage` with
  `LayerSetDirection = AXIS2`. This is the same "reference-line-plus-thickness"
  model every cabinet-CAD wall tool uses: a wall is a centerline (or reference
  face) + thickness, not a solid box authored directly.

Cabinet Vision's object model (per Cabinet Vision training material) makes the
same first-class distinction explicit in its Object Tree: **Rooms, Walls,
Assemblies, Decks, Stiles and Rails** are all objects, each described by **9 basic
parameters** — an (X, Y, Z) position plus orientation terms — establishing where
the object sits in space relative to its parent. A Wall's parent is the Room; an
Assembly's (cabinet's) parent is typically a Wall. This is a **scene-graph**, not
a flat list of solids: moving/resizing a Room parameter cascades to every Wall
under it, and moving a Wall cascades to every cabinet anchored to it.

Microvellum Toolbox draws the same line: **Wall and Room components are entities
in the Toolbox library, distinct from "products"** (the manufacturable cabinet
definitions). Walls are authored either by drawing a polyline (auto-generating a
wall run with corners already resolved) or by manual point-by-point placement,
per Microvellum University's "Wall & Room Components" training series.

### 1.2 Wall graphs and non-90° corners

A run of walls is really a **planar graph**: wall segments are edges, corners are
nodes where 2+ walls meet at an interior angle. For orthogonal (90°) kitchens this
graph degenerates into a simple rectilinear polyline, which is why so much
consumer kitchen-CAD tooling *assumes* 90° and only reluctantly supports angled
walls. Two structurally different techniques appear in the wild for resolving what
happens at a graph node (the corner):

1. **Centerline offset + intersection ("miter join").** Each wall is represented
   as a centerline segment with a perpendicular half-thickness offset on each
   side, producing two boundary polylines (interior face, exterior face). At a
   corner, the boundary polylines of the two adjacent walls are extended and
   **intersected** to find the miter point — the same technique documented for
   general polygon offsetting in the Clipper library (`jtMiter` join type),
   which computes the offset vertex until it would exceed a `MiterLimit`
   (in multiples of the offset delta), beyond which it falls back to a squared
   join to avoid unbounded spikes at very acute angles. This is exactly the
   failure mode a kitchen engine must guard against at non-90° corners (e.g. a
   30° wall intersection produces a near-degenerate miter spike).
2. **Explicit join/cleanup rules.** Revit's wall-join system (Autodesk
   documentation) exposes this as a user-controllable **Butt vs. Miter** choice
   per join, with the actual cleaned-up geometry depending on wall type, compound
   layer priorities, core-boundary alignment, and join order — i.e. the "clean"
   corner in a professional BIM tool is not a pure geometric derivation, it's a
   **rule-adjudicated** result over multiple candidate layer intersections.

For a kitchen placement engine, the practical takeaway is: **the wall graph node
(the corner) needs to be a real object** (a junction), not an implicit byproduct
of two wall rectangles overlapping — because corner cabinets, fillers, and
countertop miters all need to query "what is the interior angle at this junction"
and "which wall is the reference wall for the corner cabinet."

### 1.3 Plan vs. elevation views

Across all systems, plan view operates in the wall's 2D (X, wall-length) local
frame projected onto the world XY (floor) plane; elevation view operates in the
(wall-length, Z-height) frame. A wall-anchored cabinet's canonical parameters —
**along-wall offset (X), height off floor (Z), depth off wall face (Y)** — are
literally the coordinates in the wall's own local frame before any world
transform is applied. This is why 2D plan/elevation views can be generated as
orthographic projections of the *same* local-frame parameters rather than as
separately-authored drawings — the parametric systems (Cabinet Vision UCS,
Microvellum) generate shop drawings directly from the parametric model rather
than from a drawn view.

---

## 2. Cabinet Anchoring

Three anchor modes recur across every system surveyed:

1. **Wall-anchored.** The cabinet stores an along-wall offset (distance from a
   wall endpoint or from another cabinet) plus depth-off-wall and height. Moving
   the wall moves the cabinet (parametric dependency, not a baked world
   coordinate). This is the dominant mode for base/wall/tall runs.
2. **Corner-anchored ("consumes two walls").** A single logical cabinet object
   (or, per Chief Architect's blind-corner approach, two abutting standard
   cabinets) is parameterized by **two wall references** (or one wall + the
   junction node) instead of one. Its width is not free — it is derived from
   the corner geometry (see §3).
3. **Floating / island-anchored.** No wall reference at all; position is a
   free (X, Y) in room-world coordinates plus a rotation, most commonly
   constrained only by clearance to walls/other islands rather than by a wall
   local frame.

### Reference/anchor edge

Every wall-anchored cabinet has an implicit **reference edge** — the face that
touches the wall — and the along-wall offset is measured from a **reference
point** (a wall endpoint, an adjacent cabinet's far edge, or the corner
junction). Cabinet Vision's Assembly parameterization (9 basic parameters:
X, Y, Z position + orientation) is this reference-edge model made explicit at
the Object Tree level: an Assembly's X/Y/Z are defined **relative to its parent
Wall's origin**, not to room-world origin — confirming the local→wall→world
chain described in §4.

---

## 3. Corner Modeling

This is the crux of the placement engine and the area with the least public
vendor detail (see gaps below), but converging evidence from Chief Architect's
documented behavior, Cabinet Vision's UCS model, and general kitchen-industry
practice gives a solid empirical picture.

### 3.1 Corner as a junction/reference object

A corner needs, at minimum:

- The **junction node** (intersection point of the two wall centerlines/faces).
- The **interior angle** between the two walls (90° in the overwhelming
  majority of cases; kitchen engines that only special-case 90° are following
  the market, not a hard limitation of the math).
- A designation of **which wall is "primary"** for cabinets whose door/face
  orientation must pick one side (relevant for blind corners — see below).

### 3.2 Diagonal vs. blind parameterization

These are the two standard corner cabinet families, and they parameterize very
differently:

- **Diagonal (pie-cut) corner cabinet.** A single cabinet object that is itself
  aware it is a corner cabinet — Chief Architect's authoring rule requires
  **cabinet Width > Depth** (e.g. Width 36", Depth 24") specifically because the
  diagonal cabinet's "true" footprint is a 24"×24" square notch out of the
  corner with a **17" face mitered at 45°** to align with the flanking runs on
  both walls (this 24"/17"/45° convention is the de facto industry standard
  documented across cabinet retailers). The object consumes a fixed 24" of
  along-wall run on *each* adjacent wall — i.e. it has **two along-wall extents,
  one per wall**, not one width. A "Diagonal Door" option on the same object
  swaps the standard double-door face for the single 45°-angled door front.
- **Blind corner cabinet.** Not a single parametric corner object at all in at
  least one major system (Chief Architect): it is **two ordinary run cabinets**
  placed so one runs into the corner and is partially obscured by the other.
  The system then auto-resizes/offsets the *front items* (doors, drawer
  fronts, hardware) of the partially-hidden cabinet so they clear the hidden
  zone, and extends the countertop to fill the corner void. Industry practice
  (cabinet retailer documentation) additionally calls for the blind cabinet to
  sit **pulled ~6" off one wall** rather than flush to both, and for a
  **3" filler** between the blind unit's face frame/stile and the next cabinet
  in the run so doors/drawers clear the adjacent run — i.e. blind-corner
  handling is fundamentally a **clearance-envelope problem bolted onto ordinary
  run placement**, not a special corner solid.

### 3.3 Auto-insert vs. forced manual choice

The two documented systems diverge here:

- **Chief Architect**: semi-automatic. Moving a cabinet tool's cursor near an
  interior wall-wall junction changes the *preview* to a corner-cabinet form;
  a single click commits it. Blind corners require the **user** to place two
  cabinets and rely on automatic front-item/countertop reconciliation — the
  system does not silently decide diagonal-vs-blind for you.
- **Cabinet Vision UCS**: fully data/rule-driven. Corner behavior (which
  corner cabinet family to prefer, when to swap doors, dimension floors/ceilings
  for the corner selection) is expressed as **UCS logic** — a scripting layer
  evaluated against the Object Tree at model-build time (see §6) — meaning the
  "auto-insert vs. force manual" decision is itself a rule a shop can rewrite,
  not a hardcoded engine behavior.

No public source documents Microvellum's, Mozaik's, 2020 Design's, ProKitchen's,
or Winner/Compusoft's internal corner-selection heuristics at this level of
detail (see Gaps, end of document) — the general shape (fixed diagonal footprint
+ filler-mediated blind corner + rule-driven auto-suggest) is consistent enough
across the industry documentation found that it can be treated as a de facto
standard, but the *exact* decision trees are proprietary.

---

## 4. Transforms

### 4.1 Local → wall → world chain

The consistent pattern (explicit in IFC, implicit in Cabinet Vision's
parent/child Object Tree) is a 3-level affine transform chain:

```
P_world = M_room * M_wall * P_local

M_wall  = Translate(wall.origin) * RotateZ(wall.heading)
M_room  = Translate(room.origin) * RotateZ(room.heading)   // usually identity
P_local = (alongWall, depthOffWall, heightOffFloor)         // cabinet's own params
```

Where `wall.heading` is the angle of the wall's local +x axis (its run
direction) measured from world +x, in the floor plane. This mirrors IFC's
`IfcAxis2Placement3D` (`Location`, `Axis`, `RefDirection` — the wall's own
placement is itself relative to its parent's placement, i.e. `IfcLocalPlacement`
chains recursively exactly like the Room→Wall→Assembly chain above).

For a **corner-anchored** cabinet, `M_wall` is ambiguous by construction (two
walls meet); the practical resolution used by every system that documents
behavior (Chief Architect, and inferable from Cabinet Vision Assembly
parenting) is to pick a **primary wall** as the parent for the along-wall
transform, and derive the secondary-wall extent as a **fixed offset** (the
24" leg) rather than as an independent transform — i.e. the corner cabinet has
one real local frame (primary wall) and one derived measurement (secondary
wall leg), not two independent 3-DOF placements.

### 4.2 Rotation convention and why single-axis Y (or Z, depending on up-axis
convention) rotation suffices at 90°

If "up" is +Z (as in IFC/CAD convention used above) or +Y (as in most
game-engine/graphics conventions, including Ericson's collision-detection
text and typical OWL/three.js-style room viewers), wall headings in an
orthogonal kitchen are drawn from the set `{0°, 90°, 180°, 270°}`. A single
rotation about the vertical axis is sufficient because:

- Cos/sin of these four angles are all in `{0, ±1}` — the rotation matrix
  degenerates to **axis swaps and sign flips**, so `RotateZ(k·90°)` never
  introduces floating-point drift or off-axis components; an OBB aligned to
  a wall at any of these headings is **exactly** an AABB in the wall's own
  local frame, and the two systems (AABB broad-phase, OBB narrow-phase — see
  §5) collapse into one at these headings.
- Every downstream consumer (BOM/shop-drawing generation, CNC toolpaths in
  Microvellum/Cabinet Vision) can treat "width" and "depth" as literal X/Z
  local extents without a per-part rotation matrix, because the wall-to-world
  rotation is common to the whole run and cancels out in relative
  (cabinet-to-cabinet) calculations.

**What a 135° (or any non-multiple-of-90°) wall requires:**

- A **general 2D rotation matrix** `R(θ) = [[cosθ, -sinθ], [sinθ, cosθ]]` with
  arbitrary θ, meaning cabinet OBBs on that wall are **not** axis-aligned in
  world space and must be carried as true OBBs (center + half-extents + full
  rotation) all the way through collision and rendering — the AABB-equals-OBB
  shortcut above no longer holds, so broad-phase AABBs must be computed as the
  **axis-aligned bounding box of the rotated OBB** (a strictly larger box; see
  Ericson, ch. 4), not reused as the true collision shape.
- **Corner math changes qualitatively**: a diagonal corner cabinet's 45° face
  is defined *relative to the two flanking walls' bisector*, so at a 135°
  actual wall angle the bisector is no longer 45° from either wall — the
  cabinet-family geometry (leg lengths, face angle) has to be re-derived from
  the **actual interior angle**, not hardcoded as "half of 90°." Any engine
  that special-cases `if angle == 90` for corner-cabinet dimensioning needs a
  general branch: `faceAngle = interiorAngle / 2` measured from each wall,
  `legLength` still typically fixed by hardware (Lazy Susan diameter, hinge
  clearance) rather than scaled by angle — meaning non-90° corners often need
  a **different cabinet family entirely**, not a parametrically-scaled one, in
  real millwork (documented informally in Mozaik/Cabinet Vision forum
  discussion of angled walls; no vendor publishes closed-form non-90° corner
  dimensioning rules).
- **Miter-join math for the wall graph itself** (§1.2) also stops being a
  simple perpendicular offset+intersect at arbitrary angles without the
  `MiterLimit` clamp, because the offset distance to the miter point scales
  with `1/sin(θ/2)` for interior angle θ — this blows up as θ→0 (a very acute
  corner), which is precisely why Clipper's algorithm caps it.

---

## 5. Collision Architecture

### 5.1 Broad phase: AABB + sort-and-sweep

Christer Ericson's *Real-Time Collision Detection* (the standard reference the
game/graphics industry uses, and the closest thing to a public "textbook" for
what commercial CAD collision systems do internally) documents the canonical
broad phase: maintain all object AABBs in a single array; for a chosen sweep
axis, **sort by AABB minimum on that axis** and sweep, emitting a candidate
pair whenever two intervals overlap. This is O(n log n) sort + near-linear
sweep vs. O(n²) all-pairs, and is what makes a full-kitchen (dozens of
cabinets + walls + soffits) real-time collision check tractable.

### 5.2 Narrow phase: OBB + Separating Axis Theorem (SAT)

For any pair whose AABBs overlap, exact intersection is tested with the
**Separating Axis Theorem**: two convex shapes are disjoint iff there exists at
least one axis along which their projections do not overlap. For two OBBs this
reduces to testing exactly **15 candidate axes**: the 3 face normals of box A,
the 3 face normals of box B, and the 9 pairwise cross products of A's and B's
edge directions (3×3). If no separating axis is found among these 15, the boxes
intersect. Pseudocode:

```
function obbOverlap(A, B):
    axes = A.faceNormals() + B.faceNormals()
          + crossProduct(A.faceNormals(), B.faceNormals())   // 9 axes
    for axis in axes:
        if axis is near-zero: continue        // degenerate cross product (parallel edges)
        projA = project(A.corners(), axis)
        projB = project(B.corners(), axis)
        if intervalsDisjoint(projA, projB):
            return false   // separating axis found -> no collision
    return true             // no separating axis on any of the 15 -> collision
```

At orthogonal (0/90/180/270°) wall headings this degenerates to a plain AABB
test (see §4.2), which is why 90°-only kitchen engines can get away with pure
AABB overlap for cabinet-vs-cabinet checks and only need true OBB/SAT once
non-90° walls or rotated island cabinets are in scope.

### 5.3 Solid geometry vs. swept/clearance envelopes

A recurring, load-bearing distinction across both BIM and the academic
furniture-layout literature is that **the physical solid** of a cabinet/door
and its **required clearance envelope** are different geometric objects
evaluated with different severities:

- **Hard clash**: physical solid-vs-solid overlap (0mm tolerance) — two
  cabinet carcasses genuinely occupying the same space. Always disallowed.
- **Soft clash**: overlap of an object's solid with another object's
  **clearance/swept zone** — e.g. a dishwasher door's open-swept-arc
  overlapping a walkway, or a drawer's fully-extended envelope overlapping an
  island. Industry BIM practice treats these with a tunable buffer (documented
  ranges: ~25–100mm for general soft clashes, 100–300mm for
  service/maintenance access), and — critically — **soft clashes are
  frequently allowed to remain, subject to review**, not auto-rejected, because
  real kitchens routinely have "it's tight but it works" corners.
- The **swept envelope itself is a separate solid** from the closed-door
  solid: a door/drawer's clearance geometry is typically authored as the
  **union (or convex hull) of the closed pose and some parametrized open pose**
  (e.g. 90° door swing arc, full drawer extension box), and must be
  independently toggleable from the "as-built" solid used for BOM/manufacturing
  geometry — the two should never be conflated into one mesh, or manufacturing
  drawings will inherit phantom "open door" geometry.

### 5.4 Academic formalization: Minkowski-sum circulation checking

The most rigorous public treatment of "can a person actually walk through
here" comes from the furniture-layout research literature (Merrell et al.,
*Interactive Furniture Layout Using Interior Design Guidelines*, SIGGRAPH 2011,
and its associated patent filing, US 2013/0222393A1, "Method and System for
Interactive Layout" — same authors' technique, publicly readable via Google
Patents' OCR'd text, which is more mathematically explicit than the paper's
own PDF was able to be verified in this pass):

- Approximate a person as a **disk** `P` on the floor plane.
- Compute the **free configuration space**:
  `C_free = complement( P ⊕ (F ∪ W) )`, i.e. the Minkowski sum of the person-disk
  with the union of furniture footprints `F` and wall footprints `W`,
  subtracted from the room. This is the standard robot-motion-planning
  "configuration space obstacle" technique repurposed for interior circulation.
- A layout is penalized when `C_free` is disconnected between required regions
  (e.g. doorway to sink to stove), not merely when solids overlap.
- Separately, a **clearance violation term** is computed as an area integral of
  overlap between *expanded* (clearance-inflated) regions:
  `m_cv(I) = Σ A(f ∩ g)` over pairs of expanded item regions `f, g` — i.e.
  clearance is enforced as a **continuous, differentiable penalty** (area of
  overlap), not a boolean hard/soft flag, which is what lets this system be
  optimized by sampling (§7) rather than by discrete constraint satisfaction.
- A wall-alignment term uses `θ_w(f)` — the angle of the nearest wall segment
  to furniture item `f` — inside a cosine-penalty term that rewards
  parallel/perpendicular orientation to the nearest wall, which is the
  academic analogue of "why cabinets snap to wall heading" in commercial tools.

---

## 6. Constraint / Parametric Systems

### 6.1 Cabinet Vision UCS: rules as an embedded language over an Object Tree

Cabinet Vision's "User Created Standards" (UCS) is a real, if informally
documented, **domain-specific scripting language** layered over the Object
Tree described in §1. Key structural facts (from Cabinet Vision training/
community documentation, notably the Wikibooks "Cabinet Vision: The Last Mile"
guide):

- Every model parameter is either a **System Parameter** (an Object Tree data
  member CV itself provides — e.g. a cabinet's Width) or a **Custom Parameter**
  (user-declared, arbitrary name/type). Critically: **custom parameters never
  affect the model** until their value (or an expression derived from them) is
  explicitly assigned into a System Parameter — i.e. the rule language has a
  clean separation between "scratch computation" and "committed geometry
  change," which is a useful pattern for a placement engine's own rule layer
  (compute candidate corner-cabinet dimensions in scratch space; only commit
  once validated).
- Types are **not sticky across reassignment** — `<meas>`, `<deg>`, etc. must
  be redeclared on every assignment, or the value silently reverts to the
  default (`<meas>`, i.e. floating-point length). This is a real, documented
  footgun in the language and worth encoding as a lint rule if building an
  analogous DSL.
- **Null vs. zero are distinct**: a parameter that doesn't exist reads as null;
  testing a nonexistent parameter for numeric comparison defaults it to `0` —
  meaning "unset" and "explicitly zero" are conflated at the point of use even
  though they're distinct at declaration. (This is the same class of trap
  documented elsewhere in this project's Odoo work as the `falsy_value`
  Float/Integer issue — the fix pattern, "test for null before testing for
  zero," generalizes across both domains.)
- `=` is assignment, `==` is comparison, `:=` evaluates-then-assigns — a
  three-way split most general-purpose languages collapse into two operators,
  present here because UCS expressions can be either **live formulas**
  (re-evaluated) or **one-shot computed values**.

The load-bearing architectural point: **corner-cabinet selection logic in
Cabinet Vision is itself UCS code**, not engine code — a shop can rewrite when
a diagonal vs. blind corner is chosen, what the default leg length is, when a
filler is auto-inserted, etc., by editing the standards library rather than
patching the CAD program. This is the single clearest public example of "rules
as data" in the commercial kitchen-CAD space.

### 6.2 Microvellum: Excel-formula-driven parametric product library

Microvellum Toolbox's product definitions are described (Microvellum's own
marketing/training material) as leveraging **Excel-based formula logic** to
drive fully parametric 3D models — geometry, cut parts, hardware placement,
and machining data all derive from the same formula-driven definition, and
**product libraries remain open/editable** so a shop can tailor construction
methods without vendor involvement. This is architecturally the same pattern
as Cabinet Vision's UCS (external, editable rule layer over a fixed object
model) but authored in spreadsheet-formula syntax rather than a bespoke
scripting language — arguably an even more literal instance of "rules as data,"
since the rules are stored in a format (spreadsheet cells/formulas) with no
code/data distinction at all.

### 6.3 General parametric CAD: constraint graphs and solving order

Outside the kitchen-specific vendors, mainstream parametric/sketch-based CAD
(SolidWorks, Onshape, and the broader CAD literature on geometric constraint
solving) formalizes the same idea more rigorously:

- A sketch/assembly is a **constraint graph**: geometric entities are nodes,
  constraints (coincident, parallel, distance, angle) are edges/equations.
- **Degrees-of-freedom (DOF) analysis** determines whether the graph is
  under-constrained (residual DOF ⇒ ambiguous/movable geometry),
  well-constrained (0 DOF, unique solution), or over-constrained
  (contradictory equations ⇒ solver failure requiring manual conflict
  resolution — the failure mode SolidWorks/Onshape surface directly to users).
- Numerically, the constraint system is a set of (frequently nonlinear)
  equations solved via **Newton-Raphson iteration** (or similar), starting from
  the current geometry as an initial guess and iterating toward zero residual.
- Solving/propagation order matters: constraints are typically partitioned
  into **solvable subgraphs** (e.g. via a DOF-based dependency analysis) so
  that changes propagate in a stable topological order rather than requiring a
  full nonlinear re-solve of the entire model on every edit — directly
  analogous to Cabinet Vision's parent→child Object Tree propagation (§1) and
  to why a corner engine should model "cabinet depends on wall depends on
  room" as an explicit dependency graph rather than an ad hoc recompute.

### 6.4 Snap systems

Contrary to a common assumption that snap systems use a strict priority
hierarchy (endpoint > midpoint > perpendicular > ...), the dominant real-world
implementation (AutoCAD's documented OSNAP behavior) is **distance-based, not
rank-based**: when the cursor is within the aperture of multiple candidate
snap points, the system resolves to whichever candidate point is **closest to
the cursor**, only falling back to a configured subset of enabled snap *types*
(the user chooses which categories are candidates at all, e.g.
enable Endpoint+Midpoint+Perpendicular, disable Tangent). For a kitchen corner
engine, the practical implication is: implement snapping as **nearest-candidate-
among-enabled-categories**, not a fixed precedence list — a fixed precedence
list produces surprising results when a low-priority snap point is much closer
to the cursor than a high-priority one.

---

## 7. Placement Algorithms

### 7.1 Run packing and filler auto-insertion

Cabinet runs are fundamentally a **1D bin-packing / interval-scheduling**
problem along the wall's local x-axis: place N cabinets of fixed widths (drawn
from a catalog of standard widths, typically 3" increments) into a wall run of
length L, minimizing leftover space, subject to at least one required "give"
element. Documented industry practice (cabinet retailer/installer
documentation, consistent across multiple independent sources):

- Cabinets come in **3" width increments**; **fillers** are the standard
  mechanism for absorbing the remainder between the packed cabinet widths and
  the actual (often out-of-square, non-integer) wall run length.
- Standard practice is to **place fillers first** (against walls/corners),
  then pack cabinets into the remaining space, rather than packing cabinets
  greedily and hoping the remainder happens to fit a filler — i.e. the filler
  is a **reserved slot in the packing problem**, not a leftover.
- At least one filler per straight run between immovable obstacles (wall to
  wall) is standard, specifically to absorb out-of-plumb/out-of-square wall
  error — meaning the packing problem's "bin length" itself has **built-in
  slack tolerance**, not just a hard target length.
- At corners specifically, transitioning from one wall's run to the other
  requires a **3" filler** between the corner unit's face frame stile and the
  next cabinet, purely for door/drawer swing clearance (a soft-clash /
  clearance-envelope requirement, §5.3, encoded as a fixed-width placement
  rule rather than computed per-instance).

Pseudocode sketch of the packing rule as commonly implemented in industry
practice (not sourced to a specific vendor's internal code, which none publish,
but consistent with the retailer/installer documentation above):

```
function packRun(wallLength, requiredCorners, catalogWidths, fillerWidths=[3,6]):
    reserved = []
    if requiredCorners.hasBlindCorner:
        reserved.append(Filler(3))          # corner clearance filler, fixed
    remaining = wallLength - sum(reserved.widths)
    cabinets = greedyPack(remaining, catalogWidths, incrementInches=3)
    remainder = remaining - sum(cabinets.widths)
    if remainder > 0:
        # prefer widening/relocating a filler over forcing non-standard cabinet width
        reserved.append(Filler(remainder))
    return reserved + cabinets
```

### 7.2 Auto-fit / stretch fillers

The same sources describe filler width itself as the **free variable** used to
absorb dimensional slop: rather than solving for an exact non-standard cabinet
width, the design is packed with standard-increment cabinets and the filler is
**resized after the fact** to consume whatever remains — i.e. the filler acts as
the placement algorithm's slack variable, structurally identical to a
"stretch" element in a constraint-based layout (compare: CSS flexbox's
`flex-grow`, or a linear-programming slack variable absorbing an inequality
constraint's residual).

### 7.3 Density-function placement (research-grade alternative)

The Merrell et al. system (§5.4) represents the sole publicly-documented
example of a **non-discrete** placement algorithm in this space: rather than
greedy packing + rule-based corner selection, arrangement quality is expressed
as a single scalar **density function** aggregating clearance, circulation,
pairwise-relationship, and wall-alignment terms (each a soft, continuously
differentiable penalty), and candidate layouts are generated by an **MCMC
sampler** (Metropolis-Hastings-style accept/reject over translate/rotate/swap
proposal moves) exploring that density function, hardware-accelerated for
interactive rates. This is architecturally a completely different paradigm
from every commercial kitchen-CAD vendor surveyed (all of which are
discrete-rule/constraint-graph systems) and is flagged here as the credible
alternative architecture if a future corner-engine iteration wants
optimization-based auto-layout rather than rule-based placement.

---

## 8. Rules as Data, Not Code

The single most consistent finding across every vendor with any public
documentation depth (Cabinet Vision, Microvellum) is that **the parametric
product/rule definitions are explicitly kept out of the compiled application**:

- Cabinet Vision's UCS is a **user-editable scripting layer** over a fixed
  Object Tree — corner-selection logic, dimension defaults, filler-insertion
  triggers are all UCS code a shop can open and modify, and CV explicitly
  provides tooling (a "User Created Standard List" report) to locate where a
  given parameter is being set across the rule base.
- Microvellum's product library is **Excel-formula-driven** and explicitly
  marketed as staying "open and editable" so a manufacturer can encode its own
  construction standards without touching the core CAD/CAM engine.
- Both models share the same architectural shape: **(1) a fixed, versioned
  object schema** (Object Tree / Toolbox entity model) that the compiled
  application understands, plus **(2) an external, data-resident rule layer**
  (UCS scripts / spreadsheet formulas) that only the object schema's declared
  extension points can reach into. Neither vendor lets the rule layer touch
  arbitrary application internals — it can only set System Parameters (CV) or
  populate formula cells that feed declared geometry drivers (Microvellum).

For a corner-placement engine, this argues for the same shape: a small, stable
set of "System Parameters" per corner-junction/cabinet object (angle, leg
length, filler width, primary-wall reference, clearance envelope) that a
**data-resident rule table** (not engine code) is allowed to compute and write,
with the engine itself only responsible for evaluating dependency order and
enforcing hard invariants (no solid-solid overlap, valid DOF).

---

## 9. Comparative Table: Corner Modeling by System

Confidence reflects how much was found from primary/vendor documentation vs.
inferred from general industry practice or adjacent-system analogy.

| System | Wall model (as discoverable) | Corner object model (as discoverable) | Diagonal corner | Blind corner | Auto-insert vs. manual | Confidence |
|---|---|---|---|---|---|---|
| **Cabinet Vision** | Room→Wall→Assembly Object Tree; 9-param position/orientation per object | UCS-scriptable; corner logic is user-editable rule code, not hardcoded | Standard 24"×24"/17"-face/45° family (industry-standard dims, not CV-specific) | Not separately documented; UCS governs selection | Rule-driven (UCS decides), shop-configurable | Medium — object model and UCS mechanics are documented; exact stock corner rules are not public |
| **Microvellum** | Wall/Room are Toolbox entities distinct from products; built via polyline or manual point placement | Not documented at junction-object level in public sources found | Not documented | Not documented | Product-library rule-driven (Excel-formula), same paradigm as CV but internals not public | Low-Medium — architecture pattern (data-driven rules) confirmed; corner specifics are a gap |
| **Chief Architect** (reference, not a kitchen-specific vendor but best-documented corner UX) | Wall tool with junction detection at cursor proximity | Diagonal: single object, Width>Depth constraint enforced by UI; Blind: two ordinary cabinets + auto front-item/countertop reconciliation | Explicit "Diagonal Door" option swaps face | Documented: user places 2 cabinets, system auto-resizes hidden front items + extends countertop | Semi-automatic (preview snaps at junction proximity; user commits) | Medium-High — actual documented product behavior, most concrete public source found |
| **Mozaik** | Not found in public docs at this depth | Not found | Industry-standard dims apply generically | Not found | Not found | Low — no vendor architecture documentation surfaced |
| **2020 Design** | Not found; marketing material mentions "AI... automatically suggest optimal cabinet placements" with no mechanism disclosed | Not found | Industry-standard dims apply generically | Not found | Claimed automatic ("AI") but undisclosed | Low — consumer marketing only, no architecture disclosed |
| **ProKitchen** | Not found | Not found | Industry-standard dims apply generically | Not found | Not found | Low — no architecture documentation surfaced |
| **KCD (Compusoft-adjacent) / Winner** | Not found; KCD markets itself as unconstrained by "normal cabinet sizes" (implying a more free-form parametric core) | Not found | Not found | Not found | Not found | Low — no architecture documentation surfaced |
| **Merrell et al. (academic/patent)** | Ground-plane furniture/wall polygons, no wall-graph object model per se (walls treated as static obstacles `W`) | N/A — no cabinet-specific corner object; general clearance/circulation math applies to any furniture including corner units | N/A | N/A | Fully automatic via MCMC density-function sampling — categorically different paradigm | High — patent (US 2013/0222393A1) and paper are public and specific |
| **IFC / BIM (general reference, not kitchen-specific)** | `IfcWallStandardCase`: axis along local +x, extrusion along local +z, material layers perpendicular via `AXIS2` | Corner = wall-join cleanup problem (Revit: butt vs. miter, resolved by layer priority/core boundary rules), not a cabinet concept | N/A | N/A | N/A (architectural wall corners, not cabinetry) | High — public schema documentation |

**Gaps, stated plainly:** Mozaik, 2020 Design, ProKitchen, and KCD/Winner —
the systems named directly in the task brief alongside Microvellum and Cabinet
Vision — yielded essentially **no public architecture-level documentation** in
this pass. Their vendor sites and third-party comparison pages are
marketing/sales-oriented (feature lists, "AI-powered" claims with no mechanism
disclosed) rather than technical/training documentation. Microvellum's own
public material (training-plan pages, University video titles) confirms the
*existence* of the wall/room/product architecture described above but does not
expose junction-object or corner-rule internals at the depth Cabinet Vision's
community-authored UCS documentation does. Cabinet Vision, via the informal but
detailed Wikibooks "Last Mile" community documentation plus Craftsman
Engineering's UCS tutorial catalog, is by a wide margin the best-documented
commercial system found. Chief Architect (a general home-design tool, not a
kitchen specialist, but included because it is the only vendor with a public
KB article describing actual corner-cabinet click-to-place behavior) is the
best-documented *corner UX* specifically. The strongest **mathematical**
grounding overall comes from adjacent fields that do publish rigorously: game
physics/collision literature (Ericson), BIM schema standards (IFC), polygon
offsetting (Clipper), and academic layout-synthesis research (Merrell et al.
paper + patent) — none of which are kitchen-CAD vendors, but all of which
describe techniques directly transplantable into a corner-placement engine.

---

## Sources

- Cabinet Vision UCS overview / 9-parameter object model / craftsmanengineering.com tutorial+video catalog: [A Breakdown on UCSs](http://content.planit.com/cv/Help/CV_Help/Tips_Tricks_FAQs/UCS/A_Breakdown_on_UCSs.htm) (unreachable at fetch time; content triangulated via search snippet), [Cabinet Vision: The Last Mile / User-Controlled Standards Techniques (Wikibooks)](https://en.wikibooks.org/wiki/Cabinet_Vision:_The_Last_Mile/User-Controlled_Standards_Techniques), [Craftsman Woodworks Engineering Services — UCS tag](https://craftsmanengineering.com/taxonomy/term/108), [Cabinet Vision Tutorial (Expert-10) Introduction to UCS](https://craftsmanengineering.com/video/cabinet-vision-tutorial-expert-10-introduction-ucs)
- Microvellum Toolbox architecture / parametric product library / wall-room components: [Advanced CAD Features](https://www.microvellum.com/solutions/cad-features), [Microvellum University Training Plan: Getting Started with Toolbox](https://www.microvellum.com/resources/mvu-training-plan-getting-started), [Wall & Room Components (Part 1)](https://www.microvellum.com/resources/videos/mvu-elearning/wall-room-components-part-1), [Wall & Room Components (Part 2)](https://www.microvellum.com/resources/videos/mvu-elearning/wall-room-components-part-2)
- Chief Architect corner cabinet behavior: [Creating a Corner Cabinet (KB-00330)](https://www.chiefarchitect.com/support/article/KB-00330/creating-a-corner-cabinet.html)
- Diagonal/blind corner cabinet industry-standard dimensions and filler practice: [Blind Corner Cabinet Solutions Every Designer Should Know](https://academy.decorcabinets.com/blog-blind-corner-cabinet-solutions/), [Blind Corner Base Cabinet Dimensions](https://castacabinetry.com/post/blind-corner-base-cabinet-dimensions/), [Designing with Blind Corner Cabinets](https://www.cabinetjoint.com/video-library/designing-with-blind-corner-cabinets/), [Cabinet Fillers](https://cabinetselect.com/rta-kitchen-cabinets/fillers/), [Setting Kitchen Cabinets](https://sterlinglbr.com/blog/81226/setting-kitchen-cabinets)
- IFC wall coordinate system / material layers: [IfcWallStandardCase, IFC4.3.0.0 Documentation](http://www.bim-times.com/ifc/IFC4_3/buildingsmart/IfcWallStandardCase.htm), [IfcOpenShell Ifc4::IfcWallStandardCase](https://ifcopenshell.github.io/docs/rst_files/class_ifc4_1_1_ifc_wall_standard_case.html)
- Revit wall join / miter cleanup: [Wall Joins (Autodesk Help)](https://help.autodesk.com/cloudhelp/2016/ENU/Revit-Model/files/GUID-E6B8D985-FB52-4A5E-A825-B12531C3EA5B.htm), [Specify Wall Join Cleanup Options](https://knowledge.autodesk.com/support/revit-products/learn-explore/caas/CloudHelp/cloudhelp/2018/ENU/Revit-Model/files/GUID-130A65BC-8C57-4C31-8C07-F96041771539-htm.html)
- Polygon offset miter-join math (`jtMiter`/`MiterLimit`): [OffsetPolygons — The Clipper Library Documentation](https://documentation.help/The-Clipper-Library/OffsetPolygons.htm)
- Real-Time Collision Detection (Ericson) — AABB sort-and-sweep broad phase, OBB/SAT narrow phase: [Livro Morgan Kaufmann Real Time Collision Detection (Academia.edu)](https://www.academia.edu/29781815/Livro_Morgan_Kaufmann_Real_Time_Collision_Detection), [Separating Axis Theorem (SAT) diagram](https://www.researchgate.net/figure/Separating-axis-theorem-SAT_fig5_340681126)
- BIM hard/soft clash detection and clearance tolerances: [BIM Clash Detection: Hard, Soft & Workflow Clashes Explained](https://www.enginero.com/blogs/bim-clash-detection-hard-soft-workflow-clashes/), [Hard Clash vs Soft Clash Differences in BIM](https://www.stonehaven.ae/insights/hard-clash-soft-clash-detection)
- Furniture-layout density function, Minkowski-sum circulation, clearance/pairwise/wall-alignment terms: [Interactive Furniture Layout Using Interior Design Guidelines (SIGGRAPH 2011, ACM DL)](https://dl.acm.org/doi/10.1145/2010324.1964982), [US20130222393A1 — Method and System for Interactive Layout (Google Patents)](https://patents.google.com/patent/US20130222393)
- Generic parametric-CAD constraint solving (DOF analysis, Newton-Raphson sketch solving): [Onshape Forum — Constraints are a voodoo magic](https://forum.onshape.com/discussion/27886/constraints-are-a-voodoo-magic), [Geometric Sketch Constraint Solving with User Feedback (MIT ACDL)](https://acdl.mit.edu/ESP/Publications/AIAApaper2013-0702.pdf)
- CAD snap-priority behavior (distance-based resolution, not rigid hierarchy): [Perpendicular snap priority — Autodesk Community](https://forums.autodesk.com/t5/autocad-forum/perpendicular-snap-priority/td-p/2659049), [Object Snaps (OSNAP) Explained in AutoCAD](https://cadblockdwg.com/guides/object-snaps-osnap-explained-autocad)
- Sweet Home 3D (open-source parametric furniture project, referenced for wall/furniture magnetism precedent; source-level detail not confirmed in this pass): [Sweet Home 3D — Wikipedia](https://en.wikipedia.org/wiki/Sweet_Home_3D), [Open source interior design with Sweet Home 3D](https://opensource.com/article/19/10/interior-design-sweet-home-3d)

---

```json
[
  {
    "decision_id": "wall-segment-local-frames",
    "recommendation": "Model each wall as a first-class object with its own local 2D coordinate frame (origin at one endpoint, +x along the wall run, +z/+y vertical depending on up-axis convention), and store all wall-anchored cabinets in that local frame (along-wall offset, depth-off-wall, height) rather than baked world coordinates.",
    "rationale": "Every system with public documentation (IFC IfcWallStandardCase, Cabinet Vision's Room->Wall->Assembly Object Tree) uses this pattern. It makes wall edits (move/resize/re-angle) cascade automatically to every anchored cabinet, and lets plan/elevation views be pure projections of the same parametric data instead of separately authored drawings.",
    "adopted_by": ["cabinet_vision", "microvellum", "ifc_bim"],
    "math_sketch": "P_world = M_room * M_wall * P_local; M_wall = Translate(wall.origin) * RotateZ(wall.heading)",
    "source_url": "http://www.bim-times.com/ifc/IFC4_3/buildingsmart/IfcWallStandardCase.htm",
    "confidence": "high"
  },
  {
    "decision_id": "corner-junction-as-real-object",
    "recommendation": "Represent each wall-wall corner as an explicit junction node in the wall graph (not an implicit byproduct of overlapping wall rectangles), storing the two adjacent wall references, the intersection point, and the interior angle. Corner cabinets query the junction, not raw wall geometry.",
    "rationale": "Corner cabinets, fillers, and countertop miters all need 'what is the angle here' and 'which wall is primary' as first-class queries. Revit's wall-join cleanup and Clipper's miter-join offsetting both treat the corner as a computed object with its own degenerate cases (acute-angle spikes), which only works cleanly if the junction is modeled explicitly.",
    "adopted_by": ["revit_bim_analogy", "clipper_polygon_offsetting"],
    "math_sketch": "miterOffset = wallHalfThickness / sin(interiorAngle/2); clamp via MiterLimit to avoid spike at small angles",
    "source_url": "https://documentation.help/The-Clipper-Library/OffsetPolygons.htm",
    "confidence": "medium"
  },
  {
    "decision_id": "diagonal-corner-two-leg-parameterization",
    "recommendation": "Parameterize diagonal (pie-cut) corner cabinets with two along-wall leg extents (one per adjacent wall, both nominally 24\") plus a 45°-mitered face width (nominally 17\"), derived from the junction's interior angle rather than hardcoded, so a future non-90° corner re-derives faceAngle = interiorAngle/2 instead of breaking.",
    "rationale": "This is the converged industry-standard dimension set found across multiple independent cabinet-retailer sources, and matches Chief Architect's enforced Width>Depth authoring rule for diagonal corner objects. Hardcoding 45° instead of interiorAngle/2 silently produces wrong geometry the moment a non-90 wall angle is introduced.",
    "adopted_by": ["chief_architect", "industry_standard_practice"],
    "math_sketch": "legLength = 24in (fixed, hardware-driven); faceAngle = interiorAngle / 2 (measured from each wall)",
    "source_url": "https://www.chiefarchitect.com/support/article/KB-00330/creating-a-corner-cabinet.html",
    "confidence": "medium"
  },
  {
    "decision_id": "blind-corner-as-clearance-problem-not-solid",
    "recommendation": "Implement blind corner cabinets as two ordinary run cabinets plus (a) a fixed 3\" filler between the corner unit's stile and the next cabinet, and (b) automatic recomputation of the partially-hidden cabinet's front-item (door/drawer) positions and countertop fill, rather than authoring a bespoke blind-corner solid.",
    "rationale": "Chief Architect's documented behavior does exactly this (auto-resize/offset front items + extend countertop over two abutting standard cabinets), and cabinet-industry documentation independently confirms the 3\" filler-for-clearance convention. This keeps blind corners inside the existing run-packing and clearance-envelope machinery instead of requiring a separate corner-solid code path.",
    "adopted_by": ["chief_architect", "industry_standard_practice"],
    "math_sketch": "filler.width = 3in (fixed); hiddenCabinet.frontItems.offset = max(0, overlapWithAdjacentCabinet)",
    "source_url": "https://academy.decorcabinets.com/blog-blind-corner-cabinet-solutions/",
    "confidence": "medium"
  },
  {
    "decision_id": "single-axis-rotation-only-at-orthogonal-headings",
    "recommendation": "Treat the AABB-equals-OBB shortcut (skip full OBB/SAT, use plain axis-aligned overlap) as valid only when wall heading is an exact multiple of 90 degrees; require true OBB representation (center, half-extents, full rotation) and SAT narrow-phase the moment any wall or island cabinet has a non-orthogonal heading.",
    "rationale": "At 0/90/180/270 degree headings, cos/sin collapse to {0, +/-1}, so the wall-local OBB is numerically identical to an AABB in that frame -- this is why 90-degree-only kitchen engines can get away with pure AABB collision. At any other angle this identity breaks and reusing the AABB as the true collision shape produces false negatives on overlap.",
    "adopted_by": ["ericson_real_time_collision_detection", "general_graphics_practice"],
    "math_sketch": "if heading % 90 == 0: OBB == AABB (exact); else: broadphaseAABB = AABBof(rotatedOBB) [strictly larger], narrowphase = SAT over 15 axes (3+3 face normals + 9 edge cross products)",
    "source_url": "https://www.academia.edu/29781815/Livro_Morgan_Kaufmann_Real_Time_Collision_Detection",
    "confidence": "high"
  },
  {
    "decision_id": "aabb-broadphase-obb-sat-narrowphase",
    "recommendation": "Use a two-phase collision architecture: sort-and-sweep AABB broad phase over all cabinets/walls to generate candidate overlapping pairs, then exact OBB/SAT narrow phase (15-axis test) only on candidate pairs.",
    "rationale": "This is the standard real-time collision detection architecture (Ericson) and is the only way full-kitchen (dozens of objects) collision checking stays fast enough for interactive placement; full pairwise OBB/SAT on every object pair is unnecessary work once AABBs already prove most pairs can't intersect.",
    "adopted_by": ["ericson_real_time_collision_detection", "game_engine_standard_practice"],
    "math_sketch": "sort AABBs by min-x, sweep for interval overlap -> candidate pairs; for each candidate pair test 15 SAT axes (A.normals + B.normals + 9x cross products); no separating axis found => collision",
    "source_url": "https://www.academia.edu/29781815/Livro_Morgan_Kaufmann_Real_Time_Collision_Detection",
    "confidence": "high"
  },
  {
    "decision_id": "swept-envelope-separate-from-solid-geometry",
    "recommendation": "Author two distinct geometries per door/drawer-bearing cabinet: the closed-pose solid (used for manufacturing/BOM geometry) and a separately-toggleable swept clearance envelope (union/hull of closed pose + parametrized open pose), and evaluate them with different severities (hard clash on solids, soft/tunable-buffer clash on envelopes).",
    "rationale": "BIM clash-detection practice draws this line explicitly (hard clash = 0mm solid overlap, soft clash = buffer-zone/clearance-envelope intrusion, often allowed to persist pending review). Conflating the two into one mesh contaminates manufacturing drawings with phantom open-door geometry and removes the ability to relax clearance checks independently of solid checks.",
    "adopted_by": ["bim_clash_detection_practice"],
    "math_sketch": "solid = closedPose.mesh; envelope = convexHull(closedPose, openPose(sweepAngle|extension)); hardClash = overlap(solid_A, solid_B) > 0; softClash = overlap(envelope_A, solid_B) > toleranceBuffer",
    "source_url": "https://www.enginero.com/blogs/bim-clash-detection-hard-soft-workflow-clashes/",
    "confidence": "medium"
  },
  {
    "decision_id": "minkowski-sum-circulation-check",
    "recommendation": "For walkway/circulation validation (can a person actually move between the sink, stove, and doorway), compute free configuration space as the complement of the Minkowski sum of a person-disk with the union of furniture and wall footprints, and flag layouts where required regions become disconnected in that free space -- rather than relying solely on pairwise solid-overlap checks.",
    "rationale": "This is the only rigorously documented, publicly available formalization of interior circulation checking (Merrell et al. SIGGRAPH 2011 paper + associated patent). It correctly captures 'technically nothing overlaps but you can't walk through here,' which pairwise AABB/OBB collision alone cannot express.",
    "adopted_by": ["merrell_et_al_academic", "us2013_0222393a1_patent"],
    "math_sketch": "C_free = complement(P (+) (F union W)), where P = person disk, F = furniture footprints, W = wall footprints, (+) = Minkowski sum; flag if C_free disconnects required region pairs",
    "source_url": "https://patents.google.com/patent/US20130222393",
    "confidence": "high"
  },
  {
    "decision_id": "clearance-as-continuous-area-penalty",
    "recommendation": "Model clearance violations as a continuous area-of-overlap penalty between clearance-inflated object regions (m_cv = sum of A(f intersect g) over expanded-region pairs) rather than a pure boolean pass/fail, so a rule/scoring layer can rank near-miss layouts instead of only accepting or rejecting them.",
    "rationale": "The Merrell et al. system's clearance term is explicitly area-based and differentiable, which is what allows soft ranking of layouts (a corner solution that is 1 inch short of ideal clearance scores worse but isn't simply invalid) -- directly useful for a placement engine that needs to present ranked candidate corner solutions rather than a single hard-coded default.",
    "adopted_by": ["merrell_et_al_academic", "us2013_0222393a1_patent"],
    "math_sketch": "m_cv(I) = sum over pairs (f,g) of A(f_expanded intersect g_expanded)",
    "source_url": "https://patents.google.com/patent/US20130222393",
    "confidence": "medium"
  },
  {
    "decision_id": "rules-as-external-data-not-engine-code",
    "recommendation": "Keep corner-selection heuristics, default dimensions, and filler-insertion triggers in an external, versioned, user-editable rule table/DSL (e.g. a small formula/rule layer with declared write-access to a fixed 'System Parameter' schema) rather than hardcoding them into the placement engine's compiled logic.",
    "rationale": "Both best-documented commercial systems (Cabinet Vision's UCS scripting layer, Microvellum's Excel-formula-driven product library) converge on this shape: a fixed object schema plus an external rule layer that can only write to declared extension points. This is what lets a shop change 'when do we auto-insert a diagonal vs blind corner' without a software release.",
    "adopted_by": ["cabinet_vision", "microvellum"],
    "math_sketch": "engine.evaluate(ruleTable) writes only to declared SystemParameters[cabinet.id]; ruleTable authored external to compiled engine (spreadsheet formula or DSL script)",
    "source_url": "https://en.wikibooks.org/wiki/Cabinet_Vision:_The_Last_Mile/User-Controlled_Standards_Techniques",
    "confidence": "medium"
  },
  {
    "decision_id": "filler-as-packing-slack-variable",
    "recommendation": "Model wall-run cabinet packing as 1D interval packing with catalog widths in fixed increments (e.g. 3\"), where fillers are placed first as reserved slots (not computed as leftovers) and then resized after cabinet packing to absorb whatever dimensional slack (including out-of-square wall error) remains.",
    "rationale": "Documented cabinet-industry installation practice consistently describes placing fillers first and treating filler width as the free/slack variable, rather than solving for exact non-standard cabinet widths -- this is a simpler, more robust packing model than trying to fit exact-width cabinets to an imprecise real-world wall length.",
    "adopted_by": ["industry_standard_practice"],
    "math_sketch": "remaining = wallLength - sum(reservedFillers.widths); cabinets = greedyPack(remaining, catalogWidths, increment=3in); finalFiller.width += remaining - sum(cabinets.widths)",
    "source_url": "https://cabinetselect.com/rta-kitchen-cabinets/fillers/",
    "confidence": "medium"
  },
  {
    "decision_id": "distance-based-snap-resolution",
    "recommendation": "Implement snapping as nearest-candidate-among-enabled-categories (compute all candidate snap points from user-enabled categories, pick whichever is closest to the cursor/reference point) rather than a fixed category-priority ranking.",
    "rationale": "AutoCAD's documented OSNAP behavior resolves conflicts by cursor-proximity, not a rigid endpoint>midpoint>perpendicular hierarchy; a fixed-priority list produces surprising snaps when a low-priority candidate is much closer than a high-priority one, which is worse UX for a kitchen placement tool where users expect the visually nearest point to win.",
    "adopted_by": ["autocad_documented_practice"],
    "math_sketch": "snapPoint = argmin_{p in candidates(enabledCategories)} distance(cursor, p)",
    "source_url": "https://forums.autodesk.com/t5/autocad-forum/perpendicular-snap-priority/td-p/2659049",
    "confidence": "medium"
  }
]
```
