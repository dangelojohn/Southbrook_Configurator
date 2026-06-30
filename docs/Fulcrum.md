# Fulcrum Pro vs Southbrook — Design Audit & Carry-Over Recommendations

> Competitor design audit of [fulcrumpro.com](https://fulcrumpro.com) against the
> Southbrook trade portal, with prioritized recommendations for design elements
> to adopt.
>
> Authored 2026-06-29. Sources at end of doc.

---

## Part 1 — Fulcrum's design language (synthesized from 6 page fetches)

Fulcrum sells cloud manufacturing software (Archie AI + 10 product modules) to
small/medium shops. The site reads as **confident enterprise SaaS that has been
carefully de-corporatized**: it puts named humans, conversational headlines, and
screenshots of real product UI in front of every value proposition.

| Dimension | Fulcrum's move |
|---|---|
| **Palette** | White / off-white backgrounds, dark navy-charcoal text, teal/cyan interactive accents, gold/warning yellow for compliance badges only. No warm cream, no brand-color overload. |
| **Typography** | Clean modern sans-serif (likely system fonts or a similar grotesque). Aggressive size variation — 56-72px hero headlines down to 14px micro-copy. Limited weights but heavy use of leading + tracking. |
| **Whitespace** | Deliberately low-to-mid density. Sections are tall, vertically padded; each one delivers a single idea. |
| **Hero pattern** | Tagline ("Manufacturing Software That Feels Like The Future" / "Work together, win together") → product screenshot anchor → primary CTA ("Demo Fulcrum") → secondary text CTA. No image carousel — one big screenshot. |
| **Feature tiles** | Icon (monochrome SVG) + benefit headline + 1-sentence body + verb-driven link ("Go digital," "Streamline nesting work"). Repeated 10× in a grid for the product ecosystem. |
| **Comparison pattern** | "Old Software vs Fulcrum" repeats 5× down the /why page. Red ✕ on legacy claims, checkmark + answer on Fulcrum side. Whimsy weapon: the "spinning wheel of doom" gif represents legacy ERP frustration. |
| **Trust signals** | (a) Named team headshots ("Here for you every step of the way" — 10 named Launch staff with photos) (b) G2 5★ review pull-quotes (c) customer logo carousel repeated 2× on /c/operations (d) ITAR / CMMC 2.0 / ISO 9001 / AS9100D badges, always together (e) stat metrics in the hero — "3.6× faster response," "24% revenue growth," "80% faster implementation" |
| **Implementation visualization** | 4-phase timeline: Flag → Wrench → Checkbox → Rocket. Each phase is one icon + one sentence. No Gantt, no spreadsheet. |
| **Integrations** | Filterable grid by category (Accounting / CAD-CAE-CAM / CRM / Shipping / Nesting / etc.). Each tile is logo + name + 1-sentence purpose. |
| **Navigation** | Mega-menu, organized in 4×3 logical groupings under each top-nav item. Sticky header. "Schedule Demo" always visible top-right. |
| **CTA discipline** | Same primary CTA verb ("Demo Fulcrum" / "Schedule Demo") appears in header, hero, every feature section, mid-page form module, and footer. Secondary CTAs are always text+arrow ("Learn more →"). |
| **Audience pages** | `/c/operations`, `/lp/manufacturing-software`, `/sheet-metal-fabrication-software`, `/manufacturing-software/job-tracking`. Each is fully designed, not a stub. Customer-logo carousel repeats per page. |
| **Imagery** | Zero stock photos. Real product screenshots (neumorphic-soft UI), real team photos in casual settings, sketched wave graphics + retro "spinning wheel" icons for visual breaks. Aspirational without being precious. |
| **Tone** | Conversational and benefit-led: "Paper is dead," "duct-taped for 30 years," "Master the Chaos," "Quote to Win." Avoids enterprise jargon. Persona-aware. |
| **Distinctive UI** | Neumorphic soft-shadow aesthetic (browser logo + UI). FAQ accordion at the bottom of every product page. Numbered 1-2-3-4 feature carousel (e.g. job-tracking page). Department-grouped feature lists ("Sales / Production / Finance"). |

### Detailed per-page notes

**Homepage** — Sticky horizontal nav with mega-menu dropdowns (Archie / Product
/ Why / Start). Hero: "Work together, win together" with explanatory subhead +
"Demo Fulcrum" CTA + product screenshot showing job costing UI. Sections flow:
hero → "Paper is dead" → "On-time delivery on autopilot" → "Know exact job
costs" → "Everything's connected" (10-module grid) → Launch/implementation team
photos → customer testimonial video → demo CTA → footer.

**/why-fulcrum-manufacturing** — Repeats "Old Software vs Fulcrum" 5× across
Support, Pricing, Infrastructure, Integration, Technology. Red ✕ on legacy
claims paired with Fulcrum's answer + supporting copy + linked resources. Uses
white text on dark backgrounds for the "Old Software" panels. Sketched
Japanese wave graphics + the retro "spinning wheel of doom" provide visual
breaks and humor.

**/manufacturing-software/job-tracking** — Hero opens with "A digital traveler
to empower operators and track WIP." Four-column numbered screenshot carousel
(1-4) showing labor/machine cost tracking, inventory picking, nesting
workflow, live order progress. Secondary carousel shows hardware integration
(scanning, picking, label printing). FAQ accordion with chevron icons at
bottom. Feature storytelling uses operational scenarios ("Too many meetings,"
"Can't instantly reply to customers") instead of feature specs.

**/lp/manufacturing-software** — Announcement banner ("IMTS Chicago, Booth
#135459") → livestream teaser → hero "Manufacturing Software That Feels Like
The Future" over large product screenshot → mid-page modal form ("Take a
personalized self-guided tour" — single company-name field + privacy consent +
submit) → four product capability sections (Scheduler, Quoting, Job Tracking,
Inventory) → FAQ accordion (6 questions) → footer.

**/fulcrum-integrations** — Filterable grid by category (Accounting, Analysis,
CAD/CAE/CAM, CRM, Ecommerce, Machine Monitoring, Shipping, Tax, Quoting,
Nesting, Other) + Reset. Each card: company logo (left-aligned) + integration
name + 1-2 sentence description + "Learn more" link + close icon. Top banner
"Let It Flow" with tagline about eliminating data gaps. FAQ section addresses
API and implementation questions. ~40+ partner integrations total.

**/erp-implementation** — Hero "Get going in weeks, not years" with positioning
against legacy implementations ("80% faster"). 10 professional headshots of
named Launch Team members (Damien, Madison, Joe, Ross, Jen, Maddie, Patricia,
Yurika, Sandra, Pico) under "Here for you every step of the way." Four-phase
implementation roadmap with icon timeline: Flag → Wrench → Checkbox → Rocket.
G2 reviews with 5-star ratings; "Average response time is two hours — 3.6×
faster than typical SaaS." Three support tiers (direct, dedicated account
manager, community).

