---
course: 4 — PLM + Design
chapter: 4.3
title: FreeCAD Bridge — Generating Renderings from a Configured Kitchen
duration: 30 minutes
audience: Designer who reviews customer-facing renderings and shop-floor CAD artifacts before they go out
prereqs: Lesson 4.1 (ECOs), basic Odoo MO navigation, understanding that an MO is the unit a render belongs to
custom_modules: southbrook_freecad_bridge, southbrook_plm, southbrook_estimating
---

# FreeCAD Bridge — Generating Renderings from a Configured Kitchen

## Who this lesson is for

You're the designer who looks at every customer-facing rendering
before it ships and every shop drawing before it goes to the CNC
operator. Sometimes the rendering is wrong — a door is on the wrong
side, a panel is undersized, the cabinet shows a corner-cut where the
sale order says square. You need to know whether that's a
configurator-input problem (fix the spec) or a rendering problem
(regenerate). This lesson is the practical reality of how a
manufacturing order causes a FreeCAD job to spawn, where the
artifacts land, and what to do when one's wrong.

## Where this lives on the site

> **Manufacturing → Operations → Manufacturing Orders → [pick an MO] → CAD Artifacts**

The bridge surface is a notebook page injected onto the MO form by
`southbrook_freecad_bridge`. The page is called **CAD Artifacts**
and lives next to Components, Work Orders, the rest of the native
MO tabs. It's visible to anyone with MO read access; the actions
on it (Regenerate CAD) are gated to the **Manufacturing /
Manager** group.

There is no separate "Renderings" menu. The artifact lives on the
MO that produced it — that's the unit of provenance, because two
MOs of the same cabinet template can cut to different cut specs
(see lesson 4.2) and therefore produce different geometry.

For backend admins who need to inspect the bridge service itself:

> **Settings → Technical → System Parameters**

Three relevant parameters:

- `freecad_bridge.enabled` — master kill switch. Defaults to
  **false** on install (the G2a opt-in gate). Until an admin flips
  this to **true**, MO confirms do NOT POST to the bridge, and
  the Regenerate CAD button raises UserError.
- `freecad_bridge.url` — service URL. Defaults to
  `http://southbrook-freecad-bridge:8000` (the docker network name).
- `freecad_bridge.secret` — shared secret matching the bridge
  service's `FREECAD_BRIDGE_SECRET` env var. The bridge rejects
  requests without it; Odoo's callback rejects requests with a
  mismatching `X-Bridge-Secret` header.

## What your screen shows

The **CAD Artifacts** tab on `mrp.production` shows:

- **CAD Status** (`x_cad_status` on `mrp.production`) — a Selection
  field rendered as a badge with four states:
  - **Pending** (blue) — the MO has been confirmed but the bridge
    POST hasn't fired yet, or the bridge gate is off and the POST
    was suppressed. Default on a fresh MO.
  - **Rendering** (yellow/warning) — the bridge accepted the job
    (HTTP 2xx on POST `/render`) and is currently producing the
    artifacts. The bridge runs renders asynchronously off the
    HTTP request, so this state can persist for tens of seconds
    to a couple of minutes.
  - **Done** (green) — the bridge's background task completed and
    POSTed the callback (`/plm/cad_callback`) with attachment IDs;
    `x_cad_attachment_ids` is populated and the rendering is
    review-ready.
  - **Error** (red) — either the POST to the bridge failed (network,
    auth, 5xx) or the bridge's background task came back with
    `status=error` in the callback. The chatter carries the
    specific error message.

- **Governing ECO** (`x_plm_eco_id` → `southbrook.eco`) — m2o to
  the Engineering Change Order whose approved revision of the
  template BoM this MO was built against. Empty when no
  PLM-governed BoM revision is in scope. Click-through to read
  the ECO's rationale and history.

- **Regenerate CAD button** — visible to Manufacturing Manager only.
  Triggers `action_regenerate_cad`, which re-runs
  `_post_cad_render_job` and flips status back through Pending →
  Rendering. Confirmation prompt warns that existing artifacts
  will be superseded.

- **CAD Artifacts** (`x_cad_attachment_ids`) — many2many to
  `ir.attachment`, rendered with the `many2many_binary` widget so
  each file appears as a download chip. The bridge typically
  produces 4 artifacts per cabinet:
  - **DXF** (one per panel) — for the panel-saw / CNC nesting.
  - **SVG** — shop drawing, customer-or-floor-facing.
  - **PDF** — TechDraw orthographic three-view (front/side/top).
  - **STEP AP214** — assembly STEP file for the assembler's
    reference and for any vendor needing CAD interchange.

