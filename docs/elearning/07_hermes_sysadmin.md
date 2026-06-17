---
course: 7 — Sysadmin
chapter: 7.3
title: Hermes Console — The External Sysadmin Recommendations Queue
duration: 35 minutes
audience: IT Admin / Sysadmin who triages platform-health, backup, runner, and tunnel recommendations surfaced by the external Hermes Console
prereqs: Lessons 7.1 (the in-Odoo orchestration crons) and 7.2 (the backup pipeline); Cloudflare Access OTP enrolment for `dangelo.john@gmail.com`; familiarity with the Fabio in-Odoo queue (lessons 3.2 + 6.3) so you know what does NOT belong in Hermes
custom_modules: hermes-console (standalone repo, NOT an Odoo addon); southbrook_hermes (consumer)
---

# Hermes Console — The External Sysadmin Recommendations Queue

## Who this lesson is for

You're the sysadmin who watches the platform itself — not manufacturing,
not customer support. When the nightly backup is stale, when the
Forgejo Actions runner stops registering, when the Cloudflare tunnel
drops, the system that proactively surfaces those events to you is the
**Hermes Console**, hosted externally at `hermes.odooiq.com`. It's a
standalone control plane, separate from Odoo, that runs agent loops
against the platform and writes recommendations into its own queue for
you to approve or reject. This lesson is how you find that queue, what
the kinds of recommendations mean, and how you push an approved
recommendation through to a tenant (Southbrook's `southbrook_hermes`
Odoo addon, future Forgejo Actions runner, etc.).

## Where this lives on the site

The Hermes Console is **not** part of Odoo. It runs as two containers
on the QNAP host:

- `hermes-ui` — Vue 3 + Vite PWA
- `hermes-api` — FastAPI service backed by local SQLite

Both fronted by the shared `alfacore-caddy` and exposed via Cloudflare
tunnel at:

> **`https://hermes.odooiq.com`**

Cloudflare Access OTP is in front of the tunnel; only enrolled emails
(currently `dangelo.john@gmail.com`) can reach the UI. The Console UI
never says "Fabio" — that name belongs only to the in-Odoo skin of the
`southbrook_hermes` addon, which is a **consumer** of approved
recommendations from this Console.

If you need to inspect the backend directly:

> **`ssh admin@ssh.odooiq.com`** then
> **`docker logs hermes-api --tail 200`** and
> **`curl http://localhost:9080/api/health`** (via Caddy on the QNAP)

For the queue UI itself, after Cloudflare OTP:

> **`hermes.odooiq.com` → Recommendations tab**

For agent loop telemetry (when did each loop last run, what did it
return, was it errored):

> **`hermes.odooiq.com` → Agents tab** (proxies `GET /api/agents`)

## What your screen shows

The Console's **Recommendations queue** is the primary surface. Each
recommendation has:

- **Title** — short label written by the agent loop that filed it.
  E.g. `Nightly backup stale (28h old)` or `Backup status file missing`.
