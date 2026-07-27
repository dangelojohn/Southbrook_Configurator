# Wall (Upper) Corner Cabinet Taxonomy — Engineering Reference

Purpose: ground-truth reference for a kitchen CAD/MRP placement engine's WALL (upper) corner-cabinet logic. Every dimension below is either sourced to a primary/manufacturer/practitioner citation or explicitly marked `ESTIMATE (basis: ...)`. Where sources disagree, both figures are given with their source.

Scope note on sourcing quality: KCMA (ANSI/KCMA A161.1) sets *performance* test requirements (load, finish, operation cycles), not a public dimensional module chart in freely-crawlable form — the 2022 standard PDF is hosted by KCMA but is a certification/testing document, not a cabinet-dimension catalog. Dimensional truth for this taxonomy is therefore triangulated from (a) semi-custom/custom manufacturer spec sheets (Barker Modern, Wellborn, Shenandoah, Fabuwood, KraftMaid), (b) RTA/stock cabinet product listings from multiple vendors (cross-checked for convergence), (c) hardware engineering literature (Blum), and (d) practitioner forums (WoodWeb, CabinetJoint) for construction/hinge behavior. Convergent numbers across 3+ independent vendor listings are treated as "verified" for stock/semi-custom ranges; single-source or forum-only numbers are marked accordingly.

All wall cabinets in this document are **upper** cabinets (mounted above the countertop), as distinct from base corner cabinets (not covered here).

---

## 1. Blind Wall Corner Cabinet

A standard rectangular wall-cabinet box (1 or 2 doors) pushed into the corner so that part of its width is hidden ("blind") behind the return-wall cabinet run. The door(s) sit on the exposed leg; the blind leg is unusable storage depth that must be reached across.

