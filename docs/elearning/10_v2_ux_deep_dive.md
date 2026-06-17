---
course: 10 — Configurator Deep Dive
chapter: 10.6
title: Configurator UX v2 Deep Dive — OWL, JSON-RPC, and the QWeb Inheritance Pattern
duration: 50 minutes
audience: Estimator who designs the customer flow + frontend dev who extends the v2 chip UI.
prereqs: Course 5 (5.1, 5.4). Lessons 10.1, 10.2, 10.3. You know OWL component shape (setup, state, hooks) and have read or written one.
custom_modules: southbrook_configurator_ux, website_product_configurator
---

# Configurator UX v2 Deep Dive — OWL, JSON-RPC, and the QWeb Inheritance Pattern

## Who this lesson is for

You're the estimator who needs to know "why does the chip turn grey
after this pick" — and the developer who needs to add a new chip
group, a new endpoint, or a new keyboard shortcut. Course 5 lesson
5.4 gave you the UX vocabulary. This lesson is the implementation:
which file owns which DOM node, where state lives, how the 3
JSON-RPC endpoints sequence, what happens on every chip click. You
can repro it from the source after reading this; no surprises.

## Where this lives on the site

Two surfaces:

> **`/shop/<cabinet-slug>`** — the customer-facing v2 page on
> southbrookcabinetry.space. Every configurable product renders
> through the inherited template.

> **`/southbrook/api/configurator/{state|select|commit}`** and
> **`/southbrook/api/import/{template|preview|commit}`** — six
> JSON-RPC + HTTP endpoints. All defined in
> `addons/southbrook_configurator_ux/controllers/main.py`.

Two implementation files:

- `addons/southbrook_configurator_ux/views/configurator_template.xml`
  — the QWeb body that the OWL component mounts into.
- `addons/southbrook_configurator_ux/static/src/js/configurator.esm.js`
  — the `ConfiguratorV2` OWL component (1,307 lines).

## What your screen shows

The DOM produced by the QWeb shell:

```
#sb_cfg_v2_root[data-product-tmpl-id]
├── .sb_cfg_progwrap (role="progressbar")
│   └── .sb_cfg_progbar
├── .sb_cfg_crumbs
└── #sb_cfg_v2_main_mount[data-internal-user="0|1"]
    └── (no-JS fallback "Loading…")
```

`ConfiguratorV2` mounts into `#sb_cfg_v2_main_mount`. The static
fallback content gets replaced. The component's rendered output:

```
.sb_cfg_v2_main
├── .sb_cfg_titlebar (title + tagline + bulk-tools bar*)
├── .sb_cfg_bulkbar (* internal users only)
└── .sb_cfg_grid
    ├── .sb_cfg_panel.sb_cfg_left (sticky)
    │   ├── .sb_cfg_viewer (CSS-box preview)
    │   ├── .sb_cfg_summary (Price LIVE + Weight + SKU + spec + ring)
    │   └── .sb_cfg_actionbar (validation + Add to Quote)
    └── .sb_cfg_panel.sb_cfg_right (scroll)
        └── (4 collapsible attribute groups, chip selectors)
```

Plus two body-level overlays:

- `#sb_cfg_importOverlay` — the bulk-import modal (position:fixed).
- toast container — flash messages.

These are body-level because they sit OUTSIDE the OWL component
tree — they're rendered by the static QWeb so they can layer above
the component without OWL teleport.

## Your daily flow

You won't touch v2 every day, but if you do, four operations cover
everything.

**1. Adding a new chip group.**

The 4 groups are defined in
`southbrook_configurator_ux/controllers/main.py:126-131` as the
`ATTRIBUTE_GROUPS` constant:

```python
ATTRIBUTE_GROUPS = [
    ("Size & Layout",         ["Width", "Door Count"]),
    ("Series & Materials",    ["Series", "Box Material", "Door Style"]),
    ("Finish & Construction", ["Finish", "Hinge Side", "Finished Sides", "Gables"]),
    ("Hardware & Add-ons",    ["Handle", "Accessories"]),
]
```

