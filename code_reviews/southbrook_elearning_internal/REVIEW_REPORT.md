# Code Review & Repair Report — `southbrook_elearning_internal`

**Module:** Southbrook Internal E-Learning · **Version:** 19.0.1.3.0 → **19.0.1.4.0**
**Reviewed:** 2026-07-10 · **Odoo target:** v19 Community Edition
**Queue position:** #5 of 46 (Tier 0 — leaf; deps `website_slides`)
**Review method:** targeted review (this is a pure *data* module — no models/views/controllers/security/static) + secret/PII content scan + live cold install/upgrade on Odoo 19 CE.

---

## Executive Summary

A content-only module: 28 `slide.channel` courses / ~198 `slide.slide` lessons of generated HTML training on the Southbrook custom modules, installed into `website_slides`. The only Python is a **dev-time build script** (`scripts/build_data_xml.py`, not imported/installed) that regenerates the XML from `docs/elearning/*.md`.

**v19 compatibility is clean** — the full ~49K-line XML installs on v19 with no ParseError; slide records use the correct v19 fields (`slide_category`, not the old `slide_type`; `html_content`). No leaked credentials (the many `api_key`/`secret`/`sk-` scan hits were code examples in lesson text or CDATA substrings — no real keys).

**The one real finding was a security/info-disclosure issue:** the **Sysadmin course** embeds live infrastructure detail (`ssh admin@ssh.odooiq.com`, `ssh admin@192.168.68.108`, `smb://192.168.68.108/OdooIQ-Backups`) in lessons that shipped `visibility=connected` + `enroll=public` — i.e. **any signed-in user, including portal/dealer customers, could self-enroll and read the server IP, SSH endpoint, admin username, and backup path.** Fixed by restricting that course to members-only + invite-only, guarded by a new regression test.

---

## Original Issues Found

| # | Sev | Axis | Finding |
|---|-----|------|---------|
| S1 | **MEDIUM** | Security | `course_sysadmin` (SSH hosts, internal IP `192.168.68.108`, backup share) shipped `visibility=connected` + `enroll=public` → infrastructure recon self-enrollable by any authenticated user incl. portal/dealer customers. |
| D1 | LOW | Docs | Manifest claimed "7-course, 29-lesson"; actual is **28 courses / ~198 lessons**. Also claimed `visibility=public`; actual is `connected`. |
| — | — | — | (No `tests/` — added one guarding S1.) |

### Reviewed and found clean
- **v19 field compatibility** — installs cleanly; `slide.channel`/`slide.slide` fields (`channel_type`, `visibility`, `enroll`, `is_published`, `slide_category`, `html_content`, `tag_ids`) all valid in v19.
- **No leaked secrets** — no real API keys / passwords / tokens; the flagged strings are training references (`api_key = self.env.company.vendorx_api_key` is a code sample) or CDATA false positives.
- **Build script** (`scripts/build_data_xml.py`) — no `os.system`/`subprocess`/`eval`/`exec`/`shell=True`, no embedded secrets; and it's a dev tool, not installed (out of runtime scope).
- Seed data uses `<data noupdate="0">` (intentional — upgrades refresh the generated content).

---

## Repairs Completed
1. **S1:** `course_sysadmin` → `visibility=members` + `enroll=invite` (with an inline SECURITY comment). Non-sysadmins can no longer browse or self-enroll into the infrastructure lessons; an admin invites the sysadmin staff.
2. **D1:** manifest summary/description corrected to 28 courses / ~198 lessons and `visibility=connected` (with a note that `connected` includes portal logins, and that the course-matrix list is a representative subset).
3. **Tests:** added `tests/test_elearning_security.py` — asserts `course_sysadmin` is `members`/`invite`, catching a regression if the build script re-widens visibility.

### Deliberately NOT changed (documented as recommendations)
- **Whole-series visibility:** the other 27 courses remain `visibility=connected`, so portal/dealer customers can browse all internal manufacturing/estimating/PLM training. Low-severity (operational know-how, not secrets), but consider `visibility=members` for the whole series if internal-only exposure is desired.
- **Source-markdown redaction:** the infrastructure values live in `docs/elearning/*.md` (the build source). The access-control fix protects the deployed channel, but the *source* still contains the IPs/hostnames — redact them there (or move to an internal ops runbook) so a regen into a mis-configured channel can't re-leak them.
- The manifest course-matrix prose still lists only courses 1–7 (now noted as a subset); a full rewrite wasn't warranted.

---

## Files Changed
2 modified (`__manifest__.py`, `data/elearning_courses.xml`), 1 new dir (`tests/`). No content HTML altered (the fix is access-control, not redaction — sysadmins legitimately need the values).

## Database Impact
None structural — a `slide.channel` visibility/enroll change on one record (applied on `-u`; the file is `noupdate="0"`). No schema change.

## Security Improvements
Closed the infrastructure-recon exposure: the sysadmin course (server IP / SSH endpoint / admin user / backup path) is now members+invite, not browsable by portal/connected users. Verified no leaked credentials elsewhere.

## Performance Improvements
None applicable (static content; install-time only).

## Testing Results
_See `TEST_RESULTS.md`._ Cold install + upgrade clean on Odoo 19 CE; the new security regression test passes (1/1); DB confirms `course_sysadmin = members/invite`.

## Remaining Risks
1. Source markdown still holds the infrastructure values (see recommendation) — regen without fixing the source could re-leak if a channel is later mis-set to `connected`/`public`.
2. Whole-series is portal-visible (`connected`) — a policy decision for the owner.

## Recommendations
- Redact production IPs/hostnames from `docs/elearning/07-*.md` (build source) and re-run `build_data_xml.py`.
- Decide whether the whole internal series should be `members`-only rather than `connected`.
