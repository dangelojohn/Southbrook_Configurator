---
course: 17
chapter: 17.3
title: Sales — Generate a 3D Render and Spec Sheet PDF
duration: 3
audience: Sales rep about to send a quote PDF to a customer
jtbd: generate a 3D render and spec sheet PDF
department: Sales
custom_modules: southbrook_estimating, southbrook_estimating_website, southbrook_freecad_bridge
---

# Sales — Generate a 3D Render and Spec Sheet PDF

## When you use this

Customer wants to see the kitchen, not read line items. The platform
auto-renders a 3D shot + Signature-Series styled PDF on every Save. This
lesson is the recovery procedure for the times it doesn't.

## How rendering normally happens

On *Save* of the Order Builder, the platform fires three async jobs:

1. **3D scene snapshot** — `southbrook_estimating_website` generates a
   Three.js scene + bakes a runtime thumbnail per cabinet line (Tier-2 image
   cascade, see Prodboard manifest §11).
2. **FreeCAD render** — `southbrook_freecad_bridge` calls headless FreeCAD
   to produce a PDF + STEP + screenshots per Manufacturing Order, attached
   to the MO once it's confirmed.
3. **Signature Series PDF** — QWeb report
   `southbrook_estimating.signature_spec_sheet` renders from the SO; lives
   on the SO chatter immediately, also emailable via the *Print → Spec
   Sheet* dropdown.

## When the 3D image is missing on the PDF

- Check the SO chatter for a `_spec_for_bridge` error. The FreeCAD bridge
  reads its spec from product-template defaults in Phase 1; a brand-new
  template without defaults will show "rendering pending" instead of an
  image (see lesson 4.3 audit note #10).
- Manually re-trigger: open the MO once it exists, *Cog → Re-render via
  FreeCAD*. Round-trip is ~8 seconds at current settings.

## When the spec sheet PDF is wrong

- The PDF is regenerated on every print. Edit the SO header (customer,
  channel, zone) and re-print — never edit the PDF.
- For pricing mismatches, check the resolved pricelist on the header. If
  it shows the customer's channel correctly, the issue is upstream of the
  PDF.

## Common gotchas

- **3D never loads on mobile** — by design. Customer-side mobile shows the
  2D card stack, not the WebGL planner. Brief.
- **PDF takes 5+ seconds** — first-render hits the FreeCAD bridge, which
  is slow. Subsequent prints are <1s (cached).

## Deep dive

→ Course 4 lesson 4.3 *FreeCAD Bridge*
→ Course 5 lesson 5.4 *Configurator UX Tweaks*
