# Phase 2 charter — OWL portal Order Builder as the primary dealer surface

**Decision date:** 2026-05-30
**Decided by:** John (project owner)
**Supersedes:** Build Spec §2.1 / §2.2 (the dual-persona two-surface model)

## The pivot

The original Build Spec planned two distinct surfaces:

- **Persona A** (customer) — `/kitchen-planner` one-page SPA
- **Persona B** (dealer / sales rep) — backend Order Builder under Sales menu

Phase 1 shipped Persona B's backend Order Builder. At Phase-1 gate review
John reframed the question: **what if the dealer's primary surface IS
the page, not the backend?** Three options were laid out:

| | Option | Tradeoff |
|---|---|---|
| A | Two surfaces (original brief) | Dealer learns separate UI; two UIs to maintain |
| B | SPA-only (full pivot) | Every backend power feature reproduced in OWL+JS |
| **C** | **SPA-primary + backend escape hatch (CHOSEN)** | Dealer uses SPA for 80% of work; backend remains for power ops |

**Choice: Option C.**

## What that means

The Phase 1 backend Order Builder stays live and supported as the
**escape hatch**. It is NOT removed. Power operations stay native:

- Channel pricelist override (manual swap)
- BoM preview tab (with all OCA computed fields)
- Stage pipeline + manual stage transitions
- MO confirmation cascade
- Cross-record mass-edit
- Accounting integration touchpoints
- Multi-customer search / list views

Phase 2 introduces the **primary dealer surface** as an OWL-based
portal application at a route on `southbrookcabinetry.space/my/...`.
That portal app — not the Odoo backend — is where dealers spend their
day. The portal app and the backend share the same `sale.order` +
`product.config.session` records, so an order created in either
surface is the same order, just viewed differently.

## The canonical build targets

Two HTML mockups in `docs/` define the Phase-2 target:

- **`docs/southbrook_owl_mockup.html`** — the NEW primary build target.
  The portal-mounted OWL component tree (`<OrderBuilder/>` → 11 child
  components), the JSON-RPC reactivity pattern, the Sky/Walnut/Linen
  palette, the inline `<ConfigDrawer/>` autosave, the 5-cell header
  strip, the multi-zone collapsible grid, the BoM preview / validation
  / history / customer-print tabs. **This is what Phase 2 must ship.**

- **`docs/southbrook_internal_order_builder.html`** — the existing
  internal mockup. Captures the structural fidelity of the backend
  form (the Phase-1 deliverable). Kept as reference because its
  layout proportions, stage pipeline, and zone grid match the
  OWL mockup almost cell-for-cell; the backend stays usable.

## Implementation discipline

The Phase-2 OWL portal app must:

1. **Mount into a portal page** at `/my/southbrook/order-builder/<id>`
   (route added by `southbrook_estimating_website` addon, NOT
   `southbrook_estimating`). The engine (controllers + JSON-RPC
   endpoints) stays in `southbrook_estimating`; the portal route +
   view + OWL asset bundle stays in the website addon.

2. **Share data with the backend** via the same `sale.order` records
   and the same channel-pricelist resolver. An order created in the
   OWL portal MUST appear identically in the backend Order Builder,
   and vice versa.

3. **Component tree per the OWL mockup**: 11 components, exactly the
   set + names + nesting shown in `southbrook_owl_mockup.html`.

4. **Use OWL idioms** — `useState()` reactivity, `useService('orm')`
   for RPC, `<t-on-click>` template event binding. Avoid one-off
   jQuery / vanilla DOM patches. Each component carries `static
   template = "southbrook_estimating_website.<ComponentName>"` and
   a paired `templates/<ComponentName>.xml`.

5. **Trace-friendly RPC**: the mockup includes an RPC trace pane that
   flashes on every `orm.call`. Phase 2 should ship a dev-mode-toggled
   version of that trace pane so John can debug live behavior at gate
   review.

6. **Customer-flow variant via mode toggle, not a separate app**: the
   same `<OrderBuilder/>` root accepts a `mode` prop (`'dealer' |
   'customer'`). Customer mode hides BoM Preview, Validation,
   History, and Customer Print tabs; locks Channel to retail; gates
   action_confirm behind a salesperson approval. Per Build Spec §2.3
   ("There must not be two configurators"), this is the same app
   in two visual configurations, not two apps.

