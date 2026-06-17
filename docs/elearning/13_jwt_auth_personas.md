---
course: 13 — Fabio Deep Dive
chapter: 13.3
title: JWT Auth and Persona Resolution
duration: 30 minutes
audience: Developer touching `utils/jwt_helper.py` or any Hermes controller; IT admin responsible for the JWT secret + system parameters
prereqs: Lesson 13.1 (`13_fabio_architecture.md`) for the four-pillar picture; lesson 3.2 for the queue side; spec § 4 (persona model, ACL, tiers) at `docs/superpowers/specs/2026-06-16-southbrook-os-and-hermes-platform-design.md`; CLAUDE.md amendment 2026-06-16 (system-parameter setup)
custom_modules: southbrook_hermes
---

# JWT Auth and Persona Resolution

## Who this lesson is for

You're the developer about to touch `utils/jwt_helper.py`, an Odoo
controller that mints or verifies a JWT, or a new tool that needs to know
who's calling. Or you're the IT admin responsible for rotating the
secret, watching for misconfigurations, and making sure the right partners
land on the right persona.

The JWT layer is small (88 lines of Python) but load-bearing — every
Fabio call sits inside one. Get it wrong and the whole ACL model falls
through.

## Where this lives on the site

> **Settings → Technical → System Parameters** — search for
> `southbrook_hermes.jwt_secret`. This is the HS256 signing secret. The
> placeholder shipped by the addon is the literal string
> `PLACEHOLDER_ROTATE_BEFORE_PRODUCTION` (see `data/ir_config_parameter.xml`);
> the helper actively refuses to mint or verify against the placeholder
> (raises `RuntimeError`).

> **Settings → Users → [user] → Other** — `Share User` (the
> `res.users.share` field) decides whether `resolve_persona` returns
> `trade_partner`. Trade partners are portal users; share=True.

> **Settings → Users → [user] → Sales** — `Salesperson` membership
> (`sales_team.group_sale_salesman`) drives the `sales_rep` persona.

> **Settings → Users → [user] → Kitchen Ops** —
> `southbrook_kitchen_workspace.group_kitchen_ops` drives the
> `mfg_manager` persona.

## What your screen shows

You don't see a screen for the JWT layer most of the time — JWTs live
inside HTTP headers and a system parameter. What you see is the
consequences in three places.

### The system parameter triad

Three rows under **Settings → Technical → System Parameters** define the
auth surface:

| Key | Default at install | What it controls |
|---|---|---|
| `southbrook_hermes.jwt_secret` | `PLACEHOLDER_ROTATE_BEFORE_PRODUCTION` | HS256 signing secret. Must be rotated before any live traffic. |
| `southbrook_hermes.sidecar_url` | `https://hermes.southbrookcabinetry.space` | Where `/hermes/v1/ask` sends the LLM request. |
| `southbrook_hermes.sidecar_enabled` | `false` | Whether the proxy actually calls the sidecar (vs. returning a JSON stub). |

The shipped placeholder value (`PLACEHOLDER_ROTATE_BEFORE_PRODUCTION`)
is recognized by `_get_secret(env)` in `utils/jwt_helper.py` as a
sentinel:

```python
def _get_secret(env):
    secret = env["ir.config_parameter"].sudo().get_param(
        "southbrook_hermes.jwt_secret")
    if not secret or secret == "PLACEHOLDER_ROTATE_BEFORE_PRODUCTION":
        raise RuntimeError(
            "southbrook_hermes.jwt_secret is not set. Rotate the placeholder "
            "via Settings → Technical → System Parameters before going live.")
    return secret
```

Any controller that tries to mint or verify a JWT before the rotation
will get a `RuntimeError`, surface it as a `503 hermes_not_configured`
response (see `controllers/hermes_proxy.py` exception handling), and the
chat panel will render a clear admin-targeted error. The placeholder
exists so the addon installs cleanly without leaking a real secret in
version control; it stops short of letting you actually use it.

### The persona resolution function

In `utils/jwt_helper.py`:

```python
def resolve_persona(user):
    if user.share:
        return "trade_partner"                       # v1.0
    if user.has_group("sales_team.group_sale_salesman"):
        return "sales_rep"                           # v1.1
    if user.has_group("southbrook_kitchen_workspace.group_kitchen_ops"):
        return "mfg_manager"                         # v1.2
    raise AccessError("Hermes is not available for this user role.")
```

