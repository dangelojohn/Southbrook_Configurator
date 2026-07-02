# Track B fix chain — 2026-07-01 → 2026-07-02 session

**Scope:** the "BOM autoseed on quote" workstream in
`addons/southbrook_kitchen_3d_configurator/`. Shipped 2026-07-01 at
5.6.0, then broke end-to-end in production. This document is both the
retrospective and the runbook: every fix, every root cause, every
verification, every remaining gap.

**Audience:** the future contributor debugging a Track B regression at
02:30 in the morning. It is deliberately concrete — file paths, line
numbers, git hashes, SQL snippets — so the reader can follow the code
without re-deriving anything.

---

## 1 · Executive summary

Track B is the "quote-to-manufacture bridge" for the Kitchen 3D
Configurator. When a rep or a customer finishes a kitchen design and
clicks **Create & Confirm →**, Track B is what turns that click into a
draft Sale Order, a confirmed Sale Order, and one or more Manufacturing
Orders — automatically, without the rep having to hand-build a Bill of
Materials for each cabinet. The initial 5.6.0 shipped in one afternoon
and worked in the developer test cases; in production against real
designs it silently failed at every step. Over the following ~7 hours,
six patch releases (5.6.3 → 5.6.8) walked the failure chain one bug at
a time — an XML-escaping typo, a missing Odoo field, a stale archived
record guard, a call-ordering inversion, a missing Manufacture route on
the templates, and a transaction that quietly rolled everything back
when a downstream approval gate rejected the confirm. The chain now
persists cleanly, produces a draft Sale Order for every design, seeds
Manufacture BOMs where they were missing, and degrades gracefully to
a "here is your draft, click Request Production" screen when the
business's Production Approval workflow is legitimately blocking
release. Sales Managers get a one-click override; non-managers see a
friendly explanation instead of a rolled-back transaction.

---

## 2 · Timeline

| Version   | Commit    | Date (local)         | Fix (one-liner) |
|-----------|-----------|----------------------|-----------------|
| 5.6.0     | `5434f5f` | 2026-07-01 19:11 EDT | Track B autoseed + `Create & Confirm →` shipped (initial) |
| 5.6.3     | `1dabdce` | 2026-07-01 22:01 EDT | 3-in-1: drop `mrp.bom.note`, guard archived BOMs, fix button label triple-escape |
| 5.6.4     | `f0c76e4` | 2026-07-01 22:46 EDT | Run autoseed **before** the production-ready gate (call-ordering P0) |
| 5.6.5     | `bc3b9a9` | 2026-07-01 23:21 EDT | Attach `mrp.route_warehouse0_manufacture` to canonical templates + defense-in-depth in `_ensure_kitchen_bom` |
| 5.6.6     | `6e79099` | 2026-07-01 23:27 EDT | Wrap `order.action_confirm()` in `env.cr.savepoint()` (persistence P0) |
| —         | `a4b8cfb` | 2026-07-01 23:27 EDT | Follow-up: bump manifest to 5.6.6 (missed in `6e79099`) |
| —         | `6f375e1` | 2026-07-01 23:31 EDT | Follow-up: rewrite route-seed XML to canonical `<record id="MODULE.xmlid">` form (5.6.6 deploy blocker) |
| 5.6.7     | `4b13b55` | 2026-07-01 23:53 EDT | UX pack: customer picker on 3D canvas, `default_get` autofill, archive infra, toasts, Sales Manager auto-bypass |
| —         | `d281974` | 2026-07-01 23:54 EDT | Follow-up: search view — drop `<group string="…">` (v19 ParseError trap) |
| 5.6.8     | (working tree) | 2026-07-02   | `action_reset_quote_link` safety valve for stale draft SO links + Sales Manager auto-bypass polish |

Each commit's full message is available via
`git log <hash> --format=%B` — the messages carry the "why" and are
the authoritative record for edge-cases not captured here.

Supporting-cast commits landed in the same session:

- `5d1cf86` — Track F regression pins (7 anchor tests) + Track C doc drift fix
- `022f3cf` — pre-commit hook extended with `.esm` suffix check
- `faa01fb` — OWL tokenizer lint backported from a feature branch onto main
- `ee2c8d9` — `deploy_to_qnap.sh` SIGHUPs live workers after cold upgrade
- `eedc368` — `.gitignore` for the session's Claude scratchpad dir

---

## 3 · Root causes explained

Each subsection walks: (a) what the bug was, in code, (b) why it was
hard to catch, (c) what the fix mechanism was and why we chose that
mechanism over the alternatives.

