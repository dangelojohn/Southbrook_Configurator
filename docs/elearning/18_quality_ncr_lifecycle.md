---
course: 18
chapter: 18.2
title: Quality Inspector — The NCR Lifecycle from Open to Close
duration: 18
audience: Quality inspector or manager processing non-conformance records
prereqs: Lesson 18.1 (menu orientation), basic understanding of MOs in Odoo Manufacturing
custom_modules: southbrook_quality, mrp
---

# Quality Inspector — The NCR Lifecycle from Open to Close

## Who this lesson is for

You're the person who decides whether a flagged cabinet gets reworked,
scrapped, or accepted. This lesson walks the full state machine of
`southbrook.ncr` with the decisions you make at each state, the
financial + production downstream effects, and the recovery paths when
the floor's expectations don't match yours.

## Where this lives on the site

**Quality → NCRs** (`menu_southbrook_quality_ncr`).

The form view is the workhorse — list view gets you to the form, but
all the decisions happen on the form.

## What your screen shows

The NCR form has 5 distinct regions:

### Header
- `state` widget (statusbar): `draft → quarantine → rework / scrap / accept`
- Action buttons gated on state — *Quarantine*, *Rework*, *Scrap*, *Accept*
- `name` — auto-numbered, `NCR/YYYY/000xx` format (sequence in
  `southbrook_quality.data.sequence_data.xml`)

### Identification panel
- `production_id` — the MO this NCR points at (required, indexed)
- `product_id` — auto-fills from the MO usually
- `workorder_id` — optional; pin to the specific work order step
- `reported_at`, `reported_by` (compute from create_date / create_uid)

### Defect classification
- `defect_type` — selection: dimension / finish / hardware / material /
  handling (5 values; if your defect doesn't fit, file as `handling`
  and use the description field to detail)
- `severity` — selection: minor / major / critical
- `description` — free text, mandatory for major + critical

### Resolution
- `resolution_path` (computed) — shows the path taken: rework date,
  scrap date, accept date
- `rework_workcenter_id` — when rework, which station re-does the work
- `scrap_quantity` — when scrap, the qty written off
- `accept_reason` — when accept, the documented why

### Notebook
- **Affected MOs** — m2m to `mrp.production`, populated by the
  *Block Downstream WOs* action
- **Photos** — `ir.attachment` rows linked to the NCR
- **Chatter** — full mail.thread audit

## Your daily flow

### Opening an NCR

Two paths:

**Path A: From the floor (inline NCR — already filed by operator)**
- It lands in your queue at state `quarantine`
- You triage and decide the resolution path

**Path B: You file it yourself (post-build inspection, customer
return, internal audit)**
- *Quality → NCRs → New*
- Pick the MO via `production_id` search (toggle "Show Done MOs" filter
  to see completed runs)
- Fill `defect_type` + `severity`
- *Save* — state goes to `draft`
- Click *Quarantine* to enter the lifecycle

### State transitions

State machine, with what each transition does to downstream state:

```
draft ──[Quarantine]──> quarantine ──[Rework]──> rework ─┐
                            │                            │
                            ├──[Scrap]──> scrap          │
                            │                            │
                            └──[Accept]──> accept        │
                                                          │
                            <── [Auto-close on MO done] ──┘
```

**`quarantine`** — entering this state:
- Blocks the cabinet's downstream WOs (`mrp.workorder.state` → `pending`
  with `block_reason = ncr.<id>`)
- Notifies the quality manager via activity
- Posts to the MO's chatter

**`rework`** — entering this state:
- Creates a `mrp.workorder.duration` adjustment record on the
  `rework_workcenter_id`
- The cabinet is unblocked downstream BUT routed back to that workcenter
  first
- NCR stays open until the rework signs off (the workcenter operator
  marks it complete + you confirm)

**`scrap`** — entering this state:
- Posts a `stock.scrap` record for `scrap_quantity` (default 1) on the
  product
- Re-MOs the affected demand via the SO link (procurement rerun)
- Logs the loss to the *Scrap* GL account via stock valuation
- NCR auto-closes after the scrap journal posts

**`accept`** — entering this state:
- Unblocks all downstream WOs
- Requires Quality Manager (`group_southbrook_quality_manager`)
- Documents the `accept_reason` (mandatory)
- NCR auto-closes

### Closing the NCR

NCRs in `rework` close when the rework signs off — operator marks WO
complete, you click *Confirm Rework Done* in the NCR header. NCRs in
`scrap` or `accept` close automatically. NCRs in `quarantine` stay open
until you pick a resolution.

