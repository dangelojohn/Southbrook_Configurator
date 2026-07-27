#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
"""Pre-commit scanner for QWeb view traps that pass XML lint + Odoo
install validation but fail the v19 registry view-validator at upgrade
time. See `[[odoo19_column_invisible_parent_trap]]`.

Currently checks:

  1. column_invisible="parent.<field>" inside an embedded list view.
     The `parent` context resolves to the PARENT FORM's model, not
     the line's model. If the parent has no such field, registry
     rebuild fails ParseError at -u time with a truncated traceback
     the deploy script's grep filter hides.

     Fix: use per-row `invisible=` or `readonly=` (no `parent.`
     prefix) — those evaluate against the line model.

Exit codes:
  0  no issues
  1  one or more issues found

Run on all addons:  scripts/lint-xml-view-traps.py
Run on a file:      scripts/lint-xml-view-traps.py path/to/file.xml
"""
import re
import sys
from pathlib import Path


# Match: column_invisible="parent.<field>" or column_invisible='parent.<field>'
# with optional whitespace and any rich expression. The capture group is the
# referenced field name (the bit between `parent.` and the next non-word char).
PARENT_REF_RE = re.compile(
    r"column_invisible\s*=\s*[\"']\s*[^\"']*parent\.([A-Za-z_][A-Za-z0-9_]*)",
)


def scan_file(path: Path) -> list[tuple[int, str, str]]:
    """Return list of (line_no, field_name, full_line_excerpt) per hit."""
    hits = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                for match in PARENT_REF_RE.finditer(line):
                    field = match.group(1)
                    excerpt = line.strip()[:160]
                    hits.append((lineno, field, excerpt))
    except (IOError, UnicodeDecodeError):
        pass
    return hits


def collect_target_files(args: list[str]) -> list[Path]:
    """Resolve CLI args to a list of XML files."""
    if args:
        out = []
        for a in args:
            p = Path(a)
            if p.is_file() and p.suffix == ".xml":
                out.append(p)
            elif p.is_dir():
                out.extend(p.rglob("*.xml"))
        return out
    # No args: walk addons/ excluding common OCA / fixture trees.
    repo_root = Path(__file__).resolve().parent.parent
    addons_dir = repo_root / "addons"
    if not addons_dir.is_dir():
        return []
    skip_substrings = (
        "/static/",
        "/_test_fixtures/",
        "/.tox/",
        "/build/",
    )
    out = []
    for p in addons_dir.rglob("*.xml"):
        s = str(p)
        if any(skip in s for skip in skip_substrings):
            continue
        out.append(p)
    return out


def main() -> int:
    targets = collect_target_files(sys.argv[1:])
    if not targets:
        print("lint-xml-view-traps: no XML files to scan")
        return 0
    failure_count = 0
    for path in targets:
        hits = scan_file(path)
        if not hits:
            continue
        rel = path
        for lineno, field, excerpt in hits:
            failure_count += 1
            print(
                f"{rel}:{lineno}: column_invisible references "
                f"parent.{field} — `parent` resolves to the parent FORM's "
                f"model, not the line. Use per-row `invisible=` or "
                f"`readonly=` (drop the `parent.` prefix) — see "
                f"[[odoo19_column_invisible_parent_trap]]. "
                f"Excerpt: {excerpt}"
            )
    if failure_count:
        print(
            f"\nlint-xml-view-traps: {failure_count} suspicious "
            "column_invisible=\"parent.<field>\" reference(s) found.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
