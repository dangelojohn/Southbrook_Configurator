# Phase 1 — Retrospective

_Written 2026-05-30 during the gate-review interval. Captures what's worth
keeping for Phase 2: reusable design patterns, process disciplines, and
the lessons from the false alarms, slips, and surfacings that shaped the
final modeling layer._

This document is a forward-looking artifact, not a backward-looking report.
Everything here is something that earned its keep in Phase 1 and should
be reused — or improved — in Phase 2.

---

## 1. Four process disciplines (real artifacts of the build)

These are not descriptive labels for things that happened to work. They
are reusable disciplines that should be named, taught, and applied in
Phase 2.

### Discipline A — Method-introduction tests

**Pattern:** when commit N adds method M2 to a class that already has
method M1, commit N's test plan includes at least one direct
behavioural regression assertion on M1.

**Origin:** the NF13 false alarm in commit 6 review. A method body looked
truncated in pasted code; turned out to be a paste-rendering artifact.
But the class of slip is real — `py_compile` accepts a method with
`for x in self:` + `if guard: continue` as syntactically valid even
when the rest of the intended body is gone.

**Mitigation:** the test `test_pricelist_resolution.test_10_onchange_partner_id_resolves_pricelist`
exercises `_onchange_partner_id_southbrook_pricelist` via the `Form`
harness and asserts an observable effect (`order.pricelist_id`
matches the resolver output). Even though no bug existed, the test
catches the class.

**Phase 2 application:** any commit that touches an existing model
file checks for adjacent methods that lack direct unit coverage and
adds a behavioural assertion before the new method ships.

### Discipline B — Smoke-test stub promotion

**Pattern:** write the gate-level smoke test as a stub at the earliest
possible commit, with each step as `self.skipTest("waiting for commit N")`.
Promote stubs to real assertions incrementally as the dependency commits
land. By the time the gate-test commit ships, the test has been
enabling assertions one by one across the build.

**Origin:** commit 7 first shipped `test_phase1_smoke.py` with 10
skipTest stubs corresponding to Mapping §6 steps 1-10. Step 2 promoted
at commit 9 (Order Builder views). Step 6 promoted at commit 8 (panel
math). Steps 1, 3, 4, 5, 7, 8, 9, 10 promoted at commit 11b.

**Why it works:** each commit's PR closes a step. If commit 8's panel
math has a bug, it surfaces at the step-6 promotion, not at the final
smoke-test commit where it would compound with other unfinished work.
The slip is local to the commit that introduced it.

**Phase 2 application:** Phase 2's gate test for the customer
one-page configurator should ship as a stub file in the first Phase 2
commit, with each step skipTest'd. Same promotion pattern.

### Discipline C — Autonomous-stretch length

**Pattern:** name the boundary length of "autonomous stretch" (commits
under per-phase ack without per-commit ack), watch for failure modes
specific to that length. Six-commit stretches surface judgement-vs-
mechanical slips at the boundary — where the contributor assumed
mechanical and the work required judgement.

**Origin:** commits 2-6 were the longest autonomous stretch (per Q20
cadence). Surfaced NF11 (lead_time_extra location architectural call)
and a false-alarm NF13. Both caught at review. Commits 7-11b were the
second stretch; surfaced NF12 in anger (lint caught it pre-commit),
NF14 (toe-kick interpretation), NF15 (CSS-vars-TBD pattern).

**Why it works:** the discipline is "raise mid-stretch if anything
architectural surfaces." That keeps the per-phase ack model viable
without giving up on review safety.

**Phase 2 application:** name the autonomous stretch boundary at the
start of each phase. If Phase 2 splits into modeling + view + 3D
sub-phases, each gets its own stretch and its own ack gate.

### Discipline D — Asking-before-asserting (Claude-side)

**Pattern:** when reporting a suspected bug in pasted code, the report
shape is "I see X in the paste, that looks wrong, can you confirm on
disk?" — NOT "this is a real bug, fix it."

**Origin:** the NF13 false alarm in commit 6 review. A method appeared
truncated in pasted markdown; I called it a hard block on the ack.
Disk read + AST inspection proved the method intact. Wasted one review
cycle.

**Mitigation:** disk wins over rendered paste. Cost of asking-before-
asserting: one round-trip. Cost of asserting-broken-when-fine: a
wild-goose-chase commit + a tax on trust.

**Phase 2 application:** when something looks broken in pasted code,
the cheap reflex is to ask for a `cat -An` or AST dump before claiming
a bug. The asymmetry is fundamental: paste-rendering is unreliable;
disk content is authoritative.

---

## 2. Six reusable design patterns

These are patterns to copy verbatim into Phase 2 wherever the same
problem class shows up.

### Pattern P1 — The XML lint script (NF12)

**Problem:** XML well-formedness errors hide inside comments
(`--` inside `<!-- ... -->` is illegal) and don't surface until install.
`py_compile` doesn't catch them. The result is confusing "not well-formed"
errors at module-load time that stall reviews.

**Solution:** `scripts/lint-xml.sh` — walks the southbrook addons and
parses every `*.xml` with `xml.etree.ElementTree`. Fails fast with line+
column hint on first malformed file.