- **Source** (`source` on the local recommendation row) — which agent
  loop filed it. The sysadmin-relevant sources are:
  - `platform_health` — the LLM-backed proactive loop. Runs every
    `HERMES_PLATFORM_HEALTH_INTERVAL` seconds. Reads recent agent run
    history and surfaces patterns ("backup_health has filed the same
    issue 3 nights running — escalate"). Deterministically defaults
    `source = platform_health` on every item it emits.
  - `backup_health` — deterministic, no LLM. Reads
    `/share/CACHEDEV3_DATA/OdooIQ-Backups/hermes/<status_file>` and
    emits a recommendation when the most recent backup is older than
    `HERMES_BACKUP_MAX_AGE_HOURS` or the outcome was not `success`.
    Idempotent: skips emit if the most recent reco from `backup_health`
    is still `ready` or `approved`.
  - `daily_digest` — LLM-backed end-of-day summary, includes any
    platform-level events that fired during the day.
- **Priority** (`priority`) — `low`, `normal`, `high`, or `blocker`.
  `BackupHealthLoop` emits `blocker` on a failed outcome, `high` on
  staleness, `high` on missing status file. `platform_health` defaults
  to `normal` and the LLM can override.
- **State** (`state`) — the queue's lifecycle field. Values:
  `ready` (just created, awaiting review), `approved` (you said yes),
  `rejected` (you said no), `applied` (the bridge has pushed it
  downstream), `failed` (the bridge rejected synchronously),
  `queued` (the bridge was unreachable — sitting on the outbound
  retry queue).
- **Tenant hint** (`tenant_hint`) — optional. For sysadmin
  recommendations this is usually `null` because the action happens on
  the QNAP host, not in any tenant. Manufacturing-side recommendations
  (the Fabio queue) carry `tenant_hint = "southbrook"`.
- **Proposed action** — free-text suggestion the loop wrote. For
  `backup_health` this is literally the runbook path:
  `Check /share/CACHEDEV3_DATA/OdooIQ-Backups/hermes/cron.log on the
  QNAP for the latest run's stderr; consult
  custom-hermes-skills/skills/qnap-backup-snapshot-checker/runs/
  hermes-nightly-backup-runbook.md for the rollback path.`
- **Payload** (`payload`) — JSON the loop attached. For `backup_health`
  it carries `{"status_path": "..."}` so the approver can confirm the
  loop was reading the right file.
- **Created at / Updated at** — timestamps. A reco that's been in
  `ready` for more than 24 h is your cue that triage is falling
  behind.

The **Agents tab** (proxies `GET /api/agents`) shows per-loop:

- **Name** — `platform_health`, `backup_health`, `daily_digest`.
- **Interval seconds** — the loop's tick.
- **Last run at** — when the loop last completed.
- **Last run status** — `ok` or `error`. An `error` row that hasn't
  cleared in two ticks means the loop is wedged.

## What lives here vs. the in-Odoo Fabio queue

This is the most important distinction in the platform and the one most
likely to cause confusion. Keep it straight:

| Queue | Surface | Kinds of recommendations | Approver |
|---|---|---|---|
| **Hermes Console** (this lesson) | `hermes.odooiq.com` (external, standalone) | Platform health: backup, tunnel, runner, container restarts, disk usage | **Sysadmin** (you) |
| **Fabio** (in-Odoo) | Odoo backend → *Hermes* menu, served by `southbrook_hermes` addon | Manufacturing: slow workorder, materials blocked, scrap event, cut-spec audit, MI gate failures | **Production manager** (lesson 3.2) / **CS rep** (lesson 6.3) |

The Hermes Console is the **primary** system; Fabio is one of its
**consumers**. A recommendation that lands in Fabio either originated
inside Odoo (via the MI engine refire cron — lesson 7.1) **or** was
approved in the Hermes Console and pushed downstream to Fabio by the
`southbrook_hermes` tenant bridge.

**As sysadmin, you live in the Hermes Console queue. Manufacturing
recommendations are not your queue.** If a `tenant_hint =
"southbrook"` recommendation slips into your view, it's because the
queue UI shows everything; you can filter it out via the source filter.

## Your daily flow — On-call

**Daily (5 min, morning):**

1. Open `hermes.odooiq.com` (Cloudflare OTP gates the page).
2. Go to **Recommendations**, filter `state = ready` and `source IN
   (platform_health, backup_health)`. Sort by priority desc, created
   asc.
3. For each row, read the title and proposed action. The deterministic
   loops (especially `backup_health`) tell you exactly which file to
   check and which runbook to follow — start there before approving.
4. For `platform_health` items, the LLM has already correlated the
   evidence — read the rationale field for the reasoning, then
   independently verify the underlying claim (`backup_health filed 3
   nights running` is easy to disprove or confirm in 30 seconds via
   the queue filter).

**Per recommendation:**

- **Investigate** — do the diagnostic the proposed action suggests.
  For a backup-staleness reco, that's the lesson 7.2 procedure.
- **Approve** if the recommendation is correct AND you intend to act.
  Approval moves `state → approved` but does NOT execute anything.
- **Reject** if the recommendation is wrong, duplicate, or already
  resolved out-of-band. Rejection moves `state → rejected` with an
  optional reason and the loop's idempotency check picks up "no
  active reco" on its next tick, so duplicate emits resume only after
  a fresh failure.
- **Apply** when you're ready to execute. Apply fires the configured
  tenant bridge for the recommendation. **For sysadmin recommendations
  in current scope, there is no tenant bridge — Apply is a manual
  acknowledgement that you've completed the action.** (Future:
  Forgejo Actions tenant bridge will let you push approved sysadmin
  actions to a runner that executes them — see "Upcoming" below.)

