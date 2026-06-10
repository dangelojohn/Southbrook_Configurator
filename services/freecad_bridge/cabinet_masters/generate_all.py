# SPDX-License-Identifier: LGPL-3.0-only
"""Smoke-test driver: regenerate every canonical master with its
default dimensions.

Invocation::

    freecadcmd generate_all.py -- '<output_dir>'

If the spec arg is omitted, output goes to /srv/output/masters/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Sibling generators
import master_base
import master_wall
import master_drawer_bank
import master_tall
import master_corner
import master_vanity

GENERATORS = [
    ("base",         master_base),
    ("wall",         master_wall),
    ("drawer_bank",  master_drawer_bank),
    ("tall",         master_tall),
    ("corner",       master_corner),
    ("vanity",       master_vanity),
]


def main(output_dir: str = "/srv/output/masters") -> dict:
    written = {}
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    for name, mod in GENERATORS:
        spec = dict(mod.DEFAULTS)
        spec["output_path"] = str(Path(output_dir) / f"{name}_default.FCStd")
        try:
            path = mod.build(spec)
            written[name] = {"ok": True, "path": path}
        except Exception as exc:  # pragma: no cover — logged for visibility
            written[name] = {"ok": False, "error": str(exc)}
    print(json.dumps(written, indent=2))
    return written


# freecadcmd does NOT set __name__ to "__main__" — invoke main()
# unconditionally so the smoke driver always runs every generator.
target = sys.argv[-1] if len(sys.argv) > 1 and not sys.argv[-1].endswith(".py") else "/srv/output/masters"
main(target)