**Cost:** 2 lines of shell + an `xml.etree.ElementTree.parse()` call.

**Track record in Phase 1:** caught its first slip in anger in commit
11a (`--demo` inside a comment block). Same class as commit-5's `--grep`
slip that triggered NF12 in the first place. The institutional-memory
loop closed in one phase.

**Phase 2 application:** keep `scripts/lint-xml.sh` in place; wire into
pre-commit when the framework lands. Run before every XML-touching
commit. The cost-benefit ratio is overwhelmingly positive.

### Pattern P2 — Behavioural regression tests (NF13)

**Problem:** `py_compile` and view rendering accept methods or templates
whose body has been silently truncated or whose semantic intent has
drifted. The compile passes; the behaviour is gone.

**Solution:** every new model method introduced in a commit gets at
least one direct unit test asserting an **observable effect**, not
just "the method can be called."

**Concrete example:** `test_10_onchange_partner_id_resolves_pricelist`
asserts `order.pricelist_id` matches the resolver output via the `Form`
harness — not just "the onchange method exists."

**Phase 2 application:** apply to any new method, server action, or
hook. Particularly important for view-level code where XML lint can't
reach. The view-render tests in `test_order_builder_views.py` are the
view-specific version (assert against compiled arch, not source XML).

### Pattern P3 — The seed_mode flag (OQ2)

**Problem:** when canonical seed data is gated on an artifact that
isn't available yet, tests have a choice: hardcode illustrative numbers
(which break when canonical lands) or skip $-value assertions entirely
(which loses smoke-test value).

**Solution:** an `ir.config_parameter` named `southbrook.seed_mode`
with values `illustrative` and `canonical`. Tests read it at `setUpClass`
and gate assertion mode:

```python
if self.seed_mode == "illustrative":
    self.assertGreater(order.amount_total, retail * 0.60)
    self.assertLess(order.amount_total, retail * 0.75)
else:
    self.assertEqual(order.amount_total, expected_canonical)
```

**Phase 2 application:** any test surface where canonical data is
gated on an external artifact (e.g. the door catalog, the hardware
catalog) uses the same gating pattern. One flag mechanism, one test
file, two assertion modes.

### Pattern P4 — Named constants with PUNCHLIST entries (NF14)

**Problem:** business-logic constants get embedded as magic numbers
in formulas. When canonical data lands and a constant changes, the
update is a hunt-and-peck through every consuming file.

**Solution:** every assumed value gets:
- A named constant at the top of the consuming file
- A PUNCHLIST entry marking it `ASSUMED — awaiting <canonical artifact>`
- A swap path documented verbatim in the PUNCHLIST entry

**Concrete example:** `BOX_TH = 15.875` in `mrp_bom.py` plus
PUNCHLIST NF14 listing all geometric assumptions with the "if #8
specifies differently, change BOX_TH" swap path explicit.

**Tests use re-derivation assertions:** every expected value is
computed inline from the named constants so the tests tolerate
constant updates without expected-value edits.

**Phase 2 application:** any new domain (handle catalog, decor finishes,
toe-kick variants) uses the same pattern. PUNCHLIST is the swap-path
catalogue.

### Pattern P5 — CSS-vars-with-TBD (NF15)

**Problem:** styling tokens are gated on canonical brand guides that
aren't available yet. Hardcoding placeholder hex values + fonts means
the swap, when the brand guide lands, is a hunt-and-peck through
every QWeb template.

**Solution:** named CSS variables defined in a single shared template
(`reports/southbrook_report_styles.xml`) with `/* TBD */` markers next
to each placeholder value. Templates reference variables by name; the
swap is a single-file update.

**Concrete example:** `--southbrook-walnut: #5C4033; /* TBD */` in
the styles template, consumed by `signature_spec_sheet`, `shop_copy`,
and `door_order` via `var(--southbrook-walnut)`.

**Phase 2 application:** the Phase 2 customer one-page configurator
will need styling tokens before SIGNATURE_SERIES_TOKENS.md lands.
Same CSS-vars-with-TBD pattern.

### Pattern P6 — Dual storage when spec wins over computation (Q4)

**Problem:** dimensional values where the workbook spec rounds
differently than literal conversion (e.g. 9" = 228mm by spec, not
228.6mm by 9 × 25.4). Computing one from the other introduces drift.

**Solution:** store BOTH explicitly. `value_inches` AND `value_mm` as
sibling fields on `product.attribute.value`, each populated from the
workbook directly. **NEVER compute one from the other.**

**Concrete example:** `value_width_9` has `value_inches=9` and
`value_mm=228` both set from #5 Price Master tab.

**Phase 2 application:** any time the canonical source rounds, codes,
or specifies a value differently than a derivable computation would,
dual-store. Examples that may surface in Phase 2: door dimensions
(door reveal varies by manufacturer), handle hole spacing, hinge cup
positioning.

---

## 3. Plan vs execution

### The original commit plan

