---
course: 17
chapter: 17.11
title: Design — Update the FreeCAD Master Template
duration: 5
audience: Designer / ECO engineer updating the parametric carcass template
jtbd: update the freecad master template
department: Design / Engineering
custom_modules: southbrook_freecad_bridge
---

# Design — Update the FreeCAD Master Template

## When you use this

A new construction rule, a hardware brand switch, or a corner-detail change
that affects every future render. The master FCStd is the source of every
3D image the platform ever shows.

## Where the master lives

`/share/CACHEDEV3_DATA/Container/southbrook/freecad-data/master.FCStd` on the
QNAP. Bridge container has it read-only mounted at
`/data/master.FCStd` (RO mount fix from
`southbrook_freecad_bridge_deploy_recipe.md` — never edit live).

## The safe edit flow

1. **Open the master in desktop FreeCAD.** v0.21+. Save As → working copy
   on your laptop first; never edit the live file.
2. **Edit parametrically.** Use Spreadsheet workbench — every dimension /
   feature MUST link to a named cell. If you hard-code a number, the
   bridge can't parameterise it for downstream cabinets.
3. **Test locally.** Open a sample config in FreeCAD with override
   values; verify the geometry updates as expected.
4. **Save.** Validate that the file size hasn't ballooned (delete unused
   bodies; FreeCAD keeps them otherwise).
5. **Promote.** Coordinate with sysadmin (lesson 17.40 / deploy recipe) to
   rsync the new master into the QNAP path. The bridge image needs no
   rebuild — it reads the file at render time.

## What you CAN'T rename

Parameter names referenced by the bridge:
- `width_mm`, `height_mm`, `depth_mm`
- `door_count`, `hinge_side`
- `box_material_code`, `door_style_code`, `finish_code`
- `gable_left`, `gable_right`, `finished_side_left`, `finished_side_right`

These are wired into the bridge code; renaming them breaks every render.

## Common gotchas

- **Render comes out blank** — the master file is loadable but the bridge
  can't find the parameter map. Check `services/freecad_bridge/` logs.
- **Render dimensions are off by 25.4** — the master is set to inches; the
  bridge expects mm. Switch the file's unit settings under *Edit →
  Preferences → Units*.
- **Render takes 30s instead of 8s** — the master has stale geometry
  that's being recomputed. Open in desktop FreeCAD, *Tools → Edit
  parameters* + recompute all, save clean.

## Deep dive

→ Course 4 lesson 4.3 *FreeCAD Bridge*
