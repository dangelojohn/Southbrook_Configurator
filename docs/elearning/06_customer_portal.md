---
course: 6 — Customer Touchpoints
chapter: 6.1
title: Customer Service — Reading the Customer Portal
duration: 30 minutes
audience: Customer Service rep who fields phone + email questions about the /my/kitchen-projects portal
prereqs: Basic Odoo back-office navigation, awareness that the customer portal exists at southbrookcabinetry.space/my
custom_modules: southbrook_customer_portal, southbrook_kitchen_workspace
---

# Customer Service — Reading the Customer Portal

## Who this lesson is for

You're the Customer Service rep who picks up the phone when a customer
calls asking "Where are my design options?", "I think I clicked the wrong
one — can you fix it?", or "I never got my welcome email." You don't
design kitchens and you don't run MRP — but you need to see exactly what
the customer is seeing on their portal, know what they're allowed to do,
and know what's deliberately hidden from them so you don't accidentally
read internal pricing off the screen during a call.

## Where this lives on the site

The customer's portal lives at:

> **southbrookcabinetry.space → Sign in → My Account → Kitchen Projects**

Direct portal route:

> **> /my/kitchen-projects** — list of the customer's projects
> **> /my/kitchen-project/<id>** — the A/B/C concept review page

Your back-office view of the same data:

> **Sales → Kitchen Workspace → Projects → [open the row]**

That back-office form (`sb.kitchen.project`) shows everything the customer
sees **plus** the internal fields (estimated cost breakdown, salesperson,
opportunity link, chatter, approval audit trail). When a customer calls
asking about their portal, open the back-office form alongside — the
customer's view is a strict subset of yours.

## What your screen shows

The portal list page (`/my/kitchen-projects`) shows one row per project
the customer owns. Columns:

- **Project** — code + name (`code` and `name` on `sb.kitchen.project`,
  e.g. `KP/2026/000123 — Wilson Coastal Remodel`).
- **Theme** — one of Signature / Elegance / Contemporary / Contractor
  (`theme` on `sb.kitchen.project`).
- **State** — current lifecycle stage (`state` on `sb.kitchen.project`):
  `draft → designing → awaiting_customer → approved → in_production →
  done` (plus `cancelled` off the side).
- **Target** — target completion date (`date_target`).

The detail page (`/my/kitchen-project/<id>`) is the meat of the customer's
experience:

- **3D Preview pane** — a Three.js canvas reading from the selected
  option's `placement_data_json`. If no option is selected yet, it shows
  the first option in sequence. If JavaScript is off, a "JavaScript is
  required" notice replaces the canvas (silent — the rest of the page
  still works).
