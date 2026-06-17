---
course: 9 — ProductGraph
chapter: 9.6
title: The Southbrook Bridge — ECO Closure Triggers a Release
duration: 35 minutes
audience: PLM engineer + estimator + dev (anyone whose ECO produces a release)
prereqs: Lesson 4.1 (ECOs), Lesson 9.1 (ProductGraph overview), Lesson 9.4 (EBOM editor)
custom_modules: southbrook_plm_productgraph (the bridge); depends on southbrook_plm + product_graph_release
---

# The Southbrook Bridge — ECO Closure Triggers a Release

## Who this lesson is for

You're an engineer who's about to apply an ECO that should also push a
new BoM into MRP. Or you're a developer debugging why a `pg.release`
fired (or didn't) when an ECO closed. Or you're the IT admin verifying
the bridge is wired correctly after a deploy. The Southbrook bridge is
a single tiny addon — one Python file, two field additions, one
override of `action_apply`. But it's the **only** documented path by
which a Southbrook ECO triggers writes into `mrp.bom` via ProductGraph.

This lesson is uniquely about the **glue**: the
`southbrook_plm_productgraph` addon that wraps `southbrook.eco.action_apply`
and fires `pg.release.action_execute_release()` after the PLM side
finishes. The Southbrook ECO model lives in `southbrook_plm` (lesson
4.1). The release flow lives in `product_graph_release` (lesson 9.4).
The bridge is the single file that knows about both.

## Where this lives on the site

The bridge surfaces on the **southbrook.eco form** under
`southbrook_plm`'s usual menu:

> **Manufacturing → PLM → Engineering Change Orders → [pick ECO] →
> ProductGraph Linkage group**

You will see three new fields and one new smart button:

- Field **ProductGraph EBOM** (`pg_ebom_id` on `southbrook.eco`)
- Field **Auto-trigger ProductGraph Release on Apply**
  (`pg_auto_release`)
- Field **Triggered ProductGraph Release** (`pg_release_id`) — read-only,
  appears only after a successful bridge fire
- Smart button **PG Release** — appears only when `pg_release_id` is set;
  opens the resulting `pg.release` form

The button group is injected via the inheriting view
`view_southbrook_eco_form_inherit_pg` in
`southbrook_plm_productgraph/views/southbrook_eco_views.xml`, xpath
`//sheet position="inside"` so it lands below the existing target /
approval / document blocks.

On disk:

- Code: `~/southbrook-v19cr/addons/southbrook_plm_productgraph/`
- Deployed: `/share/CACHEDEV3_DATA/Container/southbrook/addons/southbrook_plm_productgraph/`
- README: `southbrook_plm_productgraph/README.md`
- Spec: `~/product_graph_v19/bridge_spec/SPEC.md` (the published contract)

## What your screen shows

When you open an ECO that's not yet applied:

- **ProductGraph EBOM** (`pg_ebom_id`) — many2one to `pg.ebom`. Domain
  restricted to `[('state','=','released')]` — draft/review EBOMs
  don't appear in the dropdown. Optional. `copy=False`. Read-only once
  `state == 'applied'`.
- **Auto-trigger ProductGraph Release on Apply** (`pg_auto_release`)
  — boolean, default `True`. Read-only once `state == 'applied'`. Lets
  an engineer suppress the release for an ECO that should apply
  PLM-side but NOT touch MRP.
- **Triggered ProductGraph Release** (`pg_release_id`) — many2one to
  `pg.release`, readonly. Hidden via `invisible="not pg_release_id"`
  until a successful fire stamps it.

Once the ECO transitions to applied (`state = 'applied'`) and the
bridge fired:

- The smart button **PG Release** appears (also gated on
  `pg_release_id`). Clicking it calls `action_view_pg_release` which
  opens the `pg.release` form for the resulting record.
- A chatter post on the ECO records:
  `"ProductGraph release REL-NNNN executed — mrp.bom Cabinet-36
   created. Frozen open MOs: N."` (the line count comes from
  `release.frozen_mo_count`).
- If the bridge FAILED (release error, not PLM-side error), a chatter
  post records:
  `"ProductGraph release FAILED: <exc>. The ECO remains in `applied`
   state. Retry the release manually from EBOM <name> → Release to
   MRP …"`

## Your daily flow

**1. Author the change (engineering side).**

- Open the `pg.ebom` to be released (lesson 9.4) — author it, submit,
  approve, release. Now it's in `state='released'` and visible to the
  ECO's domain filter.

**2. Author the ECO (`southbrook_plm` side).**

- **Manufacturing → PLM → Engineering Change Orders → Create.**
- Fill the usual ECO fields — title, `eco_type_id` (drives
  `target_kind` — bom, cut_spec, rule, document), targets, attachments.
- In the **ProductGraph Linkage** group, set `pg_ebom_id` to the
  released EBOM you want to push to MRP. Leave `pg_auto_release`
  checked.
- Save. The ECO is in `state='open'`.

**3. Submit + approve.**

- Move the ECO through its stages (lesson 4.1). The Southbrook ECO
  Kanban stage workflow is **stage-driven** — when a stage with
  `is_applied_stage = True` is reached AND the ECO has been approved
  via `action_approve`, you're cleared to call `action_apply`.

**4. Apply.**

- Click **Apply**. This calls `southbrook.eco.action_apply`. What
  happens, in order:
  - `super().action_apply()` runs first. The PLM side does its full
    job: state machine transition, kind-specific dispatch
    (`_apply_bom` / `_apply_cut_spec` / `_apply_rule` /
    `_apply_document`), stamps `applied_date`, posts chatter.
  - Then the bridge's loop runs. For each ECO record:
    `_should_trigger_pg_release()` returns True iff:
    - `pg_auto_release` is True, AND
    - `pg_ebom_id` is set, AND
    - `pg_release_id` is NOT already set (idempotency — already fired
      once), AND
    - `pg_ebom_id.state == 'released'` (otherwise a chatter note flags
      the skip).
  - When True, `_trigger_pg_release()` creates a `pg.release`:
    ```python
    release = self.env["pg.release"].create({
        "ebom_id": self.pg_ebom_id.id,
        "release_reason": (
            f"Southbrook ECO {self.name}: "
            f"{(self.title or 'untitled').strip()[:200]}"
        ),
    })
    release.action_execute_release()
    ```
  - The `pg.release` runs its 9-step flow (see lesson 9.4: validate,
    ensure product, freeze open MOs, create mrp.bom, archive previous,
    write outcome, audit log, notify).
  - On success: `self.pg_release_id = release.id`; chatter post on
    the ECO with the release name + new mrp.bom display name + frozen
    MO count.
  - On exception: chatter post flags the failure; ECO STAYS APPLIED.
    The bridge does NOT roll back the ECO.

**5. Verify.**

- The ECO smart button **PG Release** is now present. Click it.
- Confirm `pg.release.state == 'completed'`,
  `pg.release.mrp_bom_id` is set.
- Open **Manufacturing → Products → Bills of Materials** — the new
  `mrp.bom` is the active one for that product; the previous one is
  archived (`active=False`).

## Common mistakes + how to recover

**"I applied the ECO and the release didn't fire. The smart button
isn't there."**

Walk through `_should_trigger_pg_release` mentally. Most common cases:

- `pg_ebom_id` is blank — the engineer forgot to set it before apply.
  Once the ECO is applied (`state='applied'`), `pg_ebom_id` is
  read-only — you can't add it after the fact. **Fix**: from the
  intended `pg.ebom`, run **Release to MRP** manually (wizard).
- `pg_auto_release` was unchecked. Same fix as above.
- The EBOM you pointed at isn't `released` state. Chatter on the ECO
  will have a note: `"ProductGraph release skipped: EBOM X is in
  state <state> (must be released)"`. Release the EBOM, then
  re-trigger the release manually from the EBOM form.

**"The bridge fired but the chatter says 'ProductGraph release FAILED:
…'."**

The `pg.release.action_execute_release` raised. Common causes:

- A child item on the EBOM is not in `released` state (cross-model gate,
  EBOM Bible §10). Fix: release the child item; re-trigger the release
  via the EBOM's Release to MRP button.
- The user doing the apply isn't in `group_pg_approver`
  (`action_execute_release` checks this). The bridge runs as the user
  applying the ECO, so the apply-user must also be a PG approver.
- A row lock conflict (rare). The savepoint context manager rolled
  back the `mrp.bom` creation; `pg.release.state` is now `failed`.
  Reset to pending (`action_reset_to_pending`, approver only) and
  re-execute.

**The ECO stays in `applied` regardless**, by design (Manufacturing
Governance §8). The bridge spec is explicit: "if the pg.release fails
for any reason, the ECO STAYS APPLIED. We do NOT roll back the ECO —
the PLM side already completed, possibly with its own `mrp.bom` copy
or `cut_spec` version. Reverting that here would corrupt the PLM
audit trail."

**"I want to fire the release a second time on the same ECO."**

The idempotency check (`if self.pg_release_id: return False`) blocks
this. The bridge fires at most once per ECO. If you need to re-release
the EBOM after the first fire (e.g. the first release failed and you
fixed the upstream issue), use the EBOM's **Release to MRP** button
directly — it creates a fresh `pg.release` independent of the ECO.

**"I unchecked `pg_auto_release` AFTER approval to test something,
then re-checked it. Apply didn't fire the release."**

Check the moment-of-truth: `pg_auto_release` is read at
`_should_trigger_pg_release` time, which is during `action_apply`. If
the field value at that exact moment was False, the bridge skipped. If
you flipped it back True after `action_apply` already returned, too
late — the bridge already decided. Run the manual EBOM → Release to MRP
flow as the recovery.

**"I tried to install the bridge addon on a non-Southbrook Odoo instance
and it errored."**

Working as designed. The bridge's `depends = ["southbrook_plm",
"product_graph_release"]` — without `southbrook_plm` present, the
inherit on `southbrook.eco` fails. The bridge is intentionally
Southbrook-specific. The generic ProductGraph addons (the 5
`product_graph_*` modules + the MCP sidecar) have NO reference to
`southbrook_plm` and can be installed standalone — that's Decision D1.

**"The bridge install also raised the `base.group_user`
`api_key_duration` cap to 1825 days. Was that supposed to happen?"**

Yes. `data/api_key_policy.xml` (the bridge's install data) raises the
cap so the MCP sidecar's service account can mint a long-lived API key
without group elevation. Side-effect: every internal user in this DB
can now mint keys up to 5 years. `noupdate="1"` so an admin can lower
the cap back via Settings → General Settings → API Keys without
revert on next module upgrade.

## The sync cadence

**The bridge is event-driven, not cron-driven.** There is no scheduled
task. The release fires exactly when `southbrook.eco.action_apply` is
called. That action is itself triggered by:

- An engineer clicking the **Apply** button on the ECO form.
- A programmatic call from another module (rare).
- The Hermes (Fabio) recommendation auto-apply flow when configured for
  ECO automation (see lesson 3.2; ECO automation is opt-in).

There is **no batch mode**, no "apply all approved ECOs at midnight"
cron. Each apply is a synchronous Odoo call; the bridge runs inside
the same transaction as the PLM-side apply (until the PLM side
commits, then the release runs in its own savepoint).

## How to debug a sync mismatch

You expected a `mrp.bom` to land but didn't see it. Walk this list:

**1. Find the ECO.** Open the southbrook.eco that was supposed to fire
the bridge. Check `state`. If not `applied`, the bridge never had a
chance — fix the ECO workflow first (lesson 4.1).

**2. Check `pg_ebom_id`.** Blank? The engineer didn't link the ECO
to an EBOM. The bridge correctly skipped.

**3. Check `pg_auto_release`.** False? The engineer suppressed the
auto-release. Intentional, presumably.

**4. Check `pg_release_id`.** If set, the bridge fired. Open the
release. If `state == 'completed'`, the `mrp_bom_id` is the new
`mrp.bom`. If `state == 'failed'`, read `failure_reason`.

**5. Check the ECO chatter.** The bridge posts a message on every
fire — success or failure. Search the thread for "ProductGraph release".

**6. Check `pg.audit.log`.** Filter `res_model='pg.release'` and
sort by `create_date desc`. The most recent row for the release in
question shows `action='release'`, `from_state`, `to_state`,
payload (incl. ebom_id, revision_id, mrp_bom_id, product_id,
frozen_mo_count).

**7. Check the worker logs.** If the bridge raised an exception that
didn't go to chatter (e.g. the ECO's `action_apply` itself failed
before the bridge even ran), Odoo logs the traceback to stdout.

## The bridge security model

**The bridge runs as the ECO-applying user.** No `sudo()`. The user
calling `action_apply` must have:

- Whatever permission `southbrook_plm` requires to apply the ECO
  (typically `group_southbrook_plm_approver` or similar).
- `group_pg_approver` on the ProductGraph side
  (`action_execute_release` checks this). Without it, the release
  raises UserError and the bridge logs the failure.

This is intentional — **the apply-user IS the release-authoriser**.
The bridge does not laundered authority through sudo. If you want to
allow a junior engineer to apply ECOs but not release to MRP, the
release will fail and the ECO will be flagged "Release manual" — the
Approver retries later.

The bridge does NOT have its own ACL CSV — there are no records to
secure beyond what's already secured on `southbrook.eco` and
`pg.release`. The added fields inherit the ACLs of the parent model.

The MCP API-key duration policy
(`base.group_user.api_key_duration = 1825`) is unrelated to the bridge's
runtime authority; it's about the sidecar's service-account key
lifetime. See lesson 9.5.

## What the system is doing behind the scenes

The bridge is **one Python file, ~150 lines** (`models/southbrook_eco.py`):

```python
class SouthbrookEco(models.Model):
    _inherit = "southbrook.eco"

    pg_ebom_id = fields.Many2one("pg.ebom", ...)
    pg_release_id = fields.Many2one("pg.release", readonly=True, ...)
    pg_auto_release = fields.Boolean(default=True, ...)

    def action_apply(self):
        # 1. Let the PLM side do its whole job first.
        result = super().action_apply()
        # 2. Optionally fire a ProductGraph release per ECO.
        for eco in self:
            if not eco._should_trigger_pg_release():
                continue
            eco._trigger_pg_release()
        return result