**/c/operations** — Hero opens with "24% revenue growth" stat. Customer logo
carousel (20+ manufacturing brands). 6 interconnected workflow scenarios.
Feature deep-dives paired with product UI screenshots (operation lists, time
trackers, quality checkpoints, picking screens). Role-specific workflows for
sales, engineers, operators, purchasing. Compliance language throughout (ISO
9001, AS9100, CMMC 2.0, ITAR). Logo carousel repeats at end, emphasizing
volume.

---

## Part 2 — Southbrook today (current state from design-tokens audit)

| Dimension | Southbrook today |
|---|---|
| **Palette** | TWO live palettes. Legacy "Signature Series" (walnut `#6b3f2a`, linen `#f4ede2`, sky `#2b4f6b`, ink `#1a1814`) silently rebound at `:root` to the 2026 "Trade Portal" cool palette (taupe `#A9876B`, slate-blue `#5B7C99`, gold `#C89B5A`, blue `#2F57C4`, ink-soft `#2F3B52`, surface `#F6F8FB`). Hard contract: gold buttons use **ink text both themes** (WCAG). |
| **Typography** | Roboto Flex + JetBrains Mono (legacy), Inter (new BEM). Variation axes (`opsz`, `wght`) are used — sophisticated, but inconsistent with Fulcrum's "one weight, two sizes" simplicity. |
| **Geometry** | Tiny 2-4px radii (legacy OWL chrome), 9-12px radii (new BEM components). Hard 1px `--sb-rule` outlines everywhere — opposite of Fulcrum's soft neumorphic shadows. |
| **Layout** | Three-pane app shell (`/kitchen-planner` = 58px rail / 394px catalog / 1fr viewport), 8-col Order Builder lines grid, 5-cell header strip. Dense, mono-numeric, tabular-nums. Engineered for power-users. |
| **Marketing surface** | TINY. Just `/` (homepage), `/commercial` (sub-page), branded login. **No** per-channel pages despite 6 documented channels (dealer/tradesperson/kd/bigbox/refacing/retail), no team page, no case studies, no integrations page, no FAQ page, no comparison page. |
| **Hero** | Walnut card anchor on the right (28px shadow), 56px walnut headline on left with italic sky-blue accent. Primary CTA "Design Your Kitchen →" + ghost "Sign In". One mono meta line. **No product screenshot anchor.** |
| **Feature row** | 3-up cards with 56px sky-tinted circular FontAwesome icons. Generic copy, no screenshots. |
| **CTA strip** | One repeat of the hero CTA at the bottom. That's the only repeat. |
| **Trust signals** | **None on marketing.** No team photos, no customer logos, no testimonials, no compliance/insurance badges, no stat metrics. |
| **Comparison patterns** | None. |
| **Navigation** | Flat. No mega-menu. |
| **Theme architecture** | Dark mode opt-in via fixed-position toggle (top:70px, right:12px). OS preference intentionally ignored. Anti-FOUC inline script in `<head>`. |
| **Channel system** | Sophisticated `.sb-channel-{dealer,tradesperson,kd,bigbox,refacing,retail}` colour-coding exists in the Order Builder but is **never surfaced on marketing**. Each channel deserves its own landing page like Fulcrum's `/c/operations`. |
| **Implementation/onboarding marketing** | Not present. The whole onboarding story (Order Builder → Room Setup → 3D config → Send to Production) exists in product, but the marketing site doesn't tell it. |