### 3.1 · 5.6.0 (`5434f5f`) — the initial ship

`southbrook_kitchen_3d_configurator/models/kitchen_design.py` gained
two things:

- `_ensure_kitchen_bom(product_tmpl)` — idempotently create a template-
  level `mrp.bom` stub if none exists, using
  `southbrook_estimating.mrp_bom._compute_panel_dimensions` for the
  parametric panel geometry.
- A `Create & Confirm →` header button on the Kitchen Design form
  that dispatches `action_create_quotation` with
  `context={'confirm_immediately': True}`, then jumps the user to the
  `mrp.production` form instead of the Sale Order form.

This shipped without JS changes, deliberately dodging the Rec D Sprint
2d canvas failure surface (which had rolled back a few hours earlier;
see `docs/rec_d_sprint2d_postmortem_2026-07-01.md`). Backend-only
scope was chosen for speed. It also meant the whole path was E2E-
untested against a live prod design — the first real click happened
on 2026-07-01 evening.

### 3.2 · 5.6.3 (`1dabdce`) — three-in-one

Three independent bugs surfaced by the E2E audit fired in the same
commit because each was ~5 lines and none blocked the others.

**Bug A — `mrp.bom.note` does not exist in Odoo v19 CE.**

`_ensure_kitchen_bom` at `kitchen_design.py` (old line ~830) passed
`"note": json.dumps(panel, ...)` into `Bom.create({...})` as a
placeholder for the panel geometry JSON. A verification pass against
Odoo v19's source `mrp/models/mrp_bom.py` confirmed the model has **no
`note` column** in v19 CE — chatter comes from the `mail.thread`
inherit, not a text column. Result: the very first `Create Quotation`
click against a template without a pre-existing BOM raised
`ValueError: Invalid field 'note' on model 'mrp.bom'`. The surrounding
`try/except UserError` did **not** catch it (wrong exception type), so
the whole request transaction rolled back — including the SO create.

