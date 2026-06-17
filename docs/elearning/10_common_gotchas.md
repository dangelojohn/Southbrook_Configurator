---
course: 10 — Configurator Deep Dive
chapter: 10.7
title: Common Gotchas — Exclusion Explosion, Rule Ordering, Performance, Recovery
duration: 40 minutes
audience: Anyone who extends the configurator after the first 6 lessons. Devs, senior admins, lead estimators.
prereqs: Lessons 10.1 - 10.6. You've at minimum read 10.1, 10.2, and 10.3.
custom_modules: product_configurator, product_configurator_sale, product_configurator_mrp, website_product_configurator, southbrook_configurator_ux
---

# Common Gotchas — Exclusion Explosion, Rule Ordering, Performance, Recovery

## Who this lesson is for

You've made it through the architecture, the new-product flow, the
session state machine, both integration layers, and the v2 UX deep
dive. You can read the codebase. But the configurator is a system
that gets harder to reason about as the catalog grows — 5 attributes
with 8 values each is fine; 12 attributes with 15 values each is
where the wheels come off. This lesson is the bestiary of failure
modes that surface as the system scales, and how to recover from
each. Read it once before your next non-trivial change.

## Where this lives on the site

You'll be in three places when these gotchas bite:

> **Sales → Configuration → Configuration Rules** — to spot the
> exclusion-rule sprawl.

> **Sales → Configurable Products → Configuration Sessions** —
> filter by state=draft, group by template, to spot stuck or
> abandoned sessions.

> The dev shell (`odoo-bin shell -d <db>`) — where you'll diagnose
> and recover.

## What your screen shows

There's no single screen for "gotchas" — each one shows up
differently:

- **Exclusion explosion** — the Rules list grows from 4 records to
  40 records to 400 over six months. Every new attribute value
  needs its own exclusion against the prior ones; the rule catalog
  becomes unmaintainable.
- **Rule ordering bugs** — two rules apply to the same
  attribute_line; whichever runs second wins. The customer reports
  "the system let me pick X" when X is supposedly blocked.
- **Performance** — the wizard takes 2-4 seconds per pick on
  templates with 50+ attribute_lines. The OWL component's
  `/select` round-trip is the bottleneck.
- **"Configuration session not found"** — a customer's URL points
  at a session that's been GC'd, or never existed.
- **Stuck sessions** — `state=draft`, `value_ids` is non-trivial,
  but `validate_configuration` raises. The user can't progress AND
  can't reset.
- **Phantom variants** — `product.product` records that look like
  duplicates but aren't, blowing up the variant catalog.

## Your daily flow

The five most common gotchas, each with a recovery path.

**1. Exclusion explosion.**

You add a new Series called "Heritage." Heritage doesn't allow
Slab doors. You write a rule:

```xml
<record id="rule_heritage_door_style" model="product.config.line">
  <field name="product_tmpl_id" ref="base_2dr"/>
  <field name="attribute_line_id" ref="attr_line_base_2dr_door_style"/>
  <field name="value_ids" eval="[(6, 0, [
    ref('value_door_five_piece_woodgrain'),
    ref('value_door_fluted'),
    ref('value_door_custom')])]"/>
  <field name="domain_id" ref="domain_series_is_heritage"/>
</record>
```

Note the `value_ids` is the **allowed** set (lesson 10.2). You've
listed all 3 non-Slab values. Now add a 4th door style: "Beaded."
You have to update Heritage's rule, AND every other Series rule
that listed the allowed set. **The rule cost is O(N×M)** —
N series × M door styles. Six months and 5 new attributes later
the rule catalog has 200+ records.

**Mitigation:**

- **Use "not in" condition on domain.lines.** Instead of listing
  the allowed values on the rule, list the BLOCKED trigger values
  on the domain. The rule's `value_ids` then lists only the
  forbidden set — which is usually 1-2 items. Saves the O(N×M)
  to O(N+M). The OCA model supports it (`condition in [in,
  not in]` — see line 95 of `product_configurator/models/product_config.py`).
