# Phase 2 Track 2 — Gate Review Checklist

**Review date:** _(fill on completion)_
**Reviewer:** John (project owner)
**Scope:** The 13 Track-2 build commits, the JSON-RPC contract, and
the OWL component tree that lift from `docs/southbrook_owl_mockup.html`
into the portal.

This is the artifact for the Phase-2 charter §"Phase 2 commit lineup"
item #14. After sign-off below the gate closes; Phase 2.5 begins (the
Three.js viewport back-port from Track 1 into the portal).

## What to test against

Live host: `https://www.southbrookcabinetry.local:9443`
Branch: `main` at commit `58f3681` or later (`git log --oneline -1`)
Forgejo tip: `http://192.168.68.108:9080/git/qnap/southbrook-v19cr`

You'll need an order with **at least 4 cabinet lines spanning ≥ 2
zones** to exercise the multi-zone grid. Suggested setup:

1. Backend → `Southbrook Estimating` → `Launch 3D Configurator`
2. Configure 4 cabinets: 2 in `base_run`, 1 in `wall`, 1 in `tall`
3. Note the sale.order id from the URL once attached to an order
4. Open the portal route with that id:
   `https://www.southbrookcabinetry.local:9443/my/southbrook/order-builder/<id>`

Hard refresh (⌘-⇧-R) before each section so the asset bundle reloads.

---

## Section A · Smoke (Track 2 commits 1-5)

### A1. Portal route resolves
- [ ] `https://www.southbrookcabinetry.local:9443/my/southbrook/order-builder` →
      HTTP 200, portal chrome (header + breadcrumb + sidebar) renders.
- [ ] `My Account` sidebar shows an `Order Builder` entry.
- [ ] Clicking it lands on the same route (no-id form).

### A2. Bare-route empty state
- [ ] No-id form shows an empty-state card: "No order selected.
      Append an id to the URL — for example
      `/my/southbrook/order-builder/234`."

### A3. OWL bundle loads
- [ ] DevTools → Network → look for `*frontend_lazy*.js`.
- [ ] Response is ~7.7 MB (varies; verify ≠ 0).
- [ ] No 404/500 on the JS bundle.

### A4. Asset bundle has Track-2 markers
- [ ] DevTools → Console: paste
      ```js
      ['OrderBuilder', 'HeaderStrip', 'ZoneGroup', 'ConfigDrawer',
       'BoMPreview', 'FooterActions'].every(n =>
         document.querySelector('#order_builder_root') !== null
      );
      ```
- [ ] Returns `true` (or the mount-point div exists at minimum).

### A5. JSON-RPC controller serves payload
- [ ] DevTools → Network → filter `api/order`.
- [ ] Find the POST to `/southbrook/api/order/<id>`.
- [ ] Response 200, body has `result.order.name`, `result.lines`,
      `result.zones`, `result.bom_rollup`, `result.validation`.

---

## Section B · Chrome (T2C6 + T2C7)

Hit `/my/southbrook/order-builder/<populated-id>`.

### B1. IllustrativeBanner
- [ ] Amber strip at the top of the loaded view.
- [ ] `[ ILLUSTRATIVE SEED ]` pill (gold bg, mono).
- [ ] Body text references PUNCHLIST OQ2 + Build Spec §9.3.

### B2. OrderTitlebar
- [ ] Left: `← Back to Order Builder` link (dim, hovers to walnut).
- [ ] Below it: `<Partner Name> · Kitchen Order` (Roboto Flex, walnut,
      larger size).
- [ ] Right: `<order name> · v<N> · <state label>` (JetBrains Mono, dim).
- [ ] State label maps: draft → Draft, sent → Estimating,
      sale → Confirmed, done → In Production, cancel → Cancelled.

### B3. StagePipeline
- [ ] 5 chevron stages: Draft / Estimating / Approval / Confirmed /
      In Production.
