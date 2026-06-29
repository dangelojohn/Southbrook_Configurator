# Hermes — Operational Runbook

Day-to-day operations for the Hermes trade-partner platform shipped
2026-06-16. If you're new here, also read:

- `CLAUDE.md` § "Amendment 2026-06-16" — what's live and where the source-of-truth docs are
- `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md` — design spec (incl. § 14 implementation deltas)
- `~/.claude/projects/-Users-naadmin/memory/hermes_v1_deploy.md` — session-persistent operational notes

---

## 1. What is live

| Layer | Version | Health check |
|---|---|---|
| `southbrook_os` (Odoo addon) | `19.0.1.0.0` | `curl https://southbrookcabinetry.space/southbrook/os.json` → 200, 14 sections |
| `southbrook_hermes` (Odoo addon) | `19.0.4.0.0` | `./scripts/smoke_hermes.sh` → all PASS |
| Hermes sidecar (Vercel) | NOT YET DEPLOYED | Will be `vercel inspect` once stood up |
| OWL chat panel | embedded in Order Builder | Visible to authenticated trade partners under the order header card |

---

## 2. Daily smoke test

Run once per deploy and any time something feels off:

```bash
./scripts/smoke_hermes.sh
```

A green run confirms:
- PyJWT installed in the container
- `southbrook_hermes.jwt_secret` is a real value (not the placeholder)
- `/api/hermes/tools` returns the 13-tool registry (incl. `propose_recommendation` at T2)
- `/api/hermes/tools/get_os_section` dispatches and returns the canonical OS body
- `/api/hermes/conversation/log` accepts a write and persists a question_id
- `/southbrook/os.json` and `/commercial` regression baselines

Override env vars if needed:

```bash
PARTNER_ID=358 ./scripts/smoke_hermes.sh        # use a different real portal partner
TIER=T0+T1 ./scripts/smoke_hermes.sh            # test the narrower mask
QNAP_HOST=admin@192.168.68.108 ./scripts/smoke_hermes.sh   # LAN instead of tunnel
```

---

## 3. Deploy a code change

```bash
# 1. Make code changes, commit them.
git add addons/southbrook_hermes/
git commit -m "fix(hermes): …"

# 2. Deploy. Script picks tunnel vs LAN automatically by reachability.
./scripts/deploy_to_qnap.sh southbrook_hermes

# Or with explicit tunnel routing:
QNAP_HOST=admin@ssh.southbrookcabinetry.space RESTART=1 ./scripts/deploy_to_qnap.sh southbrook_hermes

# 3. Smoke test against prod.
./scripts/smoke_hermes.sh
```

The deploy script auto-classifies install vs upgrade per module via psql,
so adding a NEW addon and pushing it works in one command (was a recurring
"odoo -u <fresh module> = no-op" surprise pre-`93e5122`).

---

## 4. Going live with chat (the four account-gated steps)

Until these are done, the OWL chat panel renders a stub response. Trade
partners can see the panel and submit questions but get a `(Stub answer
— sidecar not yet wired.)` reply.

### Step 1. Deploy the Vercel sidecar

From your terminal (NOT mine — Vercel CLI needs your account auth):

```bash
cd .claude/worktrees/hermes-trade-partner-v1/sidecar
pnpm install
vercel link                              # one time
vercel env add HERMES_JWT_SECRET         # value from /tmp/hermes-jwt-secret.txt
vercel env add OPENAI_API_KEY            # your OpenAI key
vercel env add TENANT_REGISTRY           # paste: {"southbrook":"https://southbrookcabinetry.space"}
pnpm verify                              # confirms env vars
pnpm build:rag southbrook                # ~30s; uses OpenAI for embeddings
vercel deploy --prod                     # gets the prod URL
```

### Step 2. Tell Odoo where the sidecar lives

In Odoo, Settings → Technical → System Parameters:

| Key | Value |
|---|---|
| `southbrook_hermes.sidecar_url` | The Vercel deploy URL from step 1 |
| `southbrook_hermes.sidecar_enabled` | `true` |

### Step 3. Smoke test the full chain

```bash
./scripts/smoke_hermes.sh
```

Then in a browser: log in as a real portal user (e.g., the
`Demo Tradesperson (Tier 3)`), open an order, ask the chat panel a
question. Expect a streamed answer back within ~10s.