```

Three helpers, separated for testability:

- `_should_trigger_pg_release()` — pure-decision predicate, returns
  bool. Encodes the four conditions above. Posts a chatter note if
  the EBOM isn't released.
- `_trigger_pg_release()` — performs the create + execute. The
  try/except catches all exceptions, logs via `_logger.exception`,
  posts a chatter message, and returns (does NOT raise). This is the
  failure-doesn't-cascade contract.
- `action_view_pg_release()` — smart-button handler returning an
  `ir.actions.act_window` dict.

The test suite (`tests/test_bridge.py`) covers four cases (these are
the actual test names you can grep for):

- `test_bridge_fires_release` — ECO with `pg_ebom_id` → `pg.release.state
  == "completed"` + `mrp.bom` created.
- `test_bridge_skips_without_ebom` — no `pg_ebom_id` → no release fired.
- `test_bridge_skips_when_auto_release_off` — toggle off → no release
  fired.
- `test_bridge_idempotent` — already-released ECO would not re-fire.

The directional rule (Decision D1) is the *whole point*:

```
  southbrook_plm.eco       (Southbrook private — cabinet ECO authority)
        │
        │   on apply →
        ▼
  pg.release.action_execute_release   (generic ProductGraph LGPL)
        │
        ▼
  mrp.bom + mrp.bom.line               (Odoo core)
