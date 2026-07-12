# Code Review — `southbrook_training_hub`

**Module #45 of 46 · Odoo 19.0 CE · 699 LOC**
**Version:** 19.0.1.3.0 → **19.0.2.0.0**
**Reviewed:** 2026-07-11
**Method:** 2 parallel audit agents (security; v19+OWL) → independent source
verification incl. `search_for_user`'s gate model + the Hermes dispatch env-binding →
HEAD baseline → real fixes → live `-i`/`-u` + runtime probes on isolated DB
(`ci_train45`, full dep stack staged).

## What the module does
A discovery/retrieval layer over internal e-learning: an in-app **Help systray/panel**
(OWL), two `auth="user"` HTTP routes (`/training/recommended`, `/training/search`) for the
panel + the intranet IQ-Deck tile, a **Hermes `find_training` tool** (T0, read-only), and
curator-managed `training.item`/`tag`/`menu_link` with a JTBD verb-phrase search.

## Verdict
**A well-built, low-risk module** (both agents): v19-clean (OWL correct — no removed
`useService`, `t-esc` throughout, valid systray registration; controllers correct; least-
privilege ACLs — items are **curator-write-only**), **no injection / eval / SQL / t-raw**,
`limit` capped, `q` only in ORM `ilike`. The findings were **identity/scoping** on the
role-visibility gate, not the data path. Fixed **1 MED + 2 LOW security + the v19
`name_get`**. No test suite exists (0 tests) — validated by clean install/upgrade + probes.

## Findings

### Fixed — security
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **S1** | **MED** | **Hermes `find_training` evaluated the role gate as superuser.** `search_for_user` builds its `role_group_ids` visibility gate from `self.env.user`, but the tool called it under `.sudo()` → `self.env.user` = superuser (member of every group) → the gate matched **every** item, so a `trade_partner` persona could receive internal-role-gated training. (The HTTP controllers correctly `.with_user(request.env.user)`; the tool omitted it.) | Dropped the `.sudo()` in the tool — verified the Hermes dispatch already binds the tool `env` to the persona (`request.env(user=user.id)`), so the un-sudo'd call evaluates the gate against the real caller. (`search_for_user` still sudo's the catalogue read internally; only the gate needed the real identity.) |
| **S2** | LOW-MED | **Fail-open default + portal reach.** `role_group_ids` empty = "everyone", and `search_for_user` sudo's the actual search (so the model ACL is bypassed) — so a portal/share user hitting the two `auth="user"` routes could page through every un-gated item, including auto-seeded internal runbook titles/URLs (the seed hook sets no gate). | Added `_is_internal()` on both routes → 403 for portal/share users. The Help panel + IQ-Deck are internal surfaces; the trade-partner path is the Hermes tool (S1-scoped), not these routes. |
| **S3** | LOW | **`url` field had no scheme validation** — rendered into `window.open`/`act_url`; a `javascript:` URL is a latent script vector (curator-only write, so trusted-author). | `@api.constrains("url")` requires `http(s)://` or a leading-slash path. |

### Fixed — v19
| # | Sev | Finding | Fix |
|---|-----|---------|-----|
| **V1** | MED (cosmetic) | **`name_get()` removed in v19** — `training.tag.name_get` was silently dead, so tag widgets showed the bare name instead of `[Role] Sales Rep`. | Converted to `_compute_display_name` (`@api.depends("kind","name")`). |

### Documented (minor — not changed)
| # | Sev | Finding | Note |
|---|-----|---------|------|
| V2 | LOW | The `ir.ui.menu` computed m2m `training_item_ids` declares an explicit relation table name equal to the real `southbrook_training_menu_link` model table. Inert today (`store=False` → no DDL), but a landmine if ever flipped to `store=True`. | Drop the explicit relation/column args (let ORM auto-name). |
| V3 | INFO | The menu-scoped search path (`menu_id`) exists in the controller but the shipped Help JS never passes it — "menu-anchored recommendations" isn't wired from the systray. | Unused surface. |

## Strong positives (verified by both agents)
- **No injection / eval / SQL / t-raw**; `q` → ORM `ilike` only; `menu_id` int-coerced; `limit` capped (25 routes / 10 tool). Help panel uses `t-esc` throughout; `window.open` uses `noopener,noreferrer`.
- **Least-privilege ACLs** — `base.group_user` read-only on all three models; create/write reserved to `group_training_curator` (so no low-priv content injection). No portal ACL row.
- **Hermes tool is genuinely read-only** (T0, `scope="training_catalogue"`, only touches `training.item`) — prompt-injection has no write path.
- **v19-clean**: OWL imports from `@odoo/owl`, `useService("orm"/"dialog")` (no removed `rpc`/`user`), valid systray registration, `models.Constraint` (×3), `group_ids` (not `groups_id`), correct `post_init_hook(env)`/`migrate` signatures, `<list>`/`<chatter/>`, assets paths resolve.

## Validation
- `-i` (fresh DB, full dep stack) — **clean**, registry ~65 s; the new `url` constraint
  **passed the post_init seed** (seeded slide URLs are `/slides/...` / `/web/content/...`);
  the `display_name` compute registered without a registry break.
- `-u` — clean.
- **No test suite ships** (0 tests) — validation is install/upgrade + code review + the two
  audit agents. See `TEST_RESULTS.md`.