**On WhatsApp escalation:**

If `HERMES_WHATSAPP_ENABLED=true` and the WhatsApp sidecar is up
(check `Settings → integrations` or `GET /api/health.whatsapp.status`),
new `priority = high` and `priority = blocker` recommendations notify
the configured operator phone (E.164 from
`HERMES_WHATSAPP_OPERATOR`). The notification message is generated by
`render_new_recommendation_message` in `api/whatsapp.py`. You can
reply to that message with inbound commands (parsed by
`parse_inbound_command`) — currently supports approve/reject by
recommendation ID without leaving the chat. The shared secret on
`/api/whatsapp/inbound` is `HERMES_WHATSAPP_SHARED_SECRET`; rotate it
if the sidecar is ever cloned or the QR code re-paired.

**Weekly:**

- Open the Agents tab. Confirm `platform_health`, `backup_health`, and
  `daily_digest` all show *Last run* within the expected interval.
- Open `GET /api/health` (the overall health endpoint) via the UI or
  `curl`. Confirm `api`, `sqlite`, `llm` (per provider), `bridges`
  (per tenant), `whatsapp` are all `ok` or `disabled`. Any
  `unreachable` is your weekly triage target.

## Common mistakes + how to recover

**"`backup_health` is filing the same `Nightly backup stale` reco
every interval, even though I approved the last one."**

You **approved** it. Approval doesn't fix the underlying problem —
the loop is still reading the same stale status file. Approval moves
the reco to `approved`, which the idempotency check still treats as
"there's an active reco for this source, skip emit." So you should
NOT see duplicate emits while one is `approved`. If you are seeing
duplicates, either (a) you rejected the prior one (which the
idempotency check ignores — rejected recos are not "active"), or (b)
the loop's `recent_recommendations_for_digest(hours=48)` cutoff
expired. Fix the backup, then mark the reco `applied`. The next loop
tick reads the fresh status file and stays silent.

**"I approved a recommendation but nothing happened on the QNAP."**

Correct — approval doesn't execute anything. The current Console
build has tenant bridges only for `southbrook_hermes` and
`HomeAssistantBridge`. Sysadmin actions (restart a container, kick the
crontab, re-fire the backup) are not bridged; *Apply* on a sysadmin
reco is a manual acknowledgement that you've done the work via SSH.
The Forgejo Actions bridge that will execute approved sysadmin actions
is in the project direction (see "Upcoming") but not in the current
shipped build.

**"`platform_health` is filing recommendations that look like
hallucinations — `Disk near full on /share/CACHEDEV3_DATA` when df
shows 38%."**

The LLM loop reads agent run history, not live system state. If
`backup_health` raised a "backup status file missing" reco a week
ago and the LLM is over-indexing on that event, the reasoning chain
can drift. Reject the bad reco with a reason (the reason becomes
context for the next tick). If hallucinations persist, lower the
loop's interval to slow drift, or switch the primary provider via
`HERMES_PRIMARY_PROVIDER` if the Hermes harness is the cause and
`openai` is more grounded.

**"I can't reach `hermes.odooiq.com` — Cloudflare Access shows
'unauthorised'."**

Two layers to check. (1) Cloudflare Access OTP: are you signed in as
`dangelo.john@gmail.com`? Open an incognito window, sign in fresh.
(2) The tunnel itself: `cloudflared` is a separate container on the
QNAP. If `cloudflared` is down, you get a Cloudflare 1033 (not an
Access error). Check `docker ps | grep cloudflared` and restart if
missing. The tunnel ingress map for `hermes.odooiq.com` lives in the
cloudflared config; if you've recently changed it, a restart is
required for ingress reloads.

