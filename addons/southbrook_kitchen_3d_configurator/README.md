# Southbrook Kitchen 3D Configurator

Isometric Three.js kitchen room configurator backed by live Odoo
cabinet inventory — design, save, and quote. Odoo 19.0 CE.

**Hard dependency:** `southbrook_estimating` (vendored Three.js r160,
the channel-pricelist resolver, the Q8 canonical cabinet catalog, the
pure `kitchen_layout_engine`, and `southbrook.placement.rule` — the
rules-as-data corner layer). Canonical design docs:
`docs/superpowers/specs/2026-07-27-kitchen-templates-design.md` and the
matching plan in `docs/superpowers/plans/`.

## Kitchen Templates (5.28.0 – 5.33.0)

Prebuilt sample kitchens ("Start from Template" in the configurator's
top frame, next to the room dimensions): pick a shape, a cabinet
count, a module width and appliance sizes — the design lands fully
arranged, corner units included. The point: corner-bearing kitchens
are the hardest to quote and build from scratch, so they ship
pre-engineered — fast, easy, and correct for user and system.

### Data model (slots, not SKU pins)

- `southbrook.kitchen.template` — shape (`southbrook.room`'s
  `_LAYOUT_SHAPES` lexicon, reused not forked), default room dims,
  default module width, count bounds, generated top-view SVG thumbnail.
- `southbrook.kitchen.template.line` — a SLOT: `slot_code`,
  `cabinet_type` (base/wall/tall/corner/appliance), `wall` + `run_seq`
  (the whole spatial contract — no geometry fields), `nominal_width_in`
  (0 = parametric module width), optional `archetype_id` preference or
  hard `product_id` pin, `repeat_ok` (count growth happens by cloning
  these), `priority` (higher drops first).
- Shipped catalog: `data/kitchen_templates.xml` (`noupdate="0"` — a
  dimension correction lands via `-u`, no code deploy). Active:
  L-10X8 (flagship), SW-08, SW-12, GAL-08, GAL-10. Inactive honest
  placeholders: PEN-10X10 (needs free-anchor peninsula runs),
  H-14X12 (needs multi-run-per-wall + gaps).

### Resolver contract (`_resolve_slot`)

Hard pin → archetype link (width match preferred) → cabinet_type +
exact width among variant-bearing flagged cabinets → **empty** =
unresolved. Unresolved slots become VISIBLE placeholder lines
(SBK-UNRESOLVED, blocking `UNRESOLVED_SLOT` production check) — never
silently dropped or substituted. Appliance slots resolve to the
SBK-APPL-* stand-ins (zero-priced design lines whose front clearances
feed the motion-envelope validator via placement rules). Only
templates with existing variants qualify — the canonical Q8 catalog is
OCA-configurable with zero variants until a config session builds one.

### Parametric fill math (`parametric_fit`)

Per-wall run arithmetic: each wall's fixed slots + corner claims
consume its run; repeat slots grow only within THEIR wall's leftover
capacity (`floor(usable / module_width)`); corner slots claim the
engine's leg footprint on BOTH junction walls, absorbing leading floor
slots that fit fully inside the corner cell (mirrors the engine's
substitution semantics). UI-grade bound only — the authoritative check
stays `LayoutCapacityExceeded` at `action_auto_arrange` time. The room
is NEVER grown to fit; misfits refuse with a plain message.

### Manipulation API (server-side, canonical-only)

- Design: `action_flip_layout(axis="x"|"z")`, `action_rotate_layout
  (quarters)`, `action_reflow()` (thin auto-arrange alias).
- Line: `action_swap_product(product_id)`, `action_set_width(width_in)`,
  `action_move(wall, run_seq)`.

Every action rewrites ONLY canonical semantics (wall/run_seq/product/
width) and re-derives ALL poses via `action_auto_arrange` — poses are
never transformed numerically. Savepoint-atomic; a change the engine
would "fit" by archiving the cabinet is refused instead. Derived lines
(corners/fillers) are engine-owned and refuse manipulation. Named
`flip`, not "mirror" — `southbrook.design.reconcile` owns that word.

### Honesty guarantees

- No silent room growth anywhere: server (`UserError` on misfit),
  client (overflow warns, never mutates the room), resize route
  (`/rearrange` reverts a non-fitting resize server- and client-side).
- Unresolved slots are seen, counted, and block production readiness.
- `total_cabinets` counts cabinets; `filler_count` counts strips.
- Corner geometry and LH/RH product choice are engine-derived from the
  junction's handedness — never templated.

### Automation hook

`window.__sbk.getLayout()` → read-only deep-copied snapshot of the
open design: `[{id, sku, wall, x_position_in, width_in, cabinet_type,
is_filler}]`. Fixed key contract; never a mutation surface. Installed
on mount, removed on unmount.

## Tests

- Python: `--test-tags kitchen_templates` (33 tests) or the full
  `southbrook_kitchen_3d_configurator` tag.
- Node (no browser needed): `cd tests/node_js && npm ci && npm test`
  (69 contracts, jsdom + real OWL 2.8.2).