- [ ] Current state = walnut bg + linen text + bold.
- [ ] Earlier stages = sky-tint (--sb-sky-l) bg + dark text.
- [ ] Later stages = paper bg + dim text.
- [ ] Chevrons interlock cleanly (clip-path polygons).

### B4. HeaderStrip — 5 cells
- [ ] Customer cell (left): partner name + via (if dealer link) +
      pricelist badge below. Sky-tinted background.
- [ ] Retail Subtotal cell: `$<retail>` in JetBrains Mono.
- [ ] Channel Total cell: `$<channel>` in JetBrains Mono.
- [ ] Savings cell: `$<savings>` in green (--sb-ok).
- [ ] Lead Time cell: weeks or em-dash if 0.
- [ ] Channel badge background varies per channel:
        dealer = walnut, tradesperson = sky, kd = slate,
        bigbox = grey, refacing = tan-walnut,
        retail = rule with dark text.

---

## Section C · TabBar (T2C8)

### C1. Five tabs render
- [ ] `Order Lines` · `BoM Preview` · `Validation` · `History` ·
      `Customer Print` — in this order, left to right.
- [ ] Active tab has walnut underline + ink text + 600 weight.
- [ ] Non-active tabs are dim; hover shifts to walnut.

### C2. Count badges
- [ ] Order Lines badge = `state.lines.length`.
- [ ] BoM Preview badge = sum of all panel + hardware items.
- [ ] Validation badge = number of issues (0 in Phase 2).
- [ ] History badge = `v<N>`.
- [ ] Customer Print tab has NO badge.

### C3. Tab switching
- [ ] Click any other tab → content area swaps without a page
      reload (pure client-side).
- [ ] Active state visually moves to the clicked tab.
- [ ] No console errors.

---

## Section D · ZoneGroup + OrderLine + ConfigDrawer
(T2C9 + T2C10)

### D1. Zones render per Q21 ordering
- [ ] Base Run cabinets render first (if any).
- [ ] Then Wall, then Tall, then Island, then Accessory, then Other.
- [ ] Zones with zero lines are NOT shown.

### D2. Zone header
- [ ] Chevron icon (rotates -90deg on collapse).
- [ ] Zone name in uppercase tracked.
- [ ] Line count: "N line(s)" (singular/plural correct).
- [ ] Subtotal: retail strike + channel mono on the right.

### D3. Zone collapse
- [ ] Click zone header → lines hide; chevron rotates.
- [ ] Click again → lines reappear; chevron rotates back.
- [ ] Other zones unaffected.

### D4. Line row layout (8 columns)
- [ ] Line number (mono, centered).
- [ ] Template name + xml_id pill.
- [ ] Width: e.g. `24″` (mono).
- [ ] Spec text with badges:
        MAPLE badge (walnut bg + linen text) on maple cabinets.
- [ ] Quantity (mono, centered).
- [ ] Retail price strikethrough (dim, smaller).
- [ ] Channel price (mono).
- [ ] `⋯` menu glyph (dim).

### D5. Line selection
- [ ] Hover row → tan tint.
- [ ] Click row → row gets amber (`--sb-hl`) background.
- [ ] Click same row again → deselects.
- [ ] Click different row → selection moves.

### D6. ConfigDrawer expansion
- [ ] When a line is selected, drawer slides in below it.
- [ ] Drawer spans all 8 grid columns.
- [ ] Walnut 2px top border (visually anchors to the selected row).
- [ ] Header: `Line N · Configuration` + `[LIVE EDIT · AUTOSAVE]`
      sky pill on the right.
- [ ] 4-column grid of read-only fields:
        Template · Family · Zone · Width · Spec (full row) ·
        Quantity (editable) · Retail · Channel.

### D7. Qty autosave
- [ ] Change the Qty input (e.g. from 1 to 3).
- [ ] Pill flips to `[SAVING…]` (warn-orange) within 300ms of last
      keystroke.
- [ ] Pill flips to `[SAVED · HH:MM:SS]` after the RPC returns.
- [ ] Within 1-2s the line's price column updates (re-fetched value).
- [ ] Zone subtotal updates.
- [ ] HeaderStrip totals update.