Three buckets, evaluated in order. The first hit wins. If a user is
both a share user (portal) and in the salesman group (unusual but
possible), they resolve to `trade_partner` because `share` is checked
first. If a user matches none, the proxy returns 403 to the chat panel.

### The tier mask

```python
def tier_for_persona(persona):
    return {
        "trade_partner": "T0+T1+T2",
        "sales_rep": "T0+T1+T2",
        "mfg_manager": "T0+T1+T2",
    }.get(persona, "T0")
```

All three personas get the full T0+T1+T2 mask. This is intentional, per
implementation delta § 14.1: the trade-partner safety boundary used to be
"trade partners cannot call T2 tools at all," which is a clean idea right
up until you ship `propose_recommendation` (which is T2 and which trade
partners absolutely must be able to call to file a revision request). The
fix was to leave the mask wide open and move the trade-partner intent
allow-list *inside* `propose_recommendation` itself
(`_TRADE_PARTNER_INTENTS = ("request_revision",
"request_install_reschedule", "request_clarification")` in
`tools/write_tools.py`). Net behavior matches the spec's intent; the
enforcement layer moved.

### The JWT payload shape

`mint_jwt` (lines 29–48 of `utils/jwt_helper.py`):

```python
payload = {
    "iat": int(now.timestamp()),
    "exp": int((now + datetime.timedelta(seconds=ttl_seconds)).timestamp()),
    "tenant": tenant,
    "persona": persona,
    "partner_id": partner_id,
    "tier": tier,
}
if extra:
    payload.update(extra)
```

Four required claims:
- **`tenant`** — `"southbrook"` in v1.0. v1.x plans to scale to
  Porterly/Tribancs/etc. so the sidecar can route per tenant.
- **`persona`** — one of `trade_partner / sales_rep / mfg_manager`.
- **`partner_id`** — the requesting user's `partner_id.id`. Used by
  dispatch to look up the right portal user for record-rule scoping.
- **`tier`** — the tier mask. Always `T0+T1+T2` in v1.0.

Plus two standard JWT claims (`iat`, `exp`), and an optional `extra`
dict (the proxy passes `{"order_id": body.get("order_id")}` so tools can
optionally restrict to a specific order context).

### JWT lifetime

`DEFAULT_TTL_SECONDS = 60` at the top of the module. But the proxy
overrides this to 120s for the `/hermes/v1/ask` call:
`_JWT_TTL_FOR_ASK = 120` in `controllers/hermes_proxy.py`. The reason is
in implementation delta § 14.7 — a 60s token expired mid-loop on a
multi-step agent run (4–5 tool roundtrips), tool dispatch returned 401,
and the LLM saw a confusing "tool failed" result rather than the actual
data. 120s gives headroom for the whole loop while staying well under
Vercel's 60s function cap × multi-loop budget.

The token is still per-request, not per-conversation — every new
`/hermes/v1/ask` call mints a fresh JWT. If the user's Odoo session
expires between turns, the next turn fails cleanly at issuance.

### Claim-bound args (the dispatch-time enforcement)

In `controllers/hermes_tools_api.py`:

```python
_CLAIM_BOUND_ARGS = ("persona", "partner_id", "tenant")

# ... inside dispatch():
sig_params = inspect.signature(fn).parameters
for arg_name in _CLAIM_BOUND_ARGS:
    if arg_name in sig_params:
        if arg_name == "persona":
            args["persona"] = claims["persona"]
        elif arg_name == "partner_id":
            args["partner_id"] = claims["partner_id"]
        elif arg_name == "tenant":
            args["tenant"] = claims["tenant"]
```

Three tool args (`persona`, `partner_id`, `tenant`) are
**authoritatively set from JWT claims** before the tool runs, overriding
anything in the request body. The LLM (or a prompt-injection attack)
**cannot** spoof its persona to lift the trade-partner intent guard, and
**cannot** attribute a recommendation to another partner. This was the
fix in implementation delta § 14.2 — without it, the first
implementation accepted `persona` and `partner_id` as ordinary tool args.

Tools that don't declare those args (most tools don't) are unaffected.
The dispatch inspects the function signature with `inspect.signature(fn).parameters`
and only injects when the arg is actually declared.

## Your daily flow

This section is split by the role you're playing.

### As the developer wiring a new tool

1. Decide your persona allowlist. Trade-partner-callable? Sales-rep-only?
   Sysadmin-only?