**"The WhatsApp sidecar lost its session and notifications stopped."**

WhatsApp Web sessions occasionally drop. The sidecar is
`hermes-whatsapp` (whatsapp-web.js + headless Chrome). Recovery: SSH
to the QNAP, `docker logs hermes-whatsapp --tail 100` to find the QR
prompt URL or the auth failure, re-pair if needed. Until paired,
`/api/health.whatsapp.status` reports `unreachable` and the Console
silently falls back to in-UI notifications. **Do not** disable the
sidecar — `priority = blocker` recommendations need an out-of-band
notification channel.

## What the system is doing behind the scenes

The Hermes Console runs three components inside `hermes-api`:

1. **Local store** — SQLite file in a QNAP-mounted volume. Survives
   container, Caddy, and QNAP reboots. All recommendations, chat
   threads, and outbound bridge pushes live here. The store is
   independent of Odoo on purpose — Hermes outlives any tenant.
2. **Agent loop runner** — a single asyncio task started in the
   FastAPI `lifespan` context. Iterates `_BUILT_IN_LOOPS` per their
   interval, calls `loop.run(env)`, persists returned items as
   recommendations via `env.store.create_recommendation`. Per-loop
   exceptions are caught and recorded as an `error` run record without
   crashing the runner.
3. **Outbound queue** — a retry buffer for tenant-bridge pushes that
   failed transiently. The `southbrook_hermes` bridge POSTs to the
   Odoo addon's `create_recommendation` route; on unreachable Odoo,
   the push is queued for retry on the next `/api/queue/flush` (manual
   or scheduled).

The LLM provider registry talks OpenAI Chat Completions only. Two
providers can be configured simultaneously (`OPENAI_API_KEY` for
OpenAI; `HERMES_HARNESS_BASE_URL` + `HERMES_HARNESS_API_KEY` for the
self-hosted Hermes harness). `HERMES_PRIMARY_PROVIDER` picks the
default; per-thread overrides via the UI.

Recommendations created by the loops always include
`source = <loop name>` so the queue filter is reliable. The state
machine is `ready → approved → applied` (happy path) or
`ready → rejected` (no further state). `failed` and `queued` are
states the bridge transition can land in — a synchronous bridge
rejection goes `approved → failed`; a transient bridge unreachable goes
`approved → queued` and stays there until the retry worker drains it.

## Upcoming — Forgejo Actions bridge

Per the project direction, an upcoming tenant bridge will let you push
approved sysadmin actions to a Forgejo Actions runner registered on
the QNAP (`forgejo-runner` on the `forgejo-net` Docker network, label
`linux-amd64`). The workflow:

1. The agent loop files a sysadmin recommendation. E.g.
   `Rebuild southbrook-odoo container after image bump`.
2. You approve it in the Hermes Console.
3. *Apply* fires the Forgejo Actions bridge, which POSTs a
   `workflow_dispatch` event to the matching workflow file in the
   `qnap/sysadmin-actions` Forgejo repo.
4. The runner picks up the event, executes the workflow (which can
   build/run prod containers via the system-docker socket mount), and
   POSTs back to a Hermes callback URL with the outcome.
5. The reco transitions `applied` on runner success, `failed` on
   runner failure.

This is **not yet in the current shipped build**. Until it lands,
sysadmin recommendations are "human applies them via SSH."
The trust-boundary risk (runner has docker socket access) is the gating
concern; once approved-recommendation-to-runner is a fully signed,
auditable path, this lesson gets a new "How to execute via runner"
section.

## Quiz (5 questions, applied)

**1.** It's 9 AM. You open `hermes.odooiq.com` and see two
`backup_health` recos with `priority = blocker` from 03:30 last night
and 03:30 this morning. Both say `Nightly backup last run failed
(error)`. What's wrong with the queue and the underlying system, and
what's the right sequence?