## Amendment 1 (2026-05-30) — Three.js viewport in backend NOW (Track 1)

Original charter put Three.js + the 18 parametric element types in Phase 3.
After a second gate review, John elected reading **A**: the OWL portal
work (Track 2) proceeds as charted, AND a Prodboard-class 3D viewport
lands in the **backend** Order Builder form view immediately as a
parallel Track 1.

Two tracks now run in parallel:

| Track | Surface | Deliverable | Status |
|---|---|---|---|
| 1 | Backend (sale.order form) | Three.js viewport pane: parametric BufferGeometry from selected line's W/H/D + attrs, solid↔blueline toggle, dimension overlay, ACES Filmic + sRGB. | NEW — open questions below. |
| 2 | Portal (`/my/southbrook/order-builder/<id>`) | 14-step OWL component-tree app per `docs/southbrook_owl_mockup.html`. 2D-first; the 3D layer back-ports from Track 1 to portal as Phase 2.5. | As charted — 4 open questions still open. |

Discipline for Track 1:

- Three.js viewport mounts INTO the existing backend Order Builder form
  view (an OWL component embedded via `<field widget="..."/>` or as a
  notebook tab — choice gated on open question T1Q2 below). The
  Phase-1 backend form survives as escape hatch UI; the viewport adds
  to it, doesn't replace it.