- **Move from exclusions to attribute_line value_ids.** If a
  template never offers a value, don't list it on the
  attribute_line at all. The wizard never offers it; no rule
  needed. Use rules only for **conditional** restrictions.
- **Audit rule cardinality regularly.** Run in shell:
  ```python
  Rule = env["product.config.line"]
  by_tmpl = {}
  for r in Rule.search([]):
      by_tmpl[r.product_tmpl_id.id] = by_tmpl.get(r.product_tmpl_id.id, 0) + 1
  print(sorted(by_tmpl.items(), key=lambda x: -x[1])[:10])
  ```
  Templates with > 30 rules need a refactor.

**2. Rule ordering bugs.**

Two rules for the same attribute_line on the same template:

- Rule A: `domain_series_is_contractor` → allow `[Thermofoil Slab]`.
- Rule B: `domain_box_is_maple` → allow `[Five-Piece, Fluted, Custom]`.

User picks Series=Contractor + Box=Maple. Both rules fire. Which
wins?

The OCA engine reads rules in `sequence` order (line 165:
`_order = "product_tmpl_id, sequence, id"`). The LAST rule's
`value_ids` is what survives — the earlier rule's allowed set is
overwritten because each rule rewrites the attribute_line's
available values, not intersects.

The right answer: the **intersection** should be the allowed set
({Thermofoil Slab} ∩ {Five-Piece, Fluted, Custom} = ∅), meaning
the combination is invalid and the user should see a hard block.
The OCA engine does NOT intersect. Last-rule-wins.

**Mitigation:**

- **Author rules so they don't overlap on the same attribute_line.**
  Each (template, attribute_line) should have at most ONE rule's
  domain match at any time. Use mutually-exclusive domain
  conditions.
- **Set `sequence` explicitly when ordering matters.** The default
  is 10; set to 5/15/25 to control eval order. Higher number wins
  (runs last).
- **Combine rules into one with compound domain.** If Series=
  Contractor AND Box=Maple is the trigger, write ONE rule with a
  domain that uses `domain_line.operator = and` to require both.
  See `product.config.domain.line.operator` at line 150.

**3. Performance — slow `/select` round-trips.**

Symptom: customer picks a chip, the LIVE badge shows for 2-3
seconds before the price updates. On templates with 50+
attribute_lines.

`controllers/main.py:configurator_select` calls
`session.values_available(check_val_ids=list(all_val_ids))` which
calls OCA's rule engine for every value. Each rule evaluates its
domain via `compute_domain()` (line 34). For a template with
20 attribute_lines × 10 values × 30 rules, that's potentially
6,000 domain evals per click.

**Mitigation:**

- **Cache `all_val_ids` per template per request.** The set
  doesn't change between picks within a session.