### D8. Qty error path
- [ ] Set Qty to 0 → pill flips red, message "Qty must be > 0".
- [ ] No data corruption (line still has previous good value).

---

## Section E · BoMPreview + ValidationStrip (T2C11)

### E1. Switch to BoM Preview tab
- [ ] 3-cell summary: Cabinets / Total Panels / Edge Banding (m).
- [ ] Edge Banding shows in meters with 2 decimals.
- [ ] Panel Cut List table renders rows for panel types with
      qty > 0 (hides 0-qty rows).
- [ ] Hardware table renders 3 rows always: Hinge pairs / Handles /
      Drawer slide pairs.
- [ ] Footer: "Phase 3 polish adds per-line BoM breakdown…" note.

### E2. Switch to Validation tab
- [ ] Empty-state card: green left border + "✓ No rule issues."
- [ ] Footer note explains Phase 3 wires the real rule engine.

---

## Section F · FooterActions (T2C12)

### F1. Footer renders below the active tab panel
- [ ] Walnut 2px top border (matches drawer pattern).
- [ ] Left side: 3 action buttons in a row.
- [ ] Right side: Grand Total summary (28px walnut Roboto Flex).

### F2. Customer Print
- [ ] Click `Customer Print (PDF)`.
- [ ] New tab opens with the QWeb PDF report
      `/report/pdf/southbrook_estimating.action_report_signature_spec_sheet/<id>`.
- [ ] PDF renders (per Track 1 — already validated in Phase 1).

### F3. Duplicate as Draft
- [ ] Click `Duplicate as Draft`.
- [ ] Backend creates a v2 copy via NF6 action_duplicate_as_draft.
- [ ] Page navigates to `/my/southbrook/order-builder/<new-id>`.
- [ ] OrderTitlebar ref shows `v2` and the new order id.
- [ ] All cabinet lines are present on the duplicate.

### F4. Confirm Order
- [ ] On a draft order: button label `Confirm Order`, enabled.
- [ ] Click → button disables; pill below footer shows
      "Order confirmed."
- [ ] StagePipeline current stage advances from Draft to Confirmed.
- [ ] On already-confirmed: button disabled, label
      `Confirmed (sale)`.

### F5. Grand Total summary
- [ ] Label: `GRAND TOTAL` (caps + dim).
- [ ] Value: `$<channel_total>` (28px walnut Roboto Flex, mono).
- [ ] Subline: `<N> lines · [channel badge]`.

---

## Section G · Customer Mode (T2C13)

### G1. URL toggle
- [ ] Append `?mode=customer` to any order URL.
- [ ] Page reloads in customer view.
- [ ] Without the param: returns to dealer view.

### G2. OrderTitlebar shows badge
- [ ] Sky pill `CUSTOMER VIEW` appears before the order ref.

### G3. TabBar filtered
- [ ] Only `Order Lines` + `Customer Print` tabs visible.
- [ ] `BoM Preview`, `Validation`, `History` are hidden.

### G4. FooterActions different
- [ ] Print button label: `Print Spec Sheet (PDF)`.
- [ ] No `Duplicate as Draft` button.
- [ ] Confirm button label: `Request a Price`.

### G5. Grand Total label
- [ ] Reads `ESTIMATED TOTAL` instead of `GRAND TOTAL`.

### G6. Request a Price dispatch
- [ ] On a draft order: click `Request a Price`.
- [ ] Backend hits `action_code=request_price` (verify in
      DevTools → Network).
- [ ] Same end result as Confirm for Phase 1 (Phase 3 polish
      replaces with a salesperson-approval workflow).

---

## Section H · Integration sanity

### H1. Cross-component reactivity
- [ ] Open ConfigDrawer on a line, change qty, save.
- [ ] Verify within the same view: line price → zone subtotal →
      HeaderStrip retail/channel/savings → BoM Preview rollup
      (if cabinet count changed via qty) → FooterActions Grand
      Total ALL refresh from the single re-fetched payload.