On the kanban (shop-floor) view of MOs, the same `x_cad_status`
field is shown as a colour-coded badge so the planner can see at
a glance which MOs are CAD-ready vs blocked.

## How a render gets triggered

There are two trigger paths and both go through the same Python
method (`mrp.production._post_cad_render_job`):

**1. MO confirm hook (automatic, opt-in).**

When `mrp.production.action_confirm()` runs, the Southbrook
extension fires after `super()`. For each newly-confirmed MO, it
checks `_g2a_enabled(env)` — the system parameter
`freecad_bridge.enabled` parsed as `true`/`1`/`yes`. If on, it
calls `_post_cad_render_job()`; if off, it logs the suppression
and returns. Exceptions in the POST are caught and logged but
never re-raised, because a bridge outage must NOT block MO
confirm — confirmation is the manufacturing system's load-bearing
event and cannot depend on a render service being up.

**2. Manager-clicked Regenerate.**

The Regenerate CAD button on the MO form calls
`action_regenerate_cad`. Unlike the on-confirm hook, this one
raises UserError loudly if the gate is off — a manager click
should surface the configuration problem, not silently no-op.

## What Odoo sends to the bridge

`_spec_for_bridge` constructs the payload from the MO's product
template. The shape is:

```json
{
  "production_id": 4711,
  "dimensions": {
    "width_mm":  600.0,
    "height_mm": 720.0,
    "depth_mm":  580.0
  },
  "family": "base",
  "door_count": 1,
  "output_dir": "/srv/output/mo/4711"
}
```

Sources of each field:

- `production_id` — `self.id`.
- `dimensions` — `x_default_width_mm`, `x_default_height_mm`,
  `x_default_depth_mm` on the product template. Sensible defaults
  (600/720/580 mm — a typical base cabinet) when the template
  hasn't set them.
- `family` — `x_cabinet_family` on the product template. Defaults
  to `"base"` if missing. Tells the bridge which master to
  invoke (`master_base.py`, `master_wall.py`, etc.).
- `door_count` — `x_default_door_count` on the product template
  (1, 2, or 0 for drawer banks).
- `output_dir` — where on the bridge filesystem to write the
  rendered artifacts. The bridge attaches them to Odoo by XML-RPC
  after the render completes, but the on-disk copy stays for
  troubleshooting.

The POST is to `<bridge_url>/render` with header `X-Bridge-Secret`
and a 10-second connect timeout. The bridge responds with a job_id
+ `status: "queued"` and runs the actual FreeCAD render off-thread.

A future Module-2 enhancement will swap the template-defaults
above for the configurator's per-MO spec (so an MO for a 720
mm-wide base reads 720, not the template's 600 default). Until
that lands, the Phase-1 mapping is template-driven.

## The bridge job state machine

From `services/freecad_bridge/main.py` the job carries:

- **queued** — bridge accepted the POST, job_id assigned, the
  background task has been scheduled. The bridge tells Odoo to
  flip MO status to `rendering` at this point.
- **rendering** — the background task is running `xvfb-run
  freecadcmd render_cabinet.py` against the parametric `.FCStd`
  master, generating DXF/SVG/PDF/STEP into the output_dir.
- **done** — render completed, artifacts uploaded to Odoo as
  `ir.attachment` records via XML-RPC, callback POSTed to
  `/plm/cad_callback` with `attachment_ids`.
- **error** — render failed at some stage (FreeCAD crashed,
  geometry validation rejected the panels, output files missing).
  Callback POSTed with `status: "error"` and an error string.

The job table is in-memory (a Python dict) — when the bridge
process restarts, in-flight jobs are lost. This is intentional
for Module 2 scope; if a render is interrupted the MO sits at
`rendering` indefinitely until someone clicks Regenerate. A
persistent queue (Redis or RQ) is explicitly out of scope until
Module 4.

## Where the rendered artifacts land

Three places, in this order:

**1. On the bridge filesystem.** `/srv/output/mo/<production_id>/`
inside the bridge container. DXF, SVG, PDF, STEP files. These are
useful for troubleshooting — `docker exec` into the bridge and
inspect — but are NOT what users see.