`docs/drafts/PHASE_1_FIRST_5_COMMITS.md` (committed in commit 0a, kept as
reference) outlined Phase 1 as **5 commits**:

1. Manifest + module skeleton
2. `res.partner.channel` + `tradesperson_tier`
3. Attributes seed
4. Pricelists + channel resolver
5. Config rules + lead_time_extra + override stub

### What actually shipped

**16 commits.** Three setup (0a/0b/1), 11 feat, 1 fix, 1 9.5-split.

```
Setup: 0a, 0b, 1                          (3 commits)
Original plan: 2, 3, 4, 5                 (4 commits — matches the plan)
Plan additions:
  6  southbrook.order.analytics            (NF1 surfaced; commit 5 commit-body promise)
  7  templates + 65 rule expansion + lint  (3 surfaces in one commit)
  8  _compute_panel_dimensions             (routine #1 complete; the heavy math)
  9  Order Builder views + Q21             (Brief §2.2 deliverable)
  9.5 zone visual grouping                 (Q21 closure split atomically)
  10 QWeb reports                          (routine #6 partial)
  11a demo data                            (split for bisect-ability)
  11b smoke promotions                     (split for bisect-ability)
Fix: e8a6809                               (NF12 XML repair)
```

### Inflation drivers — review surfacing requirements, not drift

The 3× expansion was not scope creep. Every added commit traces to a
specific surfacing during review:

| Added commit | Driver | Surfaced when |
|---|---|---|
| Commit 6 (analytics) | NF1 — `southbrook.order.analytics` per Build Spec §8 | Commit 6 modeling-layer review |
| Commit 7 (lint, smoke stub, NF13 test) | NF12 surfaced post-commit-5; NF13 surfaced at review | Commit 5 review + commit 6 review |
| Commit 9.5 (zone grouping) | Q21 closure — visual grouping was acked deliverable, deferred at commit 9 | Commit 9 review |
| Commit 11a/11b split | Bisect-ability per discipline-B | Commit 11 ack |

**Important for Phase 2:** the inflation is the review process working.
Phase 2's initial plan will inflate similarly and the inflation will be
similarly driven by review-surfacing-requirements. Don't budget Phase 2
as exactly-the-plan-commits; budget Phase-2-as-the-plan-plus-review-inflation.

---

## 4. PUNCHLIST as institutional memory

Phase 1 grew the PUNCHLIST from 21 Q-numbered locked decisions to 36
distinct entries (Q1–Q23 + NF1–NF15 + OQ1/OQ2). Every entry has:

- A specific surfacing event with date
- A "why" rationale (often citing the source artifact section)
- A mitigation (named code, named test, or "deferred to phase X")
- Forensic citation: every feat commit body cites the Q/NF numbers
  the commit exercises

`git log --grep=NF14` lands on commits 8 + 9 (where the toe-kick
amendment landed). `git log --grep=Q22` lands on commits 3, 5, 7
(where door_count's hidden-attribute encoding shipped). The forensic
spine works.

**Phase 2 application:** keep the same Q/NF discipline. Continue
numbering — Phase 2 NFs start at NF16. The naming convention encodes
discovery order so future readers can reconstruct the design
conversation by reading the PUNCHLIST entries chronologically.

---

## 5. Loaded but cold — Phase 1 surfaces awaiting Phase 2 activation

These surfaces have schema, code, and tests, but no demo data or UI
exercises them at the gate review. Phase 2 picks them up rather than
re-inventing them:

| Surface | Status | Phase 2 activation path |
|---|---|---|
| Refacing channel margin-target | Routine #2 coded + tested | Add a CTHS refacing demo partner + a small refacing order |
| NF7 `southbrook_default_series` | User field + default in res.users | Wire the configurator wizard's `default_get` to read this |
| NF8 `southbrook_order_entry_mode` | User field shipped | Wire the inline drawer's xpath to conditionally reorder by mode |
| Big-box channel pricelist | Pricelist seeded ($98 fixed) | Add Home Depot / Lowe's demo partner |
| NF6 `parent_order_id` chain UI | Schema + action shipped | View widget showing the chain visually |
| KD channel pricelist | Pricelist seeded (~46% of retail) | Add a KD demo partner with component lines |

Each row represents one missed demonstration at the Phase 1 gate. Not
critical — the engine is correct — but the visual story at gate review
is thinner than it would have been with these activated. Capture for
Phase 2 planning.

---

## 6. What worked at the meta level

A short note before we close: the per-phase ack cadence (Q20), the
21-question pre-scaffold gate, the draft-promotion pattern in
`docs/drafts/`, the Q/NF numbering convention, the boundary discipline
keeping the routine register at 7 — these are all process artifacts
that did real work in Phase 1, not descriptive language.

The build that resulted is reviewable. `git log --oneline | head -20`
fits on a screen and shows what shipped at what stage. `git log
--grep='Q[0-9]\|NF[0-9]'` shows the locked-decisions trace. The
PUNCHLIST is the institutional memory. The 95 tests are the
behavioural contract.

These should outlast Phase 1. They are the build's design surface,
not just commit-time bookkeeping.

---

**End of retrospective.**
