# Manufacturing Intelligence — Corner Cabinet Production

Research notes on how professional CAD/MRP systems (Cabinet Vision, Microvellum, Homag woodWOP) represent
and manufacture cabinetry, with focus on corner-cabinet families (blind corner base, diagonal/pie-cut lazy-susan
base). Intended to inform panel genealogy, machining-operation, and BOM modeling in the Southbrook corner engine.

Confidence markers: facts pulled directly from a cited source are stated plainly; anything inferred, generalized
from forum/community consensus, or not directly confirmed in a primary manufacturer document is marked **ESTIMATE**.

---

## 1. Cabinet Metadata Models in Manufacturing Software

Commercial cabinet CAD/CAM systems (Cabinet Vision Solid, Microvellum) share a common conceptual hierarchy:

```
Cabinet (Product)
  └─ Sub-assemblies (Door assembly, Drawer box, Face frame, Carcass)
        └─ Parts (individual panels: side, bottom, top/stretcher, back, shelf, door slab, drawer front/side/back/bottom)
              └─ Operations (per-part machining: cut size, edgeband edges, drill pattern, dado/groove, hinge/pull boring)
                    └─ Hardware (hinges, slides, shelf pins, fasteners) attached to parts or the assembly
```

- **Cabinet Vision Solid / S2M**: parts carry a "Geometry" tab of properties. Two settings are structurally
  important for genealogy: *"Include Banding in Overall Part Size"* (whether the nominal part size already
  accounts for the edgeband thickness added to the core) and *"Incorporate Door Assembly Operations on Slab
  Door Part for CNC"* (whether door hardware operations — hinge cup boring — are recorded against the raw
  door *slab* part or against the finished, assembled door). This second toggle is a real-world instance of
  "does the operation belong to the raw-cut part or the assembled product" — directly relevant to panel
  genealogy modeling (cut part → machined part → assembled sub-component). [Hexagon Cabinet Vision](https://www.cabinetvision.com/compares2m)
- Buyout (pre-finished, purchased) doors can still be routed through the same machining center (the "S2M
  Center") purely for hinge/pull boring — i.e., the metadata model treats a purchased door as a part that
  enters the *operations* pipeline without having gone through the *cutting* pipeline. This is a useful pattern
  for corner-cabinet engines where some parts (e.g., factory lazy-susan platters, purchased bifold door
  hardware) never touch the saw/nest step but do need drill operations. [Hexagon Cabinet Vision](https://www.cabinetvision.com/compares2m)
- **Microvellum**: parametric definitions are driven by an embedded Excel-based formula layer per product.
  Each product's BOM lines and routing ("Route") operations are gated by conditional formulas evaluated against
  the product's attributes (width, height, depth, door count, hardware selection, etc.) — i.e., BOM-line and
  routing-step existence itself is parametric, not just dimensions. A BOM line typically requires a `Quantity`
  formula (Value-based or Attribute-based), and a Route operation requires a conditional "include this operation
  when attribute X is selected" formula. This is the direct analog of "operation applies_to a subset of cabinet
  types" needed for corner-specific machining (e.g., "add pie-cut notch operation only when door_style =
  bifold_lazy_susan"). [RSM: Product Configurator Part 2 – BOMs and Routes](https://technologyblog.rsmus.com/industry/manufacturing/product-configurator-part-2-boms-and-routes/), [Microvellum Engineering](https://www.microvellum.com/solutions/engineering)
- Microvellum's platform description: "custom tool paths for precise routing, sawing, and drilling operations,"
  generating "machine-specific g-code for any CNC machine in your shop, including routers, machining centers,
  saws, drilling machines, material handling systems, and robotic arms" — confirming the routing model spans
  multiple discrete station types, not a single monolithic "CNC" step. [Microvellum Solutions/Processes](https://www.microvellum.com/solutions/processes/)

**Panel genealogy pattern (synthesized, ESTIMATE for the general model, though each step is independently
sourced above):** `Cabinet product → BOM explosion → raw panel (material + rough size) → cut part (net size via
saw or nest program) → edgebanded part (edges banded per role) → drilled/machined part (system holes, hinge
cups, dados) → sub-assembly (door, drawer box, carcass) → packed cabinet`. Each transition is a routing
operation with its own station, and Cabinet Vision's slab-vs-assembly toggle shows that *where* in this chain
an operation is recorded is a configurable, not fixed, decision in real systems.

---

## 2. The 32mm System

- Core spec (Wikipedia, corroborated by multiple boring-jig vendor pages): hole-to-hole pitch in a vertical
  row = **32 mm**; hole diameter = **5 mm**; hole depth = **12–14 mm**; shelf-pin length = **15–16 mm**; shelf-pin
  flange diameter ≈ **7 mm**; first hole row set back **37 mm** from the front edge of the panel.
  [32 mm cabinetmaking system – Wikipedia](https://en.wikipedia.org/wiki/32_mm_cabinetmaking_system), [Euro32Products manual](https://euro32products.com/wp-content/uploads/2020/04/CondensedEuro32Manual.pdf)
- The 37 mm setback is what a "Euro-32 template" boring jig locates from; it exists so the hinge-plate/runner
  screw holes clear the front edge banding and door/drawer clearance zone while staying on the same 32 mm
  vertical grid as shelf-pin holes. [Euro32Products](https://euro32products.com/wp-content/uploads/2020/04/CondensedEuro32Manual.pdf)
- **Construction holes vs shelf holes**: the same 32 mm-pitch vertical line is used for two different purposes
  depending on row and depth — (a) *system/construction holes*, used for cam-and-dowel or knock-down (KD)
  fastener joinery at case-corner locations, and (b) *shelf-pin holes*, a duplicate/adjacent row at shallower
  depth used only for movable shelf support pins. Because they share pitch, a single boring pattern (line-boring
  head) can produce both in one pass — this is why 32mm-system boring machines have gang-drill heads with
  multiple spindle groups rather than a single spindle. [Frameless carcass construction – WoodWeb](https://woodweb.com/knowledge_base/Frameless_carcass_construction.html)
- Hinge cup positions (35 mm cup, standard "system 32" cup boring) are **not** on the 32 mm pitch itself but are
  positioned relative to it — hinge-plate screws land on the same vertical 32mm grid so a single row of holes
  serves both hinge mounting and (on the opposite/interior face) shelf pins. **ESTIMATE** (widely stated in
  32mm-system literature but not independently confirmed against a single manufacturer spec in this research pass).
- Dowel/confirmat "system holes" for carcass joinery: AWI (Architectural Woodwork Institute) standard confirmat
  screw spacing is **37 mm from the panel end, 128 mm on centers** (128 = 4 × 32, i.e., still tied to the 32mm
  grid family even though the screws themselves are structural, not shelf/hinge holes).
  [Frameless carcass construction – WoodWeb](https://woodweb.com/knowledge_base/Frameless_carcass_construction.html)

---

## 3. Machining Operations Per Panel Type

### 3.1 Joinery method (frameless / 32mm-system carcasses)

| Joint | Method | Notes |
|---|---|---|
| Side-to-top/bottom | Dowel + glue (traditional Euro) | CNC boring machine drills mating holes in the face of the side and the end-grain of the top/bottom; dowels + glue join them. |
| Side-to-top/bottom | Confirmat screw ("European assembly screw") | No glue required; can be disassembled; strength "short of a doweling machine" per shop consensus. |
| Side-to-top/bottom | Rabbet + glue + nails, or stop-dado | Lower-cost, weaker, faster-assembly alternative; common on RTA/promotional lines. |
| Back-to-case | Dado (in bottom + sides) | Standard for structural squareness; back captured in a groove. |
| Back-to-case | Rabbet instead of dado | Faster to assemble, "somewhat weaker final product." |
| Back-to-case | 1/4″ back + 3/4″ nailer strips, hot-melt glue + pocket screws | Alternate KD-friendly method allowing flat-pack shipping. |

Sources: [Frameless carcass construction – WoodWeb](https://woodweb.com/knowledge_base/Frameless_carcass_construction.html), [Case construction practices – WoodWeb](https://woodweb.com/knowledge_base/Case_construction_practices.html)

Dowel/KD construction "uses less material since top and bottom shelves are only as long as the internal width"
— i.e., in frameless construction the top/bottom/stretcher parts are cut to the *interior* case width (between
the two side panels), not overall cabinet width; side panels run full case height and depth. This is a load-bearing
fact for parametric part-size formulas: `top/bottom width = overall_width − 2 × side_thickness` (frameless), vs
face-frame construction where box parts may be sized independently of the frame. [Frameless carcass construction – WoodWeb](https://woodweb.com/knowledge_base/Frameless_carcass_construction.html)

### 3.2 Edgebanding — sequence and which edges

- General industry process order for an automatic edgebander: **Feeding → Pre-milling → Gluing → Pressing →
  End Trimming → Top/Bottom Trimming → Scraping → Buffing**. [Blue Elephant CNC — Edge Banding Machine Guide](https://www.elephant-cnc.com/blog/what-is-edge-banding-machinethe-2026-complete-guide/)
- Panel saw and edgebander are treated as matched, sequential stations in production flow: saw first (dimension
  + squareness), then band. [Caelus — Panel Saw & Edge Bander](https://www.caelus-intel.com/article/how-do-panel-saw-and-edge-bander-work-together-in-cabinet-production.html)
- Which edges get banded is a *role-driven* decision, not "all edges": doors, drawer fronts, shelves, and
  exposed end/side panels get edgebanding on visible edges; interior carcass edges captured inside a dado/joint,
  or edges that will be covered by another panel or hidden against a wall, are typically left raw. [Pedicco — Edge Banding on Cabinets](https://www.pedicco.com/news/Blogs/Edge-Banding-on-Cabinets--A-Comprehensive-Guide.html), [Elephant CNC](https://www.elephant-cnc.com/blog/what-is-edge-banding-machinethe-2026-complete-guide/)
- Cabinet Vision's "Include Banding in Overall Part Size" flag governs whether the *finished* part dimension
  reported in cut lists / CNC output already has the edgeband thickness added to the raw substrate size — a
  direct genealogy fork between "core panel size" and "banded net size." [Hexagon Cabinet Vision](https://www.cabinetvision.com/compares2m)
- **ESTIMATE** (ties to Southbrook's own recorded trap `southbrook_ptav_price_extra_gap` context, not from this
  research pass): edgeband thickness (commonly 0.4–3 mm PVC/ABS tape) is compensated in the toolpath by trimming
  flush after pressing (the "End Trimming"/"Top and Bottom Trimming" steps above), not by pre-shrinking the
  panel — i.e., the core is cut to net size *minus* nothing, banded oversize, then trim-flush cut back to net.

### 3.3 Drilling patterns

- Standard boring passes per side panel: (1) 32mm-pitch vertical construction/shelf-pin line(s) set back 37 mm
  from front, (2) hinge-plate boring (35 mm cup + 2 mounting screw holes) at door-hinge stile locations, (3)
  drawer-slide mounting holes (often on the same or an adjacent 32mm-derived grid), (4) confirmat/dowel
  construction holes at top/bottom joints. [32 mm cabinetmaking system – Wikipedia](https://en.wikipedia.org/wiki/32_mm_cabinetmaking_system), [Frameless carcass construction – WoodWeb](https://woodweb.com/knowledge_base/Frameless_carcass_construction.html)
- CNC point-to-point / machining-center boring heads execute all of the above in one clamped operation per
  panel face; nested-based (flat-table router) processing typically handles the cut-to-shape + some drilling
  but full 5- or 6-side boring is more commonly a dedicated point-to-point machine's job. [Nesting vs. Point-to-Point – Woodworking Network](https://www.woodworkingnetwork.com/magazine/nesting-vs-point-point)

---

## 4. Corner-Cabinet-Specific Manufacturing

### 4.1 Corner cabinet families

Two structurally distinct corner-cabinet geometries recur across manufacturers (Conestoga, Cabinotch, Barker,
generic KCMA-member RTA lines):

1. **Blind corner base/wall** — a rectangular-footprint cabinet that extends behind (is "blind" to) the
   adjacent run of cabinets. Looks like a normal cabinet from the front; a "blind" (unusable, inaccessible)
   section runs back into the corner. Access to the blind zone is either sacrificed (dead storage) or recovered
   with a pull-out/swing mechanism (e.g., Cabinotch's "Full Access Blind Corner," which converts the blind
   volume into a functional pull-out). [Cabinotch — Full Access Blind Corner Cabinet](https://cabinotch.info/the-cabinotch-full-access-blind-corner-cabinet/), [Conestoga — Blind Corner System](https://www.conestogawood.com/product/blind-corner-system/)
2. **Diagonal / pie-cut corner base (lazy-susan)** — the cabinet's front face is cut at 45° across the corner,
   producing a pentagonal (or, upstream in the cut sequence, a trapezoidal/diagonal) case footprint. The case
   is deeper than a standard 12″ run cabinet to reach the true corner. Typically fitted with a full-circle or
   pie-cut rotating lazy-susan shelf assembly and a pair of bifold doors. [RTA Cabinets House — Corner Cabinet Dimensions](https://rtacabinetshouse.com/blogs/cabinet-sizes-measurements/corner-kitchen-cabinet-dimensions), [Ana White — Pie Cut Corner Base Plans](https://www.ana-white.com/woodworking-projects/36-corner-base-pie-cut-kitchen-cabinet-momplex-white-kitchen)

### 4.2 How the diagonal deck is produced

- The diagonal/pie-cut cabinet's distinguishing part is its **deck** (bottom) and **top/stretcher**, cut with
  two 45° corners (or one full diagonal edge) rather than a simple rectangle. On a straight panel saw this
  requires an angled cross-cut fence setting or a second pass; on a flat-table CNC (nested-based manufacturing,
  NBM) it is a single toolpath around an irregular polygon — no fence resets needed, and NBM software nests the
  pentagon/trapezoid shape onto the sheet alongside rectangular parts from other cabinets to control material
  yield. This is precisely the class of part NBM was built to make easy relative to saw-first workflows: "the
  common goals of nesting technology are to reduce overall labor, increase material optimization, improve
  component quality and enhance component flexibility" — non-rectangular parts are the case where flexibility
  matters most, since a panel saw handles rectangles trivially but angled/irregular cuts poorly. [Woodworking Network — Nesting vs Point-to-Point](https://www.woodworkingnetwork.com/magazine/nesting-vs-point-point)
- **ESTIMATE**: for a shop running saw + separate boring machine (not full NBM), the diagonal deck/top is
  typically cut on a beam saw using an angled fence or scored/trimmed on a sliding table saw set to 45°, then
  sent through the same boring/edgebanding stations as rectangular parts — i.e., the *shape* of the cut changes
  the saw step but not the downstream routing (edgeband → drill → assemble) which treats it as just another
  panel with defined edges to band and holes to drill.

### 4.3 Bifold door sets

- A pie-cut lazy-susan corner cabinet needs two doors hinged to fold against each other and against the case,
  rather than a single door — because a single door spanning a 45°-corner opening cannot swing clear on typical
  cabinet hinge geometry. [Houseful of Handmade — corner cabinets](https://housefulofhandmade.com/how-to-build-corner-cabinets/)
- Hardware: Lazy Susan bifold door sets use **two distinct hinge types working together** — commonly cited
  angles are a "165° main hinge" (case-to-door-1) and a "135°" or "90° pie-cut" interlink hinge (door-1-to-door-2),
  so the pair folds nearly flat when opened. Several vendors sell drop-in replacement kits (Blum, Grass, Mepla,
  M&B compatible) explicitly for "pie cut corner cabinets," confirming this is a recognized, standardized
  hardware category across the industry, not a one-off DIY detail. [HBL 165°/135° hinge kit](https://www.amazon.com/HBL-Concealed-European-Adjustable-Cabinets/dp/B0FMJKP53X), [Burks 90° pie-cut hinge](https://www.amazon.com/Corner-Cabinet-Cabinets-Builders-Enthusiasts/dp/B07ZHQGXY8)
- Lazy-susan shelf assemblies mount to the *door* system in some designs (rotating with the door as it opens)
  — "Pie cut lazy susans attach to doors in corner cabinets, and when the door is opened, shelves pull smoothly
  out with the door" — meaning the door hardware and the shelf hardware are mechanically linked BOM items, not
  independent. Lazy susans come in five shape variants: Full-Circle, D-Shaped, Kidney-Shaped, Half-Moon, Pie-Cut.
  [Cabinet Parts — Pie Cut Lazy Susans](https://www.cabinetparts.com/c/organizers/kitchen-organizers/cabinet-lazy-susans/pie-cut-lazy-susans), [Rev-A-Shelf — Lazy Susans Info](https://rev-a-shelf.com/lazy-susans-info)

### 4.4 Blind panels and fillers

- Blind corner cabinets require a **blind panel** (a plain, non-door filler panel covering the blind section's
  face) plus, commonly, a separate **filler strip** between the blind cabinet and the return-wall run to allow
  door/drawer clearance to swing/open without hitting the perpendicular run. Conestoga's redesigned blind system
  is explicitly described as offering size customization with "dedicated right and left blind sections that are
  fully customizable in width, height, and depth" — i.e., manufacturers model the blind section as a
  configurable sub-assembly, not a fixed-width afterthought. [Cabinet Joint — Conestoga Corners the Market](https://www.cabinetjoint.com/2020/08/conestoga-corners-the-market/)
- Recommended pull-out/clearance dimensions (RTA vendor guidance, one representative source): pull the blind
  corner cabinet **a minimum of 9.5″** from the corner (occupying 36.5″ of wall run at a 36″ nominal cabinet, per
  that vendor's sizing) up to a maximum of 16″ pulled (43″ of wall run), to give door/drawer swing clearance
  against the perpendicular cabinet run. Cabinet pulled 3″ out from the wall for clearance is also cited.
  [RTA Cabinet Store — Blind Corner Base Cabinet](https://www.rtacabinetstore.com/blog/choosing-corner-base-cabinet-keystone-base-cabinet-layout/cbc/) — treat exact inches as vendor-specific, not universal; **ESTIMATE** that the underlying clearance
  *requirement* (adjacent door/drawer swing arc must clear the blind cabinet's front face) generalizes, but the
  specific 9.5″/16″/3″ figures are this one vendor's numbers.

### 4.5 Why diagonal-corner backs are often site-assembled

- **ESTIMATE** (not directly confirmed by a manufacturer statement in this research pass, but consistent with
  KD/shipping literature found): diagonal corner cabinet backs are frequently shipped loose / assembled on site
  because (a) the case is deep and the diagonal front makes the assembled box an awkward, non-stackable shape
  for palletizing — flat-packing the back panel separately lets the rest of the carcass nest/ship flatter;
  (b) many diagonal corner installations require field-scribing the case to out-of-square walls at the corner,
  which is easier before the back is permanently fixed; (c) knock-down / flat-pack construction generally
  exists specifically to reduce shipping volume — "the flat-packed nature of knock-down cabinets results in
  lower shipping costs by minimizing the volume and weight of individual components compared to traditional
  cabinets" — and the diagonal corner is the single highest-volume-per-cabinet SKU in a typical run, making it
  the best candidate for KD shipping even on an otherwise pre-assembled cabinet line. [Casta Cabinetry — Knock-Down Cabinets](https://castacabinetry.com/post/what-are-knock-down-cabinets/)

### 4.6 Typical part list: blind base vs diagonal-susan base vs pie-cut

(Compiled from the construction-method sources above; treat as representative, not a single manufacturer's
literal cut list — marked **ESTIMATE** as a synthesis.)

**Blind corner base (rectangular footprint, e.g., 39"–45" wide, one usable door bay + blind extension):**
- 2× side panels (full depth/height)
- 1× blind filler/end panel (closes off the blind section's front face)
- 1× bottom/deck (interior width, full extended depth)
- 1–2× stretcher/top rail(s) (interior width)
- 1× back panel (full width × height, captured in dado or nailer-strip mounted)
- 1× face frame (if frame construction) or edgebanded front edges (if frameless)
- 1× door (sized to the usable bay only — NOT the full cabinet width)
- 1× filler strip (separate BOM line, shipped/installed between blind cabinet and adjoining run)
- Hardware: 2× concealed hinges, shelf-pin sets, adjustable shelf(ves), toe-kick, mounting screws/fasteners
- Optional: blind-corner pull-out mechanism hardware (if "full access" type) — a purchased mechanical
  sub-assembly BOM line, not a fabricated part

**Diagonal / pie-cut lazy-susan base (45° diagonal front, deeper case):**
- 2× angled side panels (or 1 pair of standard sides + 1 diagonal front nailer, depending on system)
- 1× diagonal front nailer/stretcher (defines the 45° opening width)
- 1× pentagonal/trapezoidal deck (bottom) — irregular-shape cut, nested on flat-table CNC or angle-fenced on
  panel saw
- 1× matching pentagonal/trapezoidal top/stretcher
- 1× back panel — commonly two back panels meeting at a corner seam (since the case itself is L-shaped/deep),
  or a single diagonal back depending on system; per §4.5, sometimes shipped loose for site assembly
- 2× bifold doors (sized/mitered to meet at the 45° opening)
- Hardware: bifold hinge set (case hinge + interlink hinge, 2 sets), lazy-susan shelf assembly (2 shelves,
  full-circle or pie-cut, with pole/pivot hardware), toe-kick, fasteners
- Note: the lazy-susan shelf hardware and door hardware may be a single linked BOM/hardware kit rather than
  independent lines, per §4.3

---

## 5. BOM Generation Patterns

- Standard commercial BOM-explosion model treats each cabinet as a parametric product whose BOM lines are
  themselves conditional: Microvellum's approach requires a `Quantity` field per BOM line driven by either a
  fixed *Value* formula or an *Attribute* formula (e.g., "1 per door," "2 per drawer"), and hardware/parts lines
  can be included or excluded based on attribute selection (e.g., door style = bifold triggers the bifold hinge
  hardware line; corner type = diagonal triggers the pentagonal deck part instead of the rectangular one).
  [RSM — Product Configurator Part 2: BOMs and Routes](https://technologyblog.rsmus.com/industry/manufacturing/product-configurator-part-2-boms-and-routes/)
- Routing operations follow the identical conditional-inclusion pattern as BOM lines — "Route operations will
  need a condition based on attribute selection to include the route operation within the Route" — meaning the
  routing (saw → edgeband → drill → assemble → pack) is not a fixed sequence template per cabinet type but a
  filtered subset of a master operation list, evaluated per instance. [RSM — Product Configurator Part 2](https://technologyblog.rsmus.com/industry/manufacturing/product-configurator-part-2-boms-and-routes/)
- Standard station sequence, synthesized from the saw/edgebander/CNC sourcing above: **Saw or Nest (rough/net
  cut) → Edgeband → Drill/Bore (point-to-point or CNC machining center) → Assemble → Pack/Ship.** Nested-based
  shops often collapse cut+drill into a single flat-table CNC pass for irregular parts, then still route through
  a separate edgebander (edgebanding a nested/routed part is typically a distinct downstream station since most
  shops do not have in-line nest+band capability). [Woodworking Network — Nesting vs Point-to-Point](https://www.woodworkingnetwork.com/magazine/nesting-vs-point-point), [Caelus — Panel Saw & Edge Bander](https://www.caelus-intel.com/article/how-do-panel-saw-and-edge-bander-work-together-in-cabinet-production.html)
- Integration with ERP: "Integration with ERP systems helps manage bill of materials and cut lists through
  purchasing, job costing, and scheduling" — confirming the CAD/CAM BOM is meant to flow directly into
  purchasing/MRP rather than being a design-only artifact. [Microvellum — Streamlined Manufacturing Processes](https://www.microvellum.com/solutions/processes/)

---

## 6. Assembly Sequence, Numbering, and Labeling

- Manufacturing barcode/label practice (general manufacturing, applied to cabinet shops): labels/tags are
  applied at the part level immediately after cutting, and scanning stations are placed "at key workflow
  points" — i.e., the part carries a barcode from the saw/nest station onward, and each subsequent station
  (edgebander, boring machine, assembly, packing) scans it to log routing progress. Encodings commonly use
  Code 128, Data Matrix, or QR codes for serial/product IDs. [Finale Inventory — Barcode System for Manufacturing](https://www.finaleinventory.com/guides/barcode-system-for-manufacturing/), [Cleverence — Manufacturing Product Barcodes](https://www.cleverence.com/articles/business-blogs/manufacturing-product-barcode-5267/)
- "Barcodes create an auditable trail showing which lot went into which assembly, who built it, when, under
  what revision, and where it shipped" — establishing barcode-per-part as the mechanism for panel-to-cabinet
  genealogy traceability in a production environment, matching the "panel genealogy" concept in this research's
  scope. [Lowry Solutions — Barcode Systems for Manufacturing](https://lowrysolutions.com/blog/barcode-systems-for-streamlined-manufacturing/)
- **ESTIMATE** (general cabinet-industry practice, not confirmed against a specific vendor doc in this pass):
  cabinet-level numbering plans (e.g., "Cabinet 14 of 32," keyed to an elevation/floor-plan drawing) are printed
  on a cabinet tag distinct from the per-part barcode; the part barcode resolves to (cabinet number, part role,
  material, operations-required list) so that an out-of-sequence part can be routed to the correct downstream
  station and reunited with its cabinet at assembly/pack.

---

## 7. Packaging and Shipping

- Two shipping models exist industry-wide: **assembled** (cabinet leaves the shop as a fully built box, doors
  hung) and **RTA/knock-down** (flat-packed, customer or installer assembles). Knock-down "results in lower
  shipping costs by minimizing the volume and weight of individual components compared to traditional cabinets."
  [Casta Cabinetry — What are Knock-Down Cabinets?](https://castacabinetry.com/post/what-are-knock-down-cabinets/)
- Corner cabinets (both blind and diagonal) are disproportionately large/deep relative to their linear wall
  footage — diagonal corners in particular are described as "deeper than the standard 12″" wall-cabinet depth
  to reach the true corner — which means they consume more truck/pallet volume per unit than a standard run
  cabinet. [RTA Cabinets House — Corner Cabinet Dimensions](https://rtacabinetshouse.com/blogs/cabinet-sizes-measurements/corner-kitchen-cabinet-dimensions)
- **ESTIMATE**: this volume penalty is the practical driver for §4.5 (site-assembly of diagonal-corner backs) —
  shipping a corner cabinet flat-packed (back, sides, deck, doors separated) is proportionally more valuable
  for freight-cost reduction on this SKU than on a standard rectangular base cabinet, because the assembled
  corner unit's bounding box is so much larger than its flat-packed footprint.

---

## 8. Tolerances

- Panel-saw squareness in production shops: contributors in a WoodWeb discussion reported "routinely measur[ing]
  large panels out of square 1/32″ to a light 1/16″" off a high-end beam saw (Striebig); one shop's internal
  standard was **1/32″ not considered a very good tolerance**, demanding **1/64″ or better**; a lower-cost
  ($2,000-class) panel saw was reported achieving better than 1/32″. [WoodWeb — CNC Versus Panel Saw Accuracy](https://woodweb.com/knowledge_base/CNC_Versus_Panel_Saw_Accuracy.html)
- CNC positional accuracy (general CNC router class, not cabinet-specific but cited in the same accuracy
  discussion): "even relatively low cost production CNC machines have ±11 micron positional accuracy at feed
  rates up to 1000 mm/min, with ±2.5 micron repeatability possible at slower feed rates" — several orders of
  magnitude tighter than the 1/32″–1/64″ (≈ 400–800 micron) figures reported for panel saws, consistent with
  CNC being preferred for parts (like diagonal corner decks) needing angled or repeatable irregular cuts.
  [WoodWeb — CNC Versus Panel Saw Accuracy](https://woodweb.com/knowledge_base/CNC_Versus_Panel_Saw_Accuracy.html)
- Sheet-stock internal stress relief: one contributor noted plywood stress relief after cutting can produce
  gaps "as much as .25mm" when two freshly cut edges are butted together — a real-world caveat that nominal
  cut tolerance and as-assembled joint gap are not the same thing. [WoodWeb — CNC Versus Panel Saw Accuracy](https://woodweb.com/knowledge_base/CNC_Versus_Panel_Saw_Accuracy.html)
- KCMA A161.1 structural test relevant to tolerance/quality claims (not a dimensional cutting tolerance, but a
  performance tolerance): shelves and cabinet bottoms are load-tested at **15 lb/ft² for 7 days**, checked for
  excessive deflection and joint separation/failure, as part of ANSI/KCMA A161.1 certification. [Woodworking Network — ANSI/KCMA A161.1](https://www.woodworkingnetwork.com/cabinets/strength-behind-certified-cabinetry-ansikcma-a1611)
- **ESTIMATE**: no primary-source numeric value was found in this research pass for standard edgeband thickness
  compensation/trim allowance (i.e., how much oversize the raw substrate is left before banding, then trimmed
  flush). Industry-typical edgeband tape gauges are commonly 0.4 mm–3 mm (PVC/ABS), but this figure was not
  independently confirmed against a manufacturer spec in this pass and should be re-verified before being used
  as a hard constant in part-size formulas.

---

## Worked Example: Part List + Operations

### Blind-corner base cabinet (42″ nominal, blind-on-right, frameless/32mm construction)

| # | Part | Material role | Key operations |
|---|---|---|---|
| 1 | Left side panel | 3/4″ panel stock | Cut to height×depth; 32mm-system line-boring (construction + shelf-pin holes, 37mm setback); confirmat/dowel holes at top/bottom joints; edgeband front (exposed) edge only |
| 2 | Right side panel (blind side, against wall) | 3/4″ panel stock | Cut to height×depth; system holes; no edgebanding needed (concealed against adjoining cabinet) |
| 3 | Bottom/deck | 3/4″ panel stock | Cut to interior width × full depth; dado/confirmat joint prep at both ends; no edgebanding (concealed) |
| 4 | Top stretcher(s) | 3/4″ panel stock | Cut to interior width; joint prep at both ends |
| 5 | Back panel | 1/4″ panel stock | Cut to full width × height; captured in dado (or nailer-strip mount); no edgebanding |
| 6 | Blind filler/end panel | 3/4″ panel stock, matched finish | Cut to closure size; edgeband exposed edges; attached to right side, closing blind bay face |
| 7 | Door (usable bay only) | 3/4″ door slab or 5-piece assembly | Sized to usable opening width, NOT full cabinet width; edgeband all 4 edges (if slab); hinge-cup boring (35mm cup) + 2 mounting-screw holes on hinge stile |
| 8 | Filler strip (separate BOM line) | 3/4″ stock, matched finish | Cut to field width; edgebanded both long edges; shipped/installed between blind cabinet and adjoining run for door-swing clearance |
| — | Hardware | — | 2× concealed hinges; shelf-pin sets (per 32mm shelf-hole rows); 1+ adjustable shelf (edgebanded front edge); mounting screws/fasteners; (optional) blind-corner pull-out mechanism as a purchased sub-assembly |

Routing: Saw/nest (parts 1–6, 8) → Edgeband (exposed edges only, parts 1, 6, 8, shelf) → Drill/bore (system
holes on 1, 2; hinge cup on 7) → Assemble carcass (1+2+3+4+5) → Hang door (7) → Attach blind filler (6) →
Pack (filler strip 8 often packed/shipped as a separate loose item, not attached at the factory, since its
final trim width is frequently field-verified against actual wall/corner conditions — **ESTIMATE**).

### Diagonal (pie-cut) lazy-susan corner base cabinet

| # | Part | Material role | Key operations |
|---|---|---|---|
| 1 | Side panel A | 3/4″ panel stock | Cut to height × depth; system holes; edgeband exposed edge |
| 2 | Side panel B | 3/4″ panel stock | Cut to height × depth; system holes; edgeband exposed edge |
| 3 | Diagonal front nailer/stretcher | 3/4″ panel stock | Cut at 45°/defines the diagonal opening width; joint prep both ends |
| 4 | Pentagonal/trapezoidal deck (bottom) | 3/4″ panel stock | Irregular-shape cut (nested on flat-table CNC, or angle-fenced beam-saw pass); joint prep at case corners; no edgebanding (concealed) |
| 5 | Matching pentagonal/trapezoidal top/stretcher | 3/4″ panel stock | Same irregular cut as deck; joint prep |
| 6 | Back panel(s) — often two, meeting at internal corner seam | 1/4″ or 3/4″ panel stock | Cut to case backs; captured in dado/nailer; **frequently shipped loose for site assembly** rather than factory-installed (see §4.5) |
| 7 | Bifold door 1 | 3/4″ door slab | Mitered/angled edge to meet door 2 at 45°; edgeband all edges; case-side hinge boring (e.g., 165°) |
| 8 | Bifold door 2 | 3/4″ door slab | Mitered/angled edge to meet door 1; edgeband all edges; interlink hinge boring (e.g., 135°/90° pie-cut hinge) on the door-to-door edge |
| — | Lazy-susan shelf assembly | Purchased hardware kit (2 shelves + pole/pivot, pie-cut or full-circle) | Predrilled per hardware template; in some designs, mounted to and rotating with door 1 |
| — | Bifold hinge hardware | Purchased kit (case hinge + interlink hinge, 2 sets) | Linked BOM line with lazy-susan kit in some door-mounted-susan designs |
| — | Toe-kick, fasteners | — | Standard hardware lines |

Routing: Saw/angle-fence or Nest (parts 1–2, 4–5 irregular shapes; 3, 6 rectangular) → Edgeband (exposed edges
of 1, 2, 7, 8) → Drill/bore (system holes 1, 2; hinge boring 7, 8; lazy-susan mounting predrill) → Assemble
carcass (1+2+3+4+5, back 6 possibly deferred) → Hang bifold door pair (7+8, pre-linked via interlink hinge as
a sub-assembly before mounting to case) → Install lazy-susan shelf kit → Pack (case shipped with back(s) loose /
site-installed per §4.5 in many product lines — **ESTIMATE**, generalized rather than confirmed per-vendor).

---

## Sources

- [32 mm cabinetmaking system – Wikipedia](https://en.wikipedia.org/wiki/32_mm_cabinetmaking_system)
- [Condensed Euro32 Manual (Euro32Products)](https://euro32products.com/wp-content/uploads/2020/04/CondensedEuro32Manual.pdf)
- [Frameless carcass construction – WoodWeb](https://woodweb.com/knowledge_base/Frameless_carcass_construction.html)
- [Case construction practices – WoodWeb](https://woodweb.com/knowledge_base/Case_construction_practices.html)
- [CNC Versus Panel Saw Accuracy – WoodWeb](https://woodweb.com/knowledge_base/CNC_Versus_Panel_Saw_Accuracy.html)
- [Odd Cabinet Heights with 32mm System Hole Spacing – WoodWeb](https://woodweb.com/knowledge_base/Odd_Cabinet_Heights_with_32mm.html)
- [CABINET VISION | Hexagon — Compare S2M](https://www.cabinetvision.com/compares2m)
- [Cabinet Vision and the S2M Center — Craftsman Woodworks Engineering](https://craftsmanengineering.com/video/cabinet-vision-and-s2m-center)
- [Microvellum — Streamlined Manufacturing Processes](https://www.microvellum.com/solutions/processes/)
- [Microvellum — Custom Wood Product Engineering Software](https://www.microvellum.com/solutions/engineering)
- [RSM — Product Configurator Part 2: BOMs and Routes](https://technologyblog.rsmus.com/industry/manufacturing/product-configurator-part-2-boms-and-routes/)
- [HOMAG — Nesting](https://www.homag.com/en/topics/nesting)
- [HOMAG — woodWOP 9 CNC software brochure](https://www.homag.com/fileadmin/product/cnc/brochures/woodwop/CNC-Software-woodWOP-EN.pdf)
- [Woodworking Network — Nesting vs. Point-to-Point](https://www.woodworkingnetwork.com/magazine/nesting-vs-point-point)
- [Blue Elephant CNC — What Is Edge Banding Machine?](https://www.elephant-cnc.com/blog/what-is-edge-banding-machinethe-2026-complete-guide/)
- [Caelus — How Do Panel Saw and Edge Bander Work Together](https://www.caelus-intel.com/article/how-do-panel-saw-and-edge-bander-work-together-in-cabinet-production.html)
- [Pedicco — Edge Banding on Cabinets: A Comprehensive Guide](https://www.pedicco.com/news/Blogs/Edge-Banding-on-Cabinets--A-Comprehensive-Guide.html)
- [RTA Cabinet Store — Choosing a Corner Base Cabinet / Keystone Layout](https://www.rtacabinetstore.com/blog/choosing-corner-base-cabinet-keystone-base-cabinet-layout/cbc/)
- [RTA Cabinets House — Corner Kitchen Cabinet Dimensions](https://rtacabinetshouse.com/blogs/cabinet-sizes-measurements/corner-kitchen-cabinet-dimensions)
- [Cabinet Joint — Base Corner Pie Cut Lazy Susan Cabinet Assembly (BCP) video](https://www.cabinetjoint.com/video-library/base-corner-pie-cut-lazy-susan-cabinet-assembly-bcp/)
- [Cabinet Joint — Conestoga "Corners" the Market](https://www.cabinetjoint.com/2020/08/conestoga-corners-the-market/)
- [Conestoga Wood Specialties — Blind Corner System](https://www.conestogawood.com/product/blind-corner-system/)
- [Cabinotch — The Full Access "Blind Corner" Cabinet](https://cabinotch.info/the-cabinotch-full-access-blind-corner-cabinet/)
- [Houseful of Handmade — How to Build Corner Cabinets](https://housefulofhandmade.com/how-to-build-corner-cabinets/)
- [Ana White — 36″ Corner Base Pie Cut Kitchen Cabinet Plans](https://www.ana-white.com/woodworking-projects/36-corner-base-pie-cut-kitchen-cabinet-momplex-white-kitchen)
- [Rev-A-Shelf — Lazy Susans Info](https://rev-a-shelf.com/lazy-susans-info)
- [CabinetParts.com — Pie Cut Lazy Susans](https://www.cabinetparts.com/c/organizers/kitchen-organizers/cabinet-lazy-susans/pie-cut-lazy-susans)
- [HBL 165°/135° Soft Close Cabinet Hinges for Lazy Susan Bifold Doors (Amazon product listing)](https://www.amazon.com/HBL-Concealed-European-Adjustable-Cabinets/dp/B0FMJKP53X)
- [Burks 90° Pie Cut Bifold Cabinet Door Hinge (Amazon product listing)](https://www.amazon.com/Corner-Cabinet-Cabinets-Builders-Enthusiasts/dp/B07ZHQGXY8)
- [Casta Cabinetry — What Are Knock-Down Cabinets?](https://castacabinetry.com/post/what-are-knock-down-cabinets/)
- [Woodworking Network — The Strength Behind Certified Cabinetry: ANSI/KCMA A161.1](https://www.woodworkingnetwork.com/cabinets/strength-behind-certified-cabinetry-ansikcma-a1611)
- [KCMA — Cabinets Certified to Last](https://kcma.org/insights/cabinets-certified-last-0)

---

```json
[
  {
    "fact_id": "system-hole-pitch-32mm",
    "domain": "32mm",
    "statement": "32mm-system vertical hole rows use a 32mm center-to-center pitch, 5mm hole diameter, 12-14mm hole depth.",
    "numeric_value": "32 mm pitch, 5 mm dia, 12-14 mm depth",
    "applies_to": ["all"],
    "source_url": "https://en.wikipedia.org/wiki/32_mm_cabinetmaking_system",
    "confidence": "high"
  },
  {
    "fact_id": "system-hole-front-setback-37mm",
    "domain": "32mm",
    "statement": "The first row of 32mm-system holes is set back 37mm from the front edge of the panel.",
    "numeric_value": "37 mm",
    "applies_to": ["all"],
    "source_url": "https://en.wikipedia.org/wiki/32_mm_cabinetmaking_system",
    "confidence": "high"
  },
  {
    "fact_id": "shelf-pin-length-flange",
    "domain": "32mm",
    "statement": "Shelf pins used in the 32mm system are 15-16mm long with a flange diameter of approximately 7mm.",
    "numeric_value": "15-16 mm length, 7 mm flange dia",
    "applies_to": ["all"],
    "source_url": "https://en.wikipedia.org/wiki/32_mm_cabinetmaking_system",
    "confidence": "medium"
  },
  {
    "fact_id": "confirmat-screw-spacing",
    "domain": "32mm",
    "statement": "AWI standard confirmat/European assembly screw spacing is 37mm from the panel end and 128mm on centers (128 = 4x32mm grid).",
    "numeric_value": "37 mm from end, 128 mm on center",
    "applies_to": ["all"],
    "source_url": "https://woodweb.com/knowledge_base/Frameless_carcass_construction.html",
    "confidence": "medium"
  },
  {
    "fact_id": "frameless-top-bottom-sized-to-interior-width",
    "domain": "panel-genealogy",
    "statement": "In frameless/dowel-KD construction, top and bottom (stretcher) parts are cut to the interior case width (between the two side panels), not the overall cabinet width, unlike face-frame construction.",
    "numeric_value": null,
    "applies_to": ["blind-corner-base", "diagonal-corner-base", "all"],
    "source_url": "https://woodweb.com/knowledge_base/Frameless_carcass_construction.html",
    "confidence": "medium"
  },
  {
    "fact_id": "back-panel-dado-vs-rabbet",
    "domain": "assembly",
    "statement": "Cabinet backs are captured in a dado in the bottom and sides for full squareness/strength, or in a rabbet for faster but weaker assembly, or via 1/4in back plus 3/4in nailer strips for KD-friendly construction.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://woodweb.com/knowledge_base/Frameless_carcass_construction.html",
    "confidence": "medium"
  },
  {
    "fact_id": "edgebander-process-sequence",
    "domain": "machining",
    "statement": "Standard automatic edgebander process sequence: Feeding -> Pre-milling -> Gluing -> Pressing -> End Trimming -> Top/Bottom Trimming -> Scraping -> Buffing.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://www.elephant-cnc.com/blog/what-is-edge-banding-machinethe-2026-complete-guide/",
    "confidence": "medium"
  },
  {
    "fact_id": "edgebanding-exposed-edges-only",
    "domain": "machining",
    "statement": "Edgebanding is applied to visible/exposed edges (doors, drawer fronts, shelves, exposed end panels); interior edges captured in joints or hidden against a wall are typically left unbanded.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://www.pedicco.com/news/Blogs/Edge-Banding-on-Cabinets--A-Comprehensive-Guide.html",
    "confidence": "medium"
  },
  {
    "fact_id": "cabinetvision-banding-in-part-size-toggle",
    "domain": "panel-genealogy",
    "statement": "Cabinet Vision Solid/S2M has an 'Include Banding in Overall Part Size' setting controlling whether reported part dimensions in cut lists and CNC/NC output include edgeband thickness, materially affecting cut-list and CNC output values.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://www.cabinetvision.com/compares2m",
    "confidence": "high"
  },
  {
    "fact_id": "cabinetvision-door-slab-vs-assembly-operations",
    "domain": "panel-genealogy",
    "statement": "Cabinet Vision Solid/S2M has an 'Incorporate Door Assembly Operations on Slab Door Part for CNC' setting that determines whether door hardware machining (e.g., hinge boring) is recorded against the raw door slab part or the finished door assembly.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://www.cabinetvision.com/compares2m",
    "confidence": "high"
  },
  {
    "fact_id": "microvellum-bom-quantity-formula-driven",
    "domain": "bom",
    "statement": "Microvellum BOM lines require a Quantity field driven by a Value formula or an Attribute formula, and BOM line/route-operation inclusion itself can be conditionally gated on product attribute selections.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://technologyblog.rsmus.com/industry/manufacturing/product-configurator-part-2-boms-and-routes/",
    "confidence": "medium"
  },
  {
    "fact_id": "microvellum-route-operations-conditional",
    "domain": "bom",
    "statement": "Microvellum routing (Route) operations follow the same conditional-inclusion pattern as BOM lines: an operation is included in a cabinet instance's route only when a condition based on attribute selection is met.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://technologyblog.rsmus.com/industry/manufacturing/product-configurator-part-2-boms-and-routes/",
    "confidence": "medium"
  },
  {
    "fact_id": "standard-routing-station-sequence",
    "domain": "bom",
    "statement": "Standard cabinet-part routing sequence is Saw/Nest (rough or net cut) -> Edgeband -> Drill/Bore -> Assemble -> Pack/Ship, with nested-based (flat-table CNC) shops often combining cut+drill into one pass for irregular parts.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://www.woodworkingnetwork.com/magazine/nesting-vs-point-point",
    "confidence": "medium"
  },
  {
    "fact_id": "nesting-preferred-for-irregular-parts",
    "domain": "machining",
    "statement": "Nested-based manufacturing (flat-table CNC router with nesting software) is the preferred production method for non-rectangular parts (e.g., diagonal/pie-cut corner cabinet decks), since a single toolpath cuts an irregular polygon without the fence resets a panel saw would need.",
    "numeric_value": null,
    "applies_to": ["diagonal-corner-base"],
    "source_url": "https://www.woodworkingnetwork.com/magazine/nesting-vs-point-point",
    "confidence": "medium"
  },
  {
    "fact_id": "diagonal-corner-two-bifold-doors-required",
    "domain": "assembly",
    "statement": "A diagonal/pie-cut lazy-susan corner cabinet requires a pair of bifold doors rather than a single door, because one door cannot swing clear of a 45-degree corner opening.",
    "numeric_value": null,
    "applies_to": ["diagonal-corner-base"],
    "source_url": "https://housefulofhandmade.com/how-to-build-corner-cabinets/",
    "confidence": "medium"
  },
  {
    "fact_id": "bifold-hinge-two-angle-types",
    "domain": "assembly",
    "statement": "Lazy-susan bifold door hardware uses two distinct hinge types: a case-to-door hinge (commonly ~165 degrees) and a door-to-door interlink hinge (commonly ~135 or ~90 degree pie-cut), sold as standardized replacement kits compatible with Blum/Grass/Mepla/M&B.",
    "numeric_value": "165 deg case hinge / 135 or 90 deg interlink",
    "applies_to": ["diagonal-corner-base"],
    "source_url": "https://www.amazon.com/HBL-Concealed-European-Adjustable-Cabinets/dp/B0FMJKP53X",
    "confidence": "low"
  },
  {
    "fact_id": "lazy-susan-shelf-linked-to-door",
    "domain": "bom",
    "statement": "In some pie-cut lazy-susan designs, the rotating shelf assembly mounts to and rotates with the door, making the shelf hardware and door hinge hardware a mechanically linked BOM/hardware kit rather than independent components.",
    "numeric_value": null,
    "applies_to": ["diagonal-corner-base"],
    "source_url": "https://www.cabinetparts.com/c/organizers/kitchen-organizers/cabinet-lazy-susans/pie-cut-lazy-susans",
    "confidence": "low"
  },
  {
    "fact_id": "lazy-susan-shape-variants",
    "domain": "bom",
    "statement": "Lazy-susan shelf hardware is available in five shape variants: Full-Circle, D-Shaped, Kidney-Shaped, Half-Moon, and Pie-Cut.",
    "numeric_value": null,
    "applies_to": ["diagonal-corner-base"],
    "source_url": "https://rev-a-shelf.com/lazy-susans-info",
    "confidence": "medium"
  },
  {
    "fact_id": "blind-corner-door-sized-to-usable-bay",
    "domain": "panel-genealogy",
    "statement": "A blind corner base cabinet's door is sized to the usable (non-blind) bay opening only, not the full cabinet width; the blind section is closed off by a separate blind filler/end panel.",
    "numeric_value": null,
    "applies_to": ["blind-corner-base"],
    "source_url": "https://www.cabinetjoint.com/2020/08/conestoga-corners-the-market/",
    "confidence": "medium"
  },
  {
    "fact_id": "blind-corner-filler-strip-separate-bom-line",
    "domain": "bom",
    "statement": "Blind corner base cabinet installations commonly require a separate filler strip (distinct BOM line) between the blind cabinet and the adjoining perpendicular cabinet run, to provide door/drawer swing clearance.",
    "numeric_value": null,
    "applies_to": ["blind-corner-base"],
    "source_url": "https://www.rtacabinetstore.com/blog/choosing-corner-base-cabinet-keystone-base-cabinet-layout/cbc/",
    "confidence": "medium"
  },
  {
    "fact_id": "blind-corner-pull-clearance-example",
    "domain": "assembly",
    "statement": "One RTA vendor's guidance: pull a blind corner base cabinet a minimum of 9.5in from the corner (up to a maximum of 16in) and 3in out from the wall, for door/drawer swing clearance against the adjoining run.",
    "numeric_value": "9.5 in min / 16 in max pull; 3 in off wall",
    "applies_to": ["blind-corner-base"],
    "source_url": "https://www.rtacabinetstore.com/blog/choosing-corner-base-cabinet-keystone-base-cabinet-layout/cbc/",
    "confidence": "low"
  },
  {
    "fact_id": "diagonal-corner-back-often-site-assembled",
    "domain": "assembly",
    "statement": "Diagonal-corner cabinet back panels are frequently shipped loose/site-assembled rather than factory-installed, likely due to the case's disproportionate shipping volume and the need to field-scribe to out-of-square corner walls.",
    "numeric_value": null,
    "applies_to": ["diagonal-corner-base"],
    "source_url": "https://castacabinetry.com/post/what-are-knock-down-cabinets/",
    "confidence": "low"
  },
  {
    "fact_id": "knock-down-shipping-reduces-volume",
    "domain": "packaging",
    "statement": "Knock-down (flat-pack) cabinet shipping reduces shipping cost by minimizing the volume and weight of individual components compared to fully assembled cabinets.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://castacabinetry.com/post/what-are-knock-down-cabinets/",
    "confidence": "medium"
  },
  {
    "fact_id": "diagonal-corner-deeper-than-standard-run",
    "domain": "packaging",
    "statement": "Diagonal corner wall cabinets are deeper than the standard 12in wall cabinet depth in order to reach the true corner point, increasing per-unit shipping volume relative to standard run cabinets.",
    "numeric_value": ">12 in depth",
    "applies_to": ["diagonal-corner-base"],
    "source_url": "https://rtacabinetshouse.com/blogs/cabinet-sizes-measurements/corner-kitchen-cabinet-dimensions",
    "confidence": "medium"
  },
  {
    "fact_id": "panel-saw-squareness-tolerance",
    "domain": "tolerance",
    "statement": "Production panel saws (beam saws) are reported achieving squareness of 1/32in to 1/16in on large panels in normal shop use; well-maintained shops target 1/64in or better.",
    "numeric_value": "1/32 in to 1/16 in typical; 1/64 in target",
    "applies_to": ["all"],
    "source_url": "https://woodweb.com/knowledge_base/CNC_Versus_Panel_Saw_Accuracy.html",
    "confidence": "low"
  },
  {
    "fact_id": "cnc-positional-accuracy",
    "domain": "tolerance",
    "statement": "Low-cost production CNC routers achieve approximately +/-11 micron positional accuracy at feed rates up to 1000mm/min, with +/-2.5 micron repeatability achievable at slower feed rates -- substantially tighter than typical panel-saw squareness figures.",
    "numeric_value": "+/-11 micron (fast feed); +/-2.5 micron (slow feed)",
    "applies_to": ["all"],
    "source_url": "https://woodweb.com/knowledge_base/CNC_Versus_Panel_Saw_Accuracy.html",
    "confidence": "low"
  },
  {
    "fact_id": "plywood-stress-relief-gap",
    "domain": "tolerance",
    "statement": "Plywood internal stress relief after cutting can produce joint gaps of up to approximately 0.25mm when two freshly cut edges are butted together, independent of nominal cutting tolerance.",
    "numeric_value": "up to 0.25 mm",
    "applies_to": ["all"],
    "source_url": "https://woodweb.com/knowledge_base/CNC_Versus_Panel_Saw_Accuracy.html",
    "confidence": "low"
  },
  {
    "fact_id": "kcma-a161-shelf-load-test",
    "domain": "tolerance",
    "statement": "ANSI/KCMA A161.1 certification load-tests cabinet shelves and bottoms at 15 lb/sq ft for 7 days, checking for excessive deflection and joint separation/failure.",
    "numeric_value": "15 lb/ft^2 for 7 days",
    "applies_to": ["all"],
    "source_url": "https://www.woodworkingnetwork.com/cabinets/strength-behind-certified-cabinetry-ansikcma-a1611",
    "confidence": "medium"
  },
  {
    "fact_id": "edgeband-thickness-compensation-unverified",
    "domain": "tolerance",
    "statement": "No primary-source numeric value was found for standard edgeband thickness compensation/trim allowance in panel cutting; commonly cited PVC/ABS tape gauges are 0.4mm-3mm but this was not confirmed against a manufacturer spec.",
    "numeric_value": "0.4-3 mm (unverified)",
    "applies_to": ["all"],
    "source_url": "https://www.elephant-cnc.com/blog/what-is-edge-banding-machinethe-2026-complete-guide/",
    "confidence": "low"
  },
  {
    "fact_id": "part-barcode-per-station-tracking",
    "domain": "assembly",
    "statement": "Manufacturing barcode practice applies a label/tag at the part level after cutting, with scanning stations at each downstream workflow point (edgeband, boring, assembly, packing) to log routing progress and provide auditable genealogy.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://www.finaleinventory.com/guides/barcode-system-for-manufacturing/",
    "confidence": "medium"
  },
  {
    "fact_id": "erp-bom-integration",
    "domain": "bom",
    "statement": "Cabinet CAD/CAM BOMs and cut lists are designed to integrate directly with ERP systems for purchasing, job costing, and scheduling, rather than remaining design-only artifacts.",
    "numeric_value": null,
    "applies_to": ["all"],
    "source_url": "https://www.microvellum.com/solutions/processes/",
    "confidence": "medium"
  }
]
```
