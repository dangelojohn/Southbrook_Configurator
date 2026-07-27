# Changelog — `southbrook_hermes_bom`

## 19.0.2.4.0 — 2026-07-10 (code review #10)

Well-built module (v19-clean, excellent TOCTOU/advisory-lock, careful secret
handling, 26 green baseline tests). Fixed one CRITICAL + one HIGH.

### Fixed
- **CRITICAL (SSRF):** `_attach_documents` fetched AI-agent-supplied
  `source_urls` with only a scheme check. Added `_is_safe_public_url()` —
  enforces http/https and rejects non-global/reserved/multicast IPs
  (cloud-metadata 169.254.x, loopback, RFC1918, link-local) — and set
  `allow_redirects=False` so a public URL can't 3xx-bounce to an internal host.
- **HIGH (robustness):** `_validate_response` now type-checks nested sections
  (each required section is a dict; `bom.lines` is a list) so a malformed AI
  response raises a clean `UserError` inside the guarded `research()` call
  instead of crashing later and leaving the audit job stuck at `state='running'`.
  Added `isinstance` guards in `_apply_bom` (covers the reviewer-editable
  `proposed_bom_json`).
- **LOW:** `index=True` on `hermes.research.job.product_template_id` and `state`.

### Added
- `tests/test_hermes_ssrf_guard.py` — verifies the guard blocks
  metadata/loopback/private/non-http hosts and allows a public IP.

### Verified clean (no change)
All v19 axes; ACL completeness; external-service key/endpoint/timeout/secret
handling; the advisory-lock + TOCTOU re-check (well-tested); no eval/SQL-injection;
the 16 sudo() calls (hardcoded audit/state writes, admin-only config reads).

### Documented (not changed)
Synchronous worker-blocking (~7 min/run — move research + attachment fetch to
queued/async dispatch); no throttling/cost-cap on the paid external call; the
bounded ≤50-line component N+1. See `REVIEW_REPORT.md`.