**2. As `ir.attachment` records in Odoo.** The bridge's
background task uses XML-RPC (`ir.attachment.create`) to upload
each file's bytes as a separate attachment, captures the
returned IDs.

**3. Linked to the MO via `x_cad_attachment_ids`.** The bridge's
callback POSTs `attachment_ids` to `/plm/cad_callback`; the
controller writes `x_cad_attachment_ids = [(6, 0, [...])]` on
the MO. The notebook tab's `many2many_binary` widget now shows
download chips for each.

Crucially: there is **no separate "Renderings" model** and **no
customer-portal direct attach** in the v1 surface. If a customer
needs the rendering, the dealer portal's installation-PDF export
embeds the orthographic SVG views inline via the
`/render_elevation` endpoint (a separate, synchronous bridge
route distinct from the async `/render`). The per-MO STEP and
DXF artifacts are shop-floor artifacts; the customer-facing
rendering is a different code path.

## Your daily flow

**1. Review queue — first thing in the morning.**

- Open **Manufacturing → Manufacturing Orders** filtered to
  *Status = Confirmed AND CAD Status = Pending or Rendering*.
- A handful of yellow (Rendering) badges is normal for MOs
  confirmed in the last hour. A pile of yellow more than 30
  minutes old means a stuck job — check the bridge service
  health (see "Common mistakes").
- Red (Error) badges are your priority queue.

**2. Per-MO review (the loop).**

For each green (Done) MO from your shift:

- Open the MO, click the **CAD Artifacts** tab.
- Download the PDF (orthographic three-view) and confirm it
  matches the sale order's spec — door count, hinge side,
  finished sides, family. The sale-order spec is what the
  customer agreed to; the rendering is what manufacturing will
  cut. They must match.
- If they don't match, raise an ECO (lesson 4.1) — the BoM
  is wrong, not the rendering. Regenerating won't help.
- If the rendering shows obvious geometry corruption (panels
  overlapping, dimensions impossible, blank pages), click
  **Regenerate CAD** to re-fire the bridge.

**3. Handling Error states.**

- Open the MO, look at the chatter — the error message is
  there with prefix "CAD render request failed:" or "Bridge
  HTTP 500: …".
- Common messages and what they mean:
  - `bridge_secret_unset` — Odoo's `freecad_bridge.secret`
    parameter isn't set. Admin issue, not yours.
  - `bridge HTTP 400` (`unknown_template`) — the cabinet
    template's `family` doesn't map to a `.FCStd` master file
    the bridge can find. PLM-side fix (BoM ECO to correct the
    family, or admin uploads a new master).
  - `bridge HTTP 500` (`freecadcmd_exit_<n>`) — FreeCAD crashed
    on this geometry. Often a non-positive panel dimension
    indicates a bad cut spec. Check the active cut spec and
    the MO's dimensions; raise a Cut-Geometry ECO if the
    constants are wrong.
  - `non_positive_panel:<name>` — the bridge's pre-render
    `/validate` step caught a panel with a zero or negative
    dimension. Same root cause as above.
  - Network/connection errors — the bridge service is down
    or the docker network is broken. Sysadmin issue.

- Once you've understood the cause, click **Regenerate CAD** to
  retry. If the cause was on the PLM side (BoM or cut spec), fix
  the cause first via an ECO, wait for Apply, then regenerate.

## Common mistakes + how to recover

**"I clicked Regenerate CAD and got 'FreeCAD bridge is disabled.'
What do I do?"**

The `freecad_bridge.enabled` system parameter is off. This is the
G2a gate — the safe default on install. Ask an admin to set it
to `true` at **Settings → Technical → System Parameters**. (Note:
the on-confirm hook silently no-ops in this state, but the
manual button raises UserError so you don't miss the
configuration gap.)

**"The MO has been at Rendering for 45 minutes and the floor
needs the DXF for the next CNC slot."**

A render that long usually means the bridge process died
mid-render and the in-memory job table cleared on restart. Click
**Regenerate CAD** to re-fire. If the new job also stalls,
escalate to sysadmin — the bridge service itself needs
investigation. **Do not** plan around the missing DXF by
hand-drafting one; the geometry source of truth is the bridge's
`southbrook_dims` module, and a hand-drafted panel will drift.

**"The rendering looks correct, but the customer is asking why
the door grain on the visual is horizontal when they ordered
vertical."**