### Design tokens reference (current)

**Brand colors (new "Trade Portal 2026" — authoritative):**

```
Brand:    --sb-taupe #A9876B  --sb-taupe-dark #8A6B52  --sb-slate-blue #5B7C99  --sb-ink-soft #2F3B52
Actions:  --sb-gold #C89B5A   --sb-gold-hover #B5883F   --sb-blue #2F57C4   --sb-blue-hover #2546A6
Surfaces: --sb-bg #FFFFFF     --sb-surface #F6F8FB
          --sb-panel-grad: linear-gradient(160deg, #F3F5F9, #E6EAF1)
          --sb-border #D6DAE3
Status:   --sb-success #1E9E6A   --sb-success-bg #E6F7EE
          --sb-warn-bg #FBF3D6   --sb-warn-border #E7CE7A   --sb-danger #C0492F
```

**Radii / shadows / motion (the soft-depth tokens Fulcrum-style cards need
already exist):**

```
--sb-radius-card 12px
--sb-radius-btn 9px
--sb-radius-pill 20px
--sb-shadow-card 0 1px 3px rgba(29,36,51,.08), 0 8px 24px rgba(29,36,51,.06)
--sb-focus-ring 0 0 0 3px rgba(47,87,196,.45)
--sb-focus-ring-gold 0 0 0 3px rgba(200,155,90,.45)
--sb-easing cubic-bezier(0.4,0,0.2,1)
--sb-dur-fast 120ms  --sb-dur 200ms  --sb-transition 0.14s ease-in-out
```

---

## Part 3 — Carry-over recommendations, ranked by impact

### Tier 1 — adopt verbatim (biggest gap, lowest design risk)

**1. Per-channel landing pages.** Southbrook already segments
dealer/tradesperson/KD/bigbox/refacing/retail in code with distinct colours.
Mirror Fulcrum's `/c/operations`, `/sheet-metal-fabrication-software`,
`/lp/manufacturing-software` pattern: build `/trade/dealer`, `/trade/kd-cabinet-shop`,
`/trade/refacing`, `/trade/big-box`, plus one customer landing (`/`). Each
gets its own hero stat, its own pull-quote, its own product-screenshot anchor
(Order Builder line-grid for dealers, 3D viewport for retail). Token reuse
means each page costs hours, not days.

**2. Stat-driven hero metrics.** Replace the homepage walnut-card "Signature
Series" anchor with three live numbers: lead time, average quote turnaround,
signed dealer count. Fulcrum's "24% revenue growth / 3.6× faster / 80%
faster" is the model. Use the mono `--sb-mono-value` 28px style that already
exists — perfect fit.

**3. Trust band: customer logos + compliance badges.** Add a horizontal-scroll
logo carousel just below the hero (dealer logos, real installs). Below that,
the existing channel-colour pills can become a "shops we serve" band. Add
any earned compliance/insurance/affiliation badges (KCMA, NKBA membership,
etc.) in a single trust strip — Fulcrum keeps these to one row, never two.