The `/state` endpoint maps live attribute_lines to these groups by
attribute name. Attributes on the template that don't match any
group fall into an "Other" group at the end. To add a 5th group,
edit the constant. The JS reads the result from
`state.groups` — no client-side change needed (the new group will
render automatically).

Caveat: the manifest comment notes Phase 3+ moves this to a
configurable grouping (probably an `ir.config_parameter` or a new
field on `product.attribute`). For now, code edit + redeploy.

**2. Adding a new endpoint.**

The pattern is in `main.py:140-205` for `configurator_state`. To add
a new JSON-RPC route:

- Add an `@http.route("/southbrook/api/configurator/<name>",
  type="json", auth="public", methods=["POST"], website=True)`
  method on `SouthbrookConfiguratorAPI`.
- For session-touching endpoints, route through
  `_authorize_session(session_id)` (line 779) to enforce per-user
  scoping.
- Return `{ok: True, ...}` on success or `{ok: False, error: "<code>",
  message: "<text>"}` on failure. The OWL component reads `.ok` to
  branch.
- The OWL side: in `configurator.esm.js`, call `rpcJsonCall("/southbrook/api/configurator/<name>", { ... })`
  (line 59 — the bundle uses raw fetch because the public `/shop`
  page has no Odoo service worker).

**3. Changing the SKU composition.**

The SKU is composed by joining the first 3 alphanumeric characters
of values from attributes named in `SKU_ATTR_NAMES`. Both client
(`configurator.esm.js:94`) and server (`main.py:123`) define the
same constant:

```js
const SKU_ATTR_NAMES = ["Width", "Series", "Finish"];
```

```python
_SKU_ATTR_NAMES = ("Width", "Series", "Finish")
```

These **MUST stay in sync** — otherwise client preview shows one
SKU and the server writes a different `variant.default_code` at
commit time. To extend (e.g. add Door Style):

- Add "Door Style" to both arrays.
- Verify the customer-facing SKU stays readable (3-char abbrs of
  values).

`SPEC_ATTR_NAMES` (client only) at line 95 drives the "Your build"
spec line — these can diverge from SKU; the spec is a human
summary, not a code.

**4. Adding a new finish color swatch.**

The CSS-box preview uses `FINISH_COLORS` at line 81:

```js
const FINISH_COLORS = {
    "White":          "#f3f0ea",
    "Maple Stain":    "#d9a566",
    "Cherry Stain":   "#8a3b2a",
    "Walnut Stain":   "#5a3b28",
    "Custom":         "#b9a07a",
    "Maple":          "#caa06a",
    "White Melamine": "#eceae4",
};
```

Add the new finish's display name → hex. The manifest comment
notes Phase 3+ sources these from `product.template.attribute.value.html_color`
— so for new finishes, set `html_color` on the PTAV too. Today the
JS hardcoded map wins; the `/state` endpoint surfaces
`val.html_color` already but the JS preview ignores it for non-color
display_type attributes.

## Common mistakes + how to recover

**"I added a chip group and the new group's attributes are showing
in 'Other' instead."**

The group title-to-attribute-name match is case-sensitive. If the
attribute is named "doorstyle" (lowercase) and your group entry is
"Door Style", they don't match. Fix the constant or rename the
attribute.

**"I added a new endpoint but the client always gets a 404."**

Most likely the asset bundle is stale and the JS is calling the
new endpoint URL but the server hasn't been restarted. Or the
manifest's `data` list doesn't include the new route's view file —
routes are Python, so no view file is needed, but if you authored
in a new module, did you add it to `addons_path`? Run `--update=all
--dev=all` to refresh.

**"The chip selectors render but clicks don't do anything."**

OWL didn't mount. Look at the browser console:
- `Couldn't load this configurator` with a server message —
  `/state` returned an error. Common: the product isn't
  `config_ok=True`.
