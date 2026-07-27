# Code Review — `southbrook_agent_gateway` (Module #24, Tier 4)

**Version:** 19.0.1.0.0 → **19.0.1.1.0**
**Reviewed:** 2026-07-11
**Scope:** ~1669 LOC — a PUBLIC AI-agent API gateway. `controllers/main.py` exposes public routes (/llms.txt, /openapi.json, /offerings GET; /quote-request, /quote POST csrf=False; /status GET; /agent/verify/<token>) that capture quote requests → `southbrook.agent.inquiry` (+ crm lead / sale order) via a double-opt-in email-verify flow. Depends: southbrook_estimating, sale, website, crm, utm, mail, phone_validation.
**Method:** Two parallel audits (v19; security+perf) + live install/upgrade/test validation.

## Executive Summary
A **well-hardened public endpoint** on the input side (audits + validation confirm): cryptographically-strong `secrets.token_urlsafe(32/24)` tokens with `hmac.compare_digest` compares, `email_normalize` (no header injection), phone E.164, control-char strip + length caps, cleaned-payload create (no mass-assignment), server-side pricing (no client price), no XSS, IDOR closed (status gated by a secret token, no reference enumeration), PII ACL scoped to sales, per-IP rate limiting, honeypot. The "treats all input as hostile" docstring claim is verified. v19-CLEAN install.

But two real issues: **a pre-existing HIGH bug that 500'd the endpoint for every new customer** (caught only by live validation — both agents missed it), and a **CRITICAL anti-abuse gap** (the verify email is an open reflected-phishing/email-bomb relay). Fixed the HIGH bug + a self-contained C1 mitigation; documented the deeper anti-abuse hardening (owner/infra). Install + upgrade clean; **35/35 tests green** (from 2 failed / 8 errors).

## Fixed
| # | Sev | Title | Fix |
|---|-----|-------|-----|
| B1 | HIGH (pre-existing, functional) | `_find_or_create_partner` create-new-partner branch (`:375`) returned a **bare recordset** while the contract + the existing-partner branch return `(partner, is_new)`. `submit()` unpacks two values → `ValueError: not enough values to unpack` for EVERY new customer (the common case) → the public `/quote-request` + `/quote` endpoints returned **HTTP 500 for any new email**. The module's core function was broken. **Caught by live validation; both audit agents missed it (runtime logic, not v19/security).** | return `new_partner, True` |
| C1 | CRITICAL (abuse) → mitigated | The public POST sends a Southbrook-branded verify email to a caller-chosen address (reflected-phishing amplifier + email-bomb of one victim + sender-reputation damage), throttled only by a spoofable per-worker IP limiter | added a `_gateway_verify_email_allowed` guard: a global daily send ceiling (`max_daily_verify_emails`, default 200; **0 = instant kill-switch**) + a per-recipient cooldown (`verify_email_cooldown_hours`, default 24 — no re-email to the same address in the window). Bounds the blast radius + gives ops an off-switch. New regression test. |

## Documented (not applied — owner/infra/API-contract decisions)
- **H1** — the rate limiter keys off client-supplied `CF-Connecting-IP`/`X-Forwarded-For` (spoofable → per-request fresh bucket defeats throttling) and is in-process/per-worker/reset-on-restart. Trust those headers only when `remote_addr` ∈ Cloudflare ranges (infra-specific); move to a shared/persistent store.
- **H2** — every submission creates partner + lead + order pre-verification (unbounded CRM/Contacts pollution behind H1). Defer CRM record creation to post-verification; dedup leads per email/day. (A flow redesign.)
- **C1 (full)** — require an API key / CAPTCHA / proof-of-work for anonymous write routes (changes the public "AI agents can call it" contract — the module's purpose).
- **M1/M2** — the `consent` boolean and honeypot are non-security (a spec-aware attacker trivially satisfies both). **M3** — `/quote` can trigger `product.product` variant creation (bounded to real SKUs). **L1** — tokens never expire (add TTL + cleanup cron). **L2** — add `Cache-Control` to openapi.json. **L3** — body-size check is post-read (use werkzeug `max_content_length`). **L4** — cache the recomputed offerings.

## Testing Results
- **Install + upgrade:** ✅ clean. v19-CLEAN (no obj() trap; `post_init_hook(env)` correct + idempotent; ir.sequence/mail_template/utm/crm data valid; phone_validation E.164 signature correct).
- **Unit tests:** ✅ **0 failed / 0 error / 35 tests** (install + upgrade) — from **2 failed / 8 errors** (all 10 were the B1 unpack crash). Added `test_verify_email_killswitch_and_cooldown` (C1 regression).

## Recommendations (priority)
1. **H2 / C1(full)** — defer CRM creation to post-verify + require API key or CAPTCHA on the anonymous write routes.
2. **H1** — trust proxy IP headers only from Cloudflare ranges; shared rate-limit store.
3. **L1** — token TTL + spam/expired-inquiry cleanup cron.
