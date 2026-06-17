---
course: 5 — Estimating + Configurator
chapter: 5.4
title: Configurator UX v2 — Southbrook's Deltas vs OCA Stock
duration: 25 minutes
audience: Estimator + the designer who configures cabinets inside Odoo. You've used the OCA wizard once or twice and want to know why the customer-facing /shop page looks completely different.
prereqs: Lessons 5.1, 5.2. You can configure a cabinet via the OCA wizard.
custom_modules: southbrook_configurator_ux
---

# Configurator UX v2 — Southbrook's Deltas vs OCA Stock

## Who this lesson is for

You're a Southbrook estimator or designer who's worked the OCA
configurator wizard inside Odoo and now needs to understand the
customer-facing `/shop/<cabinet-slug>` page. The two surfaces are
*different* — same data, same rules, same `product.config.session`
records, but a completely redesigned UI. This lesson walks you through
what the v2 UX changes, why those changes exist, when to use which
surface, and how to read a failing validation message back to its
underlying configurator rule.

## Where this lives on the site

Two surfaces, two URLs:

> **OCA stock wizard** — opens from any cabinet's **Configure** stat
> button in the backend (the Order Builder line's Configure action).
> Lives at `/web#action=...`.

> **Southbrook UX v2** — public-facing, at **`/shop/<cabinet-slug>`** on
> southbrookcabinetry.space. Every customer who visits a configurable
> product page hits this layout. Internal users hit the same page but
> get an extra "Bulk tools" bar at the top.

The v2 layout is enabled by installing `southbrook_configurator_ux` —
uninstalling it returns the page to the OCA stock layout immediately.
No data is touched; the layout swap is pure QWeb template inheritance
plus a JS / SCSS bundle (`web.assets_frontend`).

## What your screen shows

The v2 page is a **two-pane responsive grid** plus a top strip:

- **Progress bar** (`#sb_cfg_progwrap`) — sticky at the top, fills as
  you make picks. Static `role="progressbar"` for screen readers; the
  fill (`#sb_cfg_progbar`) is rendered by the OWL component.
- **Breadcrumbs** (`.sb_cfg_crumbs`) — Shop › Category › Cabinet Name.
  Server-rendered (navigation, not state).
- **Title bar** (`.sb_cfg_titlebar`) — cabinet name, a tagline ("Build
  a made-to-spec cabinet · live pricing · SKU auto-generates as you
  configure").
- **Bulk-tools bar** (`.sb_cfg_bulkbar`) — visible only to
  internal users (`t-if="not user_id.share"` on the QWeb side, mirrored
  by `data-internal-user` on the JS side). Two buttons: "⬇ Template
  Layout" (downloads a starter xlsx via `/southbrook/api/import/template`)
  and "⤒ Import Product" (opens the import overlay modal). Customers
  never see this row.

**Left pane (sticky)** — the live preview + summary card:

- **Live preview** (`.sb_cfg_viewer`) — a CSS-box rendering of the
  cabinet that reshapes as you pick. Width/height/depth attribute
  changes resize the box; Finish picks change the front face colour
  using the JS `FINISH_COLORS` map (White → `#f3f0ea`, Maple Stain →
  `#d9a566`, etc.).
- **Replace Photo button** (`📷 Replace photo`) — drag-and-drop or
  click. Replaces the CSS box with a customer-supplied reference
  image. Local-only — the photo doesn't sync to the order.
- **Summary card** (`.sb_cfg_summary`):
  - **Price LIVE** — server-resolved after each pick (POSTs to
    `/southbrook/api/configurator/select` and reads
    `serverPrice`). The `LIVE` badge stays visible during the round-trip.
  - **Est. Weight** — `serverWeight` from the same endpoint.
  - **Auto SKU** — composed from picks against `SKU_ATTR_NAMES =
    ['Width', 'Series', 'Finish']` (live, client-side preview; the
    canonical SKU is the variant's `default_code` on commit).
  - **Your build** spec line — joins picks for `SPEC_ATTR_NAMES =
    ['Width', 'Series', 'Finish', 'Hinge Side', 'Handle']`.
  - **Completion ring** (`.sb_cfg_ring` with `--p:<pct>` CSS var) —
    progress through required attributes, with a percentage in the
    centre.
- **Action bar** (`.sb_cfg_actionbar`):
  - Validation status (`role="status" aria-live="polite"`) — green
    "Ready to add" or amber "Choose Series to continue" — driven by the
    OCA rule engine's `disabledValueIds` + the required-attribute set.
  - **Add to Quote** primary button — POSTs to
    `/southbrook/api/configurator/commit`. On success: navigates to
    the Order Builder; on `login_required`: navigates to the login
    page with `return_to=<here>`.

**Right pane (scroll)** — the chip-selector configurator:

- **4 collapsible attribute groups** (`config.step` buckets) — the
  Phase 2K wizard step grouping: Construction, Door & Finish, Hardware,
  Interior. Each group has a header (number badge → checkmark when
  complete) and a body of attribute pickers.
- **Chip selectors** for `radio` and `pills` display_types — each
  value is a clickable chip; selection highlights; disabled chips show
  with reduced opacity and `aria-disabled="true"`.
- **Native `<select>`** for `select` display_type — Width, Door
  Style, Finished Sides.
- **Color swatches** for `color` display_type — Finish.
- **Per-option price delta** (`.sb_cfg_pd`) — shows e.g. `+10%` next
  to Maple in the Box Material picker, pulled live from the
  attribute's `price_extra` via the `/state` and `/select` endpoints.

The whole reactive UI is **one OWL component** (`ConfiguratorV2`)
owning one state tree — picks, server-resolved fields, disabled value
IDs, loading flags. The component mounts at `#sb_cfg_v2_main_mount`
inside `#sb_cfg_v2_root[data-product-tmpl-id="<id>"]`. The
mount-point guard means the bundle no-ops on any page without that
root div — uninstalling the addon makes the JS silently skip.

## Your daily flow

You'll work two surfaces depending on context.

**1. The estimator's surface — OCA stock wizard (backend).**

When you're building a quote in the Order Builder (lesson 5.2), the
Configure button on each line opens the OCA stock wizard, not v2. The
backend uses the OCA layout because:

- It carries the 11 attributes in 4 step buckets (`config.step`)
  exactly as Southbrook seeded them.
- The wizard transitions are linear — Next / Previous per step — and
  let you walk back through the picks of a 20-line order quickly.
- It shows the rule-block reason in the wizard's error area when
  Rule 1 / 2 / 3 / 4 fires ("Maple box not available on Contractor
  series") so you know *why* an option is disabled.

You'll see the v2 UX only when:

- A customer or dealer is configuring on `/shop/<slug>`.
- You're internally previewing the customer-facing page to verify
  visuals or test the chip-selector behaviour (paste the URL in your
  browser).

**2. The designer's surface — v2 inside `/shop`.**

If you're previewing the customer experience, hit
`/shop/<cabinet-slug>` (e.g. `/shop/base-2-door`) while logged into
Odoo. You'll see the v2 layout plus the internal-only Bulk tools bar
at the top. The bulk tools let you download an import template
(`/southbrook/api/import/template`) or upload a filled-in CSV/xlsx
through the import overlay (`#sb_cfg_importOverlay`).

**3. Reading v2 validation messages.**

The action-bar status text is the key tell — it tells you which rule
fired:

- **"Choose a Series to continue"** — required attribute unanswered.
  Not a rule, just a missing pick. Pick a Series chip.
- **"Maple box is not available on Contractor Series"** — Rule 2
  fired. The Maple chip is disabled (greyed, `aria-disabled="true"`),
  and the status text comes from the OCA rule engine's reason field.
  This is an **exclusion** firing.
- **"Custom doors require Signature Series — switch to continue"** —
  Rule 1 fired in reverse (you picked Custom door style but Series
  isn't Signature). Switch Series to Signature or change the door
  style.
- **"Soft-close is not available on bi-fold corners"** — Rule 4
  fired. This one is a *construction rule* with negative effect — the
  soft-close kit option is hidden entirely, not just disabled. You
  won't see it in the Accessories picker on a bi-fold corner cabinet.

**Recognising exclusion vs construction rule:**

- **Exclusion** → option is *disabled* (visible, greyed). You can see
  it, you can't click it. The disabled state is driven by
  `state.disabledValueIds` populated from the `/select` endpoint
  response.
- **Construction rule (negative)** → option is *absent*. You don't
  see it at all. The attribute_line itself was never rendered
  (Rule 4 corner bi-fold).
- **Construction rule (positive)** → side effects: a price extra
  appears next to your pick (Maple `+10%`), the Auto SKU updates,
  the completion ring advances, the lead-time hint appears in
  the summary card.

**4. Common workflow — bulk-loading 30+ cabinets.**

Large-kitchen entry (30+ cabinets) is the v2 surface's biggest help.
Two paths:

- **Per-cabinet via the customer's `/shop` flow** — slow; you'd
  configure 30 cabinets one at a time. Use only if the customer is
  driving.
- **Bulk import via the v2 bulk-tools** — fast. Click "⬇ Template
  Layout" to download the starter xlsx. Fill the PRODUCTS sheet with
  one row per cabinet (default_code, name, type, internal_category,
  southbrook_category, southbrook_icon_key, attributes…). Upload via
  the import overlay. The /preview endpoint validates each row
  against the live vocab + the upsert invariants and shows you a
  status table (Status, SKU, Name, Price, Category, Icon, Row,
  Issue). Fix errors in your xlsx, re-upload, repeat. When clean,
  click **Commit N valid rows** — a single transaction creates /
  updates the `product.template` records.

The import handles **PRODUCTS only in v1**. ATTRIBUTE_LINES /
ATTRIBUTE_VALUES / BOM_HEADERS / HARDWARE_BOM / ACCESSORIES sheets
are recognised but skipped with a "deferred to v2" status row. The
endpoint contract accepts multi-sheet payloads from day one so v2 of
the importer is a server-side change only.

**5. Keyboard shortcuts.**

The chip selectors have keyboard navigation:

- Tab into the chip group — first chip gets focus.
- Arrow keys move between chips inside a group.
- Enter / Space selects the focused chip (calls
  `onChipKeydown` → `onChipClick`).
- Tab on a group header expands / collapses the group
  (`onGroupKeydown` → `toggleGroup`).

There are no other v2-specific shortcuts. Standard browser nav
(Tab / Shift+Tab) walks the form.

**6. When to fall back to the OCA stock view.**

Two situations where the v2 page isn't enough:

- **You need to see the rule-block reason verbatim.** v2 surfaces
  the reason in the action-bar status text, but truncated. The OCA
  wizard shows the full message. If a customer reports
  "I picked X and the option disappeared and I don't understand why",
  open the same cabinet in the backend OCA wizard, repro the picks,
  read the full rule reason.
- **You need to see the configurator step structure.** The 4-step
  bucket (Construction / Door & Finish / Hardware / Interior) is
  collapsible in v2 but linear in the OCA wizard. The OCA wizard's
  Next / Previous flow is easier to audit when you're verifying
  which attributes are gating progression.

Uninstall `southbrook_configurator_ux` and the v2 layout disappears
immediately; the OCA stock layout returns unchanged. Don't do this in
production — it's a single-command change but the customer-facing UX
regression is severe.

## Common mistakes + how to recover

**"The v2 page loads but the cabinet preview is blank and the picker
chips don't respond."**

The OWL component isn't mounted. Look at the browser console — if
you see `Couldn't load this configurator` with a server-side message,
the `/state` endpoint returned an error. Most common cause: the
`product.template` isn't `config_ok=True`, so the OCA module's session
machinery refused it. Fix on the admin side: open the template in the
backend, tick Configurable.

**"Customer says the Add to Quote button does nothing."**

Look at the `state.commitMessage`. If it surfaces "Authentication
required", the visitor is anonymous and the `/commit` endpoint
returned `login_required`. The v2 JS navigates to `/web/login` with a
`return_to` query string — make sure your CDN / proxy isn't stripping
query strings on auth redirects.

**"I see `+10%` next to the Maple chip even on the Contractor cabinet
where Maple is supposed to be disabled."**

The chip *is* disabled (`aria-disabled="true"`, reduced opacity), but
the price-extra label renders independently. That's deliberate — it
shows the customer "if you upgraded series, this is what Maple would
add". Don't treat it as a bug; treat it as a feature flag for the
upsell conversation.

**"The bulk-tools bar is showing for a customer."**

`#sb_cfg_v2_main_mount` carries `data-internal-user` set from
`request.env.user.share`. If a customer sees the bar, the
`user.share` check is returning `False` for a portal user — possibly
the portal user accidentally got internal access. Fix: open the user
record (Settings → Users) and verify the user is *not* in any
internal group (Sales / Inventory / etc.). The check is
client-side display logic only; the actual `/southbrook/api/import/*`
endpoints have a backend `auth='user'` + internal-user check, so the
customer can't actually use the tools even if they see them. But
hiding the bar correctly is still important visual hygiene.

**"I picked Series → Contractor and the Door Style chips show
Five-Piece Woodgrain as enabled."**

The OCA rule engine isn't producing `disabledValueIds` correctly.
Two suspects: (1) `rule_completion.xml` didn't load — re-run
`-u southbrook_configurator_ux`; (2) the `/select` endpoint failed
silently and the client kept stale state — look at the network tab,
filter on `/select`, check for non-200 responses. The session falls
through to client-side state if `/select` 500s; reload the page to
reset.

**"The 'Replace Photo' overlay accepts an image but it disappears on
reload."**

Photos are local-only (stored in component state as a data URL).
Reloading the page wipes them. Don't promise the customer their
reference photo will persist into the order — explain it's a
preview-aid only.

## What the system is doing behind the scenes

The v2 layout swaps the body of the OCA template
`website_product_configurator.product_configurator` via a single
xpath `position="replace"` on `//section[@id='unique_product_configurator']`
in `views/configurator_template.xml`. The OCA module's *route* is
preserved; only the body markup changes.

The replacement markup ships a minimal shell — root div carrying
`data-product-tmpl-id`, four OWL mount points (`#sb_cfg_v2_main_mount`,
the progress wrapper, the import overlay, the toast container), plus
breadcrumbs and a no-JS fallback. Everything else is rendered by
`ConfiguratorV2`.

On mount, the component:

1. POSTs `/southbrook/api/configurator/state` with
   `product_tmpl_id`. Receives `{ok, product, base_price, groups,
   attributes, session_id, selected_value_ids}` — the full
   configurator vocabulary baked into the response.
2. Hydrates `state.attributes`, `state.groups`, `state.picked` (any
   server-persisted picks from `selected_value_ids`).
3. Fires one `/southbrook/api/configurator/select` to populate
   `disabledValueIds`, `serverPrice`, `serverWeight`, `liveSku`
   *before* the user makes a pick — so initial invalid combinations
   (e.g. from a restored session) are already disabled.

Every chip click after that POSTs to `/select` with the full pick
set; the server is authoritative; the response reconciles
`state.serverPrice`, `state.serverWeight`, `state.disabledValueIds`,
`state.liveSku`. The component is optimistic — it updates
`state.picked` immediately and rolls back if the server response
disagrees.

On "Add to Quote", `/commit` materialises the variant via
`session.create_get_variant()`, adds it to the user's draft sale
order, moves the session to `state='done'`. Decision A (Phase 2
cart-target lock): the order goes to the **Order Builder**, not the
website_sale cart. The response carries `redirect_url` →
`/my/southbrook/order-builder/<id>` so the customer lands in their
portal estimate, not in checkout.

The whole bundle is `web.assets_frontend` only — the OCA stock
backend wizard is untouched. Authoring an additional Southbrook
configurator surface (e.g. mobile-first or 3D) means writing another
asset bundle; you don't change v2 in place.

## Quiz (5 questions, applied)

**1.** A customer reports "I clicked Series = Contractor and the
Five-Piece Woodgrain chip went grey — but the +10% price label is
still showing next to Maple. Is that a bug?"

> No. The price-extra label renders independently of the disabled
> state — it shows "if you could pick Maple, this is what it would
> cost." The Maple chip itself is disabled (greyed, can't click).
> The Five-Piece grey is Rule 1 (Series → Door Style). Both are
> expected behaviour; the +10% label doubles as an upsell hint.

**2.** Where on the v2 page would you look to confirm the OCA rule
engine actually fired Rule 2 (Box Material → Series), as opposed to
the client-side optimistic guess?

> The Network tab. Filter on `/southbrook/api/configurator/select`.
> Look at the most recent response's `disabled_value_ids` array — if
> the Maple value_id is in it when Series is Contractor, the rule
> engine fired correctly. If it isn't, the server thinks Maple is
> allowed but the chip is greyed for a different reason (client-side
> stale state, or `rule_completion.xml` not loaded).

**3.** A designer wants to load 35 cabinets into a customer's quote
from a CSV. What's the v2-specific workflow, and at which step is the
human-confirm gate?

> Open `/shop/<any-cabinet>` while logged in internally. Click "⬇
> Template Layout" — downloads a starter xlsx with the PRODUCTS sheet
> columns and an example row. Fill the PRODUCTS sheet (35 rows).
> Click "⤒ Import Product" — opens the overlay. Drop the xlsx. The
> /preview endpoint validates and shows you per-row status. Read the
> table — fix errors in the xlsx, re-upload, repeat until clean.
> Click "Commit N valid rows" — the explicit confirm gate. /commit
> writes the records inside a single transaction. The Phase-4 stop-
> point is "never commit without the human clicking Commit."

**4.** You're seeing a customer-reported "the chips are all greyed
out" but you can repro it on /shop yourself. The OCA backend wizard
on the same template works fine. Where do you look first?

> The /select endpoint response. If it's returning every value_id in
> `disabled_value_ids`, the rule engine is treating the product as
> over-constrained (probably a malformed `product.config.line`
> record). If it's returning an empty `disabled_value_ids` but the
> chips still grey out, the client-side `isValueDisabled` is hitting
> a stale state — reload the page to reset
> `state.disabledValueIds`. The OCA backend wizard reads the same
> rule engine, so the fact it works there narrows it to the
> v2-specific JS code path or the /state hydration.

**5.** Your admin wants to roll back v2 because a customer complained
about the price label format. What's the rollback procedure and what
breaks?

> Uninstall the addon: `odoo -d <db> --uninstall southbrook_configurator_ux
> --stop-after-init --no-http`. The /shop/<slug> page returns to the
> OCA stock layout immediately — same data, same rules, same
> sessions, just the OCA-shipped one-page form. Nothing else breaks:
> no schema changes, no data migration, no impact on Order Builder
> or the backend wizard. The bulk-tools endpoints
> (`/southbrook/api/import/*`) stop responding — anything currently
> using them errors out. Re-install to restore. This is the right
> rollback path *only* when v2 is broken; for the price-label
> complaint, fix the SCSS or the JS instead.

## What this lesson does NOT cover

- The OCA configurator vocabulary itself — lesson 5.1.
- How to build the actual quote — lesson 5.2.
- Hardware catalog and per-carcass resolution — lesson 5.3.
- The customer-facing portal (My Estimates page, portal account
  setup) — Course 6 (Customer Touchpoints).
- The 3D Kitchen Preview tab in the backend Order Builder — Phase 3
  surface, separate workstream.
- The Phase-3 OWL refactor that moves the disable rules from the
  OCA rule-engine reads into a data-driven JSON endpoint — not yet
  shipped.
- General Odoo Website / e-commerce administration — Odoo's own
  native eLearning track.