```

ProductGraph code NEVER imports anything from `southbrook_plm`.
That's what keeps the 5 generic ProductGraph addons publishable as
LGPL-3, while letting Southbrook drive releases from their existing
ECO workflow without forking the generic codebase.

The bridge spec at `~/product_graph_v19/bridge_spec/SPEC.md` documents
this contract for any future re-implementer. **The bridge MAY** add
fields to `southbrook.eco`, override `action_apply`, add smart buttons,
add demo data. **The bridge MUST NOT** modify any `pg.*` model
definitions, add Southbrook-specific fields to `pg.item` /
`pg.revision` / `pg.ebom` / `pg.release`, or override
`pg.release.action_execute_release` (the keystone method — the bridge
calls it, never replaces it).

## Quiz (5 questions, applied)

**1.** An engineer applies an ECO with a released `pg_ebom_id` and
`pg_auto_release = True`. The ECO state goes to `applied`. The bridge
chatter post says `"ProductGraph release skipped: EBOM Cabinet-36 is
in state superseded (must be released)"`. What happened?

> Between the time the engineer set `pg_ebom_id` and the time they
> clicked Apply, someone released a newer EBOM for the same root item.
> The new EBOM auto-superseded the one the ECO was pointing at. The
> bridge's `_should_trigger_pg_release` correctly detects the state
> mismatch and skips. **Recovery**: open the newer released EBOM and
> click **Release to MRP** there. The ECO stays applied — the PLM
> side did its job — but the release is fired against the right EBOM.