2. Decide your tier honestly. T0 = read or low-stakes write (chatter
   note, log). T1 = communication (email, activity). T2 = business
   mutation (proposes via recommendation).
3. Declare your tool signature with `partner_id` if the tool's behavior
   is scoped to the calling partner. This will be auto-injected from
   the JWT and is the safe way to scope.
4. Inside the tool, read partner from `env.user.partner_id`, NOT from
   the function arg. `partner_id` arg is "informational only" (delta
   § 14.4 — `list_my_kitchen_projects` and `list_my_recommendations`
   were rewritten to ignore the arg specifically for this reason). The
   dispatch sets `env(user=portal_user)` from the JWT, so
   `env.user.partner_id` is always the verified caller.
5. Add `check_access_rights("read")` AND `check_access_rule("read")`
   inside the tool for record-rule scope. Delta § 14.5 added these to
   three read tools that missed them; the pattern is now uniform.
6. Test with `scripts/smoke_hermes.sh` — it mints a fresh JWT and
   exercises every route.

### As the IT admin operating Fabio

**Rotate the JWT secret.**

1. Open **Settings → Technical → System Parameters**.
2. Search `southbrook_hermes.jwt_secret`. Edit the value to a fresh
   high-entropy string. The placeholder check is exact (`==` against
   `PLACEHOLDER_ROTATE_BEFORE_PRODUCTION`); any other non-empty value
   is accepted.
3. Update the sidecar's `HERMES_JWT_SECRET` env var to match (Vercel
   dashboard → Environment Variables, or `vercel env add` from CLI).
4. Redeploy the sidecar: `vercel deploy --prod`.

Rotation is currently atomic — there's no JWKS endpoint and no overlap
period. If you rotate in Odoo before the sidecar picks it up, every
in-flight chat will 401 with `invalid_token` for the gap window
(typically seconds). The spec § 12 open question 3 calls this out: "v1.0
ships with a static `HERMES_JWT_SECRET` env var; if you want rotation
from day one, we add JWKS endpoint complexity." That complexity wasn't
shipped in v1.0.

**Suggested rotation policy.**

Quarterly, or immediately on suspicion of leak. The secret never leaves
two places: the Odoo system parameter (sudo-only via the
`ir.config_parameter` ACL) and the Vercel env var (env-scoped). It is
NOT in version control — `data/ir_config_parameter.xml` ships the
placeholder, not a real secret.

**Audit who has access to the secret.**