- No error but blank static fallback — the bootstrap couldn't find
  `#sb_cfg_v2_root`. Either the QWeb inheritance didn't load (try
  `-u southbrook_configurator_ux`) or you're on a non-configurable
  product page.

**"Two Add-to-Quote clicks fire in rapid succession and we get two
order lines."**

The component sets `state.adding = true` on click and reads it for
the button's `disabled` attribute. Race: if `adding` is set after
the second click is already in flight, both POSTs land. Mitigation:
client-side debounce (already in code), but the server's
`/commit` has its own duplicate-guard via `session.state` —
double-commit on the same session is blocked because the second
call hits `state.session_locked`. The real bug if you see two
lines: the second click hit a DIFFERENT session. Audit by logging
session_id at every commit.

**"The bulk-tools bar is visible to a portal user."**

The QWeb shell sets `data-internal-user` from
`request.env.user.share` (False = internal, True = portal). The
component reads that attribute at mount and gates render. If a
portal user sees the bar, the attribute is "1" but the component
mis-reads — check the QWeb expression
`t-att-data-internal-user="'0' if request.env.user.share else '1'"`.
The endpoints themselves have a backend `auth='user' + user.share`
check (line 838, line 1000), so they'll 403 even if the UI shows
the bar — the cosmetic gap is visual only, but file a bug.

**"A chip is greyed but the user clicks anyway and the pick goes
through."**

The `isValueDisabled` check (line 503) reads
`state.disabledValueIds` from `/select` response. If the click
fires BEFORE `/select` has responded, the optimistic local update
goes through. Then `/select` returns with the disabled flag, the
UI re-renders, the value is now greyed but the pick is set. The
component's reconcile logic should roll back — verify it. If not,
the user can force-pick blocked values. Workaround: server-side
`/commit` validates again via `validate_configuration` — so it can
still reject. But UX-wise this is a bug.

## What the system is doing behind the scenes

The OWL component is **one class, one state tree**:

```js
class ConfiguratorV2 extends Component {
  setup() {
    this.state = useState({
      loading: true,
      loadError: null,
      product: { name: "", currency: {...} },
      sessionId: null,
      basePrice: 0,
      groups: [],          // from /state
      attributes: {},      // {<id>: {name, display_type, values: [...]}}
      picked: {},          // {<attrId>: <valId>}
      closedGroups: {},    // {<title>: bool}
      serverPrice: null,
      serverWeight: null,
      liveSku: null,
      disabledValueIds: [],
      adding: false,
      previewBadge: "",
      // ...
    });
    this.viewerRef = useRef("viewer");
    this.imgInputRef = useRef("imgInput");

    onWillStart(async () => {
      const r = await rpcJsonCall(
        "/southbrook/api/configurator/state",
        { product_tmpl_id: productTmplId },
      );
      if (!r || !r.ok) {
        this.state.loadError = (r && r.message) || "Could not load.";
      } else {
        this.hydrateState(r);
      }
      this.state.loading = false;
    });

    onMounted(() => {
      // Bind keyboard shortcuts, pre-fire one /select to populate disabled set.
    });
  }
  // ... toggleGroup, onChipClick, onSelectChange, onChipKeydown,
  //     onGroupKeydown, onAddToQuote, isValueDisabled, autoSku,
  //     priceText, weightText, validationClass, validationText, etc.
}
```

**Three JSON-RPC endpoints** + **three HTTP endpoints**:

| Endpoint | Type | Auth | What it does |
|---|---|---|---|
| `/state` | json | public | Returns product + attributes + groups + session_id |
| `/select` | json | public | Applies picks, returns price + weight + disabled set + live SKU |
| `/commit` | json | public | Materialises variant + adds to sale.order + locks session |
| `/import/template` | http | user (internal) | Downloads xlsx template |
| `/import/preview` | http | user (internal) | Validates uploaded xlsx, returns per-row report |
| `/import/commit` | http | user (internal) | Writes valid rows from xlsx (requires `confirm=true`) |

