---
course: 4 — PLM + Design
chapter: 4.4
title: AI Design Assist — When to Use Gemini Room Analysis, When Not To
duration: 30 minutes
audience: Designer working with a customer's kitchen photo to seed the configurator's room layout
prereqs: Lessons 4.1–4.3, basic understanding of the kitchen-project workflow, awareness that Gemini is an LLM with calibrated uncertainty
custom_modules: southbrook_ai_design, southbrook_kitchen_workspace
---

# AI Design Assist — When to Use Gemini Room Analysis, When Not To

## Who this lesson is for

You're the designer who works the kitchen project from photo to
configurator input. A customer sends a photo of their existing
kitchen, you upload it to the project, Gemini does a room reading,
and **you** confirm every single dimensional field before the
configuration engine will touch it. The whole point of the contract
is that *Gemini guesses, you sign off*. Get that boundary wrong and
manufacturing will cut cabinets to a number Gemini hallucinated. This
lesson is the practical reality of when AI assist saves you a half
hour and when using it actively makes the job worse.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo**, then:

> **Kitchen Workspace → Projects → [pick a project]**

The project form is where you upload the photo and trigger
analysis. The OWL action button to call `analyze_photo()` lands
when the Phase-2 workspace UI ships; until then, the call is
invoked programmatically from the project form via a server
action. The analysis record itself lands on the project as
`ai_analysis_id` (m2o to `sb.kitchen.ai.analysis`) and the
detected appliances land as `appliance_ids` (one2many to
`sb.kitchen.appliance`).

Admins managing the AI surface also see:

> **Kitchen Workspace → AI Design → Prompt Templates**

This is the versioned prompt-template store
(`sb.gemini.prompt.template`). Bumping a prompt revision doesn't
require a code deploy — the prompt body, model name, and
generation config are all data.

For admins inspecting the live integration:

> **Settings → Technical → System Parameters**

- `gemini.use_mock` — defaults to `True` so the addon installs
  without an API key and tests run offline. Set to `False` in
  production to call the real Gemini API.
- `gemini.api_key` — Vertex AI service-account-derived token (or
  AI Studio key for dev). Never echoed in logs.

## What your screen shows

Once an analysis has landed, the project form's AI section shows:

**`sb.kitchen.ai.analysis` record (linked via `ai_analysis_id`):**

- **Confirmed by Human** (`confirmed_by_human`, Boolean, tracking)
  — the gate. Defaults to **False** on creation. Until you flip
  it to True via the Confirm button, `is_ready_for_config_engine()`
  returns False and Module 7 (the configuration engine) refuses
  to run.
- **Confirmed by** (`confirmed_by_user_id`, m2o `res.users`,
  readonly) — stamped when you click Confirm.
- **Confirmed at** (`confirmed_at`, Datetime, readonly) — stamped
  alongside the user.
- **Raw Response (JSON)** (`raw_response_json`, Text) — exactly
  what Gemini returned. Kept for audit and reprocessing. Don't
  edit by hand.
- **Sink Detected** (`sink_detected`, Boolean) — Gemini's best
  guess about whether the photo shows a sink. Read carefully:
  this is *detected*, not *confirmed*. If the photo shows a
  corner stovetop and Gemini called it a sink, this checkbox is
  wrong and you uncheck it before confirming the analysis.
- **Window Count** (`window_count`, Integer) — number of windows
  in the room.
- **Room Door Count** (`room_door_count`, Integer) — doors INTO
  the room, NOT cabinet doors. The label exists because new
  designers mistake one for the other every time.
- **Floor Area (m²)** (`floor_area_m2_approx`, Float) — Gemini's
  approximation. Six-digit precision is a UI accident, not a
  measurement claim.
- **Ceiling Height (mm)** (`ceiling_height_mm_approx`, Float) —
  the field Gemini is *worst* at; ceiling height is hard to
  triangulate from a single photo.
- **Detected Appliances (JSON)** (`detected_appliances_json`,
  Text) — the raw appliance list from Gemini, kept alongside the
  materialised `sb.kitchen.appliance` records for audit.
- **Detected Dimensions Confidence (JSON)**
  (`detected_dimensions_json`, Text) — Gemini's per-category
  confidence (`wall_lengths`, `appliance_widths`,
  `ceiling_height`), 0..1 floats.

**Per-appliance form (`sb.kitchen.appliance`):**

- **Name** (`name`, Char) — Gemini's free-text caption ("Gas
  range, 30\"" / "Single-basin sink").
