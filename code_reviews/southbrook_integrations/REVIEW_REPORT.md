# Code Review — `southbrook_integrations`

**Module #41 of 46 · Odoo 19.0 CE**
**Version:** 19.0.1.0.0 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security+controller; v19+data/install) →
independent source verification incl. reading the MCP controller + the
`southbrook_api` login route it trusts → HEAD baseline → real fixes + regression
tests → live `-i`+`-u`+tests + seed/tile probe on isolated DB (`ci_int41`, full
api/quality/payroll/finance/MI/kitchen dep stack staged).

## What the module does
Integration scaffolds: an **MCP-into-Odoo API** (`POST /integrations/mcp/v1/invoke`)
that runs manager-registered **read-only** tools (`search`+`read` on a curated
model/domain/field-list); a **Homag CNC simulator**; a **3PL ASN**; and **IoT label
printers** (no-op in v1). Plus an MI-dashboard `mi_tiles` snapshot.

## Verdict
The MCP executor is **well-designed in the dimension the brief feared** — **no
arbitrary-method dispatch, no eval/exec/SQL**, write-category blocked, fields
allow-listed, token stored hashed + compared by indexed hash (timing-safe). But it
was **read under `.sudo()` while reachable by any API key**, and the `southbrook_api`
login route issues keys to **portal customers** — a **CRITICAL** unprivileged
read-anything of payroll/finance/NCR. Also the **headline feature shipped empty**
(the seed-tools file was never loaded). Fixed **1 CRITICAL + 1 HIGH func + 1 HIGH
priv-esc + 3 MED + the F3 tile + the baseline test**. Baseline **1 error of 11 → 0
of 15** (+2 security regression tests).

## Findings

### Fixed — security (the MCP surface)
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **C1** | **CRITICAL** | **Portal customer → API key → sudo-read all payroll/finance/NCR.** `invoke()` read via `env[model].sudo()` (bypassing ACL/record-rules/company), and the endpoint accepted **any** valid `southbrook.api.key`; `southbrook_api`'s public login issues a key to **any** user that can log in — **including portal customers**. So a customer POSTs `{email,password}`→key, then `{"tool_name":"list_payroll_runs"}`→ every employee's gross/net wages. `update_env(user=...)` was decorative under sudo. | **Dropped the `.sudo()`** (reads now run as the invoking principal — ACL/record-rules/company apply) **and** rejected **non-internal** users at the auth boundary (`user._is_internal()` → 403). |
| **H1** | **HIGH** | **Integrations Manager → sudo-read system secrets → admin escalation.** A manager (mid-level ops) could register a tool on `ir.config_parameter` (`read_fields=["key","value"]`) and invoke it — under sudo, dumping `database.secret` / `southbrook_hermes.jwt_secret` / all `southbrook.api.key` hashes → forge sessions. | Dropping sudo (C1) already bounds a manager to what they can read; **plus** an explicit `_BLOCKED_MODELS` `@api.constrains` (config_parameter, mail_server, res.users, api-keys, ir.model.data) so even an admin-key can't expose secrets over the wire. |
| **M1** | MED | **Caller-controlled `extra_domain` = sudo domain-injection / boolean oracle.** The request body's `extra_domain` was concatenated onto the curated domain and run under sudo — a blind oracle to exfiltrate non-whitelisted fields / reshape query semantics. | Removed `extra_domain` entirely — the tool's `domain_json` is the only scope; no wire-supplied domain is accepted. |
| **M2** | MED | **No `limit` cap + advisory-only rate limit → DoS/cost.** `limit=int(args["limit"])` unbounded; the per-minute window was computed but never enforced. | Clamp `limit` to `[1,500]`, `offset ≥ 0`; the controller now returns **429** when the tool's per-minute budget is exceeded. |
| **M3** | MED | **Audit log recorded no principal.** `mcp_call_log` had no `user_id`/key reference → a call couldn't be attributed to a key/user after an incident. | Added `user_id` (the authenticated principal) to the log + set it on every create; controller stashes the key hash. |

### Fixed — functional / correctness
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **F-DATA** | **HIGH** | **The headline MCP feature shipped empty** — `data/mcp_tools.xml` was **omitted from the manifest**, so the 4 seed tools were never created and `/invoke` returned 404 for every documented tool. The 3 heavy deps (quality/payroll/finance) whose sole purpose was resolving those refs were dead weight. | Added `data/mcp_tools.xml` to the manifest (verified all 4 models + fields exist). Now 4 tools seed. |
| **TILE** | LOW | **mi_tiles F3 dead feature** — `perm_create=0` for **both** groups + no seed → the Integrations Snapshot never rendered. | Granted manager create/unlink + seeded one `noupdate` singleton. |
| **TEST** | — | **Baseline error** — `stock.move.name` removed in v19; `test_asn_3pl` setUpClass built a move with `{"name": …}` → `KeyError`, blocking the whole class. | Dropped `"name"` from the move dicts. |

### Documented (cross-module / minor — not changed here)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| L1 | LOW | `southbrook.api.key.verify()` doesn't check `user_id.active` — a deactivated employee's non-expired key still authenticates. | Lives in **southbrook_api** (module #28); the new internal-user gate partially mitigates. Add an `active` check there. |
| L2 | LOW | MCP endpoint sends `Access-Control-Allow-Origin: *`. | Custom-header auth (not cookies) so not CSRF, but consider an origin allowlist. |
| L3 | LOW | IoT ZPL `_resolve` uses `getattr` on placeholders → `{env}`/`{pool}` leak object `repr()` into a label (no code exec; manager-only templates). | Restrict `_resolve` to `record._fields`. |

## Strong positives (verified)
- **No arbitrary-method dispatch** — `invoke()` is a scoped `search()+read()` only; no `getattr(model, method)`. Write category hard-blocked; disabled tools raise. **No eval/exec/compile/safe_eval/cr.execute** anywhere.
- Token stored hashed (SHA-256), verified by **indexed hash equality** (timing-safe); keys never stored cleartext.
- **Homag simulator** doesn't eval/exec/shell/write-files (pure JSON + seeded random + ACL'd ORM). **IoT print is a no-op** — the SSRF surface the brief feared isn't present in v1.
- **v19-clean** (v19 agent): controller uses `type="http"` (not the `type="json"` trap), correct `request.make_response`/`update_env`; registry-safe; `models.Constraint`; `@api.model_create_multi`; AbstractModel-inherit trap avoided; no `res.groups.users`.

## Validation
- `-i` (fresh DB, full api/quality/payroll/finance/MI/kitchen dep stack) — **clean**, registry ~66 s.
- `-u` — clean (2.2 s).
- Tests `--test-tags=/southbrook_integrations` — **15/15 pass / 0 error**, from a
  baseline of 1 error of 11 (+2 regression: sensitive-model blocklist,
  principal-logging). See `TEST_RESULTS.md`.
- **Seed probe**: 4 MCP tools created (was 0); `mi_tiles_default` materialized.