Why hard to catch: XML lint passed (no XML involved), module install
passed (`Bom.create` isn't called at install time), and every dev
smoke test against a template with a pre-seeded BOM took the fast-
path early-return at line ~810 and never reached the buggy `create`
call. Only a first-quote against a bare template hits it.

Fix mechanism: drop `"note"` from the create dict and log the panel
geometry to `odoo.log` instead. The follow-up commit that will walk
this JSON into `bom_line_ids` was already deferred (see §5), so
nothing downstream reads it — the panel geometry is deterministic
from template dims and family, so a future materialization will
recompute rather than re-read.

**Bug B — archived-BOM guard missed.**

`product_tmpl.bom_ids.filtered(lambda b: b.type == "normal")` uses
Odoo's default `active_test=True` context. If a normal BOM exists on
the template but has been archived (`active=False`), the filter
skips it, the fast-path returns empty, and `Bom.create()` runs again
— stacking a live BOM on top of the archive. That's not a correctness
disaster but does violate the "idempotent" contract of
`_ensure_kitchen_bom`.

Fix: wrap `.bom_ids` in `.with_context(active_test=False)` before the
`.filtered(...)` so archived normals are visible to the guard.

**Bug C — button label triple-escape.**

`views/kitchen_design_views.xml:117` (pre-fix) contained
`string="Create &amp;amp; Confirm →"`. XML parsing decodes
`&amp;amp;` to `&amp;` once; OWL then renders that as literal text
because it doesn't do a second HTML-unescape pass on `string=`. Users
saw a button labelled `Create &amp; Confirm →` in the header.

Fix: single-escape to `Create &amp; Confirm →`.

### 3.3 · 5.6.4 (`f0c76e4`) — the ordering P0 (and the pre-existing "deferred" comment)

With 5.6.3 in place, the E2E audit against Design #15 hit a second
class of failure: **every** kitchen design whose cabinet template did
not already have a manually-created BOM was rejected at the pre-quote
gate. The `Create & Confirm →` button raised
`UserError("Design isn't production-ready. Resolve these blocking
issues first: MISSING_BOM")` with zero autoseed activity in the log.

**Root cause.** `action_create_quotation` at (pre-fix)
`kitchen_design.py` ran in this order:

1. hard check `design.partner_id` (OK)
2. `_check_production_ready()` → returns `MISSING_BOM` when any
   `design.cabinet_line_ids.product_id.product_tmpl_id` has no normal
   BOM → `raise UserError` (fatal)
3. `SaleOrder.create(vals)` — never runs
4. `_ensure_kitchen_bom(tmpl) for tmpl in order lines` — never runs

The whole point of Track B was to auto-seed those BOMs so the gate
would pass. But the seed was scheduled to run **after** the gate, so
the gate rejected every design the seed was designed to fix.

**Why hard to catch.** The comment block at the old line 745-748
literally said the seed here was "defence-in-depth on the forward
path" because "the D12 pre-quote MISSING_BOM gate already flags
absent BOMs as blocking upstream" — someone knew the ordering was
inverted and deferred fixing it. This is the "deferred comment" the
brief calls out. In the developer's mind, an upstream gate on
MISSING_BOM was a feature, not a bug; nobody stepped through the
call chain to notice the seed only ran once the gate had already
rejected the request.

**Fix mechanism.** Insert a new autoseed loop **before** the gate,
walking `design.cabinet_line_ids.mapped("product_id.product_tmpl_id")`
and calling `_ensure_kitchen_bom(tmpl)` inside a `try/except
UserError` (per-template failure logged but non-fatal). Now the gate
sees the just-seeded stubs and `MISSING_BOM` only fires on templates
the autoseed genuinely couldn't fix. The post-SO-create autoseed loop
(the original 5.6.0 code path) was **left in place** as defense-in-
depth — it's idempotent, cheap, and catches any new template that
surfaced between design save and SO create in a longer-running session.
See `kitchen_design.py:880-897`.

Live-prod evidence at deploy time: 5 of 21 configured designs
(ids 14, 15, 17, 18, 20) had `MISSING_BOM + NEED_CUSTOMER` as their
only blockers.

### 3.4 · 5.6.5 (`bc3b9a9`) — the missing Manufacture route

5.6.4 unblocked the gate. The rep clicked **Create & Confirm →**, the
autoseed ran, `_check_production_ready` passed, `SaleOrder.create`
succeeded, `order.action_confirm()` returned without error, the app
redirected to the MO surface — **and zero MOs existed**.

**Root cause.** The 11 canonical Southbrook cabinet templates
(`southbrook_estimating.wall_1dr`, `.base_2dr`, `.drawer_bank`, …)
had `route_ids = []`. Without the standard Manufacture route on the
template, Odoo's procurement.group scheduler only sees the Delivery
route (present via the warehouse default) and spawns a delivery
picking — it never selects the BOM, so `mrp.production` is never
created. A BOM without a Manufacture route on the source template is
inert.

**Why hard to catch.** No error, no log message, no user-facing
notification. `order.action_confirm()` returned cleanly. The
procurement engine is silent when a route lookup returns nothing —
that's the expected behavior for "we don't manufacture this SKU here",
so the log line the scheduler would need to emit ("no manufacturable
route found for template X") doesn't exist. The failure is a
disappearance, not an exception.

**Fix mechanism (two-part).**

Part 1 — canonical seed at
`addons/southbrook_kitchen_3d_configurator/data/canonical_catalog_routes.xml`
(NEW, `noupdate="1"`). Links `mrp.route_warehouse0_manufacture` onto
the 11 canonical cabinet templates via `[(4, ref('...'))]` (M2M LINK,
not REPLACE — preserves any other routes a rep intentionally added).
`worktop` is deliberately excluded (countertop, not a manufactured
cabinet, same convention as `canonical_catalog_tag.xml`). `noupdate=1`
so runtime edits survive a subsequent `-u`.

Part 2 — defense-in-depth in
`kitchen_design.py:798-802` inside `_ensure_kitchen_bom`. Every call
to the seed method now also re-applies the Manufacture route on the
template (`env.ref(..., raise_if_not_found=False)` + membership
check — no-op if already present). This catches runtime-created
templates (e.g. the 3D configurator's fast-path) that missed the
`noupdate="1"` install-time seed.

The 5.6.5 route-seed XML initially shipped with a non-canonical
`<record id="route_wall_1dr"><field name="id" ref="..."/>` idiom
which v19's XML loader rejects with ParseError. Follow-up commit
`6f375e1` rewrote all 11 records to the canonical
`<record id="MODULE.xmlid">` form.

### 3.5 · 5.6.6 (`6e79099`) — the savepoint (persistence P0)

Now the gate passes, autoseed runs, SO is created, Manufacture route
is on the template, `action_confirm` returns cleanly, and — **the
autoseed BOMs are still not in the database**. `MAX(create_date) FROM
mrp_bom` on live prod was `2026-06-18`, meaning **every autoseed
since Track B shipped had silently rolled back**. Only
`design.sale_order_id` survived a click, and only because the Rec D
reconcile cron (`reconcile.py:126`) writes it in a **separate**
transaction.

**Root cause.** `southbrook_mrp_pm.SaleOrder.action_confirm`
(`addons/southbrook_mrp_pm/models/sale_order.py:182-190`) calls
`_check_production_approval_gate` **before** `super()`. That method
raises `UserError` when the SO would spawn MOs but
`production_approval_state == "none"` and `force_production_release
== False` (see `sale_order.py:152-180`). The bare
`order.action_confirm()` call at (pre-fix) `kitchen_design.py:801`
had no savepoint, so the `UserError` propagated out of the JSON-RPC
handler and Odoo rolled back the **entire request cursor** — wiping
every autoseed BOM, the SO create, and the `design.state="quoted"`
write. The rep saw the `UserError` toast and went "OK, approval
gate, makes sense" — never noticing that the design had also lost
its BOMs.

Evidence (from live-prod log tail on 2026-07-02):

- `02:56:21,416` and `02:56:21,571` — `auto-seeded BOM for B24 …` and
  `auto-seeded BOM for W24 …` log lines confirm the seeds fired.
- `02:56:22,608` — `Cannot confirm sale order S01315 — these lines
  would generate manufacturing orders but the order is not
  Production-Approved` (verbatim from `mrp_pm/sale_order.py:166`).
- Raw SQL post-commit — zero `mrp.bom` rows for the affected
  `product_tmpl_id`s.
- `SELECT MAX(create_date) FROM mrp_bom;` — `2026-06-18` DB-wide.

**Why hard to catch.** The rollback is silent. Odoo emits nothing
beyond the `UserError` toast. The autoseed log lines are still there
in the log (the log write happens outside the ORM transaction), so
`grep 'auto-seeded BOM'` shows healthy activity — but the rows never
land. Any post-facto verification via SQL misses it too if the
verifier assumes "autoseed logged = BOMs created".

**Subagent RCA — clearing premium_orchestration.** Before landing the
savepoint, a subagent audited `southbrook_premium_orchestration/`
looking for a rogue inner `try/except` pattern that might have been
eating the rollback. It found several inner try/except blocks but
proved none of them were on the confirm path — the confirm goes
straight through the `mrp_pm` override, no premium_orchestration hook
intercepts it before the raise. Report cleared premium_orchestration
of blame; the exception was propagating cleanly out to the JSON-RPC
handler, which is exactly where Odoo's cursor rolls back.

**Fix mechanism.** Wrap `order.action_confirm()` in
`self.env.cr.savepoint()` — see `kitchen_design.py:1016-1041`. On
`UserError` the savepoint reverts **only** the confirm attempt;
everything upstream (autoseed BOMs, SO create, `sale_order_id` link,
`state="quoted"`) persists. Post a `mail.thread` message to the SO
explaining the block, then return an `act_window` for the SO form
view so the rep sees the draft + chatter + a Request Production
button. The `confirm_error` variable name is loadbearing for the
error-fallback branch (line 1031).

Why savepoint on the caller side (and not remove the `mrp_pm` gate):

- The Production Approval workflow is a legitimate business rule.
  CLAUDE.md §2.2 stage pipeline explicitly names Approval as a
  required step: `Draft → Estimating → Approval → Confirmed → In
  Production`. Removing it globally would break every other confirm
  path (Order Builder, direct SO form, external integrations).
- The autoseed BOMs, SO create, and `design.state="quoted"` writes
  are all **valid to persist** even if the confirm was blocked —
  the rep still wants the draft SO on the customer's account.
- The savepoint is the smallest possible intervention: 1 caller
  scope, 1 exception type, 1 fallback view. No changes to the gate
  itself.

Also closes task #52 ("Create & Confirm → button semantics mismatch
Production Approval workflow") — the button no longer promises
"confirm that always succeeds"; it degrades gracefully to "here is
your draft SO + a Request Production button".

### 3.6 · 5.6.7 (`4b13b55`) — UX pack

Not a bug fix per se — three parallel agents shipped ~200 LoC of
customer-ease UX now that the underlying flow was persistence-safe:

- **Model layer** (`kitchen_design.py`): `default_get` override
  auto-fills `partner_id` for portal users and callers passing
  `default_partner_id`; `get_recent_partners_for_picker` /
  `get_or_create_walkin_partner` as `@api.model` public methods
  reachable via `/web/dataset/call_kw` for the 3D canvas customer
  picker; `action_open_sale_order` smart-button target; polished
  `MISSING_CUSTOMER` copy pointing at the picker.

- **View layer** (`kitchen_design_views.xml`): `partner_id` promoted
  to a prominent full-width group directly under `oe_title`; SO
  smart button on `button_box` gated on `sale_order_id` present;
  archive UX (`active` field + `web_ribbon` + Search view with
  `filter_active`/`filter_archived` + `ir.actions.server` "Archive
  selected" bulk action); "Duplicate as New Version" rename.

- **JS/canvas layer**: `CustomerPicker` widget in the top bar,
  autocomplete against `get_recent_partners_for_picker`, pinned
  "Walk-in" fallback, portal-user detection via `@web/core/user` +
  reassurance pill, toast feedback via
  `useService("notification")`.

- **Sales Manager auto-bypass** (loadbearing for §3.7 story):
  `kitchen_design.py:991-1015`. If the confirming user is in
  `sales_team.group_sale_manager`, set
  `order.force_production_release = True` and message-post the
  bypass before the `savepoint` block. Sales Managers already have
  the authority to tick that field manually on the SO form — this
  just removes a redundant click. If a non-manager clicks the
  button, the savepoint below still catches the resulting gate
  raise gracefully.

### 3.7 · 5.6.8 (working tree) — `action_reset_quote_link` safety valve

Landed in the working tree, not yet committed. Two additions:

- New `action_reset_quote_link` method on `SouthbrookKitchenDesign`
  (`kitchen_design.py:311-334`). Clears `sale_order_id` and reverts
  state to `configured` so a design can be re-quoted after a prior
  stale draft. Refuses on `state == "ordered"` to preserve the
  manufacturing/delivery audit trail. Does **not** delete the
  underlying `sale.order` — that stays as a separate rep decision.
- New "Reset Quote Link" button in the design form
  (`kitchen_design_views.xml:200-212`), `invisible` when
  `not sale_order_id` or `state == 'ordered'`, gated by a `confirm=`
  dialog.

Motivation: Design #15 pointed at a stale draft `S01314` from an
earlier failed attempt; re-clicking Create Quotation would try to
reuse the stale link's downstream logic. This gives the rep an
explicit unlink path.

---

## 4 · The verification chain

How we proved each fix worked — reproduce these to verify a
suspected regression.

**Live prod odoo shell — dry-run + rollback.**

```bash
ssh ssh.odooiq.com "$QNAP_DOCKER exec -it southbrook-odoo /usr/bin/odoo shell -d southbrook -c /etc/odoo/odoo.conf"

# inside shell:
env.cr.execute("SAVEPOINT track_b_check")
d = env["southbrook.kitchen.design"].browse(15)
d.with_context(confirm_immediately=True).action_create_quotation()
# ... observe result, check env["mrp.bom"].search([("code","like","KitchenAutoSeed-%")])
env.cr.execute("ROLLBACK TO SAVEPOINT track_b_check")
```

**Log tail comparison — before vs. after each patch.**

```bash
ssh ssh.odooiq.com "$QNAP_DOCKER exec southbrook-odoo tail -F /var/log/odoo/odoo.log" \
    | grep --line-buffered -E 'auto-seeded BOM|Cannot confirm sale order|Style error|Production-approval'
```

Missing `auto-seeded BOM` lines → autoseed never fired (5.6.4
regression).
Present `auto-seeded BOM` lines + absent `mrp.bom` rows in SQL →
savepoint regression (5.6.6).
`Cannot confirm sale order` line → gate fired, savepoint should
catch and fallback. If gate fired but no SO exists after — savepoint
missing entirely.

**Direct SQL against `mrp_bom.create_date` — persistence check.**

```sql
SELECT COUNT(*), MAX(create_date)
  FROM mrp_bom
 WHERE code LIKE 'KitchenAutoSeed-%';

SELECT id, product_tmpl_id, code, create_date, active
  FROM mrp_bom
 WHERE code LIKE 'KitchenAutoSeed-%'
 ORDER BY create_date DESC
 LIMIT 20;
```

If `MAX(create_date)` predates the last known "Create & Confirm →"
click, autoseed is rolling back → 5.6.6 regression.

**Manufacture route presence.**

```sql
SELECT rp.product_tmpl_id, pt.name, rp.route_id
  FROM stock_route_product rp
  JOIN product_template pt ON pt.id = rp.product_tmpl_id
 WHERE rp.product_tmpl_id IN (
       SELECT res_id FROM ir_model_data
        WHERE module = 'southbrook_estimating'
          AND model  = 'product.template'
 );
```

Empty rows for canonical templates → 5.6.5 regression.

**Deploy → SIGHUP → verify pattern.**

Per memory `[[odoo19_public_route_needs_sighup]]`, cold upgrade
alone does not reload live worker bytecode; every deploy of a
`kitchen_design.py` change is followed by
`docker exec southbrook-odoo kill -HUP 1` and an 8-second wait.
`ee2c8d9` folded this into `deploy_to_qnap.sh` so future deploys
handle it automatically. The 5.6.4 fix looked like a no-op for
~10 minutes until the SIGHUP landed manually; that trap is now
closed at the tool level.

---

## 5 · Remaining gaps (honesty section)

The chain is persistent and produces MOs. It is **not** yet
end-to-end complete.

- **Stub BOMs with zero components.** `_ensure_kitchen_bom` creates
  `mrp.bom` records with `bom_line_ids = []`. A confirmed MO
  spawned from these will have zero raw-material demand — nothing
  to pick, nothing to consume, no cut list. The 5.6.0 commit
  message explicitly deferred the "follow-up commit walks this
  JSON blob" work, and that commit is still unwritten. Blocker:
  no raw-material `product.product` records exist yet (panel
  stock, edge-banding, hardware, etc.). Landing the BOM-line
  materialization is a data-modeling exercise, not a code exercise,
  and belongs to a Phase-4 workstream (cut-list bridge) per
  CLAUDE.md §8.

- **`canonical_catalog_routes.xml` is `noupdate="1"`.** New
  installs get the Manufacture route via the seed on `-i`;
  existing installs (`-u`) do not re-apply the seed and instead
  get the route via the defense-in-depth in `_ensure_kitchen_bom`
  which fires at first quote time. Consequence: a template that
  exists but has never been quoted may still be `route_ids=[]`
  for a while. Not a correctness bug — the seed lands as soon as
  the template is used — but a fresh clone of prod's DB into a
  test environment would surface this asymmetry.

- **Production Approval gate is real.** The 5.6.6 savepoint and
  the 5.6.7 Sales Manager auto-bypass together address the
  approval-gate **UX** (draft persists, manager gets one click,
  rep gets a clear message). The underlying business rule — that
  a rep who is not a Sales Manager cannot spawn MOs without
  approval — remains in force globally and should **not** be
  removed. The Production Approval workflow is what
  `southbrook_mrp_pm` exists for; deleting the gate would break
  W009 semantics and every other confirm caller (Order Builder,
  direct SO form, cron reconcile, external integrations).

---

## 6 · Tooling improvements this session

Three infrastructure improvements landed alongside the Track B
fixes — each closes a class of trap that has cost multiple sessions.

- **Pre-commit hook backported to `main`** (`faa01fb`). The OWL
  tokenizer lint (`scripts/lint-owl-expr.py`) was authored on a
  feature branch on 2026-06-22 after the OWL "or"/"and"/"not"
  bug class hit Southbrook three times in <12h — and had never
  made it onto main. This session's Phase-1 P0 audit noticed
  the gap and folded the scanner, hook, install script, self-
  tests, and fixtures onto main. Wire it up with
  `bash scripts/install-hooks.sh` on a fresh clone.

- **`.esm` suffix check added to the hook** (`022f3cf`).
  Backports the pre-flight guard from
  `scripts/rec_d_sprint2d_tripwire.sh:78-85`. Odoo registers OWL
  modules using the on-disk filename minus `.js`, so a file named
  `constants.esm.js` registers as `@.../js/canvas/constants.esm`
  — importing it as `@.../js/canvas/constants` (no `.esm`
  suffix) passes XML lint, passes install, passes /web/login, but
  throws at first WebClient mount. This is the exact bug that
  forced the Rec D Sprint 2d 5.4.13 rollback. The tripwire catches
  it at commit time instead of during a deploy round-trip.

- **`deploy_to_qnap.sh` SIGHUPs live workers after cold upgrade**
  (`ee2c8d9`). Cold `-u --stop-after-init` reloads bytecode in a
  new process, but the **live** HTTP workers keep serving the
  stale ORM registry until they receive SIGHUP. The 5.6.4 deploy
  visibly did nothing for ~10 minutes until someone manually ran
  `kill -HUP 1`, at which point the fix worked correctly. The
  deploy script now does this automatically between the cold-
  upgrade success line and the `/web/login` health gate. Best-
  effort — a SIGHUP failure logs `WARNING` but doesn't fail the
  deploy (a subsequent request will reload lazily). Never
  `docker restart` — see memory
  `[[qnap_postgres_recovery_hazard]]`.

- **`docs/track_c_price_extra_pending_2026-07-01.md` drift fix**
  (`5d1cf86`). The header previously read "Not applied. Design
  ready" — a stale claim, since Track F had actually landed 5 of
  6 anchors at `southbrook_estimating` 7.2.0 with confident
  defaults. Header rewritten to "Partially landed: 5 anchors
  seeded at 7.2.0 with confident defaults; `finish_premium_colors`
  deferred". Same commit landed 7 regression pins in
  `tests/test_price_extra_flow.py`.

---

## 7 · Operational runbook (for future incidents)

Concrete triage steps for a future contributor debugging a similar
Track B failure. Symptoms are grouped; each has a check ladder
that walks from the most-recent-regression-risk downward.

### Symptom A — `Create & Confirm →` click fails silently; no MO spawned; user sees a toast or nothing

Check in order:

1. `SELECT COUNT(*), MAX(create_date) FROM mrp_bom WHERE code LIKE 'KitchenAutoSeed-%';`
   If `create_date` has **not** advanced since the click, the
   autoseed rolled back → **5.6.6 savepoint regression risk**.
   The savepoint at `kitchen_design.py:1018` must wrap only
   `order.action_confirm()`.

2. `SELECT route_id FROM stock_route_product WHERE product_tmpl_id IN (<affected template ids>);`
   If empty for a canonical cabinet template, the Manufacture
   route is missing → **5.6.5 regression**. Either
   `canonical_catalog_routes.xml` failed to load, or the
   defense-in-depth in `_ensure_kitchen_bom:798-802` was
   removed.

3. `docker exec southbrook-odoo grep 'auto-seeded BOM' /var/log/odoo/odoo.log | tail`
   If empty, the autoseed never fired → **5.6.4 regression**.
   The pre-gate loop at `kitchen_design.py:880-897` must run
   before `_check_production_ready()`.

4. Confirm the button is dispatching the expected method:

   ```bash
   docker exec southbrook-odoo /usr/bin/odoo shell -d southbrook -c /etc/odoo/odoo.conf -c \
       "print(env['southbrook.kitchen.design'].browse(N).action_create_quotation.__module__)"
   ```

   Should print `odoo.addons.southbrook_kitchen_3d_configurator.models.kitchen_design`.
   If it prints anything else (e.g. a rogue Studio override or a
   sibling addon extension), the button is not running the code
   this document describes.

### Symptom B — `Create & Confirm →` appears to succeed but MO surface shows zero MOs

`action_confirm` returned cleanly, the SO is confirmed, but no
`mrp.production` exists. Check:

1. `SELECT * FROM stock_move WHERE origin = '<SO name>';`
   Did stock moves land at all? If not, the SO isn't confirmed —
   check `sale.order.state`.

2. Do the SO's line templates carry the Manufacture route?

   ```sql
   SELECT pt.name, rp.route_id
     FROM sale_order_line sol
     JOIN product_product pp ON pp.id = sol.product_id
     JOIN product_template pt ON pt.id = pp.product_tmpl_id
     LEFT JOIN stock_route_product rp
       ON rp.product_tmpl_id = pt.id
    WHERE sol.order_id = <SO id>;
   ```

   If `route_id` is NULL for all rows, the route is missing (see
   Symptom A step 2).

3. Do those templates have `mrp.bom` records?

   ```sql
   SELECT id, code, active FROM mrp_bom
    WHERE product_tmpl_id IN (<template ids>);
   ```

   No rows → autoseed didn't fire or didn't persist.

4. If routes and BOMs are both present and MOs still don't
   spawn, walk the procurement stack: `procurement.group` on the
   SO (`_action_launch_stock_rule`), `stock.rule` on the
   warehouse's Manufacture route, and any custom
   `sale.order.line._action_launch_stock_rule` overrides in
   `southbrook_mrp_pm` or `southbrook_estimating`. Enable
   `--log-handler=odoo.addons.stock.models.stock_rule:DEBUG` and
   watch the log during a fresh confirm.

### Symptom C — button-click UserError toast: "Cannot confirm sale order … not Production-Approved"

Not a regression — the Production Approval gate fired legitimately
because the confirming user is not a Sales Manager. Behavior
per §3.5:

- The savepoint should have reverted **only** the confirm; the
  draft SO should exist with a chatter message explaining the
  block.
- The rep should be looking at the SO form with a "Request
  Production" button.

If the SO does **not** exist after this toast, the savepoint
regressed → §3.5.

---

## 8 · Session commits (git log)

Full session log — everything committed 2026-07-01 →
2026-07-02, in reverse chronological order. Track B fixes are
starred.

```
2ba510c 2026-07-02 00:46 feat(hermes): 4.6.0 · Fabio Asker group so non-admins can Ask Fabio
d281974 2026-07-01 23:54 fix(3d_configurator): search view · drop group string= (v19 ParseError trap)
4b13b55 2026-07-01 23:53 feat(3d_configurator): 5.6.7 · customer-ease UX pack (tasks #48 + #49)          [*]
4eaa93f 2026-07-01 23:39 feat(hermes) — Fabio recs #4-6 (shop-ops + persona expansion + email drafts)
6f375e1 2026-07-01 23:31 fix(3d_configurator): route seed · use direct xmlid targeting, not field.id ref [*]
a4b8cfb 2026-07-01 23:27 fix(3d_configurator): 5.6.6 · manifest version bump (missed in 6e79099)         [*]
6e79099 2026-07-01 23:27 fix(3d_configurator): 5.6.6 · savepoint action_confirm (Track B P0-A)           [*]
022f3cf 2026-07-01 23:25 chore(hooks): extend pre-commit lint with .esm suffix check (backport tripwire)
faa01fb 2026-07-01 23:23 chore(scripts): backport OWL lint scanner + pre-commit hook from feature branch
eedc368 2026-07-01 23:21 chore: gitignore .claude/ session dir
ee2c8d9 2026-07-01 23:21 ops(deploy): SIGHUP live workers after cold-upgrade success
bc3b9a9 2026-07-01 23:21 fix(3d_configurator): 5.6.5 · add Manufacture route to canonical templates     [*]
5d1cf86 2026-07-01 23:19 test(estimating): Track F regression pins · 7 anchor tests + Track C doc drift fix
f0c76e4 2026-07-01 22:46 fix(3d_configurator): 5.6.4 · autoseed BEFORE production-ready gate            [*]
1dabdce 2026-07-01 22:01 fix(3d_configurator): 5.6.3 · Track B autoseed P0 + button label + archived-BOM guard [*]
5434f5f 2026-07-01 19:11 feat(3d_configurator): BOM autoseed + confirm-immediately flow (Track B · 5.6.0) [*]
```

Working tree (uncommitted at time of writing):
`addons/southbrook_kitchen_3d_configurator/{__manifest__.py,models/kitchen_design.py,views/kitchen_design_views.xml}`
— version bump to `19.0.5.6.8`, new `action_reset_quote_link` + button.

---

## Appendix — file:line quick-reference

For readers walking the code alongside this document.

| Concern | File | Lines |
|---|---|---|
| `_ensure_kitchen_bom` (autoseed) | `addons/southbrook_kitchen_3d_configurator/models/kitchen_design.py` | 776-873 |
| Manufacture-route defense-in-depth | same | 789-802 |
| Fast-path with `active_test=False` | same | 807-811 |
| `note`-field bug (removed) | same | 861-867 |
| `action_create_quotation` | same | 875-1070 |
| Pre-gate autoseed loop (5.6.4) | same | 880-897 |
| Production-readiness gate | same | 903-910 |
| Post-SO autoseed loop (defense-in-depth) | same | 957-972 |
| Sales Manager auto-bypass (5.6.7) | same | 991-1015 |
| Savepoint block (5.6.6) | same | 1016-1041 |
| Zero/multi-MO fallback | same | 1053-1062 |
| `_check_production_approval_gate` (mrp_pm) | `addons/southbrook_mrp_pm/models/sale_order.py` | 152-190 |
| Canonical route seed | `addons/southbrook_kitchen_3d_configurator/data/canonical_catalog_routes.xml` | (whole file) |
| Reset-quote-link button | `addons/southbrook_kitchen_3d_configurator/views/kitchen_design_views.xml` | 197-212 |
| Pre-commit hook (`.esm` guard) | `scripts/hooks/pre-commit` | 94-131 |
| Deploy SIGHUP block | `scripts/deploy_to_qnap.sh` | ~194-215 |

---

*Document authored 2026-07-02, session artifact for
`southbrook-v19cr` main branch. Not a substitute for reading the
commit messages — those carry additional edge-case detail that would
bloat this runbook.*