- **Type** (`appliance_type`, Selection from `APPLIANCE_TYPES`:
  `stove` / `fridge` / `dishwasher` / `sink` / `microwave` /
  `oven_wall` / `hood` / `other`).
- **Width (mm)** (`width_mm`), **Height (mm)** (`height_mm`),
  **Depth (mm)** (`depth_mm`) — Gemini's approximations.
  Detected, not confirmed.
- **Required Clearance (mm)** (`requires_clearance_mm`, Integer)
  — minimum gap to adjacent cabinets. Stove/dishwasher typically
  30, fridge 50, sink 0.
- **Position X / Y** (`position_x`, `position_y`, Float 0..1) —
  relative position along the wall and depth axis.
- **Confirmed by Human** (`confirmed_by_human`, Boolean) — same
  gate as the analysis. Per-appliance, individually flipped.

## The detected-vs-confirmed contract (G3, the critical distinction)

The whole G3 contract exists to keep two failure modes off the
shop floor:

**Failure mode 1 — Manufacturing trusts a Gemini number.**
Cabinets cut to a width Gemini estimated; the customer's kitchen
turns out to be 30 mm narrower; panels don't fit. **Forbidden by
the contract.** Every dimensional field carries
`confirmed_by_human` and the Configuration Engine refuses to run
while any required dimension is unconfirmed
(`is_ready_for_config_engine()` returns False).

**Failure mode 2 — Hallucinated fixtures.**
Gemini reports `sink_detected: true` when the photo shows a
corner stovetop. Or it invents an appliance the photo doesn't
show. **Detected by the contract** because every appliance must
be designer-confirmed AND any unknown `kind` is coerced to
`other` with the original label preserved in notes. A confirmed
phantom is your fault; an unconfirmed one stays caged.

The vocabulary is precise:

- **Detected** — the value Gemini emitted. Stored as-is in the
  *_approx fields (`width_mm_approx`, `ceiling_height_mm_approx`)
  AND in the corresponding non-approx fields on the appliance
  records. Detected is "the model said this," not "this is
  true."
- **Confirmed** — the designer has reviewed the value, possibly
  edited it to match a measured tape reading, and clicked the
  Confirm button. `confirmed_by_human=True` plus
  `confirmed_by_user_id` and `confirmed_at` stamps.

Modules 7+ (the configuration engine, the cutlist generator)
read only confirmed values. Detected values exist on the record
for audit and for the designer's reference; they are NEVER
shipped to manufacturing-side computations.

## Your daily flow

**1. Decide whether to use AI assist at all.**

Use it when:

- The customer sent a single, well-lit, wide-angle photo of
  their existing kitchen.
- You've never visited the site and have no measurements.
- The photo shows at least two walls so the appliance positions
  along the run are inferable.
- The customer hasn't already supplied a dimensioned
  hand-sketch.

Do NOT use it when:

- The photo is low-light / heavily filtered / dim. Gemini's
  dimension confidence will be < 0.4 across the board and every
  reading needs replacing — you've just made work for yourself.
- The photo is a partial view (one wall, no context). Gemini
  will invent the other walls; you'll spend longer un-inventing
  them than measuring from scratch.
- The customer already provided measurements. Trust the
  customer's tape reading over Gemini's pixel-counted estimate.
  Skip the analysis entirely and enter the measurements
  directly.
- The kitchen is empty / under construction with no appliances
  installed. The appliance-position contract presumes installed
  appliances; an empty room produces an empty appliance list
  and you've gained nothing.
- The photo shows people, pets, or significant clutter. The
  documented warning "Sink position partly occluded by a person
  — re-measure manually" is real — Gemini hits an occlusion and
  hedges.