| Property | Value | Source |
|---|---|---|
| Box width (exposed/door leg) | 24"–36", commonly 30"–39" per vendor line | Barker Modern (24"–36" configurable); RTA vendors list 36"/39"/42" nominal widths for the *base* blind analog — wall blind cabinets in stock lines skew narrower, 24"–36" |
| Box height | 12"–48" (0.25" increments, custom); stock: 30", 36", 42" | Barker Modern spec page |
| Box depth | 12" standard; up to 24"–30" on request | Barker Modern; general wall-cabinet depth convention |
| Blind panel / filler | Blind panel integrated into cabinet face, 10"–15" wide; **separate filler strip required on the adjacent cabinet run**: 3" filler (full-overlay framed door + decorative hardware) or 1½" filler (no pull-out hardware needed) | Barker Modern (blind panel 10"–15"); KraftMaid Momentum Spec Book pages 46/48 (3" vs 1½" filler rule, "must be pulled 3\" from the corner to provide a 90° door opening... if not using decorative hardware, only need to pull 1½\"") |
| Door config | 1 or 2 doors on exposed leg only; blind leg has no door | Barker Modern product line (1-door and 2-door blind corner wall variants, left- and right-blind) |
| Hinge | Standard concealed European hinge (Blum Inserta Blumotion, soft-close) — no special angle requirement since the door swings clear of the corner | Barker Modern |
| Susan option | Not applicable in the blind leg (no rotating access); some lines add a pull-out "blind corner optimizer" basket, base-cabinet-style, in higher-end kitchens — **ESTIMATE (basis: base-cabinet blind-corner optimizer hardware, e.g. Rev-A-Shelf, adapted upward; not confirmed for wall depth ≤12" in sourced material)** | — |
| Mount height AFF | 54" standard bottom-of-cabinet (see §12) | Multiple (kitchenseer.com, bobvila.com) |
| Stacking | Rare; blind geometry complicates a stacked open-shelf topper because the blind leg's depth changes the visual line | ESTIMATE (basis: general stacking practice, no blind-specific source found) |
| Crown/valance | Blind leg forces the same corner-crown-return problem as diagonal cabinets (see §12); crown must die into a stile or AFE at the corner, not wrap the blind panel | WoodWeb, "Corner Cabinet Dimensions and Crown Moulding Transitions" |
| Weight/mounting | Standard wall-cabinet mounting (screw into studs on both legs where possible); no unusual load path since only one leg is a true door-access box | KCMA A161.1 (600 lb wall-cabinet mount test, general, not blind-specific) |
| Advantages | Cheapest corner solution; simplest box construction (no diagonal cuts, no special hinges) | Derived |
| Disadvantages | Significant dead/hard-to-reach storage in the blind leg; requires a filler strip that consumes additional wall inches beyond the box itself | KraftMaid filler-rule source |
| Cost tier | Low (stock/RTA tier) | Derived from stock pricing (SG-DCW2436 diagonal analog $326–$816 range for comparable stock box) |

---

## 2. Diagonal Wall Corner Cabinet

The most common commercial wall corner cabinet: a single box with a 45°-angled face, one door, mounted symmetrically across the corner. Also called "angle wall cabinet."

| Property | Value | Source |
|---|---|---|
| Box width x height (face) | 24"W x 12"H up to 24"W x 42"H; stock heights 12", 24", 30", 36", 42" | Nelson Cabinetry (24" wall diagonal corner, 30/36/42 heights); Home Depot/Hampton Bay WD2430-CSW (24"W x 24"D x 30"H); Granite Factory Direct WDC2412GD (24"W x 12"H) |
| Box depth (each return leg) | 12" typical (matches standard wall-cabinet depth); some vendors list 24" cross-corner depth for the full diagonal footprint | Home Depot WD2430-CSW listed as 24"Wx24"Dx30"H (full diagonal footprint); CabinetCorp SG-DCW2436 listed 24"W x 36"H x 12"D |
| Verified stock example | SG-DCW2436: 24"W x 36"H x 12"D, single 5-piece recessed door, 2 interior shelves, concealed soft-close European hinge | shop.cabinetcorp.com product page (fetched) |
| IKEA SEKTION corner wall (glass variant) | 26"W x 15"D x 40"H | IKEA product page |
| Wall consumed per leg | 24" typical each leg (matches the 24"x24" footprint convention cited across WoodWeb and stock listings); custom up to 27"x27" or 29"x29" | WoodWeb, "Corner Cabinet Dimensions and Crown Moulding Transitions" — practitioner-reported configs: 24x24 @15"deep → 12" door opening; 27x27 @15"deep → 16" opening; 29x29 @17"deep → ~13" opening w/ 2" stiles |
| Filler required | Generally none — the diagonal face is designed to meet adjacent wall-cabinet runs flush; no blind panel | Derived from product construction (self-contained 45° box) |
| Door config | Single door, 45°-angled face, opens on standard hinge swing (not a special corner hinge) | CabinetCorp SG-DCW2436 |
| Hinge requirement | Standard concealed European hinge, no elevated opening-angle requirement (110°–125° typical, sufficient since the door is already angled into the room) | shop.cabinetcorp.com (confirms "Concealed European Hinges w/ Soft-Close," no special angle called out) |
| Susan option | Full-round or kidney lazy susan often added behind the single door for interior access, typically 18"–20" diameter in a 12"-deep box | Rev-A-Shelf lazy-susan catalog (18"/20" full-circle wall susans, 2- and 3-shelf) |
| Mount height AFF | 54" standard | See §12 |
| Stacking | Common for tall-ceiling kitchens — a second, shorter diagonal or open-corner unit is stacked above a 36" or 42" diagonal box to reach 60"+ combined height | Inference from general stacked-wall-cabinet sourcing (CliqStudios, Planner5D) — no diagonal-specific citation found; treat stacking dims as ESTIMATE |
| Crown/valance | The tradeoff: "the deeper the cabinet, the smaller the door" — increasing depth to gain crown-projection clearance (~2.25" crown overhang needs ~3" added cabinet depth) shrinks the usable door opening | WoodWeb (fetched) |
| Weight/mounting | Corner uppers physically span and load both return walls; must be screwed into studs on both legs, not just one, per general wall-cabinet mounting best practice | garagejournal.com / general mounting-bracket sourcing (not corner-specific, ESTIMATE extension) |
| Advantages | Simple single-door operation, widely stocked, cheapest true corner-filling solution, no complex hinge hardware | Derived |
| Disadvantages | Deep-corner dead zone behind the door unless a susan is added; door opening width shrinks as box depth grows (WoodWeb tradeoff) | WoodWeb |
| Cost tier | Low–Mid (widely stocked, e.g. $326 special / $816 list for a 24x36x12 stock unit) | shop.cabinetcorp.com pricing |

---

## 3. Pie-Cut Wall Corner Cabinet

A 90° cross-corner box (square footprint, both legs equal) with a **two-door bi-fold "pie-cut" front** hinged together, using a specialized bi-fold corner hinge that opens in two stages. Historically paired with a pie-cut (as opposed to full-round) lazy susan.

| Property | Value | Source |
|---|---|---|
| Box footprint | 24"x24" typical corner cross-section; construction example uses a 22¾"x8' plywood strip (one leg) + 11¾"x8' plywood strip (other leg/shelf depth) | Cabinet Joint / DIY build references (Ana White plans; CabinetJoint hinge install page) |
| Shelf depth | Max 11¾" deep recommended "so stuff doesn't get lost in the back" | DIY/practitioner source (Ana White-adjacent build note, cross-referenced in search results) |
| Door config | Two doors, hinged to each other in the center (bi-fold pair), opening as one assembly | CabinetJoint, "How to Join Doors Using Corner Bi-Fold Hinges (BCP/WCP)" |
| Hinge requirement | **Two-stage bi-fold action**: doors first fold to ~60° to clear an obstruction (adjoining door/appliance), then the assembly swings to a full **170°** for corner access. Hinge cup: 35mm bore, 3mm bore distance. Doors are set ¾" offset from each other during setup with ~3/16" vertical throw for adjustment. 6-way adjustable arms (L/R, up/down, front/back) | Rockler (Blum 170° Pie Corner Hinge Kit, frameless/inset and face-frame variants); dlawlesshardware.com, hardwaresource.com (Blum pie-cut hinge); CabinetJoint (fetched — confirms 170°, offset, spring-close behavior) |
| Applies to base AND wall | Confirmed — hinge product line covers both "Base or Wall Pie Cut Cabinet" (BCP/WCP part-number convention) | CabinetJoint (fetched) |
| Susan option | Pie-cut (kidney-adjacent) lazy susan historically standard companion hardware; full-round susans also fit if the box is squared off | Woodworker Express / PiePronation product context; Rev-A-Shelf kidney-shape susan line |
| Mount height AFF | 54" standard | See §12 |
| Wall consumed per leg | ~24" each leg (matches general 90° corner cross-cabinet convention) | Derived, consistent with WoodWeb 24x24 baseline |
| Filler required | Generally none if built to the corner module; adjacent-run fillers only if the pie-cut box is oversized relative to stock corner modules | Derived |
| Weight/mounting | Same dual-leg stud-mounting requirement as diagonal (spans both walls) | Derived, general wall-cabinet mounting practice |
| Advantages | Full 170° access to the entire corner interior in one continuous door motion; no dead blind zone | Rockler / CabinetJoint hinge specs |
| Disadvantages | More expensive, more complex hinge hardware (spring-loaded, 6-way adjustable, requires precise ¾" door offset setup); door pair must be carefully aligned or the spring-close binds | CabinetJoint (fetched) |
| Cost tier | Mid–High (specialty hinge hardware alone runs well above a standard concealed hinge; Blum 170° pie-corner kits are a premium hardware line) | Rockler/HardwareSource product listings (pricing implied by "kit" branding, exact $ not captured — ESTIMATE tier only) |

---

## 4. Easy Reach Wall Corner Cabinet

A square (90°) cross-corner cabinet using **two independent bi-fold doors** (not hinged to each other as a single pie-cut pair, but each door itself a bi-fold leaf), designed for maximal accessibility. Reversible for left- or right-hand installation.

| Property | Value | Source |
|---|---|---|
| Box dimensions | 24"W x 30"/36"/42"H x 12"D (stock convention) | evafloors.com; Waverly Cabinets WC5005WER2424SO (24"W x 24"H x 12"D, single shelf); thewcsupply WER2436 (Hanover White, bi-fold door) |
| Wall consumed per leg | 24" along each wall for installation | RTA/vendor convergence (Waverly, WC Supply, e&b Cabinets WER2430) |
| Door config | Two bi-fold doors, each independently hinged, reversible mounting (left- or right-hand swing) | evafloors.com |
| Hinge requirement | Bi-fold doors open to **170°** for full corner access | evafloors.com (search-result synthesis; consistent with Blum 170° pie-corner spec in §3 — same underlying hardware family) |
| Shelves | Adjustable, typically 1–2 per stock unit (single-shelf variant confirmed at Waverly) | Waverly Cabinets |
| Susan option | Not typically used — the bi-fold door design is the accessibility mechanism, replacing the need for a rotating susan | Derived from product design intent |
| Mount height AFF | 54" standard | See §12 |
| Filler required | None beyond standard corner-module allowance | Derived |
| Weight/mounting | Dual-leg stud mounting, standard | Derived |
| Advantages | "Utilizes all available space for storage" with reversible doors; commercially the most accessible non-susan wall-corner design | evafloors.com |
| Disadvantages | Bi-fold hardware costs more than a single diagonal door; door alignment/adjustment more involved than a plain hinge | Derived from hinge complexity (§3 hardware family) |
| Cost tier | Mid | Derived |

---

## 5. Corner Display / Glass Wall Cabinet

Same box geometry as the diagonal or square corner cabinet, but the door is glazed (glass panel, often mullioned) for display of dishware. Frequently specified taller for visual impact and sometimes lit internally.

| Property | Value | Source |
|---|---|---|
| Box dimensions (diagonal-front variant) | 24"W x 12"H/30"H/36"H/42"H x 12"D | Nelson Cabinetry (White/Gray Shaker 24" Wall Diagonal Corner Cabinet Glass Door); Granite Factory Direct WDC2412GD (24"Wx12"Hx12"D) |
| Box dimensions (IKEA square-corner variant) | 26"W x 15"D x 40"H | IKEA SEKTION corner wall cabinet w/ glass door |
| Door config | Single glass door (diagonal face) or glazed panel on a square-corner box; mullions optional | Nelson Cabinetry; ABCabinetry (Wall Diagonal Glass Door Corner Cabinets) |
| Hinge requirement | Standard concealed hinge — same as §2 (diagonal), no elevated angle need since single door | Derived, consistent with diagonal-cabinet hinge sourcing |
| Susan option | Optional interior lazy susan (18"-20" full-round) for organized display rotation | Rev-A-Shelf catalog (same hardware family as §2) |
| Mount height AFF | 54" standard, though display cabinets are sometimes hung slightly higher for sightline reasons | 54" general convention; higher-mount variant is ESTIMATE (basis: common kitchen-design practice for display hutches, not independently sourced) |
| Wall consumed per leg | 24"–26" typical, matching diagonal-cabinet convention | Derived from stock listings above |
| Filler required | None typical | Derived |
| Crown/valance | Same corner-crown-return challenge as §2 (die-in stile, AFE, or deepened box) | WoodWeb |
| Weight/mounting | Glass door adds negligible structural load vs. solid door; standard dual-leg mounting | Derived |
| Advantages | High visual/design value, showcases dishware, common upsell item | Derived |
| Disadvantages | No added storage efficiency over plain diagonal (same box); glass and interior lighting add cost | Derived |
| Cost tier | Mid–High (glass door + optional interior lighting is an upgrade line item across virtually all cabinet brands) | Derived from product-line positioning (Nelson Cabinetry glass variant sold as an upsell over solid-door diagonal) |

---

## 6. Open Shelf Corner (Wall)

No door — open shelving in a corner box, either as a small end-of-run accent unit or as the full corner treatment (increasingly common in "less standard upper cabinets in favor of full-height storage paired with open upper space" design trend).

| Property | Value | Source |
|---|---|---|
| Box dimensions (small accent example) | 12"W x 12"D x 30"H (3-shelf open corner end-shelf unit) | kabinetking.com, Innovation Imperial Blue WOES1230 |
| Box dimensions (full diagonal open-corner) | Same envelope as §2 diagonal cabinet (24"x24"x12", heights 30/36/42) but without a door | Derived from diagonal-cabinet geometry, door simply omitted — ESTIMATE for the specific "no-door diagonal" SKU, general construction logic is not source-specific |
| Wall consumed per leg | 12"–24" depending on whether it's an accent end-shelf or a full corner replacement | Derived |
| Door config | None | — |
| Hinge requirement | N/A | — |
| Susan option | N/A (open access replaces need for rotation) | Derived |
| Mount height AFF | 54" standard, though open shelving is frequently hung with reduced or no lower clearance restriction since there's no door swing to clear | 54" general convention |
| Filler required | None | Derived |
| Crown/valance | Simpler than solid-door corner units — no door-swing/crown interference, but end grain/exposed shelf edges need a finished end panel treatment at the corner | WoodWeb (AFE — applied finished end — technique applies generally to corner cabinet treatments) |
| Weight/mounting | Standard; open shelves carry visible dish/glassware loads, no special reinforcement beyond KCMA's general 15 psf shelf-load test | KCMA A161.1 (15 lb/sq ft shelf load, 7-day test, general standard) |
| Advantages | Cheapest possible corner treatment; currently trending in design (2026); zero door-swing/hinge complexity | Decor Cabinets ("20+ Ideas for Full Height Kitchen Cabinets," design-trend commentary) |
| Disadvantages | No enclosed storage/dust protection; items visible at all times | Derived |
| Cost tier | Low | Derived |

---

## 7. Appliance Garage (Corner)

A short wall-mounted box, typically installed at the bottom of the wall-cabinet run just above the countertop, with a roll-up tambour door, used to store small appliances (mixers, coffee makers) at counter height while keeping them visually enclosed. The corner variant fits a 24"x24" corner footprint.

| Property | Value | Source |
|---|---|---|
| Box footprint (corner) | Designed for a 24"x24" cross-corner wall cabinet | Omega National Products A0100MUF1 ("for 24 x 24 Inch Cross Corner Wall Cabinet") |
| Overall unit height | 18½" | Omega National A0100MUF1, AG-100CSC |
| Depth | 11⅞"–11½" | Omega National (11⅞"); alternate listing 11½" |
| Overall front width | ~17" (one source) or ~16¾" (alternate source) | cabinetparts.com listing variance — both figures reported, treated as vendor-model variance not error |
| Door opening (max) | 14 9/16"W x 16"H (one model); ~13¾"W (alternate model, door opening width only) | cabinetparts.com product listings |
| Door mechanism | Wood tambour ("roll-up") door on a track (finger-lite track system or spring-tension track), sliding up and back into the cabinet above | Omega National Products (A0100MUF1 = finger-lite track; AG-100CSC = spring tension track) |
| Hinge requirement | N/A — tambour track, not hinged | Derived |
| Susan option | N/A | — |
| Mount height AFF | Sits at the countertop-to-wall-cabinet gap, i.e., roughly at the 36"–37" AFF band (top of standard base cabinet/countertop) up to ~54"+18½" ≈ mid-band; effectively fills the standard 18" reveal between countertop and the bottom of the wall-cabinet run | Derived from standard 18" reveal convention (§12) — appliance garage height (18½") almost exactly matches the standard 18" wall-cabinet-to-counter gap, confirming this is a "fills the reveal, sits below wall cabinets" product | kitchenseer.com / bobvila.com (18" reveal convention) cross-referenced with Omega 18½" garage height |
| Filler required | None; garage kit includes its own end panels | Omega National install notes (auto-download PDF referenced end panels) |
| Crown/valance | N/A (below the wall-cabinet crown line entirely) | Derived |
| Weight/mounting | Lightweight kit, screws into the underside of the wall cabinet above and/or ties into countertop-adjacent framing; not a primary structural load path | Derived, general appliance-garage install practice |
| Advantages | Hides small appliances at point of use without full cabinet install; corner variant reclaims otherwise-dead corner counter space | Derived |
| Disadvantages | Reduces usable wall-cabinet storage above (garage occupies the space that would otherwise be lower wall-cabinet volume); tambour track adds moving-part maintenance | Derived |
| Cost tier | Mid (specialty tambour hardware kit, not a plain box) | Derived from kit-based (vs. simple box) product positioning |

---

## 8. Lift-Door Corner (Aventos-style)

Not a distinct box geometry — an upward-opening lift mechanism (Blum AVENTOS family) applied to a wall corner cabinet (typically diagonal or pie-cut footprint) instead of a hinged door. Chosen for accessible/low-reach kitchens or design continuity where hinged doors are undesirable.

| Property | Value | Source |
|---|---|---|
| Mechanism families | **HK / HK-S**: single-panel lift/stay ("front lifts up"), used for accent/upper cabinets incl. above-fridge; **HL**: door lifts up **parallel** to the cabinet face (stays vertical); **HF**: **bi-fold** lift — two-part door folds in the center while lifting, "ideal for tall wall cabinets with large doors" | Blum US product pages (AVENTOS HK-XS, HF, HL — fetched via search) |
| Corner applicability | HF's bi-fold-while-lifting action is the most natural fit for a corner box since it echoes the pie-cut bi-fold geometry (§3) without needing a floor-level hinge assembly; not confirmed by Blum as a named "corner" SKU — **ESTIMATE (basis: mechanical analogy between HF bi-fold action and pie-cut bi-fold door geometry; Blum's own literature does not show a dedicated corner-Aventos product in the sources gathered)** | Blum (general AVENTOS overview, fetched) |
| Clearance requirement | Lift systems require clear space **above** the cabinet for the door to swing/lift into — meaning no soffit/crown/valance directly above the door opening, or a soffit-mounted variant with reduced lift height | Blum AVENTOS overview (general mechanism description); soffit clearance requirement is standard across all Aventos literature — ESTIMATE for exact inches (varies by model/door weight per Blum's selection software, not captured in sourced pages) |
| Soft-close | Standard across all AVENTOS lift systems | Blum |
| Electric option | SERVO-DRIVE touch-to-open/close available | Blum |
| Door weight limit (example SKU) | Blum 20L2100.N5 Aventos HL rated to 2 lb 2 oz (a light-duty example; heavier-duty SKUs exist in the HL/HF line but weren't captured in this pass) | woodworkerexpress.com (Blum SKU listing) |
| Mount height AFF | Same 54" base convention, but **effective reach requirement is reduced** vs. a hinged door since the user does not need to swing a door sideways into an adjacent obstruction — often cited as the rationale for lift doors in accessible-design corner applications | ESTIMATE (basis: general universal-design rationale for lift doors; not a corner-specific citation) |
| Susan option | Commonly paired with a susan behind the lift door since the lift door removes the door-swing conflict that otherwise limits susan size | ESTIMATE (basis: mechanical compatibility reasoning, not directly sourced) |
| Weight/mounting | Aventos arms mount to the cabinet side panels and require adequate panel thickness/screw purchase; corner box must have full-depth side panels on both return legs to anchor the lift arms | ESTIMATE (basis: general Aventos installation requirement, not corner-specific) |
| Advantages | No door swing into walkway/adjacent cabinet; strong universal-design/accessibility case; premium design feature | Derived from Blum's design-forward positioning |
| Disadvantages | Highest hardware cost of any wall-corner mechanism; requires soffit/crown clearance planning; heavier doors need higher-capacity (costlier) lift arms | Derived |
| Cost tier | High (premium hardware line) | Derived from Blum's premium/design-forward product positioning; no direct $ captured |

---

## 9. Stacked Wall Corner Cabinet

Two (rarely three) wall-cabinet boxes stacked vertically in the same corner to reach a combined height suited to 9'+ ceilings, typically a tall diagonal/door box below topped by a shorter open-shelf or glass-door accent box.

| Property | Value | Source |
|---|---|---|
| Typical use case | 9-foot ceilings: "usually use 42-inch-tall wall cabinets with crown molding or stacked cabinets for a decorative look" | Expo Home Improvement / general kitchen-height guide sourcing (search synthesis) |
| Stacking pattern | Lower box: standard 30"/36"/42" diagonal or door corner box; upper box: shorter open-shelf or glass-door accent unit, often the full remaining height to the crown/ceiling line | ESTIMATE (basis: general "stock cabinets can be stacked to make up total height desired" convention; no corner-specific stacking dimension table found) |
| Combined height range | Practically 60"–84"+ depending on ceiling height and crown allowance | Derived from stacking 30–42" lower units with 12–30"+ upper units |
| Wall consumed per leg | Matches the lower unit's footprint (typically 24" per leg, per §2/§3) — the upper stacked unit is normally sized to the same footprint for visual alignment | Derived |
| Filler required | None beyond what each individual stacked box requires | Derived |
| Crown/valance | Crown typically caps only the topmost stacked unit; the seam between stacked boxes is usually concealed with a light rail or simply butted flush | ESTIMATE (basis: general stacked-cabinet trim practice) |
| Weight/mounting | Each box is independently through-mounted to studs; the upper box's weight is NOT carried by the lower box — both are separately fastened to the wall structure | ESTIMATE (basis: standard cabinet-installation practice; stacking does not create a cantilevered load path in correct installation) |
| Advantages | Achieves floor-to-ceiling visual weight without custom-height boxes; upper box can be lower-cost open shelving | Derived |
| Disadvantages | Seam line between boxes is a visible design detail that must be planned; access to the upper stacked box may require a step stool | Derived |
| Cost tier | Mid (two boxes vs. one, but each individually stock-priced) | Derived |

---

## 10. Full-Height / Ceiling-Height Corner Cabinet

A single continuous corner unit (not stacked — one box) running from just above the countertop to the ceiling, functioning as a corner pantry column. Overlaps conceptually with "tall/pantry cabinet" category (84"–96" typical) applied to a corner footprint.

| Property | Value | Source |
|---|---|---|
| Height range | Tall/pantry cabinets typically 84"–96" | kitchensearch.com / general tall-cabinet-height sourcing (search synthesis) |
| Footprint | Matches diagonal or pie-cut corner geometry (24"x24" typical), extended in height rather than replicated as a stack | Derived from combining §2/§3 footprint with pantry-height convention |
| Door config | Often a single continuous door pair (tall diagonal or pie-cut bi-fold) rather than multiple stacked doors, for a cleaner full-height look; equally common as an internally-shelved pantry column with a tall door | ESTIMATE (basis: general full-height cabinet design commentary — "20+ Ideas for Full Height Kitchen Cabinets," decorcabinets.com) |
| Hinge requirement | If a single tall door: needs full-length concealed hinges (typically 3–5 hinge points per door leaf for a door this tall, vs. 2 for a standard 30"–42" door) | ESTIMATE (basis: general hinge-count-scales-with-door-height cabinetmaking practice, not directly sourced for corner application) |
| Susan option | Full-height corner rotating units (rare, typically custom) can use a tall pole-mounted rotating shelf system spanning nearly the full height | ESTIMATE (basis: general full-height rotating-shelf hardware category; no corner-specific product captured) |
| Mount height AFF | Bottom sits at counter height (~36") rather than the standard 54" wall-cabinet start, since it spans the full height including the "wall cabinet + gap + base cabinet" zone as one unit | Derived from combining base-height (36") and wall-cabinet-top convention |
| Wall consumed per leg | 24"–27" typical, consistent with corner-box footprint conventions above | Derived |
| Crown/valance | Crown caps the top against the ceiling; if ceiling height is non-standard, scribe/filler strips at the top are typically needed | ESTIMATE (basis: general tall-cabinet-to-ceiling install practice) |
| Weight/mounting | Because it spans from base-cabinet height to ceiling, it is often structurally tied in at both the base level (resting on floor/kick, like a base cabinet) and secured to studs at the top, unlike a pure wall cabinet which hangs entirely from stud fasteners | ESTIMATE (basis: general full-height cabinet installation logic — a floor-resting tall unit is structurally different from a suspended wall cabinet) |
| Advantages | Maximizes corner storage volume in one visually clean unit; increasingly favored in 2026 design trend toward floor-to-ceiling built-ins | decorcabinets.com |
| Disadvantages | Highest cost and most custom-fabrication-dependent of all wall-corner types; top shelves may be effectively unreachable without a stool, especially in a corner where reach is already compromised | Derived |
| Cost tier | High (typically requires custom or semi-custom fabrication, not a stock SKU) | Derived |

---

## 11. Custom Angled (135°) Wall Corner Cabinet

For non-90°/non-45° corners (bay-window returns, angled walls), a bespoke cabinet with two stiles mitered at half the interior angle (67.5° each side for a 135° corner) to fill the space without a standard 90° or diagonal module.

| Property | Value | Source |
|---|---|---|
| Applicable corner angle | 135° interior angle (i.e., an obtuse corner, common where a wall is angled relative to an adjacent run rather than square) | woodweb.com, "Cabinets in a Wide-Angle Corner"; Fine Homebuilding forum, "Crown Molding 135 Degree Inside Corner" |
| Construction approach A | Hinge one larger door off the right-hand side of a smaller cabinet, with the mating door edges glued/mitered at 67.5° each (half of 135°) | WoodWeb (search synthesis of forum construction advice) |
| Construction approach B | Build as one continuous unit and use a lazy-susan-style pivot hinge with a magnetic catch to hold the door closed, rather than a conventional hinge pair | WoodWeb (search synthesis) |
| Stock availability | Not stocked — Decora and similar lines offer a "135 degree cabinet" as a named product concept, but this is a custom/semi-custom order category, not an off-the-shelf SKU with fixed dimensions | Houzz (Decora Corner Organization Solutions - 135 Degree Cabinet, product photo reference — no dimension table found) |
| Dimensions | No standard width/height/depth table found in sourced material — dimensions are project-specific, driven by the actual wall angle and available corner space | ESTIMATE (basis: nature of custom angled work; ranges below in the JSON are extrapolated from the 90°/diagonal corner envelope, not independently confirmed) |
| Hinge requirement | Either a standard hinge pair set at the 67.5°/67.5° mitered stile angle, or a pivot/lazy-susan-style corner hinge with magnetic catch (approach B above) | WoodWeb |
| Crown/valance | Same "die into stile / AFE / deepen box" tradeoff as §2, but the miter angle for crown returns must be custom-calculated per the actual wall angle (not the standard 22.5° used for a 90°/45° diagonal corner) | Derived from WoodWeb crown-transition logic (§2) generalized to non-standard angles; Fine Homebuilding thread specifically addresses 135° crown miter challenges |
| Mount height AFF | 54" standard convention still applies | Derived |
| Wall consumed per leg | Project-specific; no fixed convention | ESTIMATE |
| Weight/mounting | Same dual-leg stud-mounting principle, but stud layout rarely aligns conveniently with a non-90°/non-45° cabinet back, often requiring cleats or blocking | ESTIMATE (basis: general custom-angle-cabinet install logic) |
| Advantages | Only viable solution for genuinely non-square/non-45° corners (bay windows, angled additions); avoids leaving unusable trapezoidal gaps | Derived |
| Disadvantages | Fully custom fabrication — no stock hardware ecosystem, highest cost and longest lead time of all wall-corner types; crown/trim miters must be field-calculated | Derived |
| Cost tier | Highest (custom shop fabrication only) | Derived |

---

## 12. Cross-Cutting Placement & Mounting Conventions

**Mounting height (AFF).** The universal residential convention is **54" from the finished floor to the bottom of the wall cabinet**, derived as: 36" standard base-cabinet height + 18" standard reveal above the countertop = 54". If base-cabinet height, countertop thickness, or backsplash height deviate from standard, the wall-cabinet mount height must be adjusted by the same delta. This 54"/18" convention applies uniformly across all wall-corner types in this document unless a type-specific override is noted (none of the corner types above deviate from it, except the full-height corner unit in §10, which spans the entire zone). *Sources: kitchenseer.com ("How High Should Kitchen Wall Cabinets Be From The Floor"); bobvila.com ("Solved! How to Find the Correct Upper Cabinet Height").*

**Depth variants (12" / 15" / 24").** Standard wall-cabinet depth is **12"**. A **15"** depth upgrade is used to store oversize dinnerware/small appliances. A **24"** depth is used specifically for the cabinet directly above a refrigerator, to bring the cabinet face flush with a 30"–36"-deep fridge cabinet rather than leaving it recessed. For corner cabinets, depth increases (beyond 12") directly shrink the usable door-opening width per the WoodWeb tradeoff cited in §2 ("the deeper the cabinet, the smaller the door"), and increase the wall footprint consumed per leg roughly 1:1 with the added depth. *Sources: kitchencabinets-serr.com ("Wall Cabinet Depths Explained, 12 vs 24 Options"); elementskbf.com; WoodWeb (crown/depth tradeoff, §2).*

**Standard wall-cabinet heights.** 12", 15"/18" (over-range or accent), 24", 30", 36", 42" are the recognized stock height rungs across vendor catalogs; 30"/36"/42" are the three heights offered for essentially every corner type surveyed in this document. *Source: cross-referenced across Nelson Cabinetry, Home Depot/Hampton Bay, CabinetCorp, evafloors.com, Waverly Cabinets listings (§1–§4).*

**Range hood / cooking-surface clearance (adjacent, not corner-specific, but constrains corner placement near a range wall).** NKBA guidance: **24" minimum clearance** from cooking surface to a protected/noncombustible surface (e.g., a range hood) directly above; **30" minimum** to an unprotected/combustible surface (e.g., plain wall-cabinet bottom) above. Do not place a cooking surface under an operable window; window treatments above a cooktop must be non-flammable. *Source: Wholesale Cabinet Supply, "Kitchen Design Guidelines & Clearances | NKBA Standards Explained" (fetched).*

**Corner functional-storage rule.** NKBA design guidance states at least one corner cabinet in a kitchen should include a functional storage device (susan, pull-out, etc.) unless the kitchen genuinely has no corners — i.e., a plain blind corner with no accessibility hardware anywhere in the kitchen fails NKBA best practice. *Source: Wholesale Cabinet Supply (fetched), synthesizing published NKBA guideline language.*

**Weight/mounting — corner uppers carry through both walls.** Corner wall cabinets are, both legs, physically continuous with the return-wall cabinet runs and should be screwed into wall studs on **both** legs wherever stud layout allows, not just the leg that appears to bear the door/visible load. KCMA A161.1 certification testing loads a fully wall-mounted cabinet to 600 lb with no visible mounting-system failure, and separately loads shelves/bottoms at 15 lb/sq ft for 7 days — these are general (non-corner-specific) construction/mounting performance baselines that corner units must also meet to carry the certification seal. *Sources: KCMA A161.1-2022 (kcma.org, general reference, PDF not fully parsed in this pass); Woodworking Network ("The strength behind certified cabinetry: ANSI/KCMA A161.1"); general stud-mounting practice (garagejournal.com, woodworkingtalk.com — cross-domain, not cabinet-specific, used only to corroborate the "span multiple studs" principle).*

**Lazy susan sizing for wall/upper corner boxes.** Full-circle susans for a standard 12"-deep upper corner box run **18"–20"** diameter (2- or 3-shelf); kidney-shaped (soft rounded-triangle cutout) susans are the more common residential choice for 90° corners and are available as small as **10"** and up to **20"–22"** in wood-classic lines for wall application (larger 24"–32" diameter susans are base-cabinet, not wall-cabinet, products). Kidney susans require hinged doors and will not mount to any other door type. *Source: Rev-A-Shelf lazy-susan catalog (fetched — Full Circle 3072/3073 series 18"/20"; D-shape/wood-classic 4WLS series 20"/22"); wwhardware.com (Types of Lazy Susans, kidney-shape-for-90°-corners framing); kitchensource.com.*

---

## Sources

- KCMA (Kitchen Cabinet Manufacturers Association), "Cabinets Certified to Last" — https://kcma.org/insights/cabinets-certified-last-0
- KCMA A161.1-2022 standard (PDF) — https://kcma.org/sites/default/files/2024-08/KCMA%20A161.1%202022%20High%20Res.pdf
- KCMA, A161.1 Quality Certification — https://kcma.org/certifications/kcma-quality-cabinet-certification
- Woodworking Network, "The strength behind certified cabinetry: ANSI/KCMA A161.1" — https://www.woodworkingnetwork.com/cabinets/strength-behind-certified-cabinetry-ansikcma-a1611
- Shenandoah Cabinetry, Standard Cabinet Specs (PDF, fetched but not machine-readable in this pass) — https://shenandoahcabinetry.com/content/dam/sites/shenandoah-site/documents/catalogs-guides-and-planning-documents/Standard_Cabinet_Specs.pdf.coredownload.inline.pdf
- KraftMaid Momentum Spec Book, pages 46/48 (blind corner filler rule) — https://s3.amazonaws.com/FlippingBookStorage/KraftMaid%20Momentum%20Spec%20Book/files/assets/basic-html/page46.html , https://s3.amazonaws.com/FlippingBookStorage/KraftMaid%20Momentum%20Spec%20Book/files/assets/basic-html/page48.html
- Wellborn Cabinet, Literature Resources / technical resources — https://www.wellborn.com/literature-resources/technical-resources/
- Wellborn Cabinet, wall cabinet sizes bulletin (PS5-9-09, corner face-frame stile spec) — https://cis.wellborn.com/cms/images/stories/users/kroberson/PS5-9-09.pdf
- Fabuwood, digital spec book — https://ezpricing.fabuwood.com/specbook
- Barker Modern, 90° corner adjustable-shelf wall cabinet — https://www.barkermodern.com/product-p/wcladj90lm.htm
- Barker Modern, 1-door blind corner wall cabinet (blind left) — https://www.barkermodern.com/product-p/w1dblindcornerleftm.htm
- Barker Modern, blind corner wall cabinet product family (search listing) — https://www.barkermodern.com/product-p/w2dblindcornerleftm.htm , https://www.barkermodern.com/product-p/w1dblindcornerrightm.htm , https://www.barkermodern.com/product-p/w2dblindcornerrightm.htm
- WoodWeb, "Corner Cabinet Dimensions and Crown Moulding Transitions" — https://woodweb.com/knowledge_base/Corner_Cabinet_Dimensions_and_Crown_Moulding.html
- WoodWeb, "Cabinets in a Wide-Angle Corner" — https://woodweb.com/knowledge_base/Cabinets_in_a_WideAngle_Corner.html
- WoodWeb, "Kitchen Cabinet Clearance Above Stove Top" — https://woodweb.com/knowledge_base/Kitchen_Cabinet_Clearance.html
- Fine Homebuilding forum, "Crown Molding 135 Degree Inside Corner" — https://www.finehomebuilding.com/forum/crown-molding-135-degree-inside-corner
- Cabinet Joint, "How to Join Doors Using Corner Bi-Fold Hinges For a Base or Wall Pie Cut Cabinet (BCP or WCP)" — https://www.cabinetjoint.com/video-library/how-to-install-base-pie-cut-hinges-bpc/
- Rockler, Blum 170° Pie Corner Hinge Kit (frameless/inset) — https://www.rockler.com/blum-170-deg-pie-corner-hinge-kit-frameless-inset
- Rockler, Blum 170° Pie Corner Hinge Kit (face frame, 1/2" overlay) — https://www.rockler.com/blum-170-deg-pie-corner-hinge-kit-face-frame-1-2-overlay
- Rockler, Blum 170° Pie Corner Hinge Kit (frameless, full overlay) — https://www.rockler.com/blum-170-deg-pie-corner-hinge-kit-frameless-full-overlay
- D. Lawless Hardware, Pie Cut Corner Hinge — https://www.dlawlesshardware.com/piecutcohi.html
- HardwareSource, Blum Pie Cut Corner Hinge — https://www.hardwaresource.com/products/blum-pie-cut-corner-hinge , https://www.hardwaresource.com/products/generic-pie-cut-corner-hinge-bundle
- Blum, AVENTOS overview — https://www.blum.com/us/en/products/liftsystems/aventos/overview/
- Blum, AVENTOS HK-XS — https://www.blum.com/us/en/products/liftsystems/aventos-hk-xs/programme/
- Blum, AVENTOS HF — https://www.blum.com/us/en/products/liftsystems/aventos-hf/programme/
- Blum, AVENTOS HL — https://www.blum.com/us/en/products/liftsystems/aventos-hl/programme/
- Woodworker Express, Blum 20L2100.N5 Aventos HL lift mechanism — https://www.woodworkerexpress.com/blum-aventos-hl-lift-mechanism-set-door-weight-2lbs-2oz.html
- CabinetParts.com, Corner Appliance Garages — https://www.cabinetparts.com/g/corner-appliance-garages-g1426
- CabinetParts.com, Omega National A0100MUF1 (corner appliance garage, finger-lite track) — https://www.cabinetparts.com/p/omega-national-products-organizers-kitchen-organizers-ONPA0100MUF1-p32859
- CabinetParts.com, Omega National AG-100CSC (corner appliance garage, spring tension track) — https://www.cabinetparts.com/p/omega-national-products-organizers-kitchen-organizers-ONPAG100CSC-p32862
- Omega National, Corner Appliance Garage install notes (PDF) — https://downloads.cabinetparts.com/auto/ONP-A0100MUF1-Install.pdf
- Rev-A-Shelf, Lazy Susans (kitchen) — https://rev-a-shelf.com/kitchen/lazy-susans
- Woodworker's Hardware, "Types of Lazy Susans" — https://www.wwhardware.com/lazy-susan-guide
- KitchenSource.com, Lazy Susans for Upper and Wall Cabinets — https://www.kitchensource.com/uppercabinetorganizers/d/lazy-susans/
- Nelson Cabinetry, White Shaker 24" Wall Diagonal Corner Cabinet Glass Door — https://nelsonkb.com/product/white-shaker-24-wall-diagonal-corner-cabinet-glass-door/
- Nelson Cabinetry, Gray Shaker 24" Wall Diagonal Corner Cabinet — https://nelsonkb.com/product/gray-shaker-24-wall-diagonal-corner-cabinet/
- Nelson Cabinetry, White Shaker 24"x30" Diagonal Corner Wall Cabinet — https://nelsonkb.com/product/24-x-30-diagonal-corner-wall-cabinet/
- CabinetCorp shop, SG-DCW2436 Diagonal Corner Wall Cabinet, 24" (fetched, full spec) — https://shop.cabinetcorp.com/sg-dcw2436-diagonal-corner-wall-cabinets-24-inch.html
- Home Depot, Hampton Bay Courtland 24"x24"x30" Diagonal Corner Wall Cabinet (WD2430-CSW) — https://www.homedepot.com/p/Hampton-Bay-Courtland-24-in-W-x-24-in-D-x-30-in-H-Assembled-Shaker-Diagonal-Corner-Wall-Kitchen-Cabinet-in-Polar-White-WD2430-CSW/314765204
- Granite Factory Direct, WDC2412GD Shaker Wall Diagonal Corner Glass Door Cabinet — https://granitefd.com/products/wdc2412gd-wall-diagonal-corner-glass-door-cabinet
- ABCabinetry, Wall Diagonal Glass Door Corner Cabinets — https://www.abcabinetry.com/product/wall-diagonal-glass-door-corner-cabinets-lancaster-white/
- IKEA, SEKTION corner wall cabinet with glass door (26x15x40) — https://www.ikea.com/us/en/p/sektion-corner-wall-cabinet-with-glass-door-white-lerhyttan-black-stained-s39259362/
- evafloors.com, Wall Easy Reach Corner Cabinets — https://evafloors.com/product/wall-easy-reach-corner-cabinets/
- Waverly Cabinets, Wall Corner Easy Reach Cabinet Bifold Door (WC5005WER2424SO) — https://www.waverlycabinets.com/product/wc5005wer2424so/
- Wholesale Cabinet Supply (thewcsupply.com), Hanover White WER2436 Easy Reach Corner Cabinet — https://www.thewcsupply.com/products/hanover-white-wer2436
- E&B Cabinets, 24W-30H-12D Corner Easy Reach Wall Kitchen Cabinet (WER2430) — https://www.eandbcabinets.com/shop/p/24w-30h-12d-corner-easy-reach-wall-kitchen-cabinet-wer2430
- Wholesale Cabinet Supply, "Kitchen Design Guidelines & Clearances | NKBA Standards Explained" (fetched) — https://www.thewcsupply.com/pages/kitchen-design-guidelines-standard-clearances
- KabinetKing, Innovation Imperial Blue WOES1230 (open corner end-shelf cabinet) — https://www.kabinetking.com/innovation-imperial-blue-woes1230.html
- RTA Cabinets House, "Corner Kitchen Cabinet Dimensions | Lazy Susan & Blind Corner Sizes" (fetched) — https://rtacabinetshouse.com/blogs/cabinet-sizes-measurements/corner-kitchen-cabinet-dimensions
- CastaCabinetry, "Blind Corner Base Cabinet Dimensions [Ultimate Guide 2026]" — https://castacabinetry.com/post/blind-corner-base-cabinet-dimensions/
- CastaCabinetry, "Corner Cabinet Dimensions: Complete Guide 2026" — https://castacabinetry.com/post/corner-cabinet-dimensions/
- PrimeHomeAndGarden, "Blind Corner Cabinet – 36-42 In Wide, 24 In Deep Standard" — https://primehomeandgarden.com/blind-corner-cabinet-organizers/
- kitchenseer.com, "How High Should Kitchen Wall Cabinets Be From The Floor?" — https://kitchenseer.com/how-high-kitchen-wall-cabinets-from-floor/
- Bob Vila, "Solved! How to Find the Correct Upper Cabinet Height" — https://www.bobvila.com/articles/upper-cabinet-height/
- kitchencabinets-serr.com, "Wall Cabinet Depths Explained, 12 vs 24 Options" — https://www.kitchencabinets-serr.com/wall-cabinet-depth/
- Decor Cabinets, "20+ Ideas for Full Height Kitchen Cabinets from Floor to Ceiling" — https://decorcabinets.com/blog-full-height-kitchen-cabinets/
- kitchensearch.com, "How Tall Are Kitchen Cabinets? A Guide to Standard Heights and Sizes" — https://kitchensearch.com/how-tall-are-kitchen-cabinets/
- Houzz, Decora Corner Organization Solutions - 135 Degree Cabinet — https://www.houzz.com/photos/decora-corner-organization-solutions-135-degree-cabinet-kitchen-phvw-vp~113892609

---

```json
[
  {
    "type_id": "blind-wall-corner",
    "display_name": "Blind Wall Corner Cabinet",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 24, "typ": 30, "max": 36 },
    "wall_b_consumed_in": { "min": 12, "typ": 15, "max": 24 },
    "box_width_in": 30,
    "box_depth_in": 12,
    "height_in": [30, 36, 42],
    "mount_height_aff_in": 54,
    "filler_required_in": { "wall_a": 0, "wall_b": 3 },
    "door_config": "1-2 doors on exposed leg only; blind leg has no door",
    "hinge_requirement": "standard concealed European hinge, no elevated angle requirement",
    "mechanism": "none (fixed blind panel)",
    "min_adjacent_clearance_in": 3,
    "frame_styles": ["framed", "frameless"],
    "complexity": 2,
    "cost_tier": 1,
    "sources": [
      "https://www.barkermodern.com/product-p/w1dblindcornerleftm.htm",
      "https://s3.amazonaws.com/FlippingBookStorage/KraftMaid%20Momentum%20Spec%20Book/files/assets/basic-html/page46.html"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "diagonal-wall-corner",
    "display_name": "Diagonal Wall Corner Cabinet",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 24, "typ": 24, "max": 29 },
    "wall_b_consumed_in": { "min": 24, "typ": 24, "max": 29 },
    "box_width_in": 24,
    "box_depth_in": 12,
    "height_in": [12, 24, 30, 36, 42],
    "mount_height_aff_in": 54,
    "filler_required_in": { "wall_a": 0, "wall_b": 0 },
    "door_config": "single door, 45-degree angled face",
    "hinge_requirement": "standard concealed European hinge (110-125 deg), no special angle",
    "mechanism": "optional full-round or kidney lazy susan behind door",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["framed", "frameless", "shaker"],
    "complexity": 1,
    "cost_tier": 2,
    "sources": [
      "https://shop.cabinetcorp.com/sg-dcw2436-diagonal-corner-wall-cabinets-24-inch.html",
      "https://woodweb.com/knowledge_base/Corner_Cabinet_Dimensions_and_Crown_Moulding.html",
      "https://nelsonkb.com/product/white-shaker-24-wall-diagonal-corner-cabinet-glass-door/"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "pie-cut-wall-corner",
    "display_name": "Pie-Cut Wall Corner Cabinet",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 22.75, "typ": 24, "max": 27 },
    "wall_b_consumed_in": { "min": 22.75, "typ": 24, "max": 27 },
    "box_width_in": 24,
    "box_depth_in": 11.75,
    "height_in": [30, 36, 42],
    "mount_height_aff_in": 54,
    "filler_required_in": { "wall_a": 0, "wall_b": 0 },
    "door_config": "two doors, bi-fold hinged pair (single pie-cut front)",
    "hinge_requirement": "170-degree bi-fold corner hinge, two-stage (60deg clear, then 170deg full swing), 35mm cup, 3mm bore distance",
    "mechanism": "pie-cut lazy susan (kidney-adjacent) common companion hardware",
    "min_adjacent_clearance_in": null,
    "frame_styles": ["framed", "frameless"],
    "complexity": 3,
    "cost_tier": 3,
    "sources": [
      "https://www.cabinetjoint.com/video-library/how-to-install-base-pie-cut-hinges-bpc/",
      "https://www.rockler.com/blum-170-deg-pie-corner-hinge-kit-frameless-inset"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "easy-reach-wall-corner",
    "display_name": "Easy Reach Wall Corner Cabinet",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 24, "typ": 24, "max": 24 },
    "wall_b_consumed_in": { "min": 24, "typ": 24, "max": 24 },
    "box_width_in": 24,
    "box_depth_in": 12,
    "height_in": [24, 30, 36, 42],
    "mount_height_aff_in": 54,
    "filler_required_in": { "wall_a": 0, "wall_b": 0 },
    "door_config": "two independent bi-fold doors, reversible left/right",
    "hinge_requirement": "170-degree bi-fold hinge per door leaf",
    "mechanism": "none (bi-fold door is the accessibility mechanism)",
    "min_adjacent_clearance_in": null,
    "frame_styles": ["framed", "frameless"],
    "complexity": 3,
    "cost_tier": 2,
    "sources": [
      "https://evafloors.com/product/wall-easy-reach-corner-cabinets/",
      "https://www.thewcsupply.com/products/hanover-white-wer2436",
      "https://www.waverlycabinets.com/product/wc5005wer2424so/"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "corner-display-glass-wall",
    "display_name": "Corner Display / Glass Wall Cabinet",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 24, "typ": 24, "max": 26 },
    "wall_b_consumed_in": { "min": 12, "typ": 15, "max": 24 },
    "box_width_in": 24,
    "box_depth_in": 12,
    "height_in": [12, 30, 36, 40, 42],
    "mount_height_aff_in": 54,
    "filler_required_in": { "wall_a": 0, "wall_b": 0 },
    "door_config": "single glass door (diagonal face) or glazed panel on square-corner box, mullions optional",
    "hinge_requirement": "standard concealed European hinge, same as diagonal wall corner",
    "mechanism": "optional interior lazy susan (18-20 in full round) for display rotation",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["framed", "frameless", "shaker"],
    "confidence_note": null,
    "complexity": 1,
    "cost_tier": 3,
    "sources": [
      "https://nelsonkb.com/product/white-shaker-24-wall-diagonal-corner-cabinet-glass-door/",
      "https://www.ikea.com/us/en/p/sektion-corner-wall-cabinet-with-glass-door-white-lerhyttan-black-stained-s39259362/"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "open-shelf-wall-corner",
    "display_name": "Open Shelf Corner (Wall)",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 12, "typ": 24, "max": 24 },
    "wall_b_consumed_in": { "min": 12, "typ": 24, "max": 24 },
    "box_width_in": 12,
    "box_depth_in": 12,
    "height_in": [30, 36, 42],
    "mount_height_aff_in": 54,
    "filler_required_in": { "wall_a": 0, "wall_b": 0 },
    "door_config": "none (open shelving)",
    "hinge_requirement": "none",
    "mechanism": "none",
    "min_adjacent_clearance_in": 0,
    "frame_styles": ["frameless", "shaker", "open"],
    "complexity": 1,
    "cost_tier": 1,
    "sources": [
      "https://www.kabinetking.com/innovation-imperial-blue-woes1230.html",
      "https://decorcabinets.com/blog-full-height-kitchen-cabinets/"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "appliance-garage-corner",
    "display_name": "Appliance Garage (Corner)",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 16.75, "typ": 17, "max": 24 },
    "wall_b_consumed_in": { "min": 16.75, "typ": 17, "max": 24 },
    "box_width_in": 17,
    "box_depth_in": 11.875,
    "height_in": [18.5],
    "mount_height_aff_in": 36,
    "filler_required_in": { "wall_a": 0, "wall_b": 0 },
    "door_config": "tambour roll-up door, no swinging door",
    "hinge_requirement": "none (tambour track, not hinged)",
    "mechanism": "wood tambour on finger-lite or spring-tension track",
    "min_adjacent_clearance_in": null,
    "frame_styles": ["framed", "frameless"],
    "complexity": 4,
    "cost_tier": 3,
    "sources": [
      "https://www.cabinetparts.com/p/omega-national-products-organizers-kitchen-organizers-ONPA0100MUF1-p32859",
      "https://www.cabinetparts.com/g/corner-appliance-garages-g1426"
    ],
    "confidence": "verified"
  },
  {
    "type_id": "lift-door-corner-aventos",
    "display_name": "Lift-Door Corner (Aventos-style)",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 24, "typ": 24, "max": 27 },
    "wall_b_consumed_in": { "min": 24, "typ": 24, "max": 27 },
    "box_width_in": 24,
    "box_depth_in": 12,
    "height_in": [30, 36, 42],
    "mount_height_aff_in": 54,
    "filler_required_in": { "wall_a": 0, "wall_b": 0 },
    "door_config": "single or bi-fold lift-up door (no side-hinged swing)",
    "hinge_requirement": "not applicable (Blum AVENTOS HK/HL/HF lift mechanism replaces hinge)",
    "mechanism": "Blum AVENTOS lift system: HK/HK-S (single lift/stay), HL (parallel lift), HF (bi-fold lift)",
    "min_adjacent_clearance_in": null,
    "frame_styles": ["frameless"],
    "complexity": 5,
    "cost_tier": 4,
    "sources": [
      "https://www.blum.com/us/en/products/liftsystems/aventos/overview/",
      "https://www.blum.com/us/en/products/liftsystems/aventos-hf/programme/",
      "https://www.woodworkerexpress.com/blum-aventos-hl-lift-mechanism-set-door-weight-2lbs-2oz.html"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "stacked-wall-corner",
    "display_name": "Stacked Wall Corner Cabinet",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 24, "typ": 24, "max": 27 },
    "wall_b_consumed_in": { "min": 24, "typ": 24, "max": 27 },
    "box_width_in": 24,
    "box_depth_in": 12,
    "height_in": [60, 66, 72, 78, 84],
    "mount_height_aff_in": 54,
    "filler_required_in": { "wall_a": 0, "wall_b": 0 },
    "door_config": "lower box door/diagonal front + upper box open-shelf or glass door, independently doored",
    "hinge_requirement": "matches whichever type is used per stacked tier (see diagonal/pie-cut/open-shelf entries)",
    "mechanism": "none additional beyond component boxes",
    "min_adjacent_clearance_in": null,
    "frame_styles": ["framed", "frameless"],
    "complexity": 2,
    "cost_tier": 2,
    "sources": [
      "https://www.cliqstudios.com/kitchen-cabinets/wall",
      "https://planner5d.com/blog/standard-kitchen-wall-cabinet-height/"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "full-height-ceiling-corner",
    "display_name": "Full-Height / Ceiling-Height Corner Cabinet",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 24, "typ": 24, "max": 27 },
    "wall_b_consumed_in": { "min": 24, "typ": 24, "max": 27 },
    "box_width_in": 24,
    "box_depth_in": 12,
    "height_in": [84, 90, 96],
    "mount_height_aff_in": 36,
    "filler_required_in": { "wall_a": 0, "wall_b": 3 },
    "door_config": "single continuous tall door pair (diagonal or pie-cut bi-fold) or internally shelved pantry column with tall door",
    "hinge_requirement": "full-length concealed hinges, 3-5 hinge points per leaf for door height",
    "mechanism": "optional full-height pole-mounted rotating shelf system (rare, custom)",
    "min_adjacent_clearance_in": null,
    "frame_styles": ["framed", "frameless"],
    "complexity": 3,
    "cost_tier": 4,
    "sources": [
      "https://decorcabinets.com/blog-full-height-kitchen-cabinets/",
      "https://kitchensearch.com/how-tall-are-kitchen-cabinets/"
    ],
    "confidence": "estimate"
  },
  {
    "type_id": "custom-angled-135-wall-corner",
    "display_name": "Custom Angled (135°) Wall Corner Cabinet",
    "category": "wall-corner",
    "wall_a_consumed_in": { "min": 18, "typ": 24, "max": 36 },
    "wall_b_consumed_in": { "min": 18, "typ": 24, "max": 36 },
    "box_width_in": null,
    "box_depth_in": 12,
    "height_in": [30, 36, 42],
    "mount_height_aff_in": 54,
    "filler_required_in": { "wall_a": null, "wall_b": null },
    "door_config": "single larger door hinged off smaller cabinet with 67.5-degree mitered mating edges, OR pivot/lazy-susan-style door with magnetic catch",
    "hinge_requirement": "standard hinge pair set at 67.5/67.5 mitered stile angle, or pivot corner hinge with magnetic catch",
    "mechanism": "none standard; occasionally a pivot lazy-susan-style door mechanism",
    "min_adjacent_clearance_in": null,
    "frame_styles": ["custom", "framed", "frameless"],
    "complexity": 5,
    "cost_tier": 5,
    "sources": [
      "https://woodweb.com/knowledge_base/Cabinets_in_a_WideAngle_Corner.html",
      "https://www.finehomebuilding.com/forum/crown-molding-135-degree-inside-corner"
    ],
    "confidence": "estimate"
  }
]
```
