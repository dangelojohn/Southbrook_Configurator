# Code Review & Repair Report — `southbrook_hermes_bom`

**Module:** Southbrook Hermes Product Research & BOM Builder · **Version:** 19.0.2.3.0 → **19.0.2.4.0**
**Reviewed:** 2026-07-10 · **Odoo target:** v19 CE · **Queue:** #10 of 46 (Tier 1; deps incl. `product_configurator_mrp`, `mrp`)
**Method:** combined audit agent (v19/security/perf) + independent verification + live install/test on Odoo 19 CE.

## Executive Summary
Southbrook-owned AI-assisted product-research + BOM-builder: a wizard calls an external "Hermes" AI service, then builds `mrp.bom` from the result. **A well-built, well-hardened module** — clean on every v19 axis, complete ACLs, and the external-service layer is genuinely security-conscious (per-call key/endpoint from `ir.config_parameter`, request timeout, `raise_for_status`, response-shape validation, key never logged, admin-set endpoint = no SSRF on the main call). The duplicate-prevention uses a correct `pg_advisory_xact_lock` + post-lock TOCTOU re-check with dedicated tests. **Baseline: 26 tests green.**

The one serious gap the well-guarded main path didn't cover: a **CRITICAL SSRF** in the *attachment* fetch of AI-supplied `source_urls`, plus a response-validation robustness gap.

## Original Issues Found
| # | Sev | Finding |
|---|-----|---------|
| S1 | **CRITICAL** | SSRF: `_attach_documents` fetches Hermes-supplied `source_urls` with only a scheme check — no private/loopback/metadata-IP blocking, default redirects. A prompt-injected/compromised Hermes response could point at `169.254.169.254`/localhost/internal services → the Odoo server fetches and stores the body as an attachment (exfiltration). |
| R1 | HIGH | `_validate_response` only checked top-level keys, not nested types; `_populate_from_response` runs OUTSIDE the wizard try/except → a malformed response (`"product_enrichment": "oops"`) raises `AttributeError`, rolls back the state write, and leaves the audit job stuck at `state='running'` (the exact failure `_mark_error` was built to prevent). Same missing `isinstance` in `_apply_bom`. |
| W1 | HIGH | Synchronous worker-blocking: research (120s) + up to 10×30s attachment fetches = ~7 min of worker time per wizard run; in CE's finite-worker model, a few concurrent dispatches can cause site-wide 502s. |
| T1 | MED | No throttling/cost control on the paid external AI call (any `group_hermes_user` can trigger repeatedly). |
| I1 | LOW | No indexes on `hermes.research.job` (`product_template_id`/`state`) — applied jobs retained forever (unbounded table). |
| N1 | LOW | N+1 component `search()` in `_apply_bom` (bounded to 50). |

### Clean (verified): all v19 axes; ACL completeness; the external-service key/endpoint/timeout/secret handling; the advisory-lock + TOCTOU re-check design (well-tested); no `eval`/`safe_eval`; one parameterized `cr.execute`; the 16 `sudo()` calls all write hardcoded audit/state fields or read admin-only config (no user-controlled escalation).

## Repairs Completed
1. **S1 (CRITICAL):** added `_is_safe_public_url()` (resolves the host and rejects non-global/reserved/multicast IPs — cloud-metadata, loopback, RFC1918, link-local) + wired it into the fetch loop, and set `allow_redirects=False` (so a public URL can't 3xx-bounce to an internal host). New regression test.
2. **R1 (HIGH):** `_validate_response` now type-checks the nested sections (each required section is a dict; `bom.lines` is a list) — so a malformed response raises a clean `UserError` *inside* `research()` (which the caller guards → `_mark_error` runs) instead of crashing later. Added `isinstance(bom_payload, dict)` and per-line `isinstance(line, dict)` guards in `_apply_bom` (covers the reviewer-editable `proposed_bom_json` path).
3. **I1 (LOW):** `index=True` on `product_template_id` and `state`.

### Deliberately NOT changed (documented)
- **W1 (HIGH — worker-blocking):** the real fix is moving the research + attachment fetches off the request thread (ir.cron/queued dispatch with the wizard polling `state`) — a design change; documented. The SSRF fix removes the *internal-host* attack; the remaining blocking-on-slow-public-URLs is a DoS budget item.
- **T1 throttling** (rate-limit/cost cap on the paid API) and **N1** (batch the ≤50-line component search) — documented.

## Files Changed
3 modified (`__manifest__.py`, `models/hermes_wizard.py`, `models/hermes_research_job.py`, `services/hermes_service.py`), 1 new test.

## Security Improvements
Closed the SSRF-to-attachment exfiltration path (private-host blocking + no redirects). Hardened response validation so a hostile/malformed AI response can't wedge the audit job or crash the apply path.

## Performance Improvements
2 indexes on the unbounded-retention job table.

## Testing Results
_See `TEST_RESULTS.md`._ Baseline 26/26 green; after fixes the suite stays green plus the new SSRF-guard test; indexes confirmed in the DB.

## Remaining Risks
1. **W1 worker-blocking** (async dispatch) and **T1 throttling** are documented design follow-ups.
2. DNS-rebinding is a theoretical residual of any resolve-then-fetch guard; `allow_redirects=False` + the resolved-IP check cover the practical cases.

## Recommendations
Deploy S1+R1 promptly (SSRF + audit-job robustness). Schedule the async dispatch (W1) and rate-limiting (T1) as follow-ups.