- Parametric carcass per `PRODBOARD_MANIFEST.md` §5: 18 element types
  emit their own `BufferGeometry`. Phase-1's `mrp.bom._compute_panel_dimensions`
  (the 7-routine register Item #1) IS the geometry source — the same
  named constants (BOX_TH, BACK_TH, DOOR_TH, etc.) drive the mesh.
  Don't fork.
- Solid↔blueline toggle as per manifest §3: blueline draws auto-dimensioned
  isometric lines derived programmatically from the bounding box.
- ACES Filmic tone mapping, sRGB output, KTX2/Basis Universal textures,
  MeshBVH for picking, scene-diff updater per manifest §10. No
  re-mount on prop change.

## Open questions for Track 1 (backend 3D)

These need answers before commit 1 of Track 1 lands. (Track 2's own
four open questions are unchanged from the original charter.)

- **T1Q1 — Three.js delivery.** Vendor into `static/lib/` (offline, repo
  size +~600KB minified), or load from CDN (zero repo bloat, but offline
  install / air-gap deploys break). **Recommended:** vendor — Phase 1
  already cares about clean offline installs (NF1 mako lesson).
- **T1Q2 — Mount point.** Three.js viewport as (a) a new notebook tab
  on the sale.order form ("3D Preview" alongside BoM Preview), or (b)
  a stacked panel ABOVE/BELOW the order_line grid (always visible), or
  (c) a side panel to the RIGHT of the order_line grid (Prodboard-style
  but in backend). **Recommended:** (c) — matches Prodboard's flex
  viewport pattern, lets sales rep see the cabinet update as they edit
  attributes. (a) is the lowest-friction Odoo-native; (b) wastes
  vertical space.
- **T1Q3 — What renders?** The currently-selected line's single cabinet,
  OR the whole kitchen run (all lines positioned along an X axis with
  zone separators). **Recommended:** start with single cabinet (Phase
  3 / Track 2 polish brings the run view). The selected-line approach
  is the right Track-1 MVP because it proves the parametric BufferGeometry
  pipeline; the multi-cabinet kitchen view is layout logic on top.
- **T1Q4 — Element type coverage on day 1.** Manifest §5.2 lists 18
  element types (hinge_block, drawer, delimiter, etc.). Day-1 coverage
  options: (a) just `carcass + door + drawer` (3 types — covers wall/
  base/drawer_bank cabinets, ~70% of templates), or (b) the full 11
  minimum types from the brief, or (c) all 18. **Recommended:** (a)
  for Track 1 — get the rendering pipeline working with 3 types, then
  iteratively add. Phase 3 polish covers the remaining 15.

## Out of scope for Phase 2 (unchanged for Track 2; Track 1 supersedes some)

- **Three.js / WebGL scene in PORTAL** — still Phase 3 for the portal.
  Track 1 brings it forward in the BACKEND only.
- **Prodboard 58/394/flex three-pane layout** — still Phase 3 even in
  backend. Track 1 ships the viewport pane only, not the catalog
  pane + tool rail rebuild.
- **Mobile** — unchanged; mobile remains Phase 3 / v2.
- **Payment** — unchanged; still v2.

## Original Phase 2 / Phase 3 split (preserved for reference)

The previous out-of-scope text below was written before the amendment.
Marker for the diff:

---

## Out of scope for Phase 2 (PRE-AMENDMENT)

- **Three.js / WebGL scene** — Phase 3. The OWL mockup is intentionally
  2D-first. Phase 2 ships without the 3D viewport, without the 18
  parametric element types from PRODBOARD_MANIFEST §5.2, without the
  solid↔blueline toggle, without ACES Filmic / KTX2 / MeshBVH.

- **Prodboard 58/394/flex three-pane layout** — that's the Phase-3
  shell when the 3D viewport lands. Phase 2 uses the OWL mockup's
  single-pane vertical layout (titlebar / stages / header strip /
  tabs / zone groups). The 58/394/flex layout slots IN to phase 3
  when the viewport joins.

- **Mobile** — Phase 2 ships desktop + tablet. Mobile is a graceful
  degradation in Phase 3 along with the 3D constraint.

- **Payment** — still v2 per the original brief.

## Phase-2 commit lineup (proposed)

To be confirmed before any code lands:

1. Scaffold `southbrook_estimating_website` addon — manifest, depends,
   portal route stub, security ACL for portal users.
2. Empty OWL mount point — portal page renders an empty
   `<div id="order_builder_root"/>` and the OWL `<OrderBuilder/>`
   root component prints "hello from OWL" reactively.
3. Static palette / type / token CSS — Sky/Walnut/Linen + Roboto
   Flex variable font loaded into the portal asset bundle.
4. JSON-RPC controller — `/southbrook/api/order/<id>` returns a
   normalised order shape (partner, channel, lines grouped by zone,
   header totals). Same data the existing backend computes; just
   shaped for client consumption.
5. `<OrderBuilder/>` root + reactive state store wired to `(4)`.
6. `<HeaderStrip/>` (5 cells) — first visible deliverable, renders
   from store, reactive to RPC.
7. `<StagePipeline/>`, `<OrderTitlebar/>`, `<IllustrativeBanner/>` —
   the surrounding chrome.
8. `<TabBar/>` + tab-panel routing (client-side, no RPC).
9. `<ZoneGroup/>` + `<OrderLine/>` — multi-zone grid populates from
   store; click-to-select; collapse/expand.
10. `<ConfigDrawer/>` — inline live-edit with autosave RPC; this is
    the one that proves the reactivity story.
11. `<BoMPreview/>`, `<ValidationStrip/>` — read-only tab content.
12. `<FooterActions/>` — action buttons (Save, Confirm, Duplicate,
    Customer Print) wired to existing model methods.
13. Customer-mode toggle — same `<OrderBuilder/>` root, `mode` prop
    flips visibility of BoM/Validation/History tabs and locks
    channel.
14. Gate review with John against the mockup.

Each step is its own commit. After step 6 John has a visible deliverable;
after step 10 the reactivity story is proven; after step 13 the customer
mode lands. The 14-step lineup is roughly 2 weeks of work if each step
is a half-day average.

## Open questions for John before commit 1

- Confirm portal route — `/my/southbrook/order-builder/<id>` or
  shorter `/builder/<id>`?
- The mockup shows breadcrumbs `Home › My Account › Order Builder ›
  SO-...` — is the portal frame (brandbar, sidebar) provided by
  `website` / `portal` already, or do we render our own per the
  mockup?
- Auth model — dealer users get a portal user under their dealer
  `res.partner` (parent_id chain), or a regular internal user with a
  specific group? The mockup assumes "Sarah Kowalski · Image Floor ·
  Dealer" which reads like a portal user.
- Asset bundle — `web.assets_frontend` (portal) or a dedicated
  `southbrook_estimating_website.assets`? The latter avoids polluting
  unrelated portal pages with OWL components they don't use.
