# 3D Viewer Improvement Plan

**Status:** authored 2026-06-24 from end-to-end test feedback; not yet executed.
**Owner:** TBD (whoever picks up the next session).
**Source-of-truth file:** `addons/southbrook_estimating/static/src/js/cabinet_viewport.esm.js` (1043 lines).

## Origin

Customer end-to-end test of the Configure Product wizard reported the 3D
preview reads as a "dark undefined" brown box — the configured cabinet
doesn't feel like the configuration it represents. Root-cause analysis
landed three intertwined causes (lighting, materials, geometry) and a
fourth category of UX friction in the wizard around it (modal pickers,
price feedback, step flow).

This document is the executable plan. Phases are ordered by impact-per-hour.

## Baseline (what's already in place — verified 2026-06-24)

Spot-checking `cabinet_viewport.esm.js` shows the foundation is more
complete than the test report assumed:

| Renderer config | Status | Line |
|---|---|---|
| `antialias: true` | ✅ in | ~132 |
| `outputColorSpace = SRGBColorSpace` | ✅ in | ~136 |
| `toneMapping = ACESFilmicToneMapping` | ✅ in | ~138 |
| `toneMappingExposure = 1.0` | ✅ in | ~139 |
| Lights: hemisphere + 2 directional | ✅ in (intensities 0.5 / 0.9 / 0.3) | ~160-188 |
| Materials: `MeshStandardMaterial` (PBR-ready) | ✅ in | ~233-264 |
| **HDRI env map** | **❌ missing** | (no RGBELoader / EquirectangularReflectionMapping) |
| **Background**: plain `#fbf7ef` color | functional, not "studio" | ~151 |
| **Material roughness/metalness tuning per attribute** | not done — all carcass/door/etc use defaults | ~233-264 |
| **Geometry**: parametric carcass with attribute-driven detailing | not done — flat box | TBD audit |
| **Shadows** | not configured | TBD audit |
| **Camera fit/reset on attribute change** | TBD audit | TBD |

So Phase 1 below is mostly *tuning + env-map* rather than a from-scratch
PBR rebuild — meaningful, but smaller than the original spec implied.

---

## Phase 1 — Lighting + Materials + Environment Map

**Goal:** make the cabinet read as a real finished surface in 30 seconds of
look-time. Highest impact per hour. No data-model changes; entirely
self-contained in the viewport file + a vendored HDRI asset.

**Estimated effort:** half day, including visual iteration.

### Scope (in)

1. **HDRI environment map** — vendor a small studio HDRI (e.g. `studio_small_08_1k.hdr`
   from Poly Haven, CC0) at
   `addons/southbrook_estimating/static/lib/hdri/studio_small_08_1k.hdr`.
   Wire via `RGBELoader` → `EquirectangularReflectionMapping` → assign
   to `scene.environment` (NOT `scene.background` — keep the existing
   warm-paper color as the visible backdrop so the page chrome stays
   the same; env map only feeds reflections / ambient PBR lighting).
   The env map alone is what transforms `MeshStandardMaterial` from
   "matte cardboard" to "finished surface" because it gives the
   material something to reflect.