**4. "Old way / Southbrook way" comparison section.** Cabinetry has a vivid
legacy: showroom visits, paper quotes, weeks-long lead times, no real-time
pricing. Steal Fulcrum's 5× repeat pattern: 5 paired rows ("Showroom-only" →
"Configure from anywhere," "PDF quotes" → "Live 3D quote with seed price,"
"6-week lead" → "Production booking visible at quote time," "No design data"
→ "Spec sheet + cut list auto-generated," "Custom = uncertain" → "Mission
Control validation pre-fab"). Use existing `.sb-card` + `.sb-note--seed`
styling. Adds a high-conversion section in 1 sprint.

### Tier 2 — adapt to Southbrook's voice

**5. Four-phase customer journey visualization.** Fulcrum has Flag → Wrench →
Checkbox → Rocket. Southbrook should have: Design (sketch icon) → Configure
(Order Builder icon) → Approve (signature icon) → Build (workshop icon). The
OWL `.o_owl_stages` chevron clip-path component already renders 5 stages
with done/current states — lift it onto the marketing page as a
non-interactive showcase. Cheapest carry-over of all.

**6. Named team photography.** Fulcrum's 10 Launch Team headshots ("Damien,
Madison, Joe…") humanize. Southbrook has a real shop, real installers, real
designers — surface a team page or a "your dedicated designer" band. Use
the new `.sb-card` panel-grad surface for the photo grid; one row, 5-6
portraits, name + role + 1 line.

**7. Mega-menu navigation.** Fulcrum's mega-menu is what makes 40+ pages
discoverable. Southbrook's flat nav will choke once the per-channel and
per-style pages exist. Plan: Solutions (5 channel pages) | Products
(Signature/Premium/Refacing series) | How It Works (process / team /
showroom) | Resources (FAQ / blog / cut-spec guide) | Sign In | **Start
Designing →** (primary CTA, always visible). Use the existing
`--sb-panel-grad` surface for dropdown panels.

**8. Numbered feature carousel (1-4) for the Order Builder.** Fulcrum's
job-tracking page has a four-column numbered screenshot strip showing the
feature in action. Southbrook's Order Builder is genuinely impressive
(5-stage chevron pipeline + bulk-edit + 3D viewport + spec-sheet export). A
4-screenshot "see it in 60 seconds" carousel on the homepage converts better
than 3 generic FA-icon feature cards. **Drop the FontAwesome circle-icon
row** — Fulcrum doesn't use it because real product screenshots are 10× more
convincing.