**The /select endpoint's most subtle behaviour** — "premature
disables." OCA's `values_available` returns the set of values
whose attributes' rules' domains all match. When picks are empty,
every value with ANY rule (whose domain depends on Series, etc.)
gets flagged unavailable — because no Series has been picked yet
to satisfy the rule's "in [...]" check. The customer would see all
Box Material chips greyed at page load.

The controller (lines 446-509) refines this: for each
"prematurely disabled" value, walk its restricting rules; keep the
disability only if at least one rule has a trigger attribute the
user HAS picked AND the user's pick doesn't satisfy the rule's
allow list. The actual code:

```python
for vid in disabled_ids:
    rules = tmpl.config_line_ids.filtered(
        lambda r, _vid=vid: _vid in r.value_ids.ids)
    for rule in rules:
        rule_blocks = False
        for dl in rule.domain_id.domain_line_ids:
            trigger_attr_id = dl.attribute_id.id
            if trigger_attr_id not in picked_set_by_attr:
                continue  # User hasn't picked the trigger yet.
            user_picks = picked_set_by_attr[trigger_attr_id]
            allowed = set(dl.value_ids.ids)
            if dl.condition == "in":
                if not (user_picks & allowed):
                    rule_blocks = True
                    break
            else:  # "not in"
                if user_picks & allowed:
                    rule_blocks = True
                    break
        if rule_blocks:
            refined_disabled.add(vid)
            break
disabled_ids = sorted(refined_disabled)
```

This is **load-bearing UX logic** — without it the v2 page is
unusable on page load. The customer's mental model: "I can't pick
this only if my prior pick makes it impossible." Implemented in
the controller, not the rule engine.

**The /commit endpoint's completeness backstop** (lines 641-657):
before calling `create_get_variant`, walk every
`attribute_line_ids` with `len(value_ids) > 1` and check whether
the session has a pick for that attribute. Returns
`incomplete_configuration` with a `missing_attributes` list. This
gives a specific error like "Please choose: Series, Finish" rather
than OCA's generic ValidationError.

**The OWL component's lifecycle** on a chip click:

1. User clicks chip → `onChipClick(attrId, val)` fires.
2. If `isValueDisabled(attr, val)` returns true, no-op.
3. Else `state.picked[attrId] = val.id` (optimistic).
4. Call `/select` with the full pick set.
5. On response, update `state.serverPrice`, `state.serverWeight`,
   `state.disabledValueIds`, `state.liveSku`.
6. Re-render is automatic (OWL `useState`).

The **import overlay** is a separate flow — it lives at
`#sb_cfg_importOverlay` (a body-level QWeb fragment) and gets
toggled by the bulk-tools bar buttons. The xlsx upload goes to
`/import/preview` (multipart form, returns a per-row report).
After review, the customer clicks Commit, which POSTs to
`/import/commit` with `confirm=true` — the explicit human gate
required by Phase-4 stop-point in the manifest.

## Quiz (5 questions, applied)

**1.** A customer reports the v2 page loads, all chips are visible,
but every chip in the Box Material group is greyed at page load
before they've picked anything. What's the most likely cause and
where do you look in the code?

> The "premature disables" refiner at
> `controllers/main.py:446-509` isn't running, or is running but
> is being bypassed. Open the Network tab on the customer's
> repro, look at the `/select` response — `disabled_value_ids`
> should be empty when no picks are made (every Box Material
> chip should be enabled at page load). If `disabled_value_ids`
> is full, the refiner ran but every rule's trigger attribute
> was somehow flagged "picked" — possibly because the session
> already had stale picks from a prior visit. Fix: clear the
> session or wipe its `value_ids`. If the refiner code is
> outright skipping (e.g. catching an exception silently), the
> fallback in line 444 (`available_ids = list(all_val_ids)`)
> would actually mean "everything enabled" — so the symptom
> rules out that branch.

**2.** You want to add a "Lead Time" badge to the summary card
showing the configured variant's expected lead time (current +
any `lead_time_extra` from picks like Maple). Walk through the
change set.

