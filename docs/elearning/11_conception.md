---
course: 11 — Creating a New Product End-to-End
chapter: 11.1
title: Conception — Capturing the New Product Idea
duration: 20 minutes
audience: Designer working with a customer requirement or with the showroom team — the person who first hears "we want this thing" and has to decide whether it becomes a one-off or a SKU
prereqs: General Southbrook product literacy. You know the difference between a base, wall, tall, and accessory cabinet. You've used the customer portal once. No model-level knowledge required for this lesson.
custom_modules: none yet — this lesson lives upstream of the platform
---

# Conception — Capturing the New Product Idea

## Who this lesson is for

You're the designer (or the sales rep with design instincts) who just
took a phone call, a showroom walk-in, or a dealer email that starts
with *"do you make a..."*. The answer is almost always *"we can"* —
but the way you capture that requirement decides whether the rest of
the chain (PLM, configurator, estimating, the shop floor) ever sees a
coherent picture. This lesson is the process for turning a verbal
request into a structured idea the next eight lessons can act on.

There is no code in this lesson. There is barely any clicking. You
will write things down, sketch, and answer four questions.

## Where this lives on the site

The conception step lives **off-platform on purpose**. We don't
spawn an Odoo record yet because:

- A premature ProductGraph record locks you into a part-number you may
  abandon (sequences burn through `PG-PRT-NNNN`).
- A premature `product.template` clutters the configurator catalog
  with half-baked SKUs nobody can quote.

You'll use:

> **Google Drive → Southbrook → New-Product Intake**

…where every new-product idea gets a folder named
`YYYY-MM-DD_<short_slug>` (e.g. `2026-06-17_floating_corner_shelf`).
The folder is the conception artifact. When this lesson is done, the
folder contains four files and the green-light decision in its name.

If your idea makes it through, lesson 11.2 picks up here and
**creates the first system record** — the `pg.item` in ProductGraph.

## What your screen shows

Your "screen" in this lesson is a folder with four expected files:

- **`intake.md`** — the customer requirement in their own words,
  pasted verbatim. Names, dates, the dealer or salesperson who took
  the call, the deadline if any.