**2. Triggering the analysis (when you've decided yes).**

- Open the kitchen project.
- Attach the photo as an `ir.attachment` on the project.
- Call `analyze_photo(attachment_id)` — currently via a
  server-action button; the OWL UI button lands in Phase 2.
- The call dispatches to `southbrook.gemini.client.analyze()`
  which either calls the real Gemini API (if
  `gemini.use_mock=False` and `gemini.api_key` is set) or
  returns a canned mock payload.
- `consume_gemini_analysis(payload)` lands one
  `sb.kitchen.ai.analysis` record and one
  `sb.kitchen.appliance` per detected appliance.
- Every newly-created record has `confirmed_by_human = False`.
- The call is **idempotent** by `(project_id, image_hash)` —
  uploading the same photo twice returns the existing analysis
  record without creating duplicates. Safe to retry on
  transient errors.

**3. The confirmation walk (this is the work).**

For each detected appliance:

- Open the appliance record.
- Cross-check with the photo (and with the customer on a call
  if the appliance is critical):
  - Is the **type** correct? (Gemini sometimes calls a
    farmhouse sink an "other" because it doesn't match the
    common-shape priors.)
  - Are the **dimensions** sane? 762 mm for a 30" range is
    correct; 800 mm is a 31.5" range, which doesn't exist —
    Gemini has rounded oddly. Replace with the standard.
  - Is the **position** correct? The `position_pct_along_wall`
    is "fraction from left edge" — 0.62 means 62% of the way
    along the wall from the left. Check by eye against the
    photo.
- Edit any wrong value. Edits write directly to the field;
  there's no review queue.
- Click **Confirm** to set `confirmed_by_human = True` for
  this appliance.

For the room analysis:

- Walk through `sink_detected`, `window_count`,
  `room_door_count`, `floor_area_m2_approx`,
  `ceiling_height_mm_approx`.
- Especially scrutinise `ceiling_height_mm_approx` — it's the
  field Gemini is worst at (the documented contract confidence
  range for this category is 0.40, the lowest). If you don't
  have a measured ceiling height, leave the field blank and
  flag the project for a site visit rather than confirming a
  Gemini guess.
- Click **Confirm** at the analysis level.

**4. Releasing to the configuration engine.**

- Once every dimensional field is confirmed
  (`is_ready_for_config_engine()` returns True), the
  configurator can proceed.
- The release is automatic — no separate "release" button; the
  next time someone runs the config engine on the project,
  the gate passes.

## Common mistakes + how to recover

**"I confirmed the analysis without reviewing each appliance
individually, and the configurator placed cabinets around a
phantom dishwasher Gemini invented."**

Each appliance has its own `confirmed_by_human`. Confirming the
analysis record does NOT cascade to the appliances —
`is_ready_for_config_engine()` checks both:

```
if not self.ai_analysis_id or not self.ai_analysis_id.confirmed_by_human:
    return False
if any(not a.confirmed_by_human for a in self.appliance_ids):
    return False
```

If your project somehow released to the engine, it means every
appliance also got confirmed. Recovery: open each phantom
appliance, click **Unconfirm** (resets `confirmed_by_human` and
the stamp fields), then delete it. Re-run the configurator. The
audit trail (mail.thread on the analysis) shows the unconfirm
and the deletion; an auditor can reconstruct what happened.

**"Gemini gave me an appliance with `kind='blender'`. The
configurator doesn't know what to do with it."**

The Gemini client's validator coerces unknown kinds to `other`
and stores the original label in the `notes` field on the
appliance. So you don't see a "blender" record — you see an
`other` record with the label "blender" in notes. Decide
whether the appliance is something the configurator cares about
(an integrated coffee station might be modelled as a built-in
appliance; a counter-top blender shouldn't be on the appliance
list at all) and either delete the record or re-type it
(`appliance_type = "other"` is the right answer for genuinely
"other," but for an oven_wall mis-classified as other you'd
flip the type to `oven_wall`).

**"The photo had a window and a back door visible on the same
wall; Gemini reported `room_door_count: 2` because it counted
the back door AND a cabinet door."**

`room_door_count` means doors INTO the room (room/hall/exterior
entries) — NOT cabinet doors. Gemini conflates them often
because the contract description in the prompt isn't unambiguous
on this. Fix the value by editing the field directly before
confirming. The next prompt-template revision is likely to
disambiguate this — file an internal ticket for the prompt-eng
team if you see it more than once a week.

**"The customer's photo was a low-resolution snapshot in poor
lighting. The Gemini analysis came back with
`dimensions_confidence.wall_lengths = 0.18`. I confirmed it
anyway and the configurator's room layout is way off."**

Low confidence values are a signal to NOT confirm. The
contract's role for `dimensions_confidence` is exactly this —
to flag readings the designer should reject rather than confirm.
There's no UI gate that prevents you confirming a 0.18-confidence
field; it's a discipline issue. Recovery: unconfirm the
analysis (re-opens the gate), edit the wrong values to either
known-measured numbers or blank, re-confirm. If the values are
unknown and unmeasurable from the photo, flag the project for a
site visit — that's the honest path. **Never confirm a field
because you want to move on.**

**"I uploaded the same photo twice and expected a fresh
analysis. Got back the same record from the first upload."**

That's the idempotency contract working as designed. `analyze_
photo` hashes the image bytes (`sha256:`) and dedups against
`(project_id, image_hash)`. Two uploads of the *same bytes* are
the same analysis. If you genuinely want to reprocess — say,
because the prompt template has been revised since the first
analysis — delete the previous analysis record first, OR call
`analyze_photo` with `prompt_template_code` set to the new
revision (the idempotency key is `image_hash`, not the
template, so this will currently still dedup; the design fix is
to fold the template code into the dedup key, which is a known
punch-list item).

**"The Gemini call returned `gemini_unavailable` and the
analysis didn't land."**

Network or timeout. The client retries with exponential backoff
(250 ms / 1 s / 4 s) per the G3 §6 contract — three retries
total. If all three failed, the network's down or Gemini is
having a bad day. Wait a few minutes and try again. If it
persists, set `gemini.use_mock=True` on the staging instance
and develop with the canned response; in production, contact
ops to check the API status. **Do not** hand-author an analysis
record to work around the outage — the dedup key would then
clash with the real analysis when the network came back.

## When NOT to use AI assist (expanded)

The default should NOT be "always run Gemini on every photo."
The default should be "use Gemini when it's the fastest path to
a good designer hand-off, otherwise measure or ask." Specific
no-fly zones:

1. **Low light or heavy filter.** The validator clamps
   out-of-range dimensions and adds warnings, but it can't fix
   confidence. Gemini's confidence on a dim photo is too low to
   be useful and your time to fix every wrong reading exceeds
   the time you'd have spent measuring.
2. **Partial view.** The contract's `wall_segments` list assumes
   Gemini can see at least two walls. A close-up of a single
   cabinet produces an analysis with one wall, no appliances,
   and a model_warnings entry. Skip.
3. **Customer supplied dimensions already.** Trust the tape
   reading. Enter the measurements directly into the
   confirmed-side fields, leaving the detected side blank, and
   set `confirmed_by_human=True` on the analysis with a note
   citing the customer.
4. **Empty / under-construction room.** No appliances to detect,
   no spatial context for Gemini to anchor wall lengths against.
5. **Photo shows people or significant clutter.** Occlusion
   trips Gemini's "re-measure manually" warning; the time to
   work around it exceeds the time to take a fresh photo.
6. **Adversarial or non-kitchen scene.** The schema validator
   will reject an analysis that came back with no plausible
   kitchen room shape, but the request still costs you a Gemini
   API call against your quota.

## What the system is doing behind the scenes

When you call `analyze_photo(attachment_id)`:

1. The handler reads `ir.attachment.raw` (or `datas`, for
   legacy attachments) on the attachment, extracts the bytes.
2. It dispatches to `southbrook.gemini.client.analyze(image_
   bytes, prompt_template_code)`.
3. The client checks `ir.config_parameter.gemini.use_mock`:
   if True, returns a canned payload from `_mock_response`;
   if False, calls `_call_gemini_real` (which lazily imports
   `httpx`, requires `gemini.api_key`).
4. `_call_gemini_real` POSTs the image + prompt to
   `https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent?key=<key>`,
   with `temperature: 0.1` and a structured `responseSchema`
   matching the G3 §4 schema. Retries per §6: three exponential
   backoffs on transient failures; one retry on 429 quota; no
   retries on 401/403 auth (those surface as `gemini_auth_failed`
   immediately).
5. The returned JSON is parsed and passed to `_validate`, which
   enforces every G3 §4.1 rule: schema version literal must
   match `southbrook.gemini.room_analysis.v1`; out-of-range
   dimensions are nulled and a warning added; unknown appliance
   kinds are coerced to `other` with the original kind stored
   in `notes`; orphan `wall_segment_id` references rejected
   with `UserError("orphan_wall_segment_id")`; confidence
   values clamped to [0,1].
6. The image hash (`sha256:`) is stamped onto the validated
   payload.
7. Control returns to `sb.kitchen.project.consume_gemini_
   analysis(payload)`. The lander searches for an existing
   analysis with the same `image_hash` in its `raw_response_json`
   (substring search); if found, returns it (idempotency). If
   not, creates a new `sb.kitchen.ai.analysis` record AND one
   `sb.kitchen.appliance` per detected appliance, all with
   `confirmed_by_human=False`. Writes the analysis link to
   `project.ai_analysis_id`.

`is_ready_for_config_engine()` checks both
`ai_analysis_id.confirmed_by_human` AND every appliance's
`confirmed_by_human`. False until ALL of them are True; downstream
Module 7 refuses to run while False, per GAP-02.

`raw_response_json` is the full Gemini response stored on the
analysis record, so any future schema versioning (v2, v3) can
re-process the original data without re-calling Gemini and
re-spending quota.

## Quiz (5 questions, applied)

**1.** A customer sends a wide-angle photo of their kitchen.
You run `analyze_photo`, get back six appliances, confirm five
of them, but skip a phantom dishwasher Gemini invented because
you intend to delete it. You click Confirm on the analysis
record (the room facts look right). Will the configurator now
proceed?

> No. `is_ready_for_config_engine()` checks every appliance's
> `confirmed_by_human`, not just the analysis record's. The
> phantom dishwasher's `confirmed_by_human` is still False, so
> the gate stays closed. Fix: delete the phantom appliance
> record (it'll come off the `appliance_ids` list), or click
> Unconfirm on the analysis and revisit. Once every remaining
> appliance is confirmed AND the analysis itself is confirmed,
> the gate opens.

**2.** The Gemini response came back with `wall_lengths`
confidence 0.22 and `ceiling_height` confidence 0.31. You don't
have a tape measure handy and the customer is on the phone
asking you to "just run it." What's the right answer?

> Tell the customer you need measurements before
> manufacturing can proceed. Low-confidence values mean Gemini
> doesn't trust its own reading; if you confirm them anyway,
> you've signed your name to a number that's wrong. Per the
> G3 contract, the entire confirmation surface exists to make
> "I signed off on Gemini's guess" your responsibility — not
> the model's. Concrete action: edit the offending values to
> blank, set the analysis-level confirm only when YOU have
> the measurements (from a follow-up site visit or customer
> sketch), and leave the project state at "Awaiting
> Dimensions" until then.

**3.** Gemini's response included `appliances[0].kind =
"espresso_machine"`. You don't see this in the appliance_type
selection. What did the system actually do?

> The Gemini client's `_validate` method intercepts unknown
> kinds: it coerces `kind` to `"other"` and appends the
> original kind to the `notes` field (`notes = … +
> "original_kind=espresso_machine"`). Plus it adds a warning
> to `model_warnings`. So you see an `other`-type appliance
> record with the original "espresso_machine" preserved in
> notes for your reference. Your decision is whether the
> appliance is relevant to cabinet placement (a fixed
> built-in espresso machine probably is; a counter-top one
> isn't) and edit accordingly.

**4.** You uploaded a photo, analysed it, did the confirm walk,
and released the project to the configurator. Two days later
the customer sends a higher-resolution version of the same
photo. You upload and re-analyse expecting a fresh analysis.
What happens?

> A NEW analysis lands — the new image has a different SHA-256
> hash, so the idempotency dedup
> (`raw_response_json ilike image_hash`) finds no match and a
> new `sb.kitchen.ai.analysis` record is created on the same
> project. Your project now has TWO analyses linked via the
> mail.thread; `project.ai_analysis_id` will be overwritten
> to point at the new one. Decision: do you re-confirm the
> new analysis (and disregard the old confirmations) or stay
> with the original? If the new image yielded different
> values, you need to repeat the confirm walk; the old
> confirmations are stale. The old record stays as audit
> history.

**5.** A junior designer confirmed every appliance and the
analysis record after a 5-second glance at the photo. Two weeks
later the cabinets arrive at the customer's home 80 mm too
wide. Where's the blame, and what's the systemic fix?

> The blame is the designer's confirm click — that's literally
> what the G3 contract is for. The system worked: Gemini gave
> approximations; the contract gated them behind
> `confirmed_by_human`; the gate fired (configurator only ran
> after the click). The designer's signature is on the
> dimensions. The systemic fix is not technical — it's
> training and audit. Concretely: surface the appliance-level
> confidence in the UI more prominently (so a 0.22 reading is
> visually impossible to confirm casually), add an audit
> report that flags analyses confirmed within N seconds of
> creation as suspicious, and use the chatter trail (the
> analysis inherits `mail.thread`, so the confirm event is
> recorded with timestamp + user) to review confirmations
> against the photo at the post-mortem. The contract makes
> the bad confirm visible; it can't prevent the bad confirm.

---

## What this lesson does NOT cover

- The downstream configuration engine that reads the confirmed
  surface to lay out cabinets — Course 5 (configurator).
- The PLM ECO workflow that revises BoMs and cut specs
  independent of any AI analysis — lessons 4.1 and 4.2.
- The FreeCAD bridge that renders the resulting cabinets —
  lesson 4.3.
- Prompt-template engineering (adding a new
  `sb.gemini.prompt.template` record) — admin workflow, separate
  doc (`docs/ai_prompt_spec.md`).
- Vertex AI / Studio key management — Course 7 (sysadmin).
- Native Odoo `mail.thread` mechanics — Odoo's own training.
