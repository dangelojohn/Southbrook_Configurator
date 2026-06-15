# KitchenForge × Marathon Hardware
## Channel Partnership Pitch — VP Sales & VP Marketing

Presented by: Southbrook Cabinetry
Date: June 2026
Platform: https://southbrookcabinetry.space

---

## Slide 1 — The cabinet shop's broken hour

- The average independent cabinet shop loses **45–90 minutes per kitchen** re-keying hardware specs across quote, cut-list, and PO.
- Hardware errors are the **#2 cause of shop callbacks** (behind only finish defects) — wrong drawer-slide length, wrong hinge cup, wrong overlay.
- Shops carry 6–14 hardware SKUs per kitchen on average. None of it is in their CAD. All of it is in someone's head.
- This is a **distribution problem disguised as a software problem.** The shop doesn't need better software — they need the right SKU specified, in stock, and shipped before they finish the quote.
- That's the hour we give back. And we hand the spec — and the rebate — to Marathon.

**Speaker notes:** Open with the operational pain, not the tech. Marathon's VP Sales hears "shop callback" and knows exactly what that costs at the dealer-rep level. Land that the broken hour is a Marathon-shaped problem before we describe what we built.

---

## Slide 2 — What we built

- **KitchenForge** is a SaaS productization of Southbrook Cabinetry's working Odoo 19 platform — live, billing real customers, processing real kitchens.
- Three modules in production: project-template spine, channel integration layer, multi-tenant control plane.
- Hardware resolver (`southbrook.hardware.catalog.resolve()`) already understands **20 finishes, 5 knob templates, full Marathon partner record** wired in.
- AI-agent surface: shop owners describe a kitchen in plain English, the system produces a quoted, cut-listed, hardware-specced project.
- **Proof:** `southbrookcabinetry.space` has been a live reference shop on this stack since 2026. We're not pitching a deck — we're pitching a platform with a year of production load on it.

**Speaker notes:** This is the credibility slide. The pitch is not "trust us, we'll build it." It is "this exists, it runs Southbrook today, and the Marathon hooks are already in the code."

---

## Slide 3 — Why Marathon

- Marathon serves the exact segment KitchenForge serves: independent cabinet shops, kitchen designers, regional manufacturers across Canada and the US.
- 6 locations × 3 provinces = the distribution backbone we cannot build and would not try to.
- Marathon's competitors (Richelieu, Häfele) are **bigger but slower** — they ship hardware, not software, and they will not have a workflow-native channel for at least 18 months.
- This is a first-mover lane: be the **hardware-spec layer for every cabinet shop running modern software** in the regions Marathon already covers.
- The category is "cabinet hardware as a workflow," and Marathon gets to define what that means.

**Speaker notes:** Acknowledge Richelieu/Häfele directly — VP Sales will think about them within 30 seconds. The frame is speed and exclusivity, not size. We do not need Marathon to outspend; we need Marathon to outmove.

---

## Slide 4 — The mechanic

Three integration primitives, all already scaffolded:

- **Telemetry endpoint** — every Marathon-spec'd cabinet emits a structured event from the shop's KitchenForge instance to Marathon's BI: SKU, finish, shop ID, project size, timestamp. Marathon sees demand signal **before the PO is cut**.
- **Spec-in defaults** — Marathon's catalog is the default hardware library for every KitchenForge shop on the Marathon-channel tier. Shops can override; most won't, because the defaults are right.
- **Auto-RFQ** — when a shop's specced hardware exceeds a configurable threshold (default: $500 line, or any item not in Marathon's stocked depth), KitchenForge fires an RFQ to the nearest Marathon branch with the full BOM attached. Branch quotes back inside the shop's quoting tool.
- Net effect: Marathon becomes **structurally present** in the shop's quoting workflow, not a phone number they call when they remember to.

**Speaker notes:** This is the demo slide. If we get a working session after this meeting, this is what we show — telemetry firing, defaults populating, RFQ landing in a Marathon inbox. All three primitives exist in `kitchenforge_marathon` today.

