---
course: 17
chapter: 17.21
title: Floor — Hardware Lookup and Install
duration: 2
audience: Assembler or hardware-station operator
jtbd: hardware lookup and install
department: Production Floor
custom_modules: southbrook_hardware_catalog
---

# Floor — Hardware Lookup and Install

## When you use this

You're mid-assembly and you need to verify the right hinge / handle /
slide for the cabinet you're working on, or you don't recognise a SKU on
the kit list.

## Where the catalog lives

**Inventory → Hardware Catalog** (menu in `southbrook_hardware_catalog`).

Read-only for floor users; search by:

- SKU (e.g. *MRTHN-H120-NS-SC*)
- Brand (Marathon, Blum, Hettich)
- Type (hinge, handle, slide, slide, leg, accessory)

## Reading a catalog entry

- **SKU code** — exact part number
- **Brand + product line** — Marathon Concealed 120° Soft-Close Negro
- **Spec PDF** — vendor's installation sheet (PDF attachment)
- **Default install pattern** — text + image showing the standard mount

## Common gotchas

- **SKU on kit list doesn't exist in catalog** — the kit was assembled
  before catalog import caught up. *Hold → Material mismatch*; CS gets
  pinged.
- **Old vs new hinge generation** — Marathon SKUs change subtly across
  generations. If the kit lists *…-NS-SC* but you've got *…-NSS-SC*,
  ask before installing.
- **No spec PDF attached** — fall back to vendor website. Catalog v1.1
  will re-import all PDFs.

## Deep dive

→ Course 5 lesson 5.3 *Hardware Catalog*