### H2. State propagation across tabs
- [ ] Select a line.
- [ ] Switch to BoM Preview tab.
- [ ] Switch back to Order Lines tab.
- [ ] Selection persists (line still highlighted).
- [ ] Drawer still visible.

### H3. Error resilience
- [ ] Access a non-existent order: `/my/southbrook/order-builder/9999999`.
- [ ] "Order not found." error card + Retry button.
- [ ] Retry shows the same error (graceful failure).

### H4. Auth (manual)
- [ ] Log out.
- [ ] Hit `/my/southbrook/order-builder` → redirected to login.
- [ ] Log back in → returned to the route.

---

## Known limitations — DO NOT FLAG

These are documented Phase-3 polish items already in commit messages.
Flagging as gate-review issues is unnecessary unless the spec on them
has changed.

| Class | Item | Phase |
|---|---|---|
| Visual | Outline post-process around hovered cabinet (vs emissive) | T1 Phase 3 polish |
| Visual | HDRI environment lighting | T1 Phase 3 polish |
| Visual | Custom font vendoring (woff2 @font-face) | T2 Phase 3 polish |
| Functional | Inline add-line flow on the portal | T2 Phase 3 polish |
| Functional | Full attribute pickers in ConfigDrawer | T2 Phase 3 polish |
| Functional | Salesperson approval workflow behind request_price | T2 Phase 3 polish |
| Functional | Real rule engine output → ValidationStrip | T2 Phase 3 polish |
| Functional | Per-line BoM breakdown + cut diagrams | T2 Phase 3 polish |
| Functional | History panel parent-order chain | T2 Phase 3 polish |
| Functional | In-page PDF preview | T2 Phase 3 polish |
| Functional | Keyboard nav (arrow keys for tabs, lines) | T2 Phase 3 polish |
| Functional | Touch / mobile breakpoint tuning | T2 Phase 3 polish |
| Functional | Bus.bus subscription for live multi-user updates | T2 Phase 3 polish |
| Architectural | Three.js viewport BACKPORT into portal | Phase 2.5 (post-gate) |
| Architectural | Cancel order button | Phase 3 |
| Architectural | Send-to-manufacturing button | Phase 4 |
| Architectural | Multi-currency awareness | Phase 4 |

---

## Sign-off

```
[ ] All sections pass
[ ] Sections passing, items needing polish noted below
[ ] Failed sections — return to engineering

Reviewer: John (project owner)
Date:    ________________
Notes:

```

---

## Track 2 commit ledger

For traceability — the 13 build commits that comprise the gate scope:

| | Commit | What |
|---|---|---|
| T2C1 | `356950a` + reconciliation/fix commits | Scaffold |
| T2C2 | `1b26361` | Empty OWL mount |
| T2C3 | `cf01f5b` | Design tokens + fonts |
| T2C4 | `1e03355` | JSON-RPC controller |
| T2C5 | `a4b812f` | Reactive store wired |
| T2C6 | `c4d7353` | HeaderStrip |
| T2C7 | `c19fc9e` | Chrome (IllustrativeBanner + OrderTitlebar + StagePipeline) |
| T2C8 | `c0b7109` | TabBar + tab-panel routing |
| T2C9 | `5773546` | ZoneGroup + OrderLine grid |
| T2C10 | `df6fa45` | ConfigDrawer with autosave |
| T2C11 | `b6b3721` + fix `57b5bce` | BoMPreview + ValidationStrip |
| T2C12 | `8bd756a` | FooterActions row |
| T2C13 | `58f3681` | Customer-mode toggle |
| T2C14 | _(this file)_ | Gate review checklist |

After sign-off → Phase 2.5: back-port the Three.js viewport from
`southbrook_estimating` Track 1 (commits 4abda45 … 2dd5e02 + e6ddcfb…
e63fb7a etc.) into the OWL `<OrderBuilder/>` portal as a sub-component.