**2.** A junior engineer (no `group_pg_approver`) applies an ECO with
a linked EBOM and `pg_auto_release` on. What happens?

> `super().action_apply()` runs — the PLM side does its job. Then the
> bridge enters `_trigger_pg_release`, creates the `pg.release`,
> calls `action_execute_release`. The release raises UserError
> ("Only Approvers may execute releases"). The bridge's try/except
> catches it, posts a chatter "ProductGraph release FAILED: …", and
> returns. The ECO stays `applied`. An Approver can retry from the
> EBOM's **Release to MRP** button later.

**3.** The IT admin deploys the bridge to a fresh Odoo container that
already has `product_graph_release` installed but NOT `southbrook_plm`.
What happens?

> The install fails immediately at the manifest dependency check —
> `depends = ["southbrook_plm", "product_graph_release"]` requires
> `southbrook_plm` to be installable first. Without it, the bridge is
> not installable. This is by design: the bridge is Southbrook-private
> and meaningless without the Southbrook ECO model.

**4.** A regulator asks "show me the full audit trail of the BoM
change that resulted from ECO ECO-2026-0042." Where do you look?

> Three places, joined by IDs. (a) The southbrook.eco record with
> `name = "ECO-2026-0042"` — its chatter has the "ProductGraph release
> X executed" post; its `pg_release_id` field links to the release.
> (b) The `pg.release` record's chatter and `pg.audit.log` row with
> `action='release'`, payload containing ebom_id, revision_id,
> mrp_bom_id, product_id, frozen_mo_count, incompatible_with_previous.
> (c) The previous `mrp.bom` (now `active=False`) for the same
> product, archived by the release flow — confirms the
> manufacturing-side state at the time of change.