> Two `blocker` recos from `backup_health` two nights in a row means
> the idempotency guard didn't suppress the second. The most likely
> cause: you rejected (not approved) the first reco, OR `backup_health`'s
> 48-hour "recent" window expired between emits. Either way, the
> underlying backup is broken two nights running — that's the urgent
> issue. Sequence: (a) SSH to the QNAP and run the lesson 7.2 manual
> backup procedure to plug the gap, (b) read `/share/.../_meta/logs/`
> for both nights to find the root cause, (c) fix, (d) re-fire the
> backup once, (e) come back to the Console, mark BOTH recos
> `applied`. The next tick will be silent.

**2.** A production manager opens a ticket: "I see a recommendation
about Cloudflare tunnel health in my Hermes queue inside Odoo. Is
that for me?" What do you tell them, and what's the correct surface?

> No, that's a sysadmin recommendation that got mis-routed into the
> Fabio queue. Tunnel health belongs in the **external Hermes Console
> at hermes.odooiq.com**, not in the in-Odoo *Hermes* menu. If it
> landed in Fabio, either the `tenant_hint` on the original Console
> recommendation was set to `southbrook` incorrectly, or the
> `southbrook_hermes` addon is mis-filtering. Triage: dismiss it
> from the production manager's queue, find the original in the
> Console (filter `source = platform_health` or by title), and
> investigate from the sysadmin side.

**3.** The Agents tab shows `backup_health` *Last run* is 4 hours
old; the interval is supposed to be 15 minutes. Recommendations
section is empty. Is the system healthy or broken?

> Broken. The loop hasn't ticked in 16 intervals. Most likely the
> agent loop runner task crashed and the lifespan didn't restart it
> (or the API container is up but the runner thread is wedged).
> Recovery: `docker logs hermes-api --tail 200` for a stack trace
> from the runner; if found, restart with `docker restart hermes-api`.
> Confirm recovery by watching the Agents tab — `backup_health`
> *Last run* should advance within 15 minutes.

**4.** You approve a `Nightly backup stale` reco. An hour later
`backup_health` files a fresh one. Bug, or intended?

> Intended IF the underlying backup is still stale. Approval doesn't
> fix the backup; the loop reads the same status file on its next
> tick, sees the same staleness, and would normally suppress the
> emit because the prior reco is still in `approved` state (not
> rejected). If you're seeing a fresh emit, check: (a) did you
> actually approve, or did you mis-click reject? (b) is the prior
> reco older than 48 h (the `recent_recommendations_for_digest`
> window)? If both no, that's a real bug — file against
> `BackupHealthLoop` idempotency check.

**5.** You're paged via WhatsApp with a `blocker` reco. You reply
`approve 142` from your phone. What does the system do, and what does
it NOT do?

> The WhatsApp sidecar receives the inbound, posts it to
> `/api/whatsapp/inbound` with the shared secret. The Console parses
> `approve 142` via `parse_inbound_command`, looks up reco id 142,
> moves its state to `approved`, and replies via the sidecar with
> a confirmation. What it does NOT do: it does not execute the
> remediation. *Apply* is still a manual step from the UI (or, when
> the Forgejo Actions bridge ships, an automatic runner dispatch).
> WhatsApp lets you triage from the phone; the actual fix still
> happens at the keyboard.

---

## What this lesson does NOT cover

- The Premium Orchestration six crons (in-Odoo) → **lesson 7.1**.
- The QNAP backup script details and the restore procedure →
  **lesson 7.2**.
- The Fabio (in-Odoo) recommendation queue for manufacturing — that's
  a separate queue with a different audience. The production
  manager's view → lesson 3.2; the CS rep's view → lesson 6.3.
- Cloudflare Access enrolment / OTP onboarding for new sysadmin
  operators → separate platform doc.
- The Console's chat surface (chat threads, message history, queue-from-message)
  — useful as a "scratch with the LLM, promote an assistant reply
  to a queued recommendation" workflow but out of scope here; the
  queue side of that flow is the same as a loop-generated reco.
- Multi-tenant onboarding (adding a new tenant bridge for a future
  Alfacore or third-party consumer) → see `hermes-console/README.md`
  §"Multi-tenant readiness".