The system parameter is readable only by users in the
`base.group_system` group (Odoo's standard ACL on `ir.config_parameter`).
Trade partners cannot read it. Reviewers (group_hermes_reviewer) do not
inherit `group_system` — only the other direction (`group_system`
inherits `group_hermes_reviewer`).

### As the developer reading a request log

A typical good-state log line for `/api/hermes/tools/get_order_status`:

```
... POST /api/hermes/tools/get_order_status HTTP/1.1 200 ...
... [DEBUG] JWT verified: tenant=southbrook persona=trade_partner
                          partner_id=42 tier=T0+T1+T2
... [DEBUG] Tool get_order_status called for partner 42, order 235
```

A bad-state log line means one of the error envelopes from delta § 14.11:

| Code | When |
|---|---|
| `missing_bearer_token` (401) | Authorization header missing |
| `invalid_token` (401) | JWT signature wrong or expired |
| `hermes_not_configured` (503) | Secret not set or PyJWT missing |
| `unknown_partner` (403) | `partner_id` claim points at a deleted partner |
| `partner_has_no_user` (403) | Partner has no linked `res.users` |
| `not_allowed_for_persona` (403) | Tool's persona allowlist doesn't include claim |
| `tier_required` (403) | Tool's tier not in claim's tier mask |

## Common mistakes + how to recover

**"The chat panel is returning 503 with `hermes_not_configured`."**

You're hitting one of two RuntimeErrors:
- `southbrook_hermes.jwt_secret` is still the placeholder. Fix: rotate
  it (see admin flow above).
- `PyJWT` (`import jwt`) is not installed in the container. Fix:
  `docker exec southbrook-odoo pip install PyJWT --break-system-packages`
  (the temporary install, per CLAUDE.md amendment), OR bake into the
  Docker image. The dependency is documented in the manifest comments
  but deliberately not gated on install — the helper raises a clear
  RuntimeError when missing, which surfaces as the 503.

**"A trade partner is getting 403 `forbidden` on every chat turn."**

`resolve_persona` returned `AccessError`. Three causes:
- The user is internal but matches none of the persona buckets. They're
  not a share user, not a salesman, not in `group_kitchen_ops`. Fix:
  add them to one of those groups, OR (if they're an admin who just
  wants to test) add them to the kitchen ops group.
- The user IS a share user but somehow got into the chat panel without
  share=True (very rare). Fix: verify the user record.

**"The sidecar is rejecting tokens with `invalid_token`."**

Three causes:
- Secret mismatch between Odoo's system parameter and Vercel's
  `HERMES_JWT_SECRET` env var. Fix: re-sync, redeploy sidecar.
- Clock skew. The `exp` claim is in seconds; if the sidecar's clock
  drifts past `exp`, it'll reject as expired. Fix: NTP on both
  hosts.
- The sidecar's `HERMES_JWT_SECRET` env var is empty / missing —
  delta § 14.9. Sidecar should respond 503 `jwt_config` (not 401
  `invalid_token`) in this case — if you see 401 instead, your
  sidecar is on a pre-delta build, redeploy.

**"A new tool I added is accepting a `persona` arg from the LLM and
running with it."**

The dispatch's claim-binding (delta § 14.2) inspects the function
signature: it only overrides `persona` / `partner_id` / `tenant` if those
args are *declared on the tool function*. If you declared a `persona` arg,
dispatch overrides it. If you didn't, no override happens and the LLM
can pass anything — but the tool can't *use* it anyway because no claim
was bound. The takeaway: declare those args explicitly when you need
them; never read persona/partner_id from anywhere else.

**"`schedule_followup_activity` raised `AccessError` even though the
partner can see the order."**

Almost certainly because the partner has no linked `res.users` record.
Dispatch returns 403 `partner_has_no_user` in that case (delta § 14.3).
Fix: open the partner record, invite as portal user from the partner
form. The auto-generated portal user gets linked to `res.partner.user_ids`
and dispatch resolves cleanly.

## What the system is doing behind the scenes

### Why HS256 (symmetric), not RS256 (asymmetric)

v1.0 has one signer (the Odoo proxy) and one verifier (the sidecar). A
shared secret is sufficient. RS256 would let *multiple* signers verify
against a public key, which is the right pattern for a JWKS endpoint with
rotation overlap — and that's deferred to v1.x (spec § 12 q3). HS256 is
the simpler thing that works for v1.

The algorithm is locked in two places in `jwt_helper.py`:
`JWT_ALGORITHM = "HS256"` at module scope, and `algorithms=[JWT_ALGORITHM]`
in the `verify_jwt` call. A token signed with any other algorithm
(including the dangerous `none`) is rejected by PyJWT.

### Why persona is server-side, not client-side

`resolve_persona(user)` reads `user.share` and `user.has_group(...)` —
both of which are sourced from the Odoo database via the authenticated
session. The client (browser) cannot influence these. The persona is
locked into the JWT at mint time, and the sidecar trusts the JWT, not
anything else from the wire. This is the spec § 3 invariant: "the sidecar
never holds business state; the JWT carries the identity."

### Why dispatch re-resolves the user from `partner_id`

`POST /api/hermes/tools/<slug>` runs as `auth='public'` — it has no
session. Dispatch verifies the JWT, then:

```python
partner = request.env["res.partner"].sudo().browse(claims["partner_id"])
if not partner.exists():
    return 403 unknown_partner
user = partner.user_ids[:1]
if not user:
    return 403 partner_has_no_user
env_with_user = request.env(user=user.id)
```

This is what makes record rules apply. If dispatch ran the tool as the
public user (the default for `auth='public'`), every tool would run with
the least-privileged identity, returning empty results and silently
hiding everything the partner owns. Delta § 14.3 was added because the
original implementation fell back to `request.env.user` (public) when
the partner had no user — a misconfiguration that should be loud became
silent.

### Why the `extra` dict pattern

`extra` is the open-ended JWT extension hook. The proxy uses it for
`{"order_id": body.get("order_id")}` so tools can optionally see what
order the chat panel was open against. The claim isn't required (the
trade-partner chat panel might be open without an order context — e.g.
from a general portal page), but when present it lets the LLM scope its
RAG queries and tool calls more tightly. Tools that want this read
`claims.get("order_id")` — but in v1.0 no tool actually reads it
from claims; the order id comes through the request body. Reserved for
future use.