The bridge renders parametric carcass geometry — it doesn't
apply material textures, grain direction, or finish colour.
Those are visualisation concerns the customer-facing webGL
configurator handles (see Course 5). The MO's CAD Artifacts
are shop drawings: panel dimensions, joinery, hinge positions.
If the customer is reviewing a rendering with material
detail, they're looking at a configurator screenshot, not a
bridge artifact. Escalate to whoever cut the screenshot.

**"I see a door on the wrong side of the rendering, but the
sale order spec is correct."**

The Phase-1 bridge reads template defaults
(`x_default_door_count`, `x_cabinet_family`) — NOT the
configurator's per-MO spec. If your cabinet template's default
is "hinge_side=L" and the order configured "hinge_side=R",
the rendering will show the template's L. This is a known
Phase-1 limitation that Module 2 closes by swapping in the
configurator's spec. Workaround until that lands: explain to
the customer that the SHOP DRAWING is to-scale and dimensioned
correctly; the visual orientation of the door swing is from the
template stock master. Don't regenerate — it won't change.

**"I raised an ECO that bumped the BoM and applied it. Should I
regenerate CAD on every in-flight MO of that template?"**

No. The CAD artifacts for an in-flight MO are valid as long as
the MO's `southbrook_bom_version` and
`southbrook_cut_spec_version_id` snapshots (captured at line
confirm time, see lesson 4.2) match what the artifacts were
rendered against. The MOs in flight cut to those snapshots, so
their existing CAD is correct. New MOs after the Apply will
render against the new BoM version on confirm. Regenerating
in-flight MOs would produce CAD that does NOT match the
material on the floor — confusing rather than helpful.

**"The render is wrong because the configurator-fed dimensions
don't match what the model master expects."**

That's a *parametric configurator* issue, not a render issue.
The bridge takes width/height/depth/family/door_count as input
and produces geometry. If the input is wrong (configurator gave
incorrect dimensions), regenerating won't help — fix the
configurator output via a Construction-Rule ECO if the rule
is wrong, or via a sale order edit if the user picked wrong.
If the input is correct but the model master misinterprets it,
that's a bridge-side bug — file it with the FreeCAD masters
team (the masters live in `services/freecad_bridge/cabinet_
masters/`).

## What the system is doing behind the scenes

When you click Confirm on an MO, this happens (assuming the
gate is on):

1. `mrp.production.action_confirm()` runs Odoo's stock
   confirm logic via `super()`.
2. The Southbrook override iterates the just-confirmed MOs and
   calls `_post_cad_render_job()` on each.
3. `_post_cad_render_job` builds the spec via `_spec_for_bridge`
   (template-default driven), reads `freecad_bridge.url` and
   `freecad_bridge.secret` from ir.config_parameter, POSTs JSON
   to `<url>/render` with the secret in `X-Bridge-Secret`, with
   a 10-second timeout.
4. On 2xx, the MO's `x_cad_status` writes to `rendering` and
   the chatter posts a "CAD render job posted to bridge"
   message. On non-2xx or `requests.RequestException`, the MO
   writes to `error` and the chatter posts the failure detail.

The bridge service runs the render asynchronously
(`BackgroundTasks` in FastAPI). When the render completes:

5. The bridge's background task uploads each output file as
   an `ir.attachment` via XML-RPC.
6. The bridge POSTs `/plm/cad_callback` on Odoo with
   `{production_id, status, attachment_ids}` and the
   `X-Bridge-Secret` header.
7. The `FreecadBridgeController.cad_callback` route validates
   the secret, parses the JSON, writes `x_cad_status = "done"`
   and `x_cad_attachment_ids = [(6, 0, [...])]` on the MO.
8. The endpoint is idempotent — the bridge can replay the
   callback safely and the MO converges on the same state. The
   attachments themselves are already in Odoo before the
   callback fires; the callback's only job is linking them.

The geometric source of truth is `southbrook_dims` — a Python
module shared between Odoo and the bridge via a `/srv/shared`
mount and `PYTHONPATH`. Odoo's G1 test asserts the panel
formulas the configurator's `create_get_bom` produces match
`southbrook_dims.panel_cut_list(...)`. The bridge's
`render_cabinet.py` imports the same `panel_cut_list`. By
construction, the BoM's panels and the rendered geometry's
panels are computed by the same code — there's no drift, as
long as G1 stays green.

## Quiz (5 questions, applied)