> Three files. (a) `controllers/main.py:configurator_select` —
> add `lead_time` to the response, computed from
> `session.product_tmpl_id.lead_time + sum(picked PTAV.lead_time_extra)`.
> Reuse `picked_set_by_attr` already in scope. (b)
> `static/src/js/configurator.esm.js` — add
> `state.serverLeadTime` to the `useState` tree; hydrate from
> the /select response in the reconcile callback; expose a
> `leadTimeText` getter that formats it ("3 weeks" or "5 weeks
> + 2 weeks for Maple"). (c) Update the summary-card QWeb in
> the template literal to render `t-esc="leadTimeText"`. SCSS
> tweak optional. Test: pick Maple, verify the badge updates
> live.

**3.** A developer adds a new endpoint `/southbrook/api/configurator/save_draft`
that lets a customer bookmark a session (mapped to
`session.action_save_config(name)`). The customer reports "click
Save, nothing happens." Diagnose.

> Three suspects:
> (a) The endpoint is `auth='public'` but the customer is anonymous
> and `action_save_config` requires a real user_id — the public_user
> has no portal context, so the bookmark is technically saved but
> unreachable. Confirm by browsing
> `Session.search([("is_saved", "=", True)])` — count delta should
> be zero for the anonymous case.
> (b) The endpoint forgot the `_authorize_session` guard, and a
> mismatched session_id is being passed. Server silently ignores.
> Audit the OWL component's call signature.
> (c) The website GC cron (3-day threshold) doesn't respect
> `is_saved` and the saved session is gone the next day. (See
> Lesson 10.3 for the cron bug.) Customer's "save" worked but the
> session vanished overnight.

**4.** You're asked to add keyboard shortcut `Enter` to commit-and-
go directly from the chip grid. Where do you wire it without
breaking existing chip-keyboard semantics?

> Don't reuse `onChipKeydown` — it already handles Enter/Space to
> select the focused chip. Add a global keydown listener inside
> the component's `onMounted` hook scoped to the component's root
> element (e.g. `useRef("root")` and bind
> `addEventListener('keydown', ...)`). Check
> `ev.target.matches('.sb_cfg_actionbar button')` AND `ev.key ===
> 'Enter'` — only fire commit when the focus is in the action bar
> already, NOT from a chip. Otherwise users pressing Enter to
> select a chip would commit unintentionally. Add visible focus
> styles and the standard prevent-double-fire `state.adding` gate.

**5.** A customer reports "Add to Quote shows 'Adding…' for 30
seconds then errors with 'Configuration session belongs to a
different user.'" What sequence of events causes this?

> The session was created under one user (probably during an
> anonymous browse), then the customer signed up / logged in
> mid-session. The session's `user_id` is still the prior
> (public) user. `/commit` calls `_authorize_session(session_id)`
> which checks `session.user_id.id == request.env.user.id` and
> returns the "forbidden" error dict. The 30-second hang is
> probably the OWL component spinning until the response — the
> server returns fast, the JS just doesn't surface the error
> nicely.
>
> Recovery for the user: refresh the page — `/state`
> `_get_or_create_session` will find no draft session under the
> new user and create a fresh one. They'll lose their picks
> (the old session is orphaned). Long-term fix: on login from
> `/shop`, re-attach the prior session's `user_id` to the new
> user before redirecting — currently not implemented.

---

## What this lesson does NOT cover

- Configurator vocabulary basics — Course 5, Lesson 5.1.
- 5-addon architecture — Lesson 10.1.
- Setting up a new configurable product — Lesson 10.2.
- Session state machine — Lesson 10.3.
- Sale flow integration — Lesson 10.4.
- MRP flow integration — Lesson 10.5.
- Common gotchas (rule ordering, exclusion explosion, performance) —
  Lesson 10.7.
- The Phase-3 3D parametric carcass layer — separate workstream.
- General OWL framework administration — Odoo's own dev docs.