- **Reduce rule count via the cardinality audit (gotcha #1).**
- **Add Postgres indexes**: `product_config_line.product_tmpl_id`,
  `product_config_line.attribute_line_id`,
  `cfg_line_attr_val_id_rel(cfg_line_id)`. These are usually
  created by Odoo but verify under load.
- **Move heavy computations off the request path.** If you need
  derived data per pick (e.g. recommended add-ons), pre-compute
  at variant creation and read from the variant instead of
  recomputing in `/select`.
- **Profile with `pyinstrument`**: `odoo-bin shell -d <db>
  --enable=pyinstrument` then profile a real `/select` call to
  identify the actual hotspot.

**4. "Configuration session not found" — the dreaded error.**

Customer URL: `/configurator/<session_id>/...`. Server returns
404 or the v2 page shows `loadError = "session belongs to a
different user"`. Three causes:

- **Session GC'd.** Customer left it 3+ days, the website GC
  cron unlinked it. Recovery: customer reconfigures from
  scratch. No recovery for lost picks unless they hit Save
  Configuration first (and even then, see Lesson 10.3 gap re:
  `is_saved` not protecting against the website cron).
- **Session owned by another user.** Customer was anonymous, then
  logged in. The session's `user_id` is base.public_user; the
  authenticated user can't access it. Recovery: have the customer
  start a fresh session post-login, OR fix the controller to
  reassign `user_id` on login (currently not implemented).
- **Session never existed (typo / old link).** Customer
  bookmarked a session URL that got GC'd. Recovery: redirect to
  the product page so they can start fresh.

The defensive controller pattern (already in the codebase): every
endpoint that touches a session calls
`_authorize_session(session_id)` and returns an `error` dict the
OWL component can render gracefully.

**5. Stuck sessions.**

`state=draft`, `value_ids` has 8 values, `validate_configuration()`
raises. The customer can't proceed. The web UI greys everything out.

Common causes:

- The customer's prior picks no longer satisfy a rule that was
  added after the session was created. Rules are stored on the
  template — if you added a new rule, prior draft sessions
  immediately become invalid.
- A `default_val` on an attribute_line was changed; the session's
  auto-seeded default no longer matches the allowed set.
- An attribute_value was deactivated (`active=False`) but the
  session still references it.

**Recovery in the shell:**

```python
Session = env["product.config.session"]
s = Session.browse(<session_id>)
# What's currently picked
print([v.name for v in s.value_ids])
# Try validating to see the actual error
try:
    s.validate_configuration()
except Exception as e:
    print(repr(e))
# Strip the offending value(s)
s.value_ids = [(3, <bad_value_id>)]  # remove
# Or clear all picks and start over
s.value_ids = [(5, 0, 0)]
# Re-validate
s.validate_configuration(final=False)
```

The `write()` override (line 845) auto-prunes invalid values on
the way back — but only if you write `value_ids` directly. If
you go through `update_config(attr_val_dict)` (line 754) it
respects the dict semantics first.

**6. Phantom variants.**

Symptom: a template that should have 4 variants (one per Series)
has 47 variants in `product.product`. The catalog explodes.

Cause: every distinct `value_ids` combination through the
configurator can materialise a new variant. With
`create_variant='dynamic'`, OCA tries to dedupe — but only on
**exact** PTAV match. If two sessions pick the same values in
different orders or with custom values that differ trivially
(whitespace, case), they may create two variants.

Custom-value sessions ALWAYS create new variants (custom values
aren't dedupable). 47 variants on a custom-engraving template
might be 47 distinct engravings — that's correct.

**Mitigation:**

- **Audit periodically:**
  ```python
  P = env["product.product"]
  by_tmpl = {}
  for p in P.search([("config_ok", "=", True)]):
      by_tmpl[p.product_tmpl_id.id] = by_tmpl.get(p.product_tmpl_id.id, 0) + 1
  print(sorted(by_tmpl.items(), key=lambda x: -x[1])[:10])
  ```
- **For custom-value-heavy templates, accept the variant count.**
  It's intentional.
- **For non-custom templates with sprawl, dedupe**:
  ```python
  # Find variants with identical PTAV signatures and merge
  # (manual review — script the candidates, don't auto-delete)
  ```

## Common mistakes + how to recover

**"I added a new rule and the install errored: 'Values must belong
to the attribute of the corresponding attribute_line set on the
configuration line.'"**

The `check_value_attributes` constraint (line 229 of
`product_configurator/models/product_config.py`) verifies that
every value in `value_ids` is one of the values on the
`attribute_line_id`. You linked the rule to (say) Door Style's
attribute_line but listed a Series value_id. Fix the value_ids to
match the attribute_line's allowed set.

**"After I bumped the OCA module to a new version, the
auto-prune in `write()` started clearing valid picks."**

OCA may have changed how `values_available` interacts with
required attributes. Diff the method in the version upgrade. Common
case: a method that used to return all attribute_values when no
constraint applied now returns only matching ones. Fix by reading
the new contract carefully; don't just disable the override.

**"I uninstalled `southbrook_configurator_ux` and the rule the
addon shipped via `rule_completion.xml` stayed in the DB."**

Records in `noupdate="0"` files with explicit XML ids are still
data records — uninstall removes them ONLY if the data record's
`module` is the uninstalled module. Confirm:
`env["ir.model.data"].search([("module", "=", "southbrook_configurator_ux"),
("model", "=", "product.config.line")])`. If empty, the data
records were imported under a different module name (e.g.
manual XML id without module prefix) and uninstall doesn't sweep
them. Manually delete the orphaned records.

**"My v2 chip group is showing Other instead of the 4 named
groups."**

The attribute names on the new template don't match the
`ATTRIBUTE_GROUPS` constant (line 126 of
`controllers/main.py`). Spelling, case, leading/trailing spaces all
matter. Either rename the attribute or extend the constant. See
Lesson 10.6 for the constant.

**"BoM rollup produces empty BoMs for every variant of one
template."**

The parent BoM has zero unconditional lines AND zero conditional
lines that ANY variant matches. Check: open the parent BoM —
`bom_line_ids` should be non-empty; for any line with a
`config_set_id`, its `configuration_ids` should have at least one
`value_ids` set that matches a real variant's picks. Lesson 10.5
walks the rollup mechanics.

**"Customer reports the v2 page froze mid-configuration."**

Most likely the `/select` endpoint 500'd and the OWL component is
spinning waiting for response. Open Network tab → look at
`/southbrook/api/configurator/select` — what was the response?
The controller has a belt-and-braces fallback (line 435-444): if
`values_available` raises, it treats all values as enabled. If
even THAT fails, the response is a Python exception JSON. Add
the customer's session_id to the log, repro in shell with
`session.values_available(...)`, fix the actual error (often a
malformed rule data record).

## What the system is doing behind the scenes

The five gotchas above expose four design choices in the OCA
codebase that are load-bearing:

1. **Declarative rule engine.** Rules are data records, not code.
   This is a strength (auditable, hot-loadable, multi-tenant
   friendly) and a weakness (exclusion explosion, rule ordering
   surprises, no compile-time checks). Every gotcha here is an
   instance of the data-vs-code trade-off.
2. **Optimistic UI + server reconciliation.** The v2 OWL
   component updates state on click and reconciles from `/select`.
   This makes the UI feel snappy but creates race windows where
   clicks fire before the previous response. Mitigation:
   server-side guards (state lock, validation) always run; the UI
   is decoration, not enforcement.
3. **Session-as-receipt.** Once `state=done`, the session is
   immutable. This makes audit trails clean but means any
   "I want to edit my done configuration" flow has to spawn a
   new session via `reconfigure_product`. The old one stays.
   Database grows — see GC crons in Lesson 10.3.
4. **PTAV-level pricing/weighting.** `price_extra` and
   `weight_extra` live on `product.template.attribute.value`, NOT
   on the bare `product.attribute.value`. Every (template, value)
   gets its own override row, which is correct but means setting
   a price extra on a value is **per template** work.
   Centralising "Maple costs $X everywhere" requires either a
   script or a custom field.

The exclusion-explosion problem in particular has been raised
upstream multiple times. The OCA's TODO comment at line 38 of
`product_configurator/models/product_config.py`:

```python
# TODO: Enable the usage of OR operators between implied_ids
# TODO: Add implied_ids sequence field to enforce order of operations
# TODO: Prevent circular dependencies
```

These are exactly the cures for exclusion explosion + rule
ordering. Upstream hasn't shipped them. Southbrook works around
via discipline (Lesson 10.2's "use attribute_line value_ids, not
rules, for permanent restrictions").

## Quiz (5 questions, applied)

**1.** Your team adds 3 new Series this quarter (Heritage, Modern,
Industrial). Each must restrict door style. After authoring,
the configurator wizard takes 8 seconds per pick on the affected
templates. Outline a 3-step diagnosis-to-fix path.

> (1) Profile: open the dev shell, time
> `session.values_available(check_val_ids=list_of_all_value_ids)`
> on one of the slow sessions. If it's > 2s, you've found the
> bottleneck — rule eval count. (2) Count: run the rule cardinality
> audit from gotcha #1. If the affected templates have > 30 rules
> each, you've confirmed exclusion explosion. (3) Refactor: move
> permanent restrictions to `attribute_line.value_ids` (drop
> Slab from Heritage's door style attribute_line directly, kill
> the rule). Validate by re-timing — should drop to < 500ms per
> pick.

**2.** Two rules on the same template restrict the Door Style
attribute_line. Rule A allows {Slab}; Rule B allows {Slab,
Five-Piece, Fluted}. A user picks the trigger conditions for
BOTH rules simultaneously. Which value ends up offered, and how
do you make the intended behaviour (intersection — only Slab)
the actual behaviour?

> Last-rule-wins by `sequence` order. If Rule B's sequence > Rule
> A's sequence, the wizard offers {Slab, Five-Piece, Fluted} even
> though Rule A says only Slab. Fix: combine the two rules into
> one with a compound `product.config.domain` whose
> `domain_line_ids` require BOTH trigger conditions (use the `and`
> operator on the domain.line, default). Single rule, single
> allowed set ({Slab}). Cleaner than fighting sequence order.

**3.** Your monitoring shows 18,000 `product.config.session` rows
in the database. 17,200 are draft, 6 months old. Why didn't the
GC crons clean them up, and what's the recovery?

> Two suspects:
> (a) Crons are disabled. Check **Settings → Technical → Scheduled
> Actions** — both crons `active=True`? If not, enable.
> (b) Crons are running but the unlink is failing on a constraint
> (e.g. a draft session is referenced by a sale.order.line, but
> the cron tries to delete it anyway and Postgres FK refuses).
> Check the cron's last_call → error_count.
>
> Recovery: in the shell, run the unlink manually with explicit
> filter and try/except per record so one failure doesn't abort
> the batch:
> ```python
> from datetime import timedelta
> cutoff = fields.Datetime.now() - timedelta(days=30)
> sessions = env["product.config.session"].search([
>     ("state", "=", "draft"),
>     ("write_date", "<", cutoff),
> ])
> for s in sessions:
>     try: s.unlink()
>     except Exception as e: print("skip", s.id, e)
> env.cr.commit()
> ```

**4.** You ship a new attribute and accidentally set
`default_val` to a value that violates a rule already in the
catalog. Install runs clean (the rule fires only when the trigger
attribute is picked, which the default doesn't satisfy). Three
months later, customers start hitting "Default values provided
generate an invalid configuration" on session create. What
changed?

> Someone added the trigger attribute's default_val too. Now
> session creation seeds both attribute defaults simultaneously,
> and the rule's trigger is satisfied at create time —
> `validate_configuration(final=False)` runs during create
> (line 886) and raises. Fix: change one of the default_vals so
> the combination is valid, OR drop the default_val on the
> attribute that was added later (defaults are optional). Audit
> all attribute_lines' default_val combinations against the rule
> catalog before shipping new defaults.

**5.** A senior dev wants to "fix" rule ordering by overriding
`_order` on `product.config.line` to use a custom priority field.
The change ships. Three weeks later, 4 templates start showing
wrong allowed values. Diagnose and outline the right fix.

> The override changed eval order, which in last-rule-wins
> semantics changes which rule's `value_ids` survives. Templates
> whose rules were authored expecting the original `sequence,
> id` order now have a different "last rule" — wrong allowed
> values surface. Two options:
> (a) Revert the override; document the gotcha; insist new rules
> set explicit `sequence`.
> (b) Implement actual intersection semantics — override
> `values_available` to compute the intersection of allowed
> value sets from all matching rules, not last-wins. This is the
> right long-term fix and matches the OCA TODO. Risk: behaviour
> change to existing rules — every overlap that worked by
> accident may now break. Test against the full rule catalog
> before shipping.

---

## What this lesson does NOT cover

- Configurator vocabulary basics — Course 5, Lesson 5.1.
- 5-addon architecture — Lesson 10.1.
- Setting up a new configurable product — Lesson 10.2.
- Session state machine — Lesson 10.3.
- Sale flow integration — Lesson 10.4.
- MRP flow integration — Lesson 10.5.
- V2 UX deep dive — Lesson 10.6.
- The 3D parametric carcass layer (Phase 3) — separate workstream.
- General Odoo administration, performance tuning, database
  maintenance — Odoo's own native eLearning track + sysadmin
  Course 7.