- **Design Options grid** — one card per `sb.kitchen.design.option` row,
  showing `name` (e.g. "Option A — Coastal Walnut"), `description`
  (HTML), `estimated_price` (the customer's price, NOT the cost), and
  `estimated_lead_time_days`.
- **"Select this option" button** — visible per card while the project
  state is `designing` or `awaiting_customer` AND that card isn't already
  selected. Posts to `/my/kitchen-project/<id>/select/<option_id>` and
  flips `is_selected = True` on that row (the design-option model's
  `write()` override forces the other cards to `False` atomically — only
  one option may carry `is_selected = True` at a time).
- **"I approve <option_name>" button** — appears only when state is
  `awaiting_customer` AND a design option is selected. Posts to
  `/my/kitchen-project/<id>/approve`, which creates an
  `sb.kitchen.approval` record (`approval_type='design'`,
  `approver_type='customer'`, `state='approved'`) and runs
  `action_customer_approves()` on the project, advancing state to
  `approved`.
- **Spec Sheet PDF** — appears after the customer approves; renders
  inline via `<iframe>` on desktop + Android, downloadable on iOS Safari
  (which silently blanks PDF iframes — so the "Download Spec Sheet"
  button is the only path that works there).

What the customer **cannot see** (and what you must not read off your
screen during a call):

- **Cost breakdown.** The customer sees one number per option,
  `estimated_price`. They do not see materials cost, labour cost, the
  margin, or the dealer-pricelist column. None of those fields are
  rendered on the portal templates.
- **Internal chatter.** The `mail.thread` on `sb.kitchen.project` is back
  office only. Notes the designer wrote ("customer wants drawer pulls
  but won't say which") never reach the portal.
- **Dealer pricing.** If the customer is attached to a dealer, the dealer
  sees the −50% column on /my/dealer/orders — but the **customer** never
  sees the dealer's pricelist, only their own retail-equivalent
  `estimated_price`. Two pricelist columns are a dealer thing
  (lesson 6.2), not a customer thing.
- **Other customers' projects.** The portal ACL is enforced by
  `rule_portal_kitchen_project_own_only` (record rule on
  `sb.kitchen.project`, `domain_force = [('partner_id', '=',
  user.partner_id.id)]`). A portal user *cannot* see, link to, or even
  probe-by-ID another customer's project — the controller's
  `_fetch_project_for_user` raises `MissingError` for both "no such
  project" and "wrong customer" using the same message, so existence of
  other projects can't be inferred.

## Your daily flow

**1. Start of shift (5 min):**

- Open **Sales → Kitchen Workspace → Projects** and filter by
  **State = Awaiting Customer**. These are the customers who currently
  have the ball — they've seen the A/B/C and need to pick + approve.
- Sort by `date_target` ascending. The ones near their target completion
  date are the calls most likely to come in today.

**2. Per customer call (the loop):**

When a customer calls asking "what's going on with my kitchen":

- Search the projects list by their phone or email. Open the row.
- Read `state` first — that one field tells you which sentence to say:
  - `draft` → "We've just created your project — your designer is
    starting on options this week."
  - `designing` → "Your designer is working on three concepts; they'll
    be in your portal in a few days."
  - `awaiting_customer` → "Your three concepts are live in the portal —
    you need to pick one and approve. Want me to walk you to the URL?"
  - `approved` → "You approved — we're scheduling production."
  - `in_production` → "We're building it. The target completion is
    <`date_target`>."
  - `done` → "It's installed. Anything wrong?"
- If they want to know what they're seeing on the portal, **read the
  same `sb.kitchen.design.option` rows back off the back-office form**.
  Same names, same prices, same lead times.

**3. Walking a customer through first login (3 min):**

When a customer says "I never got my password email":

- Open the customer's `res.partner` form.
- Check the customer's `res.users` link (the user record under
  *Settings → Users*). If there's no user, click the partner-form **Grant
  Portal Access** action (native Odoo); that triggers the standard portal
  invite email — the customer gets a signup link that lets them set their
  own password.
- If the user exists but the customer never set a password, the same
  *Grant Portal Access* action re-sends the invite.
- Tell them what URL they're going to:
  `southbrookcabinetry.space/my/kitchen-projects` is the bookmark.

**4. Spotting customers who've gone quiet (5 min at start of shift):**

- Filter projects on **State = Awaiting Customer** AND
  `write_date < today - 14 days`. These are projects where the customer
  was told "your concepts are ready" two weeks ago and hasn't acted.
- Cross-check the customer's `res.users.login_date` (Odoo native field
  on the user record) — if they've never logged in OR their last login
  was before the project was submitted, the welcome path is probably
  broken (wrong email, spam folder).
- Call the customer. Don't email — a customer who isn't reading the
  portal email isn't reading your follow-up email either.

**5. End of shift (5 min):**

- Any customer you walked through approving a design — open their
  project, check `state` is now `approved` and there's a fresh row on
  the **Approvals** tab with `approver_type = customer`. If state is
  still `awaiting_customer`, they didn't actually click — call back
  tomorrow.

## Common mistakes + how to recover

**"The customer says they clicked Approve but my back-office still says
awaiting_customer."**

Two real causes:

1. They clicked **Select this option** (the per-card button) but never
   scrolled down to **I approve <option>** (the green button at the
   bottom of the page). Selection ≠ approval. Check `selected_design_
   option_id` on the project — if it's set but state is still
   `awaiting_customer`, that's the diagnosis. Walk them through the
   second click.
2. They got a CSRF token error and the redirect bounced them back to
   the same page. Rare, but happens when they leave the tab open
   overnight. Ask them to reload the page first, then click Approve.

**"The customer says they want to change which option they selected
after they already approved."**

Approval flips the project to `approved` and the state-machine
disallows going backward through the public actions. You **cannot**
un-approve via the portal — there's no button for it. From your back
office: the designer can run `action_set_state('designing')` (back to
designing), the customer re-selects + re-approves, and a fresh
`sb.kitchen.approval` row is created. **Escalate this to the
designer** — don't write the state field yourself.

**"The customer says the portal shows the wrong price."**

The portal shows `sb.kitchen.design.option.estimated_price`. If that's
wrong, it's wrong on the model — the portal is just a window. Open the
back-office form, fix the value on the relevant option row, and tell
the customer to refresh. **Do not** quote them a different price over
the phone without changing the field — what they see on screen IS the
contractual quote.

**"The customer is asking why their installation date moved."**

`date_target` on the project is the only date the portal shows. If the
production planner moved it, it moved on the project. The customer
won't see a chatter note explaining why (chatter is internal). You'll
have to read the planner's chatter entry yourself and translate it
into a customer-friendly sentence on the call.

**"A second customer called saying they can see another customer's
project."**

That's a P0 — escalate to IT immediately. The portal ACL
(`rule_portal_kitchen_project_own_only`) is supposed to make this
impossible. If it actually happened, either (a) a customer is logged
in as the wrong `res.users`, or (b) the rule has been disabled. **Do
not write to the project** while investigating — you'll mess up the
audit trail.