### Why the placeholder is a literal string

`PLACEHOLDER_ROTATE_BEFORE_PRODUCTION` is the *exact* string the helper
compares against. Two reasons:
- The addon installs cleanly without a manual env-var step. Trade
  partners can't access `Settings → Technical`, so a missing secret
  doesn't break their UI before it's wired up.
- The string is loud and impossible to mistake for a real secret. A
  developer who greps for it in the codebase finds the rotation TODO
  immediately. A leaked logs grep for the value matches the literal
  string, not a hashed/encoded artifact.

The cost is one extra branch (`if not secret or secret ==
"PLACEHOLDER_…"`). The benefit is a foolproof default.

## Quiz (5 questions, applied)

**1.** Trade-partner Fred chats Fabio. The LLM emits a tool call with
`persona="mfg_manager"` and `partner_id=99` in the args. What happens at
dispatch?

> Both args are overridden from the JWT claims (delta § 14.2). Dispatch
> inspects the tool function signature — if `persona` and `partner_id`
> are declared, they get set to `"trade_partner"` and Fred's partner id
> from the verified JWT, regardless of what the LLM sent. If they're
> not declared, no override happens but the tool can't use the LLM's
> values anyway because the args wouldn't be bound. The persona
> escalation attempt is silently neutralized.

**2.** You rotate the JWT secret in Odoo but haven't redeployed the
sidecar yet. What's the user-facing symptom?

> Every in-flight chat returns a sidecar error to the panel. From
> Odoo's perspective, mint succeeds. The sidecar's `verifyJwt` fails
> because its `HERMES_JWT_SECRET` env var still has the old value. The
> sidecar responds 401 `invalid_token`; the proxy passes that through
> to the panel which renders "(Hermes is unavailable: invalid_token)".
> Fix: update the Vercel env var, `vercel deploy --prod`. Time gap is
> typically seconds during which chat is down.

**3.** A new internal user is created with `share=False`, no salesman
group, no kitchen_ops group. They open the Order Builder. What
happens when they try to chat?

> `resolve_persona` raises `AccessError("Hermes is not available for
> this user role.")`. The proxy returns 403 with `{error: "forbidden",
> detail: "Hermes is not available…"}`. The chat panel renders
> `(Hermes is unavailable: Hermes is not available for this user role.)`.
> Fix: add the user to one of the three persona-deciding groups
> (probably `southbrook_kitchen_workspace.group_kitchen_ops` for an
> internal user).

**4.** The JWT TTL is 60s in `DEFAULT_TTL_SECONDS` but 120s in
`_JWT_TTL_FOR_ASK`. Which one is actually used by a chat turn, and
why the discrepancy?

> 120s. `controllers/hermes_proxy.py` passes `ttl_seconds=_JWT_TTL_FOR_ASK`
> to `mint_jwt`, overriding the helper's default. The discrepancy is
> the implementation delta § 14.7 — a 60s token expired mid-loop on a
> multi-step agent run. 60s remains the helper default for callers
> that don't need the wider window; the proxy explicitly bumps to 120
> because the LLM may do 4–5 tool roundtrips per turn.

**5.** A developer wants to add a new persona `installer` for the
field-install team. Where do they edit it, and where does the addition
fail open?

> Edit `utils/jwt_helper.py` — add a fourth branch in
> `resolve_persona(user)` (decide what group implies installer), and
> a key in `tier_for_persona` (decide what tier mask). They must ALSO
> update every `@hermes_tool` decorator's `personas` list to include
> `"installer"` everywhere appropriate — otherwise existing tools will
> reject installers as `not_allowed_for_persona`. The mask change
> alone doesn't enroll the persona; the tool registry filtering is
> the second check.

---

## What this lesson does NOT cover

- The recommendation queue itself — lesson 13.2.
- The tool registry mechanics, `@hermes_tool`, and dispatch internals
  beyond the JWT layer — lesson 13.4.
- The 9 read tools' record-rule scoping in detail — lesson 13.5.
- The T0/T1/T2 tier model and the `propose_recommendation` intent
  allow-list — lesson 13.6.
- The chat panel + sidecar (the consumers of these JWTs) — lesson 13.7.
- The sidecar's JWT verification path (TypeScript in `sidecar/lib/jwt.ts`,
  not Python) — lesson 13.7 references it.
- General Odoo session / cookie auth, which is separate from the
  Hermes JWT layer.
