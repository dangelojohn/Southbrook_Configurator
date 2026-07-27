# Corner Hardware Engineering — Mechanism Envelopes

Research pass on corner-cabinet hardware: hinge opening angles, motion envelopes
(swing radius / extraction depth / lateral sweep), minimum cabinet sizes, weight
ratings, and adjacent-cabinet clearance rules. Every dimensioned fact below is
cited to its source URL. Where a manufacturer's public materials did not yield a
number, the field is marked `null` in the JSON and the gap is called out in
prose — nothing below is fabricated.

Unit convention: source units are quoted as published (mm or in). Converted
equivalents are added in parentheses only where the source didn't already give
both.

---

## 1. Blum CLIP top / CLIP top BLUMOTION hinge family (opening-angle envelopes)

Blum's standard concealed-hinge line is the backbone of every corner-adjacent
door because the **opening angle determines how far a door swings before it
clears a lazy-susan post, an adjoining drawer bank, or a pie-cut neighbor
door**. Key angle SKUs relevant to corner work:

- **170° CLIP top** (`71T6550` screw-on / `71T6540B` INSERTA, straight-arm;
  `71T6650`/`71T6640B` half-cranked): full dimensioned tables (H = plate
  height, P = door protrusion, S = side-arm protrusion, T = door thickness)
  for overlay, partial/twin-overlay, and reveal applications. **Inset is not
  possible with the 170° hinge** (needs the separate inset face-frame
  adapter, itself incompatible at 170°). A **130° angle-restriction clip
  (70.6103)**, black nylon, tool-free, snaps onto the hinge arm and mechanically
  caps the swing at 130° — this is the standard fix when a 170° door would
  otherwise strike an adjacent pull-out or door handle at full swing.
  Source: [Blum 2012 catalogue, CLIP top 170° hinges, pp.18–19](https://www.wwhardware.com/media/installation/170_hinge_applications.pdf).
- **Mitered-corner door application** (two doors meeting at a mitered/45°
  corner joint, half-cranked hinge, H=3 plate): **max. protrusion 78 mm**
  at full 170° swing, trial-application recommended; with the 70.6103 clip
  fitted the swing is held to 130°, cutting the protrusion envelope
  accordingly. **Thick-door twin application** (two adjoining cranked
  hinges back to back): max. protrusion 65 mm at H=0, minimum reveal table
  ranges 0–21 mm depending on door thickness T=22–32 mm. **Lip-door
  application**: max. protrusion 74 mm at H=3. All three "special
  applications" carry Blum's own "trial application recommended" caveat —
  i.e. Blum does not warrant these as drop-in without a physical mockup.
  Source: [Blum 2012 catalogue, Special applications, p.19](https://www.wwhardware.com/media/installation/170_hinge_applications.pdf).
- **95° blind-corner hinge** (inset app., 95°/83° dual-angle SKU `DQDK7Y`;
  overlay app. `DQDKXA`): reduced-angle hinge specifically for the door
  immediately adjacent to a blind-corner cabinet, so the door doesn't
  need to swing past the point where it would hit the corner filler or
  the neighboring cabinet. Source: [Blum catalogue 2022/23, hinge index p.72](https://publications.blum.com/2022/catalogue/en/72/); confirmed product listing [79T9550 — 95° CLIP top, blind corner, inset](https://www.barkerdoor.com/79T9550-Blum-CLIP-TOP-95-degrees-BLIND-CORNER-p/79t9550.htm).
- **+45° diagonal hinge** (95° opening, e.g. `79B9698` BLUMOTION INSERTA):
  used on the single diagonal (pie-cut) door of a corner base cabinet,
  "for corner cabinets with doors set back." Source: [Barkerdoor 79t5550 listing](https://www.barkerdoor.com/Blum-CLIP-TOP-45-degrees-angled-hinge-p/79t5550.htm); [Woodworkerexpress 79B9698 listing](https://www.woodworkerexpress.com/blum-95deg-clip-top-blumotion-hinge-45-diagonal-inserta.html).
- **Corner-cabinet bi-fold hinge, 60°** (`DQDQJY`, replaces legacy
  79.815/79.850): the hinge that joins the **two bi-fold doors together**
  at their shared vertical edge on a pie-cut lazy-susan corner cabinet.
  **Front thickness FD 15–23 mm, factory-set for 19 mm.** Explicitly
  "for use in combination with a 155° or 170° hinge" — that second,
  full-swing hinge attaches the outer bi-fold leaf to the cabinet frame.
  The 60° limit on the bi-fold joint is deliberate: it "lets the door
  easily clear any adjoining cabinet obstructions before it completely
  opens" — i.e. it is the mechanism's built-in adjacent-clearance answer.
  3-D adjustment, tool-free door-to-cabinet removal. Screw-on and
  knock-in-boss variants, nickel or onyx black.
  Source: [Blum catalogue 2024/25, p.116 (corner cabinet bi-fold hinge)](https://publications.blum.com/2024/catalogue/en/116/); [HardwareSource Pie Cut Corner Hinge listing](https://www.hardwaresource.com/products/blum-pie-cut-corner-hinge) (35 mm cup, 45 mm screw spacing, "hinge only — mounting plate 652304 sold separately," "will not replace other brands").
- **Weight rating**: Blum's general CLIP top guidance caps doors around
  **22 kg (≈48 lb)** per hinge pair for standard SKUs, with heavier-door
  variants (125° "thick door" hinge) rated for doors up to 32 mm thick;
  published community/reseller sources cite an 8–26 kg range depending on
  angle/model — **ESTIMATE (basis: Blum EASY ASSEMBLY blog + reseller
  guidance, not a single authoritative table)**.
  Source: [Blum EASY ASSEMBLY — number of hinges](https://ea.blum.com/en/number-of-hinges/); [Blum UK KIT Shop — Which hinge?](https://blumkit.co.uk/blogs/technical-blog/which-hinge).

**Engineering takeaway for the placement engine:** a corner base cabinet
with bi-fold doors needs *two* hinge families modeled together — the 60°
bi-fold joint (door-to-door) and a 155°/170° door-to-frame hinge on the
outboard leaf — and the outboard leaf's swing (up to 170°, capped to 130°
with the restriction clip) is what actually determines the lateral
clearance envelope against the neighboring cabinet run.

---

## 2. Blum SPACE CORNER (drawer-based blind-corner base cabinet system)

SPACE CORNER replaces the door-and-pullout blind-corner approach entirely:
the *corner itself* is a full-extension L-shaped TANDEMBOX/TANDEM drawer
that pulls straight out, bringing the dead corner contents to the user —
no swing-out arm, no lazy susan.

- **Compatible cabinet type:** blind-corner base cabinet, corner sizes
  **36", 39", or 42"** (nominal footprint of the two intersecting runs).
  Recommended overall corner-cabinet-size window **900–1200 mm**.
  Source: [SPACE CORNER installation sheet, p.36 (2012)](https://www.wwhardware.com/media/installation/b568corner.pdf); [Blum SPACE CORNER overview (AU)](https://www.blum.com/au/en/products/cabinet-applications/space-corner/overview/).
- **Motion envelope (extraction):** full-extension drawer — for the 39"
  corner cabinet the drawer box measures **443 mm (17-7/16") or 435 mm
  (17-1/8")** wide (depending on 5/8" vs 3/4" drawer-side material) by
  **670 mm (26-3/8") or 789 mm (31-1/8")** deep on the two legs, with a
  diagonal front opening of **475 mm (18-11/16")** and a **256 mm
  (10-1/16")** diagonal corner-cut dimension. Runner setback/length data
  (TANDEM plus BLUMOTION 568.6860B01 for 5/8" sides, 568A6860B01 for
  3/4" sides): setback A **108/117 mm**, B **114/123 mm**, C
  **141/150 mm**, D (runner length) **365/374 mm** to **493/502 mm**
  depending on drawer material. **Requires special (non-standard)
  cabinet and drawer construction** — Blum publishes dedicated
  construction drawings; this is not a drop-in retrofit into an ordinary
  blind-corner box. Minimum inside drawer width for the locking device is
  **121 mm (4-3/4")**, height-adjustable **±3 mm (1/8")**.
  Source: [SPACE CORNER installation sheet, pp.36–37](https://www.wwhardware.com/media/installation/b568corner.pdf).
- **Weight rating:** **dynamic load 110 lb (50 kg), static load 125 lb**
  per drawer (confirmed independently in the SPACE CORNER product memo:
  "50 kg, 650 mm" runner set). Source: [SPACE CORNER installation sheet p.36](https://www.wwhardware.com/media/installation/b568corner.pdf); [Blum SEA product memo](https://d2.blum.com/services/BEC003/mem016b-p_fl_dok_bsg_$sen-sg_$aof_$v1.pdf).
- **Door-attachment / front geometry:** "can be used with standard fronts
  — no special front assembly required." SPACE CORNER pairs with
  **SYNCROMOTION**, a linkage that lets a *standard* (non-diagonal) front
  swing inward slightly during opening so the drawer body can clear the
  corner geometry — i.e. the front-panel motion is not purely linear; it
  has a small rotational component that must be modeled if the placement
  engine treats fronts as rigid extrusions.
  Source: [Blum SPACE CORNER product memo](https://d2.blum.com/services/BEC003/mem016b-p_fl_dok_bsg_$sen-sg_$aof_$v1.pdf); [Blum SPACE CORNER overview](https://www.blum.com/au/en/products/cabinet-applications/space-corner/overview/).
- **Adjacent-cabinet restriction:** none published beyond standard full-
  extension clearance (drawer needs its full extension length clear in
  front of the cabinet — same as any full-extension drawer bank); no
  swing arc to collide with neighbors since there is no rotating arm.
  This is SPACE CORNER's main *advantage* over susan/swing-out systems
  from a clearance-engineering standpoint — **ESTIMATE (basis: absence of
  any swing/rotation component in the mechanism description)**.

---

## 3. Kessebohmer Magic Corner (Standard / "Magic Corner Two")

A swing-out steel-frame system mounted inside a **blind-corner cabinet
with bi-fold hinged doors** (the doors open first, then the frame swings
the shelves out into the room).

- **Cabinet fit:** outer cabinet footprint **500 × 900 mm or 500 × 1000 mm**
  (i.e. a 900 mm or 1000 mm blind-corner base run). **Door width 450–600
  mm** (17.7"–23.6"). **Minimum clear unit height: 525 mm (20.7").**
  Source: search-aggregated from PWS/East Coast Kitchens/Kesseböhmer
  listings — [PWS Magic Corner 900–1000mm product page](https://www.pws.co.uk/product/kmcuscr); [Kesseböhmer Spec & Price Guide 2017 (PWS)](https://uploads-ssl.webflow.com/5b911d408065b64c949a8505/5b911d408065b692889a874e_Kesse_Spec_Price_Guide_2017.pdf); [East Coast Kitchens 900/1000mm Magic Corner](https://eastcoastkitchens.co.uk/kitchen-storage-accessories/3618-kessebohmer-9001000mm-style-magic-corner-pull-out-storage.html).
- **Shelf dimensions/load:** front shelf **295 × 470 × 88 mm, 14 kg**
  (≈31 lb); back shelf **390 × 470 × 88 mm, 18 kg** (≈40 lb) — **ESTIMATE
  confidence-medium (basis: aggregated reseller spec text, not the
  Kesseböhmer factory datasheet directly)**.
- **Motion envelope:** the frame is bottom-mounted; opening the bi-fold
  doors first is a **hard precondition** — the shelves cannot swing out
  until both door leaves are clear, meaning the *door* opening angle
  (see the Blum 60° bi-fold hinge above, or Kesseböhmer's own bi-fold
  hardware) gates the whole mechanism's usable arc. No independent
  extraction-depth/lateral-sweep figures were found published for the
  frame swing itself.
- **Basic-model line ("Magic Corner Two"), handing:** sold as
  handed left/right frames requiring separate basket sets. Source:
  [CabinetParts.com — Magic Corner Two, blind right, frame only](https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54810241-p24385) *(page returned HTTP 403 on direct fetch; title/description only confirmed via search snippet)*.

**Gap:** Kesseböhmer's own CAD/engineering PDFs (behind a dealer portal)
were not reachable; the numbers above come from downstream reseller
listings, which is a real provenance weakness — flagged in the JSON as
`confidence: "medium"`.

---

## 4. Kessebohmer LeMans II (pull-out kidney-tray blind-corner system)

The most widely OEM'd blind-corner mechanism in North America — sold
directly by Kesseböhmer and rebadged by **Häfele** as "LeMans II"
(identical hardware, Häfele SKU prefix `541.xx`).

- **Cabinet fit / minimum opening by tray-size series** (each series
  differs only in kidney-tray radius, not mechanism geometry):
  - **Series 40** (two 12" trays): min. cabinet opening **14-1/4" W ×
    21-1/2" H**.
  - **Series 45** (two 15" trays): min. cabinet opening **16-1/2" W ×
    21" H**.
  - **Series 50** (two 18" trays): min. **face-frame** opening **17-3/4"
    W × 21-1/2" H**.
  - General face-frame minimum **16-1/8" W** / frameless minimum
    **16-1/2" W**; internal cabinet height minimum **21-1/2"** across
    the line.
  Source: [CabinetParts — LeMans II Series 40](https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132740-p24162); [CabinetParts — LeMans II Series 45](https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132745-p24164); [CabinetParts — LeMans II Series 50](https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132751-p24167) *(all three pages 403'd on direct re-fetch; numbers confirmed via search-result snippets and cross-checked against the Häfele-branded reseller pages below)*.
  - Häfele-branded confirmation: **minimum cabinet height 21-1/2",
    shelves height-adjustable every 2", door/drawer-door compatible
    (works with door-only or door+drawer fronts).**
    Source: [Häfele LeMans II product page](https://www.hafele.com/us/en/product/kesseboehmer-lemans-ii-set-for-blind-corner-cabinets/P-00856493/) *(via search snippet — direct fetch not attempted)*.
- **Required hinge/door opening angle:** **the LeMans II continues to
  function fully at door-opening angles down to 85°** — i.e. the door
  hinge does not need to reach full 90°+ swing for the pull-out to clear;
  this is the mechanism's designed tolerance for a door that gets
  partially blocked by a neighboring appliance or cabinet.
  Source: [search-aggregated Kesseböhmer/Häfele spec text, "85°" opening requirement](https://www.hafele.com/us/en/product/kesseboehmer-lemans-ii-set-for-blind-corner-cabinets/P-00856493/).
- **Weight rating:** **55 lb (25 kg) max per tray.**
- **Motion envelope:** two kidney-shaped shelves rotate out of the blind
  cavity on a pivoting post as the door opens; no published numeric
  swing-radius or lateral-sweep figure was found (only tray plan
  dimensions via the "12/15/18-inch tray" naming, which describes the
  tray's long-axis size, not the arc it sweeps) — **gap, marked null**.
- **Adjacent-cabinet restriction:** none explicitly published; general
  blind-corner design guidance (see §11 below) applies — a dishwasher or
  full-height appliance immediately next to the blind run needs a filler
  so its handle doesn't intersect the corner door's swing.

---

## 5. Kessebohmer Arena Classic / Arena Plus (lazy-susan tray hardware)

Not a full mechanism on its own — **Arena Classic/Style/Plus are the
shelf-and-railing hardware lines** that Kesseböhmer supplies into
pie-cut susan units (including the Hettich-branded carousels in §12–13,
which use "Arena STYLE"/"Arena CLASSIC" shelves under license/OEM).

- **Load rating:** **Arena Plus rated 55 lb/shelf**; melamine-coated wood
  shelves with a non-slip anti-slip coating, steel railing, height-
  adjustable, "360° view of shelving."
  Source: [WoodworkerExpress — Arena Classic Super Susan listings](https://www.woodworkerexpress.com/super-susan-arena-classic-32-2-shelf-kidney-lazy-susan-kit-w-attached-bearing-chrome-white-kessebohmer.html); [Kesseböhmer US — lazy susan storage solutions](https://www.kesseboehmer.us/kitchen/corner-cabinets/lazy-susan).
- **Cabinet fit:** typical kidney-shelf sets sized **28" or 32"**
  diameter for 33"/36" pie-cut corner cabinets.
- **Gap:** no independent motion-envelope (swing radius) figure beyond
  the shelf diameter itself was found for the Kesseböhmer-branded product
  page; the dimensioned swing drawings that *do* exist (Hettich's
  Carousel/Semi-circular Carousel installation sheets, §12–13) use these
  same Arena shelves and give the actual radius/clearance numbers — cross-
  referenced there.

---

## 6. Häfele-branded corner hardware (OEM note)

Häfele's catalog corner-cabinet line for the North American market is,
for the mechanisms checked, **the same Kesseböhmer engineering rebadged**
— "LeMans II," "Magic Corner" etc. appear under both brands with
identical dimensions (see §3–4; Häfele SKU `541.xx` = Kesseböhmer
`541.xx`). No Häfele-original corner mechanism (distinct geometry) was
found in this pass; Häfele's own **FunLine/FunFront** naming did not
resolve to a distinct corner product in search. This is recorded as a
**gap** rather than assumed absent — Häfele's German-market catalog may
carry additional in-house corner systems not indexed by English-language
retailers.
Source: [Häfele LeMans II listing](https://www.hafele.com/us/en/product/kesseboehmer-lemans-ii-set-for-blind-corner-cabinets/P-00856493/); [HäfeleHome AU — LeMans II](https://www.hafelehome.com.au/products/lemans-ii).

---

## 7. Rev-A-Shelf 5PSP series (wire blind-corner swing-out optimizer)

- **Cabinet fit / minimum opening:**
  - **5PSP-15 (15" model):** face-frame minimum cabinet opening
    **15" W × 20-1/4" D × 21" H**.
  - **5PSP-15SC (soft-close 15" model):** face-frame minimum
    **15" W × 21-21/32" D × 22" H**.
  - **5PSP-18 (18" model):** face-frame/frameless minimum
    **18" W × 21.66" D × 22" H**.
  Source: [CabinetParts — 5PSP-15-CR listing](https://www.cabinetparts.com/p/revashelf-organizers-kitchen-organizers-RV5PSP15CR-p38452) *(403'd on direct re-fetch; dimensions confirmed via search snippet)*; [Rev-A-Shelf 5PSP series page](https://rev-a-shelf.com/5psp-series).
- **Handing:** non-handed (fits either a left- or right-blind corner
  cabinet without a separate mirrored SKU) — per product naming
  ("Non-Handed Two-Tier Blind Corner Swing-Out Organizer").
- **Weight rating:** not found as a distinct 5PSP number in this pass;
  Richelieu's resale of the *related* Rev-A-Shelf two-tier round-wire
  blind-corner organizer lists **45 lb/shelf**, and the soft-close 150-lb
  full-extension-slide variant lists **27 lb/shelf (194 sq in shelf
  area)** — **ESTIMATE (basis: adjacent/similar Rev-A-Shelf SKU family
  sold through Richelieu, not the 5PSP datasheet itself)**.
  Source: [Richelieu — Rev-A-Shelf two-tier blind-corner organizer](https://www.richelieu.com/us/en/category/kitchen-and-bathroom-accessories/kitchen/corner-cabinet-storage-systems/base-corner-cabinet-storage-systems/blind-corner-shelves-ras/rev-shelf-two-tier-organizer-for-blind-corner-cabinet/1170331/sku-537221MPR); [Richelieu — blind-corner organizer w/ soft-close](https://www.richelieu.com/us/en/category/kitchen-and-bathroom-accessories/kitchen/corner-cabinet-storage-systems/base-corner-cabinet-storage-systems/blind-corner-solutions/blind-corner-organizer-with-soft-close/1205660/sku-53PSP18SCMP).
- **Motion envelope:** wire baskets swing out of the blind cavity on a
  pivot post, then the whole assembly extends toward the user — no
  published numeric swing-radius or lateral-sweep figure beyond the
  minimum-opening box; a wider blind-corner run gives more swing
  clearance but no manufacturer minimum-clearance-to-neighbor number was
  published — **gap, marked null**.

---

## 8. Rev-A-Shelf lazy susan lines (6000/32-series, Polymer, kidney)

- **6265 series** (D-shape, diagonal-corner, 5-shelf): **22" diameter,
  for 56"–62" inner cabinet height** range (i.e. tall pantry-style corner
  application, not a standard 34-1/2" base cabinet).
  Source: [CabinetParts — 6265-20-11-50 listing](https://www.cabinetparts.com/p/revashelf-organizers-kitchen-organizers-RV6265201150-p37645); [Rockler — 6265 series D-Shape 5-Shelf Corner Lazy Susans](https://www.rockler.com/d-shape-5-shelf-corner-lazy-susans-rev-a-shelf-6265-series).
- **6472 series** (kidney-shape, 2-shelf, wall/base corner): available
  **18", 24", 32" diameter**; the 32" model spec'd **for 26"–32" cabinet
  height** (wall-cabinet range).
  Source: [CabinetParts — 6472-32-11-52 listing](https://www.cabinetparts.com/p/revashelf-organizers-kitchen-organizers-RV647232-p38483).
- **6065 series** (full-circle, 5-shelf, polymer, pantry): **32"
  diameter**, telescoping shaft **adjustable 56"–62" inner cabinet
  height.**
  Source: [BedBathAndBeyond — 6065 series listing](https://www.bedbathandbeyond.com/Home-Garden/Rev-A-Shelf-6065-Series-32-Inch-Full-Circle-5-Shelf-Lazy-Susan/40340708/product.html).
- **Motion envelope:** full 360° (full-circle series) or ~270°
  (kidney/D-shape, which omit the pie slice that would otherwise
  protrude past the door swing) rotation in place — **no fixed
  extraction depth** (these are rotate-in-place, not pull-out,
  mechanisms) but the **diameter itself is the lateral-sweep number**:
  a 32" diameter shelf sweeps 16" from the corner post in every direction
  as it rotates, so the door opening must clear a 16"-radius arc at
  shelf height.
- **Gap:** no manufacturer weight-per-shelf figure was recovered for
  these specific series in this pass (Rev-A-Shelf's general "Lazy Susans
  Info" page is descriptive, not tabular); assume typical wire/polymer
  lazy-susan shelf ratings in the 25–40 lb range seen elsewhere in the
  line — **ESTIMATE (basis: adjacent Rev-A-Shelf/Richelieu SKUs, not
  confirmed for 6065/6265/6472 specifically)**.

---

## 9. Vauth-Sagel VS COR Flex (full-access blind-corner pull-out)

- **Variants by minimum cabinet opening width:**
  - **Saphir:** minimum cabinet opening **15"**.
  - **Planero:** minimum cabinet opening **17-1/2"**.
  - **Scalea:** sold as a "36-inch blind-corner pull-out," 4-basket.
  Source: [CabinetParts — VS COR FLEX Saphir, 15" min opening](https://www.cabinetparts.com/p/vauth-sagel-organizers-kitchen-organizers-VS90092000001-p125390); [CabinetParts — VS COR FLEX Planero, 17-1/2" min opening](https://www.cabinetparts.com/p/vauth-sagel-organizers-kitchen-organizers-VS90092000011-p125411); [WoodworkerExpress — COR Flex Scalea 36" listing](https://www.woodworkerexpress.com/cor-flex-scalea-full-access-36-blind-corner-pull-out-4-basket-carbon-steel-gray-Vauth-sagel.html).
- **Weight rating:** **max. 17 lb per shelf/basket** — a notably lower
  per-shelf rating than the Blum/Kesseböhmer/Rev-A-Shelf systems above;
  worth flagging for the placement engine's weight-budget logic if VS COR
  is offered as an option.
  Source: [Vauth-Sagel VS COR product-family page](https://vauth-sagel.com/gb/en/products/product-variants/vs-cor).
- **Mechanism:** frame mounted to the cabinet **floor** (not the sides),
  unhanded (works in either a left- or right-blind corner without a
  mirrored SKU), claims access to "100% of the cabinet."
- **VS COR Fold:** a second product line in the same family; no
  dimensioned data was recoverable in this pass beyond the marketing
  tagline ("turns a fold into kitchen gold") — **gap, marked null,
  confidence low.**
- **Gap:** extraction depth, swing radius, and required door angle were
  not found published for either VS COR Flex or VS COR Fold in the
  sources reached (Vauth-Sagel's technical planning PDFs sit behind a
  dealer/CAD portal not reachable via open web fetch).

---

## 10. Ninka Trigon (retrofit corner-basket fitting) & Qanto (vertical-rising corner unit)

- **Trigon:** retrofittable pull-out/revolving-shelf fitting for blind
  corners. **Load capacity up to 25 kg (55 lb) per shelf.** Tool-free
  removable/replaceable trays, stepless tool-free height adjustment,
  optional damped soft-close (retrofittable). Shelves made from
  100%-recycled milled material.
  Source: [Ninka TRIGON product page](https://www.ninka.com/en/TRIGON.html); [Gamma Fittings — Ninka TRIGON](https://gammafittings.co.uk/product/ninka-corner-system-trigon/).
- **Qanto:** a **vertically-rising** corner/island storage unit (distinct
  motion type — the whole basket assembly lifts up and out rather than
  swinging or extending horizontally), marketed for corner and island
  cabinets. No dimensioned minimum-cabinet or load-rating figure was
  recovered in this pass.
  Source: [Ninka Qanto product page](https://www.ninka.com/en/Qanto.html); [T&S Architectural — Ninka Qanto vertically-rising corner/island unit](https://www.tandsarchitectural.co.uk/corner-and-island-storage-unit-vertically-rising-ninka-qanto); [Häfele Home AU — Ninka Qanto-B Model 4](https://www.hafelehome.com.au/products/ninka-qanto-b-corner-unit-model-4).
- **Gap:** neither product's motion envelope (extraction depth / swing
  radius / vertical travel) or minimum cabinet dimensions were found
  published in openly reachable sources — Ninka's technical planning
  documents were not located. Marked null, confidence low.

---

## 11. Hettich CargoMan (pull-out shelves for corner cabinet)

- **Cabinet fit:** **minimum inside carcase depth 490 mm (19.3").**
  Works in odd or even numbers as individual single units (no handed
  pairing required); installs on the cabinet floor with no extra
  attachment hardware.
- **Load rating:** **20 kg/shelf (44 lb).**
- **Dimensioned envelope table** (X = cabinet width, X2 = shelf swing
  offset, Y = depth, Z = minimum internal cabinet height for one shelf
  layer), all in mm:

  | Cabinet width | X | X2 | Y | Z (min. height/layer) |
  |---|---|---|---|---|
  | 900 | 860 | 450 | 490 | 150 |
  | 1000 | 1000 | 500 | 490 | 150 |
  | 1000 | 1000 | 600 | 490 | 150 |

  Source: [Hettich Design Collection — Corner Solution / CargoMan, catalogue p.6](https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf).
- **Motion envelope:** each shelf **swivels out individually and
  completely** (not a linked assembly) — melaminated bottom shelves,
  non-slip surface, chrome-plated rail.

---

## 12. Hettich Moving Corner — "Cargo Series" & "Comfort" (swing-out + pull-out combined)

Two related SKU families, both for **blind-corner base cabinets**, combining
a swing-out arm with a telescoping pull-out basket:

- **Cargo Series:** for **900 mm and 1000 mm wide corner cabinets**.
  Integrated soft-close ("Silent System"), ClickFixx tool-free assembly,
  stainless-steel wire basket, chrome-plated, 10-year anti-rust warranty.
  **Dimensioned frame envelope:** width **516 mm**, plus **80 mm** offset,
  depth **520 mm / 525 mm**. **Installation dimensions:** cabinet inside
  width **860–968 mm**, depth **≥390 mm or ≥500 mm** (two drawing
  variants), pull-out reach **412–568 mm**, **470 mm** fixed offset,
  **295 mm** basket depth, **door width 450–600 mm**, and critically a
  **swing angle of ≤80°** marked on both installation drawings — i.e. the
  cabinet door needs to open to no more than ~80° for the mechanism to
  clear; a wider opening isn't required and isn't harmful either, but 80°
  is the drawn reference angle for the arm's clearance path.
  Source: [Hettich Design Collection — Moving Corner (Cargo Series), pp.8–9](https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf).
- **Moving Corner Comfort:** for **narrower corner units, 450–600 mm
  front width** (a single-leaf door corner, not the full 900/1000 mm
  blind run). Baskets at the back pull out individually; height-
  adjustable knob for ergonomic reach. **Inside width 862 mm, or
  945–971 mm depending on door width; depth 500 mm; height 545 mm.**
  **Dimensioned table (min. door width → min. dim A → min. inside
  carcase width, all mm):**

  | Min. door width | Min. dim A | Min. inside carcase width |
  |---|---|---|
  | 450 | 394 | 862 |
  | 500 | 444 | 862 |
  | 550 / 600 | 494 | 945 |

  Source: [Hettich Design Collection — Moving Corner Comfort, p.10](https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf).
- **Weight rating for both:** not separately tabulated in the source
  beyond the CargoMan 20 kg/shelf figure (§11) — **ESTIMATE (basis:
  same "Arena"-branded basket construction shared across the Hettich
  corner line)**.

---

## 13. Hettich Semi-circular Carousel & full Carousel (susan-style, dimensioned)

Two distinct rotating-shelf products with full manufacturer dimensioned
drawings — the best swing-radius data recovered in this research pass:

- **Semi-circular Carousel:** for corner base units, **carcase 900 mm or
  1000 mm.** **Installation height 730 mm (28.7").** Pivot arm cut-to-
  length on site; bearings secured to the corner post. Shelf options:
  Arena STYLE/CLASSIC melamine-coated wood (non-slip coating) or
  chrome-plated/powder-coated steel wire, both with steel railing.
  **Dimensioned drawing values (mm):** for the 900 mm cabinet — shelf
  radius reference **750**, min. cabinet depth **≥475**, offset **65**,
  edge clearance **27**, panel-thickness range **32–38**, min. door-side
  clearance **≥412**; for the 1000 mm cabinet — shelf radius reference
  **850**, min. depth **≥525**, same 65/27/32–38 offsets, min. clearance
  **≥462**. Interior frame depth **657–693 mm**.
  Source: [Hettich Design Collection — Semi-circular Carousel, p.12](https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf).
- **Full (three-quarter-circle) Carousel:** for corner base units,
  **carcase 800×800 mm or 900×900 mm.** **Variable installation height:
  center column adjustable 839–889 mm**, or field-cut shorter. Adjustable
  bearings for quick shelf-height changes. **Dimensioned drawing values
  (mm):** 900×900 cabinet — min. opening **≥860**, shelf swing reference
  **420**, pivot bore **⌀5**, angle markers **90°/80.2°** (the shelf's
  active rotation arc — i.e. the two-part revolving shelf doesn't
  complete a full 360° per shelf, it indexes through roughly 270–290°
  effectively per the two callouts), min. front clearance **≥510**, rear
  clearance **≤350**; 800×800 cabinet — min. opening **≥740**, swing
  reference **360**, min. front clearance **≥480**, rear **≤260**.
  Source: [Hettich Design Collection — Carousel, p.13](https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf).
- **Note on interpretation:** the 90°/80.2° angle pair is read directly
  off the manufacturer's dimensioned isometric but the drawing's exact
  geometric meaning (door-opening requirement vs. shelf-index angle) is
  not spelled out in accompanying prose — flagged as **confidence:
  medium** on the `required_hinge_angle_deg` field for this SKU rather
  than treated as a confirmed door-swing spec.

---

## 14. Hettich WingLine 170 (bi-fold door track for corner/tall pantry units)

Not a susan or pull-out — a **top-mounted bi-fold door track** used on
tall corner pantry units (2-panel folding door wrapping the corner),
directly comparable in function to the Blum 60°/170° bi-fold hinge pair
in §1 but implemented as a sliding/folding track rather than two hinges.

- **Cabinet fit:** for **1 folding door with 2 panels**; door height **up
  to 2200 mm (86.6")**; each door panel width **up to 300 mm (11.8")**.
  For wooden doors, or wood/aluminium-framed doors. Compatible with the
  soft-closing **Sensys** hinge.
- **Opening angle:** **up to 170°** overall fold, with the operating-
  principle drawing showing intermediate stop positions at **110°/125°**
  and a guide-bar throw of **430 mm**, carcase-inside-edge clearance
  **8.5 mm**, minimum edge distance **≥12 mm**, mounting hole **⌀10×12
  mm for "socket no. 33."**
  Source: [Hettich Design Collection — WingLine 170, pp.14–15](https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf).
- **Adjacent-clearance note:** because this is a full-height door
  (up to 2200 mm), the fold-back envelope runs the full height of the
  cabinet — any adjacent tall unit (fridge, wall oven column) needs
  clearance for the folded panel's full height and the 430 mm guide-bar
  throw, not just a base-cabinet-height arc.

---

## 15. Hettich Horizon Plus (parallel-swivel corner-door fitting)

A door-swivel fitting (not a pull-out) that **lifts the door horizontally
out of the flush front and swings it to the side**, so an open door can
sit flush in front of an *adjacent* cabinet segment instead of protruding
into the room at 90–170°. Explicitly usable "on single or double doors as
well as on corner units."

- **Door-attachment geometry:** operating-principle drawing gives
  **door thickness T = 16–26 mm** as the supported range, a lateral
  swing throw of **16–30 mm**, and a minimum edge clearance of **≥2 mm**.
  Source: [Hettich Design Collection — Horizon Plus, p.16](https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf).
- **Relevance to corner placement:** this is the mechanism family to
  reach for when the design goal is "corner door must not collide with
  the neighboring cabinet's open door/handle at any swing angle" — by
  design it minimizes the lateral sweep versus a conventional hinge,
  at the cost of a more complex door-to-carcase linkage.
- **Gap:** no minimum-cabinet-size or weight rating was found published
  for Horizon Plus in this catalogue excerpt.

---

## 16. Blum AVENTOS lift systems — corner/diagonal relevance (largely a gap)

AVENTOS (HF, HK, HK-XS, HK-S, HL, HS) is Blum's **vertical lift-door**
family for overhead/wall cabinets. Searches for a corner- or diagonal-
front-specific AVENTOS variant (e.g. for a diagonal corner wall cabinet)
did **not** surface a distinct Blum product or planning document in this
pass — AVENTOS is applied to corner wall cabinets only in the generic
sense that a standard AVENTOS lift arm can be installed on a
non-diagonal front adjacent to a corner, not on the pie-cut/diagonal
front itself. General figures found (not corner-specific, quoted for
context only):

- **AVENTOS HK:** cabinet heights **up to 600 mm**, widths **up to
  1800 mm**.
- **AVENTOS HK-S:** cabinet heights **186 mm (7-3/8") – 610 mm (24")**,
  widths **up to 1828 mm (72")**; fits above refrigerators/pantries;
  BLUMOTION soft-close standard.

Source: [Blum AVENTOS HK-XS programme page](https://www.blum.com/us/en/products/liftsystems/aventos-hk-xs/programme/); [Blum AVENTOS HK top programme page](https://www.blum.com/us/en/products/liftsystems/aventos-hk-top/programme/); [Blum AVENTOS HK-S programme page](https://www.blum.com/us/en/products/liftsystems/aventos-hk-s/programme/).

**This is a confirmed research gap, not a fabricated entry**: no
dimensioned corner/diagonal AVENTOS envelope was located. If the
placement engine needs a corner wall-cabinet lift solution, treat this
as open and pursue Blum's dealer-only planning documents or a direct
Blum technical-support query.

---

## 17. General adjacent-clearance design rules (cross-manufacturer, not hardware-specific)

Several clearance rules recur across kitchen-design literature
independent of any one manufacturer's hardware — useful as fallback
heuristics when a specific mechanism's clearance figure is a gap above:

- **Appliance-adjacent-to-blind-corner rule:** a dishwasher, refrigerator,
  or any handled appliance placed directly next to a blind-corner
  cabinet needs a **filler panel, typically 3"–6" wide**, between the
  appliance and the corner run, because the appliance handle protrudes
  further than a standard door/drawer pull and will otherwise intersect
  the corner door's swing arc.
  Source: [Fix It In The Home — Dishwasher in Corner](https://fixitinthehome.com/dishwasher-in-corner_gem1/); [Decor Cabinets Academy — Blind Corner Cabinet Solutions](https://academy.decorcabinets.com/blog-blind-corner-cabinet-solutions/).
- **General principle:** "the door and handle on a blind corner need room
  to open without hitting the adjacent cabinet, appliance, or hardware" —
  manufacturers provide door-swing-radius diagrams (see the Blum
  mitered-corner and Hettich Moving-Corner drawings above) specifically
  so installers can map this clearance; this is treated in the field as
  a mapping/measurement problem, not a fixed universal number, which is
  exactly why the per-SKU dimensioned envelopes in §1–15 matter more than
  a single rule of thumb for the placement engine.

---

## Sources

- Blum, 2012 CLIP top 170° hinge catalogue pages — https://www.wwhardware.com/media/installation/170_hinge_applications.pdf
- Blum catalogue 2022/2023, hinge index — https://publications.blum.com/2022/catalogue/en/72/
- Blum catalogue 2024/2025, corner bi-fold hinge — https://publications.blum.com/2024/catalogue/en/116/
- Blum SPACE CORNER installation/planning sheet (2010/2012) — https://www.wwhardware.com/media/installation/b568corner.pdf
- Blum SPACE CORNER product memo (Blum SEA) — https://d2.blum.com/services/BEC003/mem016b-p_fl_dok_bsg_$sen-sg_$aof_$v1.pdf
- Blum SPACE CORNER overview (Blum AU) — https://www.blum.com/au/en/products/cabinet-applications/space-corner/overview/
- Blum AVENTOS HK-XS / HK top / HK-S programme pages — https://www.blum.com/us/en/products/liftsystems/
- Blum EASY ASSEMBLY — number of hinges — https://ea.blum.com/en/number-of-hinges/
- Blum UK KIT Shop — Which hinge? — https://blumkit.co.uk/blogs/technical-blog/which-hinge
- HardwareSource — Blum Pie Cut Corner Hinge — https://www.hardwaresource.com/products/blum-pie-cut-corner-hinge
- Barkerdoor — Blum 79T9550 (95° blind corner) — https://www.barkerdoor.com/79T9550-Blum-CLIP-TOP-95-degrees-BLIND-CORNER-p/79t9550.htm
- Barkerdoor — Blum 79t5550 (45° angled hinge) — https://www.barkerdoor.com/Blum-CLIP-TOP-45-degrees-angled-hinge-p/79t5550.htm
- Woodworkerexpress — Blum 79B9698 (95° +45 diagonal Inserta) — https://www.woodworkerexpress.com/blum-95deg-clip-top-blumotion-hinge-45-diagonal-inserta.html
- Hettich Design Collection — Corner Solution / Overhead Units catalogue — https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf
- Kesseböhmer US — corner cabinets / lazy susan overview — https://www.kesseboehmer.us/kitchen/corner-cabinets/magic-corner , https://www.kesseboehmer.us/kitchen/corner-cabinets/lazy-susan
- PWS Distributors — Kesseböhmer Magic Corner 900–1000mm — https://www.pws.co.uk/product/kmcuscr
- Kesseböhmer Specification & Price Guide 2017 (PWS) — https://uploads-ssl.webflow.com/5b911d408065b64c949a8505/5b911d408065b692889a874e_Kesse_Spec_Price_Guide_2017.pdf
- East Coast Kitchens — Kesseböhmer Magic Corner 900/1000mm — https://eastcoastkitchens.co.uk/kitchen-storage-accessories/3618-kessebohmer-9001000mm-style-magic-corner-pull-out-storage.html
- CabinetParts.com — Kesseböhmer LeMans II Series 40/45/50, Magic Corner Two — https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132740-p24162 , -HAF54132745-p24164 , -HAF54132751-p24167 , -HAF54810241-p24385
- Häfele — Kesseböhmer LeMans II product page — https://www.hafele.com/us/en/product/kesseboehmer-lemans-ii-set-for-blind-corner-cabinets/P-00856493/
- HäfeleHome AU — LeMans II — https://www.hafelehome.com.au/products/lemans-ii ; Ninka Qanto-B Model 4 — https://www.hafelehome.com.au/products/ninka-qanto-b-corner-unit-model-4
- CabinetParts.com — Rev-A-Shelf 5PSP-15-CR, 6265-20-11-50, 6472-32-11-52 — https://www.cabinetparts.com/p/revashelf-organizers-kitchen-organizers-RV5PSP15CR-p38452 , -RV6265201150-p37645 , -RV647232-p38483
- Rev-A-Shelf — 5PSP series, Lazy Susans info — https://rev-a-shelf.com/5psp-series , https://rev-a-shelf.com/lazy-susans-info
- Rockler — Rev-A-Shelf 6265 series D-Shape 5-Shelf Corner Lazy Susans — https://www.rockler.com/d-shape-5-shelf-corner-lazy-susans-rev-a-shelf-6265-series
- BedBathAndBeyond — Rev-A-Shelf 6065 series 32" — https://www.bedbathandbeyond.com/Home-Garden/Rev-A-Shelf-6065-Series-32-Inch-Full-Circle-5-Shelf-Lazy-Susan/40340708/product.html
- Richelieu Hardware — Rev-A-Shelf blind-corner organizers — https://www.richelieu.com/us/en/category/kitchen-and-bathroom-accessories/kitchen/corner-cabinet-storage-systems/base-corner-cabinet-storage-systems/blind-corner-shelves-ras/rev-shelf-two-tier-organizer-for-blind-corner-cabinet/1170331/sku-537221MPR , /blind-corner-solutions/blind-corner-organizer-with-soft-close/1205660/sku-53PSP18SCMP
- Vauth-Sagel — VS COR product-family page — https://vauth-sagel.com/gb/en/products/product-variants/vs-cor
- CabinetParts.com — VS COR FLEX Saphir/Planero — https://www.cabinetparts.com/p/vauth-sagel-organizers-kitchen-organizers-VS90092000001-p125390 , -VS90092000011-p125411
- WoodworkerExpress — COR Flex Scalea 36" — https://www.woodworkerexpress.com/cor-flex-scalea-full-access-36-blind-corner-pull-out-4-basket-carbon-steel-gray-Vauth-sagel.html
- Ninka — TRIGON, Qanto product pages — https://www.ninka.com/en/TRIGON.html , https://www.ninka.com/en/Qanto.html
- Gamma Fittings — Ninka TRIGON — https://gammafittings.co.uk/product/ninka-corner-system-trigon/
- T&S Architectural — Ninka Qanto vertically-rising corner/island unit — https://www.tandsarchitectural.co.uk/corner-and-island-storage-unit-vertically-rising-ninka-qanto
- Fix It In The Home — Dishwasher in Corner clearance rule — https://fixitinthehome.com/dishwasher-in-corner_gem1/
- Decor Cabinets Academy — Blind Corner Cabinet Solutions — https://academy.decorcabinets.com/blog-blind-corner-cabinet-solutions/

```json
[
  {
    "hardware_id": "blum-clip-top-170-corner-adjacent",
    "vendor": "Blum",
    "product_line": "CLIP top / CLIP top BLUMOTION 170°",
    "cabinet_types": ["blind-corner-base", "adjacent-to-corner-any"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": 3.07, "swing_radius": null},
    "required_hinge_angle_deg": 170,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 48,
    "sources": [
      "https://www.wwhardware.com/media/installation/170_hinge_applications.pdf",
      "https://publications.blum.com/2022/catalogue/en/72/",
      "https://ea.blum.com/en/number-of-hinges/"
    ],
    "confidence": "high",
    "notes": "Mitered-corner door application: max protrusion 78mm (3.07in) at full 170°, half-cranked H=3 plate; angle restriction clip 70.6103 caps swing at 130° to reduce protrusion/collision risk against adjacent doors. Inset not possible at 170°. Weight rating is general CLIP top guidance, not this SKU specifically (ESTIMATE)."
  },
  {
    "hardware_id": "blum-clip-top-95-blind-corner",
    "vendor": "Blum",
    "product_line": "CLIP top 95°/83° blind-corner hinge (DQDK7Y inset, DQDKXA overlay)",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": 95,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": null,
    "sources": [
      "https://publications.blum.com/2022/catalogue/en/72/",
      "https://www.barkerdoor.com/79T9550-Blum-CLIP-TOP-95-degrees-BLIND-CORNER-p/79t9550.htm"
    ],
    "confidence": "medium",
    "notes": "Reduced-angle hinge specifically for the door adjacent to a blind-corner cabinet so it doesn't swing past the point of hitting the corner filler/neighboring cabinet. Dual-angle spec 95°/83° per catalogue index; door thickness and boring dims not recovered."
  },
  {
    "hardware_id": "blum-clip-top-95-plus45-diagonal",
    "vendor": "Blum",
    "product_line": "CLIP top BLUMOTION 95° +45 diagonal (e.g. 79B9698, Inserta)",
    "cabinet_types": ["pie-cut-corner-base"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": 95,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": null,
    "sources": [
      "https://www.woodworkerexpress.com/blum-95deg-clip-top-blumotion-hinge-45-diagonal-inserta.html",
      "https://www.barkerdoor.com/Blum-CLIP-TOP-45-degrees-angled-hinge-p/79t5550.htm"
    ],
    "confidence": "medium",
    "notes": "For the single diagonal (pie-cut/set-back) door of a corner base cabinet; door thickness range and boring dims not recovered in this pass."
  },
  {
    "hardware_id": "blum-corner-bifold-hinge-60",
    "vendor": "Blum",
    "product_line": "Corner cabinet bi-fold hinge 60° (DQDQJY, ex-79.815/79.850) + 155°/170° outer hinge",
    "cabinet_types": ["pie-cut-corner-base"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": 60,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": null,
    "sources": [
      "https://publications.blum.com/2024/catalogue/en/116/",
      "https://www.hardwaresource.com/products/blum-pie-cut-corner-hinge",
      "https://www.hardwaresource.com/products/blum-corner-hinge-bundle"
    ],
    "confidence": "high",
    "notes": "Joins the two bi-fold door leaves of a pie-cut corner cabinet. Front thickness FD 15-23mm (0.59-0.91in), factory-set 19mm (0.75in). Must be paired with a separate 155° or 170° hinge on the outer leaf to the cabinet frame -- that outer hinge's angle (see blum-clip-top-170-corner-adjacent) governs the actual lateral sweep against neighboring cabinetry. 60° limit is explicitly designed to clear adjoining obstructions before full opening."
  },
  {
    "hardware_id": "blum-space-corner",
    "vendor": "Blum",
    "product_line": "SPACE CORNER (TANDEM plus BLUMOTION / TANDEMBOX antaro-intivo)",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": 35.4, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": 31.1, "lateral_sweep": 0, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 110,
    "sources": [
      "https://www.wwhardware.com/media/installation/b568corner.pdf",
      "https://d2.blum.com/services/BEC003/mem016b-p_fl_dok_bsg_$sen-sg_$aof_$v1.pdf",
      "https://www.blum.com/au/en/products/cabinet-applications/space-corner/overview/"
    ],
    "confidence": "high",
    "notes": "Full-extension L-shaped drawer, not a swing/rotate mechanism -- lateral_sweep is 0 because there is no rotating arm (main clearance advantage vs. susan/swing-out systems). Corner cabinet sizes 36in/39in/42in; recommended cabinet width window 900-1200mm. Uses SYNCROMOTION linkage so a standard (non-diagonal) front can swing slightly inward during opening -- model as near-rigid with small rotational component. Weight: 110 lb dynamic / 125 lb static per drawer. Requires special (non-standard) cabinet/drawer construction, not a retrofit."
  },
  {
    "hardware_id": "kessebohmer-magic-corner-standard",
    "vendor": "Kesseböhmer",
    "product_line": "Magic Corner / Magic Corner Two",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": 35.4, "depth": 19.7, "door_opening": 17.7},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 31,
    "sources": [
      "https://www.pws.co.uk/product/kmcuscr",
      "https://uploads-ssl.webflow.com/5b911d408065b64c949a8505/5b911d408065b692889a874e_Kesse_Spec_Price_Guide_2017.pdf",
      "https://www.kesseboehmer.us/kitchen/corner-cabinets/magic-corner"
    ],
    "confidence": "medium",
    "notes": "Sold for 900mm or 1000mm blind-corner cabinets (35.4in/39.4in), door width 450-600mm (17.7-23.6in), minimum clear unit height 525mm (20.7in). Front shelf 14kg (31lb)/back shelf 18kg (40lb) -- weight_rating_lb given here is the lower (front-shelf) figure; treat as per-shelf, not per-unit. Bi-fold doors must open fully before the frame swings out -- gating angle equals whatever bi-fold hardware is fitted (see blum-corner-bifold-hinge-60 as one option). No independent swing-radius figure found; numbers sourced via resellers, not Kesseboehmer's own datasheet (portal-gated)."
  },
  {
    "hardware_id": "kessebohmer-lemans-ii",
    "vendor": "Kesseböhmer",
    "product_line": "LeMans II (Series 40 / 45 / 50)",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": 14.25, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": 85,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 55,
    "sources": [
      "https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132740-p24162",
      "https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132745-p24164",
      "https://www.cabinetparts.com/p/kessebohmer-organizers-kitchen-organizers-HAF54132751-p24167",
      "https://www.hafele.com/us/en/product/kesseboehmer-lemans-ii-set-for-blind-corner-cabinets/P-00856493/"
    ],
    "confidence": "high",
    "notes": "Series 40 min. opening 14.25in W x 21.5in H (listed here); Series 45 min. 16.5in W x 21in H; Series 50 min. face-frame 17.75in W x 21.5in H. General min. face-frame width 16.125in, frameless 16.5in, height 21.5in across the line. Functions fully down to an 85° door-opening angle -- door hinge does not need full swing. 55 lb (25kg) max per tray. Rebadged identically by Haefele (541.xx SKUs)."
  },
  {
    "hardware_id": "hafele-lemans-ii-oem",
    "vendor": "Häfele",
    "product_line": "LeMans II (Kesseböhmer OEM, Häfele 541.xx)",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": 16.125, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": 85,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 55,
    "sources": [
      "https://www.hafele.com/us/en/product/kesseboehmer-lemans-ii-set-for-blind-corner-cabinets/P-00856493/",
      "https://www.hafelehome.com.au/products/lemans-ii"
    ],
    "confidence": "medium",
    "notes": "Identical hardware/engineering to kessebohmer-lemans-ii, sold under the Haefele brand; no distinct Haefele-original corner mechanism was located in this research pass despite searching for FunLine/FunFront naming."
  },
  {
    "hardware_id": "kessebohmer-arena-lazy-susan-hardware",
    "vendor": "Kesseböhmer",
    "product_line": "Arena Classic / Arena Style / Arena Plus (shelf+rail hardware, OEM'd into Hettich carousels)",
    "cabinet_types": ["pie-cut-corner-base"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": 0, "lateral_sweep": 16, "swing_radius": 16},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 55,
    "sources": [
      "https://www.woodworkerexpress.com/super-susan-arena-classic-32-2-shelf-kidney-lazy-susan-kit-w-attached-bearing-chrome-white-kessebohmer.html",
      "https://www.kesseboehmer.us/kitchen/corner-cabinets/lazy-susan"
    ],
    "confidence": "medium",
    "notes": "Shelf-and-rail hardware line, not a standalone cabinet fitting; typical set sized 28in or 32in diameter for 33in/36in pie-cut corner cabinets. swing_radius/lateral_sweep estimated at half the 32in diameter (rotate-in-place mechanism, not extend-and-swing). Confirmed used under Arena STYLE/CLASSIC naming inside Hettich Carousel and Semi-circular Carousel products (see hettich-carousel-full and hettich-semicircular-carousel)."
  },
  {
    "hardware_id": "revashelf-5psp-blind-corner",
    "vendor": "Rev-A-Shelf",
    "product_line": "5PSP series wire blind-corner swing-out optimizer",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": 15, "depth": 20.25, "door_opening": 15},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 45,
    "sources": [
      "https://www.cabinetparts.com/p/revashelf-organizers-kitchen-organizers-RV5PSP15CR-p38452",
      "https://rev-a-shelf.com/5psp-series",
      "https://www.richelieu.com/us/en/category/kitchen-and-bathroom-accessories/kitchen/corner-cabinet-storage-systems/base-corner-cabinet-storage-systems/blind-corner-shelves-ras/rev-shelf-two-tier-organizer-for-blind-corner-cabinet/1170331/sku-537221MPR"
    ],
    "confidence": "medium",
    "notes": "15in model: face-frame min. 15in W x 20.25in D x 21in H (soft-close variant: 15in W x 21.66in D x 22in H). 18in model: 18in W x 21.66in D x 22in H. Non-handed (fits either left- or right-blind corner without a mirrored SKU). Weight rating (45 lb/shelf) taken from an adjacent Rev-A-Shelf two-tier SKU sold via Richelieu, not the 5PSP datasheet directly -- treat as ESTIMATE. No published swing-radius/lateral-sweep figure found."
  },
  {
    "hardware_id": "revashelf-lazy-susan-series",
    "vendor": "Rev-A-Shelf",
    "product_line": "6065 (full-circle) / 6265 (D-shape) / 6472 (kidney) lazy susan series",
    "cabinet_types": ["pie-cut-corner-base", "corner-wall", "corner-pantry-tall"],
    "min_cabinet_in": {"width": 32, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": 0, "lateral_sweep": 16, "swing_radius": 16},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": null,
    "sources": [
      "https://www.cabinetparts.com/p/revashelf-organizers-kitchen-organizers-RV6265201150-p37645",
      "https://www.cabinetparts.com/p/revashelf-organizers-kitchen-organizers-RV647232-p38483",
      "https://www.bedbathandbeyond.com/Home-Garden/Rev-A-Shelf-6065-Series-32-Inch-Full-Circle-5-Shelf-Lazy-Susan/40340708/product.html",
      "https://www.rockler.com/d-shape-5-shelf-corner-lazy-susans-rev-a-shelf-6265-series"
    ],
    "confidence": "medium",
    "notes": "6265 (D-shape, 5-shelf, 22in dia): for 56-62in inner cabinet height (tall/pantry). 6472 (kidney, 2-shelf): 18/24/32in dia options, 32in model for 26-32in cabinet height (wall-cabinet range). 6065 (full-circle, 5-shelf, polymer, 32in dia): 56-62in adjustable inner cabinet height. Rotate-in-place mechanism -- lateral_sweep/swing_radius given here (16in) is the largest-diameter (32in) example's radius; scale per actual diameter selected. No manufacturer per-shelf weight rating recovered for these specific series (gap)."
  },
  {
    "hardware_id": "vauth-sagel-vs-cor-flex",
    "vendor": "Vauth-Sagel",
    "product_line": "VS COR Flex (Saphir / Planero / Scalea)",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": 15, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 17,
    "sources": [
      "https://www.cabinetparts.com/p/vauth-sagel-organizers-kitchen-organizers-VS90092000001-p125390",
      "https://www.cabinetparts.com/p/vauth-sagel-organizers-kitchen-organizers-VS90092000011-p125411",
      "https://vauth-sagel.com/gb/en/products/product-variants/vs-cor"
    ],
    "confidence": "medium",
    "notes": "Saphir variant min. opening 15in; Planero variant min. opening 17.5in; Scalea sold as a 36in blind-corner pull-out. Floor-mounted frame, unhanded, claims access to 100% of cabinet. 17 lb/shelf is notably lower than Blum/Kesseboehmer/Rev-A-Shelf systems -- flag for weight-budget logic. Extraction depth/swing radius/required door angle not found published (technical planning PDFs are dealer/CAD-portal gated)."
  },
  {
    "hardware_id": "vauth-sagel-vs-cor-fold",
    "vendor": "Vauth-Sagel",
    "product_line": "VS COR Fold",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": null,
    "sources": ["https://vauth-sagel.com/gb/en/products/product-variants/vs-cor"],
    "confidence": "low",
    "notes": "No dimensioned data recovered beyond the marketing tagline. Full gap -- all envelope/rating fields null pending access to Vauth-Sagel's dealer-portal technical documents."
  },
  {
    "hardware_id": "ninka-trigon",
    "vendor": "Ninka",
    "product_line": "TRIGON corner-basket retrofit fitting",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 55,
    "sources": [
      "https://www.ninka.com/en/TRIGON.html",
      "https://gammafittings.co.uk/product/ninka-corner-system-trigon/"
    ],
    "confidence": "medium",
    "notes": "Retrofittable into an existing blind corner. Tool-free removable/replaceable trays, stepless tool-free height adjustment, optional retrofittable damped soft-close. 25kg (55lb) per shelf. No minimum-cabinet or motion-envelope figures recovered (gap)."
  },
  {
    "hardware_id": "ninka-qanto",
    "vendor": "Ninka",
    "product_line": "Qanto vertically-rising corner/island unit",
    "cabinet_types": ["blind-corner-base", "corner-tall-pantry"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": null,
    "sources": [
      "https://www.ninka.com/en/Qanto.html",
      "https://www.tandsarchitectural.co.uk/corner-and-island-storage-unit-vertically-rising-ninka-qanto"
    ],
    "confidence": "low",
    "notes": "Distinct motion type: basket assembly lifts vertically and out rather than swinging/extending horizontally. No dimensioned envelope, minimum cabinet size, or weight rating recovered in this pass -- full gap."
  },
  {
    "hardware_id": "hettich-cargoman",
    "vendor": "Hettich",
    "product_line": "CargoMan",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": 35.4, "depth": 19.3, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": 19.3, "lateral_sweep": 17.7, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 44,
    "sources": ["https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf"],
    "confidence": "high",
    "notes": "Min. inside carcase depth 490mm (19.3in). Dimensioned table (mm): 900mm cabinet -> X=860,X2=450,Y=490,Z=150; 1000mm cabinet -> X=1000,X2=500 or 600,Y=490,Z=150. Z=150mm is min. internal cabinet height per shelf layer. 20kg/shelf (44lb). Each shelf swivels out individually (not linked); no extra attachment hardware; usable in odd/even single-unit counts (non-handed)."
  },
  {
    "hardware_id": "hettich-moving-corner-cargo",
    "vendor": "Hettich",
    "product_line": "Moving Corner - Cargo Series",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": 33.9, "depth": 15.35, "door_opening": 17.7},
    "motion_envelope_in": {"extraction_depth": 22.4, "lateral_sweep": 18.5, "swing_radius": null},
    "required_hinge_angle_deg": 80,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 44,
    "sources": ["https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf"],
    "confidence": "high",
    "notes": "For 900mm and 1000mm wide corner cabinets. Frame envelope 516mm width + 80mm offset, depth 520/525mm. Install dims: inside width 860-968mm (33.9-38.1in), depth >=390mm or >=500mm, pull-out reach 412-568mm, 470mm fixed offset, 295mm basket depth, door width 450-600mm (17.7-23.6in). Swing angle <=80 degrees marked on both installation drawings -- the door needs to open to no more than ~80 deg for the arm to clear. Silent System soft-close, ClickFixx assembly, stainless wire basket, 10yr anti-rust warranty. Weight rating estimated from shared Arena-basket construction with CargoMan (20kg/shelf)."
  },
  {
    "hardware_id": "hettich-moving-corner-comfort",
    "vendor": "Hettich",
    "product_line": "Moving Corner Comfort",
    "cabinet_types": ["blind-corner-base"],
    "min_cabinet_in": {"width": 17.7, "depth": 19.7, "door_opening": 17.7},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": 44,
    "sources": ["https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf"],
    "confidence": "high",
    "notes": "For narrower single-leaf corner units, front width 450-600mm (17.7-23.6in) -- distinct from the 900/1000mm Cargo Series. Inside width 862mm, or 945-971mm depending on door width; depth 500mm (19.7in); height 545mm. Dimensioned table (mm): door 450->dim A 394->carcase width 862; door 500->dim A 444->carcase width 862; door 550/600->dim A 494->carcase width 945. Height-adjustable knob for ergonomic reach; baskets pull out individually at the back."
  },
  {
    "hardware_id": "hettich-semicircular-carousel",
    "vendor": "Hettich",
    "product_line": "Semi-circular Carousel (Arena STYLE/CLASSIC shelves)",
    "cabinet_types": ["pie-cut-corner-base"],
    "min_cabinet_in": {"width": 35.4, "depth": 18.7, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": 29.5, "swing_radius": 29.5},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": 16.2},
    "weight_rating_lb": null,
    "sources": ["https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf"],
    "confidence": "high",
    "notes": "For 900mm or 1000mm carcase corner base units. Installation height 730mm (28.7in). Pivot arm field-cuttable; bearings secured to corner post. 900mm cabinet: shelf radius ref 750mm (29.5in), min depth >=475mm (18.7in), min door-side clearance >=412mm (16.2in). 1000mm cabinet: shelf radius ref 850mm (33.5in), min depth >=525mm (20.7in), min clearance >=462mm (18.2in). Interior frame depth 657-693mm. Shares Arena-brand shelf hardware with Kessebohmer (see kessebohmer-arena-lazy-susan-hardware)."
  },
  {
    "hardware_id": "hettich-carousel-full",
    "vendor": "Hettich",
    "product_line": "Carousel (three-quarter-circle revolving shelves, Arena STYLE/CLASSIC)",
    "cabinet_types": ["pie-cut-corner-base"],
    "min_cabinet_in": {"width": 33.9, "depth": 20.1, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": 80.2,
    "adjacent_clearance_in": {"left": 13.8, "right": null, "front": 20.1},
    "weight_rating_lb": null,
    "sources": ["https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf"],
    "confidence": "medium",
    "notes": "For 800x800mm or 900x900mm base-unit carcases. Variable install height: center column adjustable 839-889mm, or field-cut shorter. 900x900 cabinet: min opening >=860mm (33.9in), shelf swing ref 420mm, min front clearance >=510mm (20.1in), rear clearance <=350mm (13.8in). 800x800 cabinet: min opening >=740mm (29.1in), min front clearance >=480mm (18.9in), rear <=260mm (10.2in). Angle markers 90deg/80.2deg read off the manufacturer's isometric drawing describe the shelf's active rotation arc (not confirmed as a door-opening requirement) -- required_hinge_angle_deg recorded at medium confidence pending clearer source prose."
  },
  {
    "hardware_id": "hettich-wingline-170",
    "vendor": "Hettich",
    "product_line": "WingLine 170 bi-fold door track",
    "cabinet_types": ["corner-tall-pantry"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": 16.9, "swing_radius": null},
    "required_hinge_angle_deg": 170,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": null,
    "sources": ["https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf"],
    "confidence": "high",
    "notes": "Top-mounted 2-panel bi-fold door track for tall corner pantry units -- functional analog to Blum's 60deg/170deg bi-fold hinge pair (see blum-corner-bifold-hinge-60) but implemented as a sliding/folding track. Door height up to 2200mm (86.6in); each panel width up to 300mm (11.8in); opening up to 170deg with intermediate stops at 110/125deg; guide-bar throw 430mm (16.9in); carcase-inside-edge clearance 8.5mm; min edge distance >=12mm; mounting hole dia 10x12mm for 'socket no. 33'. Compatible with soft-closing Sensys hinge. Because door height runs up to 2200mm, adjacent tall units (fridge, oven column) need clearance for the panel's full height, not just a base-cabinet arc."
  },
  {
    "hardware_id": "hettich-horizon-plus",
    "vendor": "Hettich",
    "product_line": "Horizon Plus parallel-swivel door fitting",
    "cabinet_types": ["blind-corner-base", "corner-tall-pantry", "L-corner-base"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": 1.18, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": 0.08},
    "weight_rating_lb": null,
    "sources": ["https://www.hettich.com/fileadmin/Media_Center/Catalogue/Gen_Corner___OverHead_Design_Collection_Book.pdf"],
    "confidence": "medium",
    "notes": "Lifts the door horizontally out of the flush front and swings it to sit flush in front of an adjacent cabinet segment, instead of protruding into the room -- designed specifically to minimize lateral sweep vs. a conventional hinge for corner/multi-element cabinet runs. Door thickness T=16-26mm (0.63-1.02in) supported; lateral throw 16-30mm (0.63-1.18in, using max as lateral_sweep); min edge clearance >=2mm (0.08in). Usable on single/double doors and corner units. No minimum-cabinet-size or weight rating found published."
  },
  {
    "hardware_id": "blum-aventos-hk-corner-adjacent",
    "vendor": "Blum",
    "product_line": "AVENTOS HK / HK-S (general lift system, not corner-specific)",
    "cabinet_types": ["corner-wall"],
    "min_cabinet_in": {"width": null, "depth": null, "door_opening": null},
    "motion_envelope_in": {"extraction_depth": null, "lateral_sweep": null, "swing_radius": null},
    "required_hinge_angle_deg": null,
    "adjacent_clearance_in": {"left": null, "right": null, "front": null},
    "weight_rating_lb": null,
    "sources": [
      "https://www.blum.com/us/en/products/liftsystems/aventos-hk-xs/programme/",
      "https://www.blum.com/us/en/products/liftsystems/aventos-hk-top/programme/",
      "https://www.blum.com/us/en/products/liftsystems/aventos-hk-s/programme/"
    ],
    "confidence": "low",
    "notes": "CONFIRMED GAP: no dedicated Blum AVENTOS corner or diagonal-front variant was located. AVENTOS is only relevant to corner walls in the generic sense of a standard lift front installed on a non-diagonal cabinet adjacent to a corner. General (non-corner) figures for context only: AVENTOS HK cabinet height up to 600mm, width up to 1800mm; AVENTOS HK-S height 186-610mm, width up to 1828mm. All corner-specific envelope/rating fields null pending Blum dealer-portal or direct technical-support follow-up."
  }
]
```