### Step 4. (Optional, durability) Rebuild the QNAP image

```bash
# On the QNAP host
ssh admin@ssh.southbrookcabinetry.space
cd /share/CACHEDEV3_DATA/Container/southbrook
./build_image.sh                          # builds southbrook-odoo:dev from services/odoo/Dockerfile
docker-compose up -d --force-recreate southbrook-odoo
```

This locks in PyJWT + markdown (currently installed ad-hoc via
`pip install --break-system-packages`). The Dockerfile fix landed in
commit `d633e74`.

---

## 5. The toggle states explained

`southbrook_hermes.sidecar_enabled` in `ir.config_parameter`:

| Value | Behavior |
|---|---|
| `false` (default) | `/hermes/v1/ask` returns a JSON stub; OWL panel renders the stub answer; no sidecar traffic. Safe to deploy any time. |
| `true` | `/hermes/v1/ask` mints a 120s JWT, POSTs to `sidecar_url + /api/hermes/ask`, streams the body back. Requires `sidecar_url` to point at a real, reachable sidecar. |

If you flip to `true` and the sidecar isn't there, every chat-panel
submit gets `502 sidecar_unreachable`. Flip back to `false` to restore
stub behavior.

---

## 6. Common troubleshooting

### `503 hermes_not_configured`

Either:
- **PyJWT not installed in the container** — `docker exec southbrook-odoo pip install --break-system-packages PyJWT`. Volatile until you rebuild the image.
- **JWT secret is the placeholder** — rotate via Settings → Technical → System Parameters; key `southbrook_hermes.jwt_secret`. The helper refuses to mint or verify with `PLACEHOLDER_ROTATE_BEFORE_PRODUCTION`.

### `403 partner_has_no_user` from tool dispatch

The partner is JWT-authenticated but has no linked `res.users` record.
For the smoke script: use a real portal partner ID (e.g., 352 — the
default). For production: investigate why the partner has no portal
invite accepted.

### `403 tier_required`

The persona's tier mask doesn't include the tool's required tier. Check
`tier_for_persona` in `addons/southbrook_hermes/utils/jwt_helper.py` —
all three personas should currently include `T2`.

### Deploy says "Modules loaded" but module is still `to upgrade`