**1.** An MO is sitting at CAD Status = Pending an hour after
confirm. You check the chatter — no error messages, no "CAD
render job posted" line either. What's the most likely cause,
and what's your next step?

> The `freecad_bridge.enabled` system parameter is off, so the
> on-confirm hook silently no-op'd the POST. Pending is the
> default state on a fresh MO and only flips to Rendering once
> a POST succeeds. Confirm with sysadmin (Settings → Technical
> → System Parameters) — if the bridge is supposed to be on,
> flip the gate to true; otherwise, accept that this MO will
> never auto-render and click Regenerate CAD if you want it.

**2.** A customer's quote says hinge_side=R for a base cabinet,
but the rendering on the MO is showing the hinge on the left.
You confirm the MO's product template has `x_default_hinge_side
= "L"`. Should you regenerate CAD? Raise an ECO?

> Neither — yet. The Phase-1 bridge reads the template default,
> not the configurator's per-MO spec, so the rendering is
> correctly showing the template default even though the MO is
> intended for the right-hinged variant. Regenerating produces
> the same wrong rendering. The Module-2 fix swaps in the
> configurator spec; until that lands, the workaround is to
> mark the rendering as a stock-master visualisation and trust
> the dimensioned shop drawing for the floor. Raising an ECO
> wouldn't fix it either — the BoM and the cabinet's intent
> are both correct; the limitation is in the bridge spec
> mapping. File this as a Module-2 punch-list item, not as a
> daily fire.

**3.** You see five MOs all at CAD Status = Error, all
confirmed in the last ten minutes, all with the chatter
message "Bridge HTTP 500: freecadcmd_exit_134". What
investigation path do you take?

> A common-cause failure across five recent MOs points at the
> bridge service itself rather than per-MO geometry — exit
> 134 is SIGABRT, FreeCAD aborting at startup. Possibilities:
> the bridge container OOM'd and restarted with a broken venv;
> a new `.FCStd` master was uploaded with corrupted bytes; the
> xvfb display server failed. Don't keep clicking Regenerate —
> that adds load. Page sysadmin to inspect the bridge logs
> (`docker logs southbrook-freecad-bridge`) and the
> `/health` endpoint. Once the service is healthy again,
> Regenerate the five MOs.

**4.** A BoM ECO applied at 14:00 bumped a panel formula. You
have two MOs of that template: MO/1234 was confirmed at 10:00
this morning, MO/1235 will be confirmed at 16:00. Should you
Regenerate CAD on either, and why?

> Regenerate neither — both for the same reason. MO/1234's
> `southbrook_bom_version` snapshot captured the OLD version
> at 10:00 confirm. Its existing CAD artifacts were rendered
> against the old version and match the panels currently
> being cut. Regenerating would render against the new
> template, producing artifacts that DON'T match the actual
> material on the floor — exactly the wrong thing. MO/1235
> at 16:00 hasn't been confirmed yet; its CAD will render
> automatically on confirm against the new version. The
> bridge correctly handles both without manual intervention.

**5.** The customer service team is asking why their copy of
the rendering shows different door colours than what the
customer ordered. You open the MO's CAD Artifacts and confirm
the SVG matches the cabinet's geometry but the customer's
saved PDF has different colours. Where's the source of the
mismatch?

> The bridge's `/render` endpoint produces geometric shop
> drawings — uncoloured DXF/SVG/PDF/STEP. Door colour, finish,
> grain are visualisation concerns rendered by the
> customer-facing configurator (Course 5), not by FreeCAD.
> The PDF the customer saved was a configurator screenshot
> export, not a bridge artifact. They're two different
> rendering pipelines that share the same parametric
> dimensions but different visualisation surfaces. Resolve by
> pointing CS at the configurator-export path; the MO's CAD
> Artifacts are correct for what they are.

---

## What this lesson does NOT cover

- Raising an ECO when the bridge's rendering reveals a wrong
  BoM — lesson 4.1.
- Authoring or revising a cut spec whose constants drive the
  panel geometry the bridge renders — lesson 4.2.
- The AI-design Gemini room analysis that precedes the
  cabinet selection — lesson 4.4.
- The dealer-portal installation-PDF export that uses
  `/render_elevation` synchronously — Course 6 (dealer portal).
- Bridge service ops (container restarts, log inspection,
  master uploads) — Course 7 (sysadmin).
- Native Odoo MO mechanics — Odoo's own training.
