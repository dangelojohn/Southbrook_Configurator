#!/usr/bin/env python3
"""
scripts/lint-owl-expr.py — fail on OWL tokenizer violations in t-* attrs.

Catches two bug classes that pass server-side XML lint and Odoo module install
but throw OwlError at browser-side template-compile time:

1. Bare-word logical operators (or / and / not) inside t-* attribute
   expressions. Python and legacy server-side QWeb accept these; OWL's
   restricted JS tokenizer treats them as stray identifiers.
2. JavaScript regex literals (/pattern/flags) inside t-* attribute
   expressions (non-attf only). OWL's tokenizer doesn't understand `/`
   in expression context.

Both bug classes hit Southbrook three times in <12 hours on 2026-06-22
(see memory note owl-tokenizer-constraints): configurator-ux f05b99d,
mrp_pm kanban f3d13dd / ab45954.

Scope:
- OWL-compiled contexts only:
    * Any XML file under .../static/src/...
    * Inside <templates>...</templates> blocks of view files (kanban/etc.)
- Server-side QWeb is intentionally NOT scanned: PDF reports, mail
  templates, website portal templates with <template> (singular) — these
  use the Python QWeb sandbox where or/and/not are valid.
- Vendored OCA modules are skipped per CLAUDE.md "What you do not touch".

Per-attribute rules:
- t-attf-* values are STRING TEMPLATES with {{...}} / #{...} interpolation
  (URLs, class strings, style strings). Word-op check applies only inside
  interpolations; regex-literal check is skipped (URL paths contain /).
- All other t-* values are pure expressions; both checks apply.

Usage:
  ./scripts/lint-owl-expr.py [PATH ...]    # PATHs default to addons/

Exit:
  0  all clean
  1  at least one violation
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# OWL t-* attributes that carry JS expressions.
T_EXPR_ATTRS_EXACT = frozenset({
    "t-if", "t-elif", "t-out", "t-esc", "t-att",
    "t-attf", "t-value", "t-foreach",
})
T_EXPR_ATTR_PREFIXES = ("t-att-", "t-attf-", "t-on-")

# Vendored OCA modules from CLAUDE.md § "What you do not touch".
# Listed by their addon-directory basename.
VENDORED_ADDONS = frozenset({
    "product_configurator",
    "product_configurator_mrp",
    "product_configurator_sale",
    "website_product_configurator",
})

# Per-line attribute match. (Multi-line t-attr values are uncommon enough to
# accept the false-negative; the same expressions usually appear on one line
# elsewhere.)
ATTR_RE = re.compile(
    r"""\b(t-[a-zA-Z][a-zA-Z0-9_-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')"""
)

# Bare-word logical operators with word-boundaries on both sides. Identifiers
# like 'order', 'format', 'cannot' are NOT matched.
WORD_OP_RE = re.compile(r"\b(or|and|not)\b")

# Rough JS regex literal: /pattern/flags. Negative lookbehind avoids matching
# after \w (identifier) or / (comment). Body excludes newline and unescaped
# slash; supports backslash escapes. Optional standard regex flags follow.
REGEX_LIT_RE = re.compile(r"(?<![\w/])/(?:\\.|[^\\/\n])+/[gimsuy]*")

# String literals to strip out of the expression before scanning. We strip both
# 'single' and "double" quoted strings so the word 'or' inside a string literal
# (e.g. <t t-out="'orange or banana'"/>) doesn't trigger a false positive.
STRING_LIT_RE = re.compile(r"'[^']*'|\"[^\"]*\"")

# {{...}} and #{...} interpolation blocks inside t-attf-* string templates.
INTERP_RE = re.compile(r"\{\{([^}]*)\}\}|#\{([^}]*)\}")

# OWL kanban-style record access. ONLY OWL templates use this pattern;
# server-side QWeb has no `record.<field>.raw_value` / `.value` accessor.
# Detection signal for inherit-view files that xpath into a parent kanban's
# <templates> block: the source file has no <templates> wrapper but its
# injected content runs in OWL context after view combination.
OWL_RECORD_RE = re.compile(r"\brecord\.[a-zA-Z_][a-zA-Z0-9_]*\.(?:raw_value|value|domain)\b")


def is_t_expr_attr(name: str) -> bool:
    if name in T_EXPR_ATTRS_EXACT:
        return True
    return any(name.startswith(p) for p in T_EXPR_ATTR_PREFIXES)


def is_vendored(path: Path) -> bool:
    parts = path.parts
    if "addons" not in parts:
        return False
    idx = parts.index("addons")
    if idx + 1 >= len(parts):
        return False
    return parts[idx + 1] in VENDORED_ADDONS


def is_static_src(path: Path) -> bool:
    s = str(path).replace("\\", "/")
    return "/static/src/" in s


def owl_line_ranges(lines):
    """Return list of (start, end) inclusive 1-based line ranges that are OWL-
    compiled. For files under static/src/, the whole file. For view files with
    <templates> blocks, the contents of each such block. Empty list → not OWL."""
    ranges = []
    in_block = False
    block_start = None
    for lineno, line in enumerate(lines, 1):
        if not in_block and "<templates" in line:
            in_block = True
            block_start = lineno
        if in_block and "</templates>" in line:
            ranges.append((block_start, lineno))
            in_block = False
            block_start = None
    return ranges


def violations_for_attr(name, value):
    """Yield (kind, fix) tuples for a single t-* attribute value."""
    if name.startswith("t-attf"):
        # String template: only {{...}} / #{...} interpolations are expressions.
        # Regex-literal check skipped (URL paths contain /).
        for m in INTERP_RE.finditer(value):
            expr = m.group(1) if m.group(1) is not None else m.group(2)
            stripped = STRING_LIT_RE.sub("", expr)
            wm = WORD_OP_RE.search(stripped)
            if wm:
                yield (f"word operator '{wm.group(1)}' inside interpolation",
                       "use ||, && (XML-escape as &amp;&amp;), !")
    else:
        stripped = STRING_LIT_RE.sub("", value)
        wm = WORD_OP_RE.search(stripped)
        if wm:
            yield (f"word operator '{wm.group(1)}'",
                   "use ||, && (XML-escape as &amp;&amp;), !")
        rm = REGEX_LIT_RE.search(stripped)
        if rm:
            yield ("JS regex literal",
                   "use string methods (indexOf, startsWith, substring)")


def scan_file(path: Path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as exc:
        print(f"{path}: cannot read ({exc})", file=sys.stderr)
        return

    if is_static_src(path):
        ranges = [(1, len(lines) + 1)]
    else:
        ranges = owl_line_ranges(lines)
        if not ranges:
            # No literal <templates> block. Inherit-view escape hatch: if the
            # file uses OWL-only record.X.{raw_value,value,domain} access, the
            # whole file is OWL after view combination (xpath into a parent
            # kanban's <templates>).
            if OWL_RECORD_RE.search("".join(lines)):
                ranges = [(1, len(lines) + 1)]
            else:
                return  # Server-side QWeb only; skip.

    def in_owl_range(ln):
        return any(s <= ln <= e for s, e in ranges)

    for lineno, line in enumerate(lines, 1):
        if not in_owl_range(lineno):
            continue
        for match in ATTR_RE.finditer(line):
            name = match.group(1)
            if not is_t_expr_attr(name):
                continue
            value = match.group(2) if match.group(2) is not None else match.group(3)
            for kind, fix in violations_for_attr(name, value):
                yield (lineno, name, value, kind, fix)


def iter_xml(targets):
    for target in targets:
        if not target.exists():
            print(f"warning: {target} does not exist", file=sys.stderr)
            continue
        if target.is_file():
            if target.suffix == ".xml" and not is_vendored(target):
                yield target
        else:
            for f in sorted(target.rglob("*.xml")):
                if not is_vendored(f):
                    yield f


def main(argv):
    if any(arg in ("-h", "--help") for arg in argv[1:]):
        print(__doc__)
        return 0

    targets = [Path(p) for p in argv[1:]] if len(argv) > 1 else [Path("addons")]
    total = 0
    files_seen = 0
    files_with_violations = 0

    for f in iter_xml(targets):
        files_seen += 1
        violations = list(scan_file(f))
        if violations:
            files_with_violations += 1
            for lineno, name, value, kind, fix in violations:
                print(f'{f}:{lineno}: {kind} in {name}="{value}"')
                print(f"    fix: {fix}")
                total += 1

    if total:
        print(
            f"\nFAIL: {total} OWL violation(s) across {files_with_violations} "
            f"file(s) (scanned {files_seen} XML files in OWL contexts).",
            file=sys.stderr,
        )
        print("See memory note: owl-tokenizer-constraints", file=sys.stderr)
        return 1

    print(
        f"OK: no OWL tokenizer violations "
        f"({files_seen} XML files scanned, OWL contexts only)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