This is the classic dep-cycle / cold-install gap. Check
`SELECT name, state FROM ir_module_module WHERE state != 'installed' AND name LIKE 'southbrook_%'`.
If you see a cluster of `to upgrade` modules, there's a circular
dependency. See `~/.claude/projects/-Users-naadmin/memory/hermes_v1_deploy.md`
for the 2026-06-16 incident (which was Fabio Ask's dep cycle).

### `/my/fabio` or `/my/<route>` returns 404 after a deploy

Usually a controller load error. Pull the cold-upgrade log:
```bash
ssh admin@ssh.southbrookcabinetry.space 'cat /tmp/deploy_upgrade.log' | grep -E 'ERROR|Traceback'
```
If a Python import error shows up, fix the import and redeploy. If the
log says `Modules have inconsistent states`, see the previous section.

### Forgejo `git.southbrookcabinetry.space` returns 307

That's correct — it's the Cloudflare Access login redirect. Browser GET
needs an authenticated session; git push uses HTTPS auth with stored
credentials and works directly. If you see 502 instead, the Cloudflare
tunnel → Caddy → Forgejo chain is broken (yesterday it was; today it's
healed).

---

## 7. JWT secret rotation

Generate + store + write:

```bash
SECRET=$(openssl rand -hex 32)
echo "$SECRET" > /tmp/hermes-jwt-secret.txt
chmod 600 /tmp/hermes-jwt-secret.txt

ssh admin@ssh.southbrookcabinetry.space "/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker exec southbrook-odoo bash -c \"echo 'env[\\\"ir.config_parameter\\\"].sudo().set_param(\\\"southbrook_hermes.jwt_secret\\\", \\\"$SECRET\\\"); env.cr.commit()' | odoo shell -d southbrook --no-http\""

# Restart so workers reload (config params are read fresh per call, but a
# restart is the easy safe thing).
ssh admin@ssh.southbrookcabinetry.space '/share/CACHEDEV3_DATA/.qpkg/container-station/bin/system-docker restart southbrook-odoo'

# If the sidecar is live, MIRROR the new value to Vercel:
cd .claude/worktrees/hermes-trade-partner-v1/sidecar
vercel env rm HERMES_JWT_SECRET production
vercel env add HERMES_JWT_SECRET production    # paste new value
vercel deploy --prod
```

The mirror MUST happen before/during the Odoo restart; otherwise minted
JWTs won't verify on the sidecar side until the values match.

---

## 7a. Recommendation types

The Fabio approval queue (`southbrook.hermes.recommendation`) supports
five `recommendation_type` values, each with a distinct apply behavior:

| Type | What apply creates | Source |
|---|---|---|
| `task` | `project.task` | Default; partner-requested intents from Hermes Chat |
| `risk` | (chatter post only) | Operational alerts |
| `note` | (chatter post only) | Free-form annotations |
| `followup` | (chatter post only) | "Remember to do X later" |
| `prospect` | `crm.lead` with mapped priority + tag + filtered website | Hermes Console `lead_prospector` agent loop (Gemini-grounded search) |

### Prospect apply behavior

When `recommendation_type='prospect'` is approved + applied, the
`_create_crm_lead` method maps the payload like so:

| Payload key | Lead field | Notes |
|---|---|---|
| `company` | `partner_name` | falls back to "Unknown company" |
| `city` | `city` | "Toronto, ON" → "Toronto" (province stripped) |
| `why_fit` | description (head) | 1-2 sentence rationale |
| `proposed_action` (rec) | description | "Proposed next step:" prefix |
| `source_url` | `website` AND description | ONLY set on `website` if not a `vertexaisearch.cloud.google.com` redirector |
| `contact_hint` | description | email/phone/form URL |
| `lead_type` | description + `tag_ids` | auto-creates `crm.tag` "Hermes: <lead_type>" if absent |
| priority (rec) | `priority` | low/normal/high/blocker → 0/1/2/3 |

The created `crm.lead` is linked back via the recommendation's
`created_crm_lead_id` field; the lead's chatter records the Hermes
provenance. Test coverage: `tests/test_prospect_recommendation.py`
(11 unit tests, tag `prospect`).

## 8. Adding a new tool

```python
# addons/southbrook_hermes/tools/read_tools.py (or write_tools.py)

@hermes_tool(
    personas=["trade_partner", "sales_rep"],
    tier="T0",
    scope="own_order",
    description="One-sentence description for the LLM.",
)
def your_new_tool(env, arg1: int, arg2: str = None):
    # env is already scoped to env(user=portal_user) by the dispatch
    # controller; record rules apply. If you need cross-user reads, use
    # .sudo() with a documented reason (spec § 4.4).
    return {"key": "value"}
```

Then add to the smoke test in `scripts/smoke_hermes.sh` so future
deploys catch breakage. Deploy. Run the smoke. Done.

---

## 9. Where things live

| Concept | Path |
|---|---|
| OS canonical content | `addons/southbrook_os/canonical/*.md` |
| OS generators (mirror Odoo state to MD) | `addons/southbrook_os/models/os_generators.py` |
| OS RAG export | `addons/southbrook_os/exports/rag_corpus_export.py` |
| OS public endpoint | `/southbrook/os.json` (controller in `controllers/os_public.py`) |
| Hermes tools | `addons/southbrook_hermes/tools/{read_tools,write_tools}.py` |
| Hermes JWT helper | `addons/southbrook_hermes/utils/jwt_helper.py` |
| Hermes proxy / browser entry | `addons/southbrook_hermes/controllers/hermes_proxy.py` |
| Hermes tools API | `addons/southbrook_hermes/controllers/hermes_tools_api.py` |
| Hermes conversation log | `addons/southbrook_hermes/controllers/hermes_conversation_api.py` |
| OWL chat panel | `addons/southbrook_hermes/static/src/components/hermes_chat/` |
| Order Builder injection | `addons/southbrook_hermes/views/order_builder_chat_inject.xml` |
| Vercel sidecar code | `sidecar/` (in this repo; can be extracted later) |
| Image Dockerfile | `services/odoo/Dockerfile` (PyJWT + markdown pinned) |
| Deploy script | `scripts/deploy_to_qnap.sh` |
| Smoke test | `scripts/smoke_hermes.sh` |
| JWT secret backup | `/tmp/hermes-jwt-secret.txt` (mode 600, lost on reboot — save to password manager) |