**5.** An estimator says "I changed an `mrp.bom` line by hand to add a
fastener because the ECO didn't include it. Did the bridge undo my
edit on the next ECO apply?"

> Sort of, yes. The bridge fires `pg.release.action_execute_release`
> which finds the active `mrp.bom`, archives it (`active=False`,
> assuming `archive_previous_bom=True` on the release — default), and
> mints a fresh BOM from the EBOM. The estimator's hand-edit lives in
> the now-archived BOM and is no longer the active one. **Recovery
> path**: the estimator's edit should have been a new ECO that added
> the fastener line in the next EBOM revision. Bible R1 forbids
> direct `mrp.bom` writes precisely because of this loss-of-truth
> scenario; lesson 9.4 is the long form.

---

## What this lesson does NOT cover

- The Southbrook ECO state machine and stage workflow — lesson 4.1.
- The detail of the `pg.release` 9-step flow — lesson 9.4.
- Cut spec activation triggered by an ECO with `target_kind='cut_spec'`
  — that's a separate `_apply_cut_spec` path inside `southbrook_plm`,
  unrelated to the bridge.
- Hermes/Fabio recommendations that auto-apply ECOs — lesson 3.2.
- The MCP sidecar's `propose_revision` flow (the agent path to author
  an EBOM) — lesson 9.5.