## Common mistakes + how to recover

- **"I clicked Scrap by mistake. Now the cabinet is gone."** The
  `stock.scrap` move is reversible only via a manual reverse stock
  move. Open the cabinet's product → *Stock → Stock Moves* → find the
  scrap → *Reverse*. This is a *quality manager* action; you'll need
  approval.

- **"NCR says state = accept but the cabinet is still red on the
  kanban."** The kanban reads `mrp.workorder.block_reason`; the NCR
  accept didn't clear that field. Open the NCR → *Cog → Force Unblock
  Downstream*. (Bug; the auto-clear should happen.)

- **"I see two NCRs on the same MO. Which is canonical?"** Both are. NCRs
  are additive; one cabinet can have multiple defects. State of EACH NCR
  must resolve. Don't close one as a duplicate without resolving its
  finding.

- **"Reworking sends the cabinet to SB-ASSY but it should go to
  SAND."** `rework_workcenter_id` is the target. Edit the NCR before
  clicking *Rework*; once submitted, the routing's stuck.

- **"I want to file an NCR after the MO closed."** Allowed — toggle the
  *Show Done MOs* filter when searching `production_id`. The NCR will
  post but state machine is shallower (no downstream WOs to block).

- **"Customer returned a cabinet 6 weeks after delivery."** File the
  NCR linked to the original MO. Severity = critical regardless of
  defect. Triggers ECO consideration (lesson 17.10) and a supplier
  defect entry if material-driven (lesson 18.5).

## What the system is doing behind the scenes

The NCR is mostly a state machine plus a few side effects:

- **Block / unblock** is a write to `mrp.workorder.block_reason`. The
  field is a Char that the Southbrook MES kanban reads + decorates with
  the red border.

- **Stock scrap** uses the native `stock.scrap` model — no Southbrook
  wrapper. So scrap journal valuation comes from native COGS / scrap
  account configuration.

- **Re-MO via SO link** uses `procurement.group.run()` on the originating
  SO line's qty. If the SO had multiple cabinets, only the scrapped one
  re-MOs.

- **Supplier defect auto-link** — if `defect_type = material` and the
  product has a recent PO, the NCR auto-creates a
  `southbrook.quality.supplier_defect` linked to the supplier (lesson
  18.5 for the scoring side).

- **MI engine subscription** — `southbrook_quality.mi_engine_ext`
  watches NCR creates with `severity = critical` and posts a Hermes
  recommendation to the Plant GM persona.

## Quiz (5 questions, applied)

**Q1.** You file an NCR with `defect_type = dimension` and
`severity = major` against MO 1234. The floor reports the cabinet
"shipped to assembly anyway." What did you forget?

> Click *Quarantine* on the NCR header. Save alone doesn't block
> downstream — state must move from `draft` to `quarantine` for the
> `mrp.workorder.block_reason` write to fire.

**Q2.** You decided rework was the right call. You click *Rework*,
pick SAND as the target. Later you realise the right station was
SB-EDGE. What's the recovery?

> NCR is now in `rework`. Click *Cog → Reset to Quarantine* (manager
> only). Edit `rework_workcenter_id`. Click *Rework* again. Logs both
> attempts in the chatter.

**Q3.** A `scrap` NCR posted a `stock.scrap` for qty 1. The customer's
SO had a qty of 2 of that product. What happens to fulfilment?

> Procurement reruns for qty 1 (the scrapped one). The other unit, if
> already produced, continues. If not yet produced, the live MO covers
> both demands; no re-MO needed.

**Q4.** You accept an NCR for "cosmetic blemish, customer accepted."
The `accept_reason` field is mandatory. What do you write?

> "Customer approved cosmetic blemish on RHS gable; documented in SO
> chatter at <link>. No discount applied." Be specific — `accept` is
> the only path where Finance / Quality audit might come back later.

**Q5.** You log a `defect_type = material` NCR. No supplier defect
appears. Why?

> The product wasn't traceable back to a recent PO — purchased > 90
> days ago, or sourced as drop-ship without a Southbrook receipt. The
> auto-link only fires when a PO line is within the lookback window.
> File the supplier defect manually (lesson 18.5).

## What this lesson does NOT cover

- The math behind SPC sampling that often surfaces NCRs — lesson 18.3.
- Cpk capability — lesson 18.4.
- The supplier scoring side of supplier defects — lesson 18.5.
- Native Odoo Quality alerts — we don't use them; Southbrook quality
  layer is the source of truth.
