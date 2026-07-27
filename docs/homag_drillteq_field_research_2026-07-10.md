# HOMAG DRILLTEQ V-200 — Field Research (grounding for the Panel Digital Twin)

**Date:** 2026-07-10
**Method:** 6 parallel research subagents (web), synthesized. Every non-obvious claim is sourced; anything unverifiable is tagged `[UNVERIFIED]`.
**Why:** the physical DRILLTEQ is not available to us. This memo grounds the twin's data model, the simulator's realism, and the Phase-5 telemetry seam in the real machine + HOMAG software ecosystem, so we build toward reality instead of guesses.

Companion docs: `~/Downloads/HOMAG_DRILLTEQ_V200_Odoo_Integration_Analysis.md` (2026-07-07 gap analysis) · `~/Downloads/Southbrook_MRP_Intelligence_Architecture_2026-07-10.md` (strategy) · `docs/superpowers/plans/2026-07-10-panel-digital-twin.md` (Phase 1 plan).

---

## 1. The machine (V-200)

- **Class:** compact vertical CNC processing center for cabinet panels — vertical + horizontal drilling, grooving/slot cutting, edge routing, furniture-connector holes (dowels, eccentric fittings, Clamex, back-panel grooves).
- **Panel envelope (real bounds for the twin's dimension fields):** length **200–3050 mm** × width **70–850 mm** × thickness **12–60 mm**.
- **Spindles (3 package options):** 8 or 13 vertical + 4 horizontal-X + 2 horizontal-Y + a grooving saw. Router: 5 kW, HSK-63F, 4-position tool changer.
- **Control:** **powerTouch2** HMI + **woodWOP** programming; **tapio**-compatible; Beckhoff PLC. Program output = **`.mpr`** files.
- Source: [HOMAG DRILLTEQ V-200](https://www.homag.com/en/product-detail/machines/cnc-drilling-and-routing-machining-centers/vertical-cnc-processing-center-drillteq-v-200), [WOOD TEC PEDIA](https://wtp.hoechsmann.com/en/lexikon/36539/homag_drillteq_v-200), [Promob builder](https://suporte.promob.com/hc/en-us/articles/31114081902481-Builder-Weeke-Homag-DRILLTEQ-V-200).

## 2. How data leaves the machine — the Phase-5 seam (most important section)

Three real, tiered ingest paths (lowest effort first):

1. **HOMAG File Agent `.hol` feedback drop — free, no subscription, works on DRILLTEQ-class machines today.** Machines write completion feedback as `.hol` CSV files to a monitored network share. Fixed field positions: **timestamp (`yyyyMMddHHmmss`) @1 · type `PNL` @2 · quantity @6 · Part ID @31**. Crucially, the woodWOP program embeds a macro that bakes the part UID into the NC program itself:
   `HOMAG_PRODUCTIONMANAGER_FEEDBACK={Version:1.00,PARTID:<UID>,MPRNUMBER:<n>,MPRCOUNT:<n>}`
   → completion matches back to an order line **by UID**. Requires min firmware CADMatic 3.0 (saws) / PC85 (CNC). Source: [File Agent feedback](https://docs.homag.cloud/en/data-exchange/homag-file-agent/feedback-of-machines).
2. **HOMAG Connect REST** (typed .NET clients, GitHub [`HomagGroup/HOMAG-Connect`](https://github.com/HomagGroup/HOMAG-Connect)). Auth = **SubscriptionId + Authorization Key** from the tapio portal (simpler than full OAuth). Needs productionManager **"Advanced"** license. Exposes machine state, warnings, counters, maintenance intervals, 90-day history. Source: [Connect Machine Data](https://docs.homag.cloud/en/data-exchange/homag-connect/homag-connect-machine-data), [auth](https://docs.homag.cloud/en/data-exchange/homag-connect/authentication).
3. **tapio cloud** (4 REST APIs behind Azure AD OAuth2: Core/Discovery/Management/Application) + the on-machine **tapio CloudConnector** edge agent (an OPC-UA client that relays upward). Source: [developer.tapio.one](https://developer.tapio.one/general/available-apis), [CloudConnector](https://github.com/tapioone/CloudConnector).
4. **OPC-UA / umati** — Connect Machine Data aligns to **OPC 40550 "UA for Woodworking"** ([spec](https://reference.opcfoundation.org/Woodworking/v100/docs/)). Standard on new machines from **2024+** (paid add-on otherwise). Public umati test server: `opc.tcp://opcua.umati.app:4840`. HOMAG's own conformance `[UNVERIFIED]` (WEINIG is the confirmed woodworking sample-server contributor).

**Recommendation for our Phase 5:** target the **`.hol` file drop first** — it's free, works today, and its Part-UID-in-CSV model maps 1:1 onto `sb.panel.barcode` + `sb.machine.event`. Promote to HOMAG Connect REST if/when a productionManager Advanced license exists.

## 3. Machine state, faults, counters (grounds the event + future OEE/downtime models)

- **Canonical state enum (umati OPC 40550):** `STANDBY / WORKING / READY / ERROR` (+ `RecipeInRun`). HOMAG marketing also tracks loss categories: **waiting / setup(changeover) / malfunction / maintenance**. Use these for a Phase-5 machine-state field rather than inventing our own.
- **Fault/alarm structure (Connect Machine Data warnings):** `startTime/endTime · severity (1–1000) · localizedSource (component ID) · localizedMessage · category (e.g. "Fault") · sourceMessageId (the fault code) · causality`. → near-ready schema for a downtime-reason model; enriches `sb.machine.event`.
- **Counters:** parts/cycles with value + timestamp + granularity — the OEE feed; confirms per-part completion logging. Feed these into the existing `mes_mps` `oee_snapshot`, never a second OEE engine.
- Source: [Connect Machine Data](https://docs.homag.cloud/en/data-exchange/homag-connect/homag-connect-machine-data), [MMR Connect API](https://docs.homag.cloud/en/mmr-mobile/in-a-nutshell/connect-api), [umati woodworking](https://reference.opcfoundation.org/Woodworking/v100/docs/).

## 4. Per-part identity + barcode (validates Phase 1/2)

HOMAG's own `productionAssist` ecosystem is barcode/QR-driven — **we are mirroring a workflow HOMAG already ships:**
- The **Labeling package** prints a per-part label (job name, edging info, barcode/QR) automatically in production order; affixed manually.
- **productionAssist Feedback** = scan the label to report a part finished → decrements the worklist. **productionAssist Sorting** = scan → LED-guided shelf.
- **On-machine scanner on the V-200 itself is `[UNVERIFIED]`** — the machine has a sensor **plausibility check** (X/Y verify actual vs DB) + a **length-measurement run** (auto-corrects hole positions), but barcode reading lives in the surrounding productionManager/productionAssist layer, not confirmed as V-200 hardware.
- Barcode **symbology unconfirmed** `[UNVERIFIED]` — "barcode or QR"; Code128/DataMatrix are industry-common but not a stated HOMAG spec.
- Source: [Identify parts by scanning](https://docs.homag.cloud/en/news/article/identify-parts-simply-by-scanning), [Report parts finished](https://docs.homag.cloud/en/productionassist-feedback/tutorial/report-parts-as-finished), [Labeling package](https://wtp.hoechsmann.com/en/lexikon/38094/homag_labeling_package).

## 5. Program & bore-pattern representation (grounds Phase 3 program generation)

- **woodWOP MPR / MPR5** — native format, **ASCII/text**, block-structured: data head → variable table (`L` length, `B` width, `D` thickness, ~99 vars) → coordinate system → contour elements (`KP` point, `KL` line, `KA` arc…) → **processing macros** (each starts with `<` in col 1 + ID + name). A drill/bore macro carries **X/Y, depth, diameter, face/side**. Exact field mnemonics `[UNVERIFIED]` (primary PDF unreachable). MPR5 = later revision of the same family.
- **BTLx** (design2machine XML) — Drilling element = `StartX, StartY, Angle, Inclination, DepthLimited, Depth, Diameter` relative to a `ReferenceSide` (1 of 6 faces). Clean model, but BTLx is timber-frame-oriented; cabinet 32mm work is MPR-dominated.
- **32mm System (cabinet standard):** two rows of **5 mm** holes, **32 mm** on-center, front row set back **37 mm**; **hinge cup = 35 mm** dia, ~12–13 mm depth; shelf pins 5 mm; dowel ~5 mm, cam-lock ~8 mm. → a `bore_positions` record should carry: `x, y (panel-local), diameter, depth, face/side, type(line-bore/shelf-pin/hinge-cup/dowel/cam)`. This is the target shape for promoting the hidden `_derive_predrilled_holes()` heuristic in P3.
- Source: [woodWOP](https://www.homag.com/en/software/woodwop-versions), [BTLx 2.1 spec](https://www.design2machine.com/btlx/BTLx_2_1_0.pdf), [32mm System](https://truepositiontools.com/learn/how-to/getting-to-know-the-32-mm-system-for-cabinet-making/).

## 6. Tooling & wear (grounds Phase 3 changeover cost + Phase 6 tool-life)

- **Tool DB / spindle assignment:** tapio **ToolManager / twinio** (tool database, per-spindle limits, sharpening tracking, performance history).
- **Tool-life units (validates `life_unit` holes/cycles):** general wood bits ~**1,000 holes**; hinge-cup bits ~**50–500 holes** (material/coating; TiN ≈2×). Bore cycle ~**10 s/hole**.
- **Changeover cost (real anchors for the Phase-3 optimizer):** tool change ~**40 s** with the auto changer vs ~**12 min** manual.
- **Wear signals:** spindle-motor current trending catches ~70–80% of flank wear (alerts 8–15 min pre-failure); acoustic/vibration for more.
- **Honest gap:** HOMAG Connect exposes counters + maintenance intervals but **not** tool-wear externally (serviceAssist does it proprietarily). → Phase-6 tool-wear = **estimate from hole-counts today**, measure later. Matches the strategy doc's "estimate-now / measure-later" bridge.
- Source: [tapio ToolManager](https://toolmanager.homag.cloud/), [twinio](https://digital.homag.com/en/twinio/), [CNC monitoring](https://ifactoryapp.com/blog/cnc-machine-monitoring).

## 7. Integration reality (validates the whole architecture)

Batch-size-1 cabinet lines run: **ERP/PPS → woodWOP CAM → machine control**; barcode labels applied at cutting; downstream machines read the barcode to load the program; completion flows back via File Agent auto-feedback or productionAssist scan; **ControllerMES** is HOMAG's own MES; the productionManager Connect API bridges to external ERP. A comparable line (Breitschopf) runs **~1,500 parts/shift** — a real simulator-volume anchor. Source: [batch size 1 kitchens](https://www.homag.com/en/company/news/case-studies/detail/production-line-for-batch-size-1-kitchens), [ControllerMES](https://www.homag.com/en/product-detail/software/production-management/controllermes).

---

## What this changes for our build (actionable)

**Phase 1 (built, `southbrook_panel_twin`): no code change needed.** The research *validates* the existing design — optional `panel_id` on `sb.machine.event` is exactly right for `.hol` rows that arrive and match by UID; `barcode` = the HOMAG Part UID; `life_unit` in holes/cycles is correct. Simulator placeholder programs (`HINGE_32MM_RIGHT`, `SHELF_PIN_5MM`) are directionally accurate.

**Refinements to fold in later (documented here, not built now — YAGNI):**
- **Phase 5 ingest** = poll the **`.hol`** share, parse the fixed-field CSV, match Part ID → `sb.panel.barcode`. Add a machine-**state** field aligned to umati `STANDBY/WORKING/READY/ERROR`. Add a downtime-reason model shaped like the Connect warnings schema (`category` + `sourceMessageId` + `severity`).
- **Phase 3 program-gen** = emit `bore_positions` as `{x, y, diameter, depth, face, type}`; target **`.mpr`** (ASCII macro blocks) as the output format.
- **Phase 6 tool-wear** = estimate from hole-counts (Connect gives counters, not wear).
- **Licensing note:** HOMAG Connect REST needs a productionManager **"Advanced"** license — confirm what Southbrook's DRILLTEQ ships with before committing to that path; the `.hol` drop needs none.

**Open items to confirm with a HOMAG dealer (can't verify online):** exact MPR bore-macro field mnemonics; whether the V-200 has an on-machine scanner; barcode symbology; the machine's actual firmware tier (gates `.hol` + OPC-UA availability).
