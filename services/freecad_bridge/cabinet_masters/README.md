# Cabinet Master Generators (FreeCAD headless)

Python scripts that FreeCAD's `freecadcmd` runs to produce the six canonical
parametric cabinet masters as `.FCStd` files. The scripts **are** the
parametric masters — the `.FCStd` files they emit are reproducible artefacts.

## The six masters

| # | Family | Generator | Notes |
|---|--------|-----------|-------|
| 1 | Base   | `master_base.py`   | Box + door + adjustable shelf + toe-kick |
| 2 | Wall   | `master_wall.py`   | Box + door + adjustable shelf, no toe-kick |
| 3 | Drawer Bank | `master_drawer_bank.py` | Box + N drawer fronts + interior runners |
| 4 | Tall   | `master_tall.py`   | Pantry / oven base; tall box + 1-2 doors |
| 5 | Corner | `master_corner.py` | L-shaped carcass + bifold door |
| 6 | Vanity | `master_vanity.py` | Base with plumbing cutout on the back |

## How they run

Each generator is invoked the same way:

```
freecadcmd master_base.py -- '<spec_json>'
```

Where `spec_json` is:

```json
{
    "width_mm":  600,
    "height_mm": 720,
    "depth_mm":  580,
    "door_count": 1,
    "output_path": "/srv/output/masters/base_600x720x580.FCStd"
}
```

Defaults match Peter Tuschak's NF14 dimensions for the most common SKU per
family. Override per-call when generating a non-default master.

`generate_all.py` runs every master with its default dimensions and writes
the .FCStd files into a single directory — that's the smoke-test entry
point and the source of the six "canonical" masters the SAMI memory
references.

## Why scripts, not hand-built .FCStd files

A `.FCStd` is a binary zip of XML topology + brep faces. Hand-building the
six masters in the FreeCAD GUI works, but the result is not reproducible:
the moment Peter Tuschak signs off on a new panel formula in
`shared/southbrook_dims.py`, every hand-built master needs to be re-opened
and re-saved manually.

These generator scripts make the six masters **derivable**:

* `shared/southbrook_dims.py` is the single source of panel geometry.
* The scripts call its `panel_cut_list()` and place each panel cut.
* Regenerating after a dims update is one `python generate_all.py` away.

The output `.FCStd` files still open in FreeCAD GUI normally — engineers
can hand-tweak them, add fillets, drop in real hardware models, etc. The
*next* regeneration overwrites those tweaks; that's the point. The
generators are the contract; the .FCStd files are derived artefacts.

## Smoke test (Module 2 G1-adjacent)

The generators import `shared.southbrook_dims` which is the same module the
G1 BoM-contents gate asserts against. If G1 stays green, the master
geometry stays in sync with the BoM math by construction.