## What the system is doing behind the scenes

Each portal click writes to one of three tables:

- **`sb.kitchen.design.option`** — *Select this option* sets
  `is_selected = True` on the chosen row. The model's `write()` override
  runs an atomic compensating write that sets `is_selected = False` on
  every other option for the same project, so the one-of-N invariant is
  enforced at the ORM layer, not by the UI.
- **`sb.kitchen.approval`** — *I approve* creates a new approval row
  with `approval_type='design'`, `approver_id = current portal user`,
  `approver_type='customer'`, `state='approved'`, `date_decided=now`.
  This is the audit trail; it's permanent and append-only.
- **`sb.kitchen.project`** — the same *I approve* call then runs
  `action_customer_approves()`, which (a) checks a design option is
  selected, (b) calls `action_set_state('approved')` (which validates
  against the `VALID_TRANSITIONS` set in
  `southbrook_kitchen_workspace/models/sb_kitchen_project.py` — an
  off-graph transition like `draft → approved` raises `UserError`), and
  (c) triggers the `email_template_design_approved` lifecycle email via
  `_send_lifecycle_email`.

The portal controller (`southbrook_customer_portal/controllers/main.py`)
uses `sudo()` on all reads because the portal user's own ACL is
read-only on the project (per `ir.model.access.csv` —
`perm_read=1,perm_write=0`). The controller is the layer that decides
*which* project to read; the record rule
(`rule_portal_kitchen_project_own_only`) is the layer that decides which
project the portal user is even *allowed* to read if they probe by ID.
Two layers of defence; both have to fail for cross-customer leakage.

## Quiz (5 questions, applied)

**1.** A customer calls and says: "I clicked Approve but the page came
back and the green button is gone — did it work?" The state on your
back-office form still reads `awaiting_customer`. What do you check
first?

> Open the customer's project in back office and look at
> `selected_design_option_id`. If it's set but state is still
> `awaiting_customer`, they only clicked **Select this option**, not
> **I approve**. Walk them through scrolling down to the green button.
> If `selected_design_option_id` is empty, they never even selected —
> tell them to pick a card first.

**2.** A customer says: "I want to see the cost breakdown — what's the
labour cost on Option B?" Where do you read that off the portal?

> You don't. The portal shows ONE number per option,
> `estimated_price` on `sb.kitchen.design.option`. There is no cost
> breakdown rendered on the customer-facing template. If they want
> a breakdown, the conversation goes to their designer / salesperson,
> not to you. Don't read the back-office cost figures out loud — those
> aren't priced for the customer.

**3.** Filter projects by **State = Awaiting Customer**. You spot one
that's been in that state for 18 days, last write was 17 days ago.
What's your next action?

> Open the customer's `res.users` (linked from `res.partner`) and check
> `login_date`. If they've never logged in or last logged in before the
> project was submitted, the welcome path is broken — phone them, not
> email. Re-issue the portal invite via *Grant Portal Access* on the
> partner form if their account exists but has never been used.

**4.** A customer says: "I just opened my portal and I can see another
customer's project — there's a kitchen called 'Smith Renovation' but
I'm not Smith." What do you do?

> Treat as a P0 security incident. Do NOT write to either project
> while investigating. The record rule
> `rule_portal_kitchen_project_own_only` is supposed to make this
> impossible — if it actually happened, either the customer is logged
> in as the wrong user account or the rule has been disabled.
> Escalate to IT immediately and capture the screen state on the call.

**5.** The customer says: "I changed my mind — I want Option C, not
Option B. Can you switch it for me?" The project state is `approved`.
What's the right answer?

> "You can't un-approve from the portal — there's no public button for
> it." Don't try to flip `is_selected` on Option C from your back
> office while state is `approved` — the project state-machine treats
> approval as a contractual gate. **Escalate to the designer**: they
> can run `action_set_state('designing')` to roll the project back to
> the designing stage, the customer re-selects + re-approves, and a
> fresh `sb.kitchen.approval` row is created so the audit trail shows
> the change.

---

## What this lesson does NOT cover

- General Odoo portal mechanics (sign-up, password reset internals) →
  Odoo's own native eLearning track.
- The dealer-portal surface (separate URL, separate rules, different
  audience) → lesson 6.2.
- Fabio's customer-communication recommendations queue (when the
  system flags a customer who's been quiet) → lesson 6.3.
- The Configuration Engine output that feeds `placement_data_json`
  and what the 3D preview is actually rendering — that's a designer /
  config-engine topic, not a CS topic.
- How the spec-sheet PDF is generated (the
  `report_signature_spec_sheet_doc` template) → estimating /
  configurator track, lesson 5.2.
