---
course: 1 — Workcenter Operators
chapter: 1.1
title: What is a Southbrook Kitchen Workcenter
duration: 15 minutes
audience: Every shop-floor operator on their first day at Southbrook
prereqs: None — this is the orientation lesson
custom_modules: southbrook_mrp_kitchen_workcenters, southbrook_mrp_pm
---

# What is a Southbrook Kitchen Workcenter

## Who this lesson is for

You're new to the Southbrook shop floor and you've been told you'll work at
a station — the edge bander, the CNC, the assembly bench, the sanding line,
the paint booth. This 15-minute lesson tells you what a "workcenter" is in
Odoo, how Southbrook customised it for cabinet work, and where your station
sits in the day's flow. Every other Course 1 lesson assumes you've read this.

## Where this lives on the site

Sign in at **southbrookcabinetry.space/odoo** with your operator account.

> **Manufacturing → Configuration → Work Centers**

That's the master list of every station in the shop. The Southbrook-custom
fields show up as a "Kitchen" tab on each workcenter form.

The menu you'll spend most of your day in is the touchscreen-friendly view:

> **Manufacturing → Operations → Work Orders**

Filtered by your station, that's your queue.

## What your screen shows

Open a workcenter (e.g. **SB-EDGE Edge Bander**) and you'll see two layers:

**The Odoo native fields** — these come stock with Odoo MRP and apply to
every shop floor on earth:

- **Name** + **Code** — human label + short identifier you use in
  conversation ("I'm on SB-EDGE today").
- **Working hours** + **Time efficiency** — when the station is open, and
  how much of nominal capacity it really delivers.
- **Cost per hour** (`costs_hour`) — the dollar rate the planner uses to
  cost a job.
- **OEE target** (`oee_target`) — the Overall Equipment Effectiveness
  number your station is held to. Southbrook standard is 85%.

**The Southbrook kitchen fields** — added by
`southbrook_mrp_kitchen_workcenters`, prefixed `x_sbk_*`:

- **Station type** (`x_sbk_station_type` on `mrp.workcenter`) — the
  category your station belongs to, drawn from a fixed list of 14:
  engineering, cutting, cnc, edge_banding, drilling, sanding, finishing,
  countertop, assembly, hardware, quality, packing, subcontract, other.
  This is what the scheduler uses to figure out "this MO needs an
  edge_banding step — who's available?"
- **Bottleneck (Configuration)** (`x_sbk_is_bottleneck`) — a True/False
  flag. True means the planner treats your station as the constraint
  that decides the whole shop's daily throughput. Not the same as "I'm
  busy right now"; it's a structural decision the engineer made.
- **Supported materials** (`x_sbk_supported_material_ids`) — m2m to
  `southbrook.kitchen.material`. The materials your station can handle
  (e.g. SB-EDGE supports melamine, MDF, particle board; not solid wood).
- **Supported finishes** (`x_sbk_supported_finish_ids`) — same idea for
  paint/lacquer/waterborne finishes. Important on PAINT.
- **Max panel size** (`x_sbk_max_panel_length_mm` /
  `x_sbk_max_panel_width_mm`) — the physical envelope. A 2800mm panel
  doesn't fit on a 2500mm bed.
- **Default setup time** (`x_sbk_default_setup_time_min`) — the minutes
  the planner adds to every fresh job on this station for tool prep.
- **Changeover time** (`x_sbk_changeover_time_min`) — the minutes added
  when consecutive jobs need a tool/colour/material swap.
- **Allows parallel jobs** (`x_sbk_allows_parallel_jobs`) — True if more
  than one work order can run at once (e.g. CURE has many panels drying
  simultaneously; SB-EDGE does one at a time).
- **OEE target** (`x_sbk_oee_target`) — Southbrook overrides the native
  target per station. 0.85 = 85% = world-class threshold.

## The 14 seeded workcenters

Memorise these — they're the shop. Codes are stable; you'll see them on
every traveler and every cut spec.

| Code | Name | Station type | Bottleneck | Parallel |
|---|---|---|---|---|
| `ENG01` | Design Review / Production Engineering | engineering | No | Yes |
| `SB-SAW` | Panel Saw / CNC Nesting | cutting | **Yes** | No |
| `SB-CNC-BORE` | CNC Boring | cnc | **Yes** | No |
| `CNC02` | CNC Router 02 (Backup) | cnc | No | No |
| `DOOR-SHOP` | Door Shop | cnc | No | Yes |
| `SB-EDGE` | Edge Bander | edge_banding | **Yes** | No |
| `SB-ASSY` | Carcass Assembly | assembly | **Yes** | Yes |
| `SB-DOOR` | Door Hanging | assembly | No | Yes |
| `SB-HW` | Hardware Fitting | hardware | No | Yes |
| `SAND` | Sanding Prep | sanding | No | Yes |
| `PAINT` | Paint Booth | finishing | **Yes** | No |
| `CURE` | Cure / Dry Room | finishing | No | Yes |
| `SB-QC` | Quality Control | quality | **Yes** | No |
| `SB-PACK` | Pack & Label | packing | No | Yes |

The six **bottlenecks** are the stations the planner protects: cutting
(SB-SAW), CNC boring (SB-CNC-BORE), edge banding (SB-EDGE), carcass
assembly (SB-ASSY), paint (PAINT), and quality (SB-QC). If you work at
one of those, your idle time becomes a P0 issue on the manager's
dashboard within a shift.

## What this lesson does NOT cover

- Day-to-day operation of a specific station — see the role lessons:
  edge banding (1.2), CNC (1.3), assembly (1.4), finishing (1.5).
- Native Odoo MRP vocabulary (Manufacturing Order, Work Order, BoM,
  Routing) — covered by Odoo's own training portal.
- Logging downtime — lesson 1.6.
- Reading a cut spec from PLM — lesson 1.7.
- What the planner does with bottleneck flags — Course 2 (Production
  Planning).

## Quiz (3 short questions)

**1.** You're hired at Southbrook and told you'll be working at "SB-EDGE."
What station type is that, and is it a bottleneck?

> SB-EDGE is the Edge Bander. Its `x_sbk_station_type` is `edge_banding`
> and its `x_sbk_is_bottleneck` is True. Your idle time matters.

**2.** Your supervisor says "we need to run the backup CNC today." Which
code is that, and which primary does it back up?

> Code is `CNC02` (CNC Router 02 — Backup). It backs up `SB-CNC-BORE`
> (CNC Boring), wired through `alternative_workcenter_ids` on the
> primary so the scheduler can route to it automatically.

**3.** The paint booth (`PAINT`) is a bottleneck with `x_sbk_allows_parallel_jobs`
set to False, but the cure room (`CURE`) right next to it has the same
station type (`finishing`) and `x_sbk_allows_parallel_jobs` set to True.
Why the difference?

> Physical reality. The booth sprays one job at a time — you can't
> spray two colours in the same chamber. The cure room is a big warm
> room with racks: many panels can dry in parallel, so the planner
> can pile work there without losing throughput.