**9. FAQ accordion at the bottom of every product page.** Cabinetry has
FAQ-rich SEO surface ("What's the lead time?" / "Are these all-plywood?" /
"Do you ship to my state?" / "What's the difference between Signature and
Premium?"). Fulcrum uses 6 questions per page. Component cost is one
expandable list + chevron icon — already styleable from existing tokens. SEO
bonus on top.

**10. Filterable integrations / capabilities grid.** Southbrook integrates
with Hermes, FreeCAD, ProductGraph, the cut-spec engine, Mission Control,
the Avery label printer. A filterable grid by category (Design / Estimating
/ Manufacturing / Logistics) tells the platform story for trade buyers in a
single page. Mirror Fulcrum's `/fulcrum-integrations` layout exactly — it's
a good interaction model.

### Tier 3 — material to consider, but DON'T blindly copy

**11. Neumorphic soft-shadow aesthetic.** Fulcrum's UI has soft outer shadows
+ light fills. Southbrook's hard 1px `--sb-rule` outlines feel more
architectural / blueprint, which suits a cabinetmaker. Don't replace the
borders globally — but DO add the
`--sb-shadow-card 0 1px 3px + 0 8px 24px` (already in tokens!) to homepage
feature cards and dealer logo tiles to add Fulcrum-like soft depth where it
doesn't fight the engineering aesthetic.

**12. Conversational headlines.** Fulcrum's "Paper is dead" / "Master the
Chaos" / "Quote to Win" voice is loose and punchy. Southbrook positions as
premium custom — "Custom kitchen cabinets, designed online." is more
on-brand than "Cabinets is dead." Adopt the *structure* (short punchy
headline + 1-line subhead) without lifting Fulcrum's specific voice.

**13. Whimsy graphics (spinning-wheel-of-doom).** Don't. They work for
Fulcrum because the target audience (machine-shop owners) shares the joke.
Southbrook's audience includes interior-designer trade buyers and
end-customers spending $30k+ on cabinetry — a retro joke icon would erode
premium positioning.

**14. "Schedule Demo" mid-page lead-capture form.** Fulcrum's `/lp/` page has
an inline form mid-scroll. Southbrook's primary CTA is "Design Your Kitchen"
(a configurator entry, not a lead form), which is actually a stronger
conversion model — the user already self-qualifies by entering the Order
Builder. Keep the configurator-first CTA; consider adding a secondary "Talk
to a designer" inline form on `/trade/*` pages where the buying cycle is
longer.

---

## Part 4 — Concrete next-3-sprints proposal

| Sprint | Scope | Files touched | Cost |
|---|---|---|---|
| **A** | Homepage redesign: replace 3-up FA-icon row with 4-step numbered screenshot carousel of the Order Builder; add trust-band (logos + compliance pills + 3 stat metrics); add "Old way / Southbrook way" 5× comparison section | `homepage_template.xml`, `homepage.scss`, new `/static/img/screens/*` assets | 3-4 days |
| **B** | Mega-menu navigation + 5 per-channel landing pages (`/trade/dealer`, `/trade/kd`, `/trade/refacing`, `/trade/big-box`, `/trade/tradesperson`); each reuses homepage layout with channel-coloured hero, channel-specific stat metrics, channel-relevant comparison rows | New `views/nav_megamenu.xml`, `views/channel_template.xml`, `static/src/scss/channel.scss`; one website route controller per channel | 1 sprint |
| **C** | Team page (`/about/team` — designer + install + production headshots, named); FAQ accordion component (reusable, mounted at bottom of every channel page + homepage); filterable integrations grid at `/platform` | New `team_template.xml`, `faq_template.xml`, `platform_template.xml`; one OWL accordion component | 1 sprint |

All three reuse the existing token system — no new SCSS file is required at
the design-token layer, only template + per-page SCSS additions.

### Suggested first concrete step

Sprint A is the highest-leverage move: it transforms the homepage from "we
have a logo and a configurator button" into "we are a credible operating
system for custom cabinetry buying" using only template + asset work. Scope
it as a single PR against `feature/prodboard-tier-2-mi-quality`.

---

## Sources

- [Fulcrum | Cloud Manufacturing Software (homepage)](https://fulcrumpro.com/)
- [Why Fulcrum Manufacturing](https://fulcrumpro.com/why-fulcrum-manufacturing)
- [Manufacturing Job Tracking Software](https://fulcrumpro.com/manufacturing-software/job-tracking)
- [Fulcrum Pro Manufacturing Software (landing page)](https://fulcrumpro.com/lp/manufacturing-software)
- [Fulcrum Integrations](https://fulcrumpro.com/fulcrum-integrations)
- [Fulcrum Launch — ERP Implementation](https://fulcrumpro.com/erp-implementation)
- [Shop Operations](https://fulcrumpro.com/c/operations)
- WebSearch — `site:fulcrumpro.com` (URL discovery)

### Southbrook codebase references audited

- `addons/southbrook_estimating/static/src/scss/_southbrook_design_tokens.scss` (design tokens, both palettes)
- `addons/southbrook_estimating_website/static/src/scss/portal_root.scss` (3,166 lines — OWL chrome)
- `addons/southbrook_estimating_website/static/src/scss/_southbrook_design_overrides.scss` (cascade-tie resolver)
- `addons/southbrook_estimating_website/views/homepage_template.xml` + `static/src/scss/homepage.scss`
- `addons/southbrook_estimating_website/views/commercial_template.xml`
- `addons/southbrook_estimating_website/views/auth_template.xml`
- `addons/southbrook_estimating_website/views/portal_template.xml`
- `addons/southbrook_estimating_website/static/src/js/portal_boot.esm.js`
- `addons/southbrook_estimating_website/static/src/js/room_layout.esm.js`
- `addons/southbrook_estimating_website/static/src/js/room_setup_wizard.esm.js`
- `addons/southbrook_estimating_website/static/src/js/kitchen_viewport.esm.js`
- `addons/southbrook_estimating_website/views/kitchen_planner_template.xml` + `static/src/scss/planner.scss`
- `addons/southbrook_estimating_website/static/src/js/sb_theme_toggle.esm.js`
- `addons/southbrook_estimating_website/views/design_system_chrome.xml`
- `docs/CUSTOMER_TO_MANUFACTURING_FLOW.md` (canonical design rationale)
- `docs/PRODBOARD_MANIFEST.md` (layout grid §8.1, recipe grammar §5)