---

## Slide 5 — The numbers (12-month conservative case)

- **Subscription tier:** $149/mo per shop, Marathon-channel SKU. 60/40 split (Southbrook / Marathon).
- **Rebate:** $8 USD per Marathon-spec'd cabinet, paid by Marathon to Southbrook on the ledger.
- **Year-1 conservative ramp:** ~280 shops onboarded, avg 38 cabinets/shop/month = **~$1.0M ARR** through the Marathon channel alone.
- Marathon's revenue from this is **dwarfed by the hardware pull-through it generates** — every spec'd cabinet that lands in a Marathon branch is hardware Marathon would have lost to a Richelieu order or a substitution.
- Full scenario model (conservative / base / aggressive) in the ROI calculator deliverable.

**Speaker notes:** Lead with the conservative number. Anchor on pull-through, not subscription revenue — VP Sales cares about hardware volume, not SaaS bookings. The $1M ARR is the easy story; the real story is the multiple of that in hardware orders Marathon now sees originate.

---

## Slide 6 — Proof: Southbrook is the reference shop

- `southbrookcabinetry.space` runs the exact stack we are proposing to deploy at every channel shop.
- 17 production modules. Live customer-facing storefront. Quoting, cut-spec, PLM, hardware catalog, the full surface.
- Southbrook **eats its own dogfood every day** — every kitchen our shop quotes goes through this platform.
- This is the Sternberg practical-intelligence story: the tacit shop-floor knowledge — which hinge for which overlay, which slide for which weight class, which finish hides which wood — is **encoded in the templates and exclusion rules**. We did not invent it. We captured it.
- That captured intelligence ships to every shop on the channel. Marathon's catalog rides inside it.

**Speaker notes:** This is the unique defensibility slide. Anyone can build a SaaS. Nobody else has 15 years of Southbrook's shop-floor decisions encoded in exclusion rules. That is the moat, and it ships with the platform.

---

## Slide 7 — The 90-day path

- **Days 0–30:** Joint announcement, Marathon catalog imported in full (CSV wizard exists), first 10 pilot shops from Marathon's top accounts onboarded on the house.
- **Days 31–60:** Telemetry live to a Marathon BI dashboard. First auto-RFQs firing. Weekly joint sales-ops review.
- **Days 61–90:** Pilot shops convert to paid. Marketing co-launch (case study from 2 pilot shops, joint webinar, presence at Marathon's next dealer event).
- **End-of-quarter checkpoint:** 25+ paying shops, $40K+ MRR through the channel, exclusivity clock starts.
- Southbrook funds the engineering. Marathon funds the channel motion. Both sides have skin in the first 90 days.

**Speaker notes:** A 90-day path makes this real. VP Sales hears "pilot" and "top accounts" and can immediately picture which 10 shops they would put in. That is the test. If they can name the shops, we are in.

---

## Slide 8 — The ask

- **6-month exclusivity** in the cabinet-hardware category on the KitchenForge channel. No Richelieu, no Häfele, no in-house buildouts during the window.
- **Joint go-to-market commitment:** co-branded launch, Marathon sales team trained on the platform, KitchenForge included in Marathon's dealer-onboarding kit.
- **Catalog access:** full Marathon SKU master with attributes (finish, dimension, stocking depth by branch) under NDA. We've already imported the partner record and 20 finishes — give us the rest.
- **One executive sponsor on each side.** VP Sales or VP Marketing for Marathon. Southbrook's principal for us.
- **Decision target: 14 days from today.** Pilot shops named. Catalog handoff scheduled. Channel SKU live by August.

**Speaker notes:** Be opinionated on the timeline. This pitch loses energy fast if it gets routed into a Q3 "evaluation." Ask for the executive sponsor and the 14-day decision in the room. If they push back on exclusivity, the fallback is 90-day exclusive on the pilot cohort with right-of-first-refusal on category at month 6.