- **`scope.md`** — your decision: is this a **one-off custom** (a
  single sale-order line built once, no SKU) or a **new SKU** (worth
  the engineering investment because it'll sell again)? Three
  paragraphs maximum. Lesson 11.2 won't fire until this answer is
  *new SKU*.
- **`sketch.<ext>`** — a hand sketch, a Sketchup screenshot, a
  napkin photo, a Prodboard export — any visual that another human
  could look at and say *"yes, that's the thing."* Lesson 11.4 (BoM)
  consumes this directly; the more honest your sketch, the less
  rework downstream.
- **`spec_draft.md`** — the unstructured spec. Width range,
  height range, depth, materials we'd build it from, door style if
  applicable, hardware, finish constraints. *Bullet points are fine.*
  This becomes the property-template selection in lesson 11.2.

## Your daily flow

**1. Hear the requirement (5 min):**

- Take the call, the email, the walk-in conversation. Write down
  what they said in `intake.md` *in their own words*. Do not
  translate ("they want a 36-inch base with hidden hinges") — paste
  the verbatim ("we need cabinets in front of the window that don't
  block the view"). The verbatim becomes the acceptance test later.
- Note the deadline if any. *"For our open-house in three weeks"*
  is the difference between *new SKU* (no) and *one-off* (yes).

**2. Scope it (10 min):**

- Ask the four questions below and write the answers in `scope.md`.
- **Q1: Have we built this before?** Search the existing catalog
  (Sales → Configurable Templates) for anything close. If yes, this
  is probably a *configurator delta* (add an attribute value), not
  a new product. Stop the lesson and skip to lesson 5.4
  (configurator UX) for the right path.
- **Q2: Will this customer want it again?** Or another customer?
  If the honest answer is *no, this is a one-off built around one
  kitchen*, it's a one-off. One-offs go through the sale order with
  a custom line; they don't get a ProductGraph item, a configurator
  entry, or a BoM template. Stop the lesson; the rest of Course 11
  doesn't apply.
- **Q3: Can our shop floor build it on the existing workcenters?**
  Look at the existing workcenter codes (`SB-EDGE`, `SB-CNC-BORE`,
  `SB-ASSY`, `SB-DOOR`, `SAND`, `PAINT`, `CURE`). If the answer is
  *"we'd need a new machine"* or *"this is hand-built only"*, flag
  that to the production manager **before** sketching. New products
  that require new workcenters are a much bigger project — they need
  capex sign-off before lesson 11.2.
- **Q4: Is the math sane?** Will the price likely land within
  ±30% of an existing comparable SKU? If not, the customer
  probably wants something we can't profitably build at our
  margins; have the price conversation first, before the design
  conversation.

**3. Sketch (5 min):**

- Draw it. Photograph the napkin. Drop the file in the folder as
  `sketch.<ext>`. *Resist the urge to model it in CAD now* — that
  belongs to lesson 11.4 (BoM authoring) once the spec is locked.

**4. Draft the spec (10 min):**

- In `spec_draft.md`, bullet the spec. Don't be precise — be
  *complete*. Width range (not a single number), height range,
  depth, materials, door style, hardware, finish. The PLM engineer
  in lesson 11.2 needs these to pick a property template; vagueness
  here costs three days later.

**5. Green-light decision (2 min):**

- Rename the folder. If green-lit for SKU, append `_GREEN`. If
  decided as one-off, append `_ONEOFF`. If parked for now, append
  `_PARK`.
- Send a one-line Slack message to the production manager and the
  PLM engineer: *"New SKU intake green-lit:
  `2026-06-17_floating_corner_shelf_GREEN`. Lesson 11.2 yours."*

That's it. You're done. The PLM engineer takes over at lesson 11.2.

## Common mistakes + how to recover

**"I created a `pg.item` already because I was excited."**

Roll it back. ProductGraph items in `concept` state can be archived
(`active=False`) but the part number is burned — `PG-PRT-0042` is
gone. Not a disaster, but a habit to break. The intake folder is
the right artifact at this stage.

**"The customer wants it in two weeks. We don't have time for the
conception folder."**

Two weeks is a **one-off**, not a new SKU. Build it through the sale
order with a custom configured product line and skip Course 11
entirely. New SKUs need 6–12 weeks of catalog hygiene minimum
(lessons 11.2 through 11.7) and any compression of that is
manufacturing debt you'll pay back during the first MO.

**"The sketch is just words. Drawing isn't my thing."**

Words are fine *if* they're complete. The litmus test:
hand `spec_draft.md` to the PLM engineer with no other context. If
they can describe the cabinet back to you correctly in 60 seconds,
the spec is enough. If they need to ask three follow-ups, the spec
needs a sketch.

**"I scoped it as SKU but the production manager says we'd need
a new workcenter."**

Pull the green-light. Rename the folder `_BLOCKED_CAPEX`. The
project is not dead, but lesson 11.2 doesn't fire until the
production manager has run a capex pass on whatever new equipment
the SKU implies. New cabinets that need new workcenters are a
separate conversation with the owner, not a Course 11 conversation.

**"Two designers green-lit overlapping ideas in the same week."**

Lesson 11.2's PLM engineer is the merge point. They open both
folders, pick the better-scoped one (or invent a third), and tell
the losing designer to archive their folder
`*_DUPLICATE_OF_<slug>`. This is normal — Southbrook ideates faster
than it can engineer; conception is throwaway-cheap on purpose.

## What the system is doing behind the scenes

(Almost nothing — that's the point of this lesson.)

The only "system" at this stage is **the folder name convention** and
**the one-line Slack notification**. No Odoo records, no
ProductGraph records, no `sale.order` lines.

This is deliberate. Every other lesson in Course 11 writes to
production data — the conception step is the one place where ideas
that don't survive contact with reality can die cheaply. The cost of
a dead intake folder is zero; the cost of a dead `pg.item` is a
burned part number, an audit-log row, and explaining the
abandonment in the next PLM weekly.

When lesson 11.2 fires, the PLM engineer reads `spec_draft.md`,
picks a property template, fills in the values, and *that's* the
moment the platform learns about the product. Everything before that
is human work.

## Quiz (5 questions, applied)

**1.** A dealer calls and says *"we need a cabinet that fits over a
gas fireplace flue — narrow, tall, vented at the back."* You've never
built one. Two other dealers have asked about similar fireplaces this
year. What do you do?

> Open the intake folder. Capture the dealer's words verbatim in
> `intake.md`. In `scope.md` answer Q2 "yes, three dealers in a year
> implies a SKU." Q3 "buildable on SAW+EDGE+ASSY+QC, vent cut is a
> CNC operation we already do for ovens." Sketch the venting in the
> back. Green-light → `_GREEN`. Notify the PLM engineer; lesson 11.2
> picks it up.

**2.** A customer comes in with a magazine clipping of a Scandinavian
floating shelf and says *"we want six of these in our kitchen."* The
shelf is not in our catalog. What do you do?

> One-off. Single kitchen, no second customer in sight, no SKU
> investment justified. Skip Course 11 entirely; build it through the
> sale order as a custom line with a free-text description and a
> custom price. Drop the magazine clipping in the kitchen project
> folder for the PLM engineer to glance at during cut-spec authoring.

**3.** You sketched the new SKU but the production manager points out
that the panel sizes you specified exceed `x_sbk_max_panel_length_mm`
on every workcenter we own. What do you do?

> Pull the green-light. Two options: (a) revise the spec to panels
> the existing workcenters can handle (probably means two-piece
> construction, joined at install) — go back to step 4 of the daily
> flow; (b) flag for capex review — rename folder
> `_BLOCKED_CAPEX`. Either way, lesson 11.2 does **not** fire today.

**4.** You're three days into a new-SKU intake and realise it's
fundamentally an existing SKU with a new door style. What do you do?

> Rename folder `_DUPLICATE_OF_<existing_sku>`. The right path is a
> *new attribute value* on the existing template, not a new SKU.
> Send the spec to the configurator admin (lesson 5.4 + 11.5) instead
> of the PLM engineer. Saves about six weeks of unnecessary
> engineering.

**5.** The PLM engineer takes the green-lit folder and says *"I can't
pick a property template from this — it's too vague."* What's the
recovery?

> Go back to step 4. The spec wasn't complete. Add the missing fields
> — typical hardware? mounting style? load rating? finish range? — to
> `spec_draft.md`, then re-notify. This is normal on the first
> intake you author; by your fifth, the spec will be tight on the
> first pass.

---

## What this lesson does NOT cover

- Anything Odoo. Conception is off-platform; lesson 11.2 is where
  the first system record is created.
- How to build a one-off custom line on a sale order — that's
  lesson 5.2 (estimating a quote) with the *Custom Product* path.
- Configurator deltas (adding a new attribute value to an existing
  SKU) — lesson 5.4 (configurator UX tweaks) is the right place.
- Capex requests for new workcenters — out of scope for Course 11
  entirely; that's a manager-to-owner conversation.
- The next lesson (11.2) where the PLM engineer creates the
  `pg.item` record in ProductGraph and the new product becomes real.