2. **Three-light studio rig** — replace the current 2-dir + 1-hemi setup with:
   - **Key**: `DirectionalLight(0xffffff, 1.2)` from front-upper-left
     (cabinet's perspective), positioned `(-3, 4, 3)`, with shadows enabled.
   - **Fill**: `DirectionalLight(0xfff5e6, 0.4)` from front-upper-right
     (~33% of key intensity, slightly warm), positioned `(3, 2, 2)`,
     no shadows. Lifts the front face out of black.
   - **Rim/back**: `DirectionalLight(0xffffff, 0.5)` from behind-above,
     positioned `(0, 3, -4)`, no shadows. Separates the cabinet from
     the background.
   - Keep the **HemisphereLight** but drop intensity to 0.2 (HDRI now
     does most of the ambient work). Warm-from-above (`0xffeed4`),
     cool-from-below (`0xc4d5e0`).
   - Net: 4 lights instead of 3, but the second directional ("dirB" at
     line ~182) is replaced rather than added.

3. **Material per-attribute tuning** — current materials are all
   defaults on `MeshStandardMaterial`. Without textures, tune
   `roughness` / `metalness` to produce believable surfaces:
   - **Carcass** (interior side of box): `roughness=0.85, metalness=0.0`
     — matte melamine reads correct.
   - **Door** (the visible front): driven by Finish attribute —
     `Stain` → `roughness=0.45`, `Paint` → `roughness=0.7`,
     `Matte` → `roughness=0.95`. Color from Finish.
   - **Worktop**: `roughness=0.5, metalness=0.0` for natural wood,
     `0.2 / 0.3` for stone-look.
   - **Hardware** (handles, hinges, pulls): NEW separate material —
     `MeshStandardMaterial({metalness: 0.9, roughness: 0.3})` with
     color from Pull Finish. Polished Nickel → `0xc8c8d0`,
     Matte Black → `0x202020`, Brushed Brass → `0xb5926a`.
     This is what makes the hardware READ as metal.

4. **Soft contact shadows** — enable `renderer.shadowMap.enabled = true`
   + `shadowMap.type = PCFSoftShadowMap`. Key light casts shadows,
   fill/rim do not (perf + visual cleanliness). Add a shadow-catcher
   plane below the cabinet — `ShadowMaterial({opacity: 0.3})`.

### Out of scope (explicitly NOT in Phase 1)

- Per-species wood-grain texture / normal map (Phase 1 ships color +
  roughness + env reflection only — that's the 80% win; full PBR
  textures are Phase 1.5 if needed).
- Geometry changes (Phase 2).
- UI / wizard changes (Phase 3).
- Per-template HDRI variants (one neutral studio HDRI for all cabinets).
- Animated transitions when attribute changes.

### Files to touch

- `addons/southbrook_estimating/static/src/js/cabinet_viewport.esm.js`
  - lines ~132-139: renderer config (add `shadowMap.enabled = true`)
  - lines ~149-188: scene + lights (replace dirA/dirB/hemi block,
    add env-map setup via RGBELoader)
  - lines ~233-264: material defs (per-attribute roughness/metalness,
    new hardware material)
- `addons/southbrook_estimating/static/lib/hdri/` (NEW dir + 1 HDR file
  + LICENSE.txt noting CC0 source)
- `addons/southbrook_estimating/__manifest__.py`: add HDR file to
  `assets.web.assets_backend` (or a new bundle if needed for binary)
- Bump version: 19.0.4.7.0 → 19.0.4.8.0

### Acceptance criteria

- Visual: open the configurator on Base Cabinet · 4-Drawer Pot.
  Front face is no longer black. Door reads as wood with a believable
  finish (specular highlight from env map visible). Hardware reads
  as metal, not painted plastic. Cabinet sits in space with a soft
  shadow beneath it.
- Render performance: still 60 fps on a recent MacBook Air (env map
  doesn't tank perf at the 1k HDR size).
- A/B compare: drop a screenshot before and after to a
  `docs/3d_viewer_phase1_before_after/` folder for the record.
- Existing "Blueline" toggle still works (it switches to
  `MeshBasicMaterial` — unaffected by env map).

---

## Phase 2 — Parametric front-face geometry

**Goal:** make the geometry express the configuration. Currently a
4-drawer Shaker cabinet with bar pulls renders as the same brown box
as a 1-door Slab cabinet. After Phase 2, the silhouette reflects
drawer count, door style, and handle.

**Estimated effort:** 1-2 days. Significantly bigger than Phase 1
because every attribute-driven detail is its own geometry generator.

### Scope (in)

Parametrically generate the front face from the configured attributes:

- **Drawer count** (from template + Width): inset N drawer-front panels
  with realistic gaps. Drawer height divided proportionally, with the
  top drawer often slightly smaller.
- **Door style** = Shaker: recessed frame extrusion on each door front
  (frame thickness ~5cm, center panel inset ~6mm).
- **Door style** = Raised Panel: chamfered center panel.
- **Door style** = Slab: flat panel (current default).
- **Handle/Pull**: simple parametric mesh (Bar Pull = horizontal cylinder
  with end caps, Knob = sphere) positioned per the Handle Placement
  rule (top-center on doors, top-edge on drawers).
- **Toe-kick recess** at base: ~10cm tall, ~5cm deep, color matching
  carcass.
- **Finished side panels**: extend the door material around the
  exposed side(s) when the Finished Sides attribute is set.

### Out of scope (explicitly NOT in Phase 2)

- Hinges (visible at the door edges) — defer to Phase 2.5 if needed.
- Crown molding on top of wall cabinets.
- Interior detailing (shelves, drawer interiors) — Blueline view
  already exposes these; solid mode keeps them implicit.

### Files to touch

- `addons/southbrook_estimating/static/src/js/cabinet_viewport.esm.js`
  - Likely a new section / class for "front face builder" that takes
    the attribute dict and returns a `THREE.Group` of meshes.
  - Replace the current single-quad door geometry with the new
    builder's output.
- Possibly split into a new file
  `addons/southbrook_estimating/static/src/js/cabinet_front_builder.esm.js`
  if cabinet_viewport.esm.js grows past 1500 lines.
- Bump version.

### Acceptance criteria

- A 4-drawer cabinet shows 4 drawer fronts (not a single door panel).
- A Shaker door shows the recessed frame; a Slab door doesn't.
- Bar pulls appear at the right position on doors vs drawers.
- Toe-kick recess visible at the base of base cabinets.
- Existing template list (35 SB-* cabinets) all render without
  geometry errors — test by walking 5 cabinets of different types
  (4-drawer, sink, corner, wall, vanity).

---

## Phase 3 — Wizard UX (inline pickers, price feedback, step flow)

**Goal:** reduce friction in the configurator wizard itself. The 3D fix
makes the preview look right; the wizard fix makes USING it feel right.

**Estimated effort:** 1-2 days. Most of this is OCA wizard inheritance,
which has the usual "don't touch OCA core, override carefully" complexity
per CLAUDE.md §3.

### Scope (in)

1. **Inline option pickers for short option sets** — replace the
   full-modal "Search:" dialog with:
   - Image/swatch tiles for visual attributes (Finish, Wood Species,
     Door Style, Pull Finish) — actual color swatches and small
     thumbnails.
   - Segmented buttons / radio chips for small enumerations (Width,
     Frame Style, Finished Sides — anywhere with ≤6 options).
   - Reserve the search modal only for genuinely long lists (e.g.
     Accessories with sub-options).

2. **Continuous price feedback**:
   - Per-option delta inline next to each selectable value
     (e.g. "Soft-Close +$15.00", "LED +$125.00") — visible BEFORE
     the user picks.
   - Persistent price/weight summary pinned beside the 3D view
     (currently buried below the fields).
   - Live breakdown: "base $545 + options $570 = $1,115".

3. **Step flow + confirmation**:
   - Add a final summary/confirmation step that lists every chosen
     attribute with its price contribution.
   - Rename the final step's button "Next" → "Confirm configuration".
   - Make the completed-step badges in the step bar clickable for
     jumping back without repeated "Back" clicks.
   - Surface required attributes; disable invalid combinations with
     a short reason (don't allow dead-ends).

4. **Smaller polish**:
   - Two-column layout on wider viewports: controls left, sticky 3D
     preview right.
   - "Blueline" → "Blueprint" / "Realistic" label change (less jargon).
   - Add viewer affordances: orbit/zoom/reset icons + preset camera
     angles (Front / Three-quarter / Top).
   - "Fit/reset camera" framing on load and on attribute change so
     the model doesn't drift off-center.

### Out of scope (explicitly NOT in Phase 3)

- Mobile-specific layout (kept as Phase 4 if a customer-mobile flow
  is in scope — the wizard is primarily a sales-rep tool).
- Multi-language support beyond what OCA already provides.
- Per-user "saved configurations" feature.

### Files to touch

- `addons/southbrook_estimating/static/src/xml/cabinet_viewport.xml`
  (Blueline label, viewer affordances).
- New view inherit XML for the OCA wizard:
  `addons/southbrook_estimating/views/product_configurator_wizard_inherit.xml`
  (or similar). Hide single-value attributes (the Family/Cabinet Style
  case from the prior fix round); restyle selectors as swatches.
- New Owl component for the inline swatch picker (if the OCA wizard's
  field rendering can be swapped for a custom widget).
- Possibly a new OWL component for the price-breakdown sidebar.
- `addons/southbrook_estimating/__manifest__.py` for any new
  asset bundle entries.

### Acceptance criteria

- Picking a Finish or Door Style does NOT open a modal — values are
  visible inline as swatches.
- Each option shows its price delta in-place.
- A persistent price summary is visible while the user changes options
  (not below-the-fold).
- The final step says "Confirm configuration" with a summary of all
  picks before commit.
- Step-bar badges for completed steps are clickable.

---

## Cross-cutting: phasing rationale + how to validate

- **Phase 1 first** because lighting/materials/env-map is universally
  impactful (every cabinet looks better immediately) and has zero data-
  model risk. Half-day of work changes the entire first-impression of
  the configurator.
- **Phase 2 next** because once Phase 1 makes the surface look real, the
  "but it's just a box" complaint becomes the next obstacle. Phase 2
  takes 1-2 days but every cabinet benefits.
- **Phase 3 last** because the wizard UX work touches OCA inheritance
  which is the highest-risk area per CLAUDE.md ("don't touch OCA
  directly"). Worth doing on a fresh day with full attention.

**Validation method for each phase:** walk a diverse set of templates
through the configurator after the phase ships — recommend 5 cabinets
of different types:

- Base Cabinet · 4-Drawer Pot (SB-BASE-4DRW) — the original test case
- Base Cabinet · Single Door (SB-BASE-1DR) — slab door baseline
- Wall Cabinet · Glass Door (SB-WALL-GLASS) — transparency / interior
- Tall Pantry · Pull-Out (SB-TALL-PANTRY-PO) — height + drawer mix
- Corner Cabinet · Lazy Susan (SB-CORNER-LSUSAN) — complex geometry

A/B screenshots before and after each phase, dropped in a sibling docs
folder, are the artifact record.

## Adjacent work this plan does NOT cover

- **Variant SKU + standard_price** (Bug #3 from end-to-end test) — needs
  a `product.config.session.create_get_variant` override in southbrook
  code. Separate ticket.
- **Wizard final "Next" button label** (Bug #4) — would naturally land
  in Phase 3 alongside the step-flow work.
- The 3D viewer ALSO renders in the customer-facing portal page; this
  plan focuses on the sales-rep wizard surface. Audit needed to confirm
  both surfaces benefit from the same viewport module (likely yes).
