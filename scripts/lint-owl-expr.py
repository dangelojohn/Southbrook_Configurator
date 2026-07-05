#!/usr/bin/env python3
"""
scripts/lint-owl-expr.py — fail on OWL tokenizer violations in t-* attrs.

Catches four bug classes that pass server-side XML lint and Odoo module
install but throw OwlError at browser-side template-compile (or render)
time:

1. Bare-word logical operators (or / and / not) inside t-* attribute
   expressions. Python and legacy server-side QWeb accept these; OWL's
   restricted JS tokenizer treats them as stray identifiers.
2. JavaScript regex literals (/pattern/flags) inside t-* attribute
   expressions (non-attf only). OWL's tokenizer doesn't understand `/`
   in expression context.
3. JS-style backslash-escaped quotes inside t-* attribute values
   (e.g. t-esc="x + '\\"'" thinking `\\"` escapes). In a JS backtick
   template literal `\\"` resolves to a literal `"`, which then closes
   the XML attribute prematurely. Use &quot; / &apos; XML entities
   instead. Added 2026-06-27 after the OdooIQ-supplied kitchen-3d
   addon hit it on its first mount (commit 85f8fa9 → fix 34e32fb).
4. Bare use of a JS global constructor/function NOT on OWL's compiler
   allowlist (String, Number, Boolean, JSON, Symbol, Map, Set, Promise,
   parseInt, parseFloat, isNaN, isFinite, ...). OWL's expression
   compiler special-cases a fixed RESERVED_WORDS list — Math, RegExp,
   Array, Object, Date pass through to the real global — anything else
   bare gets rewritten as a component-context property lookup instead,
   which is `undefined` for a global like `String`, throwing "Cannot
   read properties of undefined" at render time. Added 2026-07-04
   after `t-esc="String.fromCharCode(...)"` in the Room Setup wizard's
   WallDimensionsStep passed server-side XML lint + module install
   clean but crashed the OrderBuilder's owl lifecycle on every attempt
   to reach Step 2 (QA report via external E2E test agent, order
   S01360). Fix: move the call into a real JS method and reference it
   via `this._method()` in the template instead.

These bug classes hit Southbrook five times in under 6 weeks (see memory
note owl-tokenizer-constraints): configurator-ux f05b99d, mrp_pm kanban
f3d13dd / ab45954, planner_boot.esm.js (2 latent caught by JS-block
extension 2026-06-27), kitchen-3d t-esc escaped-quote 2026-06-27, Room
Setup wizard bare-`String` 2026-07-04.

Scope:
- OWL-compiled contexts only:
    * Any XML file under .../static/src/...
    * Inside <templates>...</templates> blocks of view files (kanban/etc.)
    * 2026-06-27 — inside `xml`-tagged template literals in .esm.js /
      .js files under .../static/src/... (Component.static template =
      xml`...`, plus const TEMPLATE = xml`...` and similar patterns).
      Added after two latent `and` operators inside such literals broke
      OrderBuilder mount in production despite the rest of this linter
      coming back clean. See commit 3af970d 2026-06-27.
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

# Bug class 4: JS globals NOT on OWL's RESERVED_WORDS allowlist — the
# compiler's own list (see addons/web/static/lib/owl/owl.js):
#   true,false,NaN,null,undefined,debugger,console,window,in,instanceof,
#   new,function,return,eval,void,Math,RegExp,Array,Object,Date,__globals__
# Anything else referenced bare (not as `this.X` / `obj.X` / part of a
# longer identifier) resolves to an undefined component-context property
# instead of the real global.
#
# Rather than hand-enumerate "known bad" globals (String, Number, JSON,
# ... — an open-ended, easily-incomplete list: Infinity, document,
# Reflect, WeakMap, BigInt, globalThis, btoa, etc. are just as broken and
# just as easy to reach for), this derives the check from the REAL
# allowlist structurally: this codebase's convention never uses a
# PascalCase identifier for component-local data (props/state/loop vars
# are always camelCase or snake_case), so any bare PascalCase identifier
# inside a t-* expression is almost certainly a global constructor/
# namespace reference. Exclude it only if it's actually on OWL's
# allowlist (Math, RegExp, Array, Object, Date, NaN all happen to be
# PascalCase already). A separate fixed list covers common *lowercase*
# global functions (parseInt, fetch, btoa, ...) that the PascalCase
# check can't catch structurally.
OWL_RESERVED_WORDS = frozenset(
    "true false NaN null undefined debugger console window in "
    "instanceof new function return eval void Math RegExp Array "
    "Object Date __globals__".split()
)
PASCAL_GLOBAL_RE = re.compile(r"(?<![\w.$])([A-Z][a-zA-Z0-9_]*)\b")
LOWERCASE_GLOBAL_FN_RE = re.compile(
    r"(?<![\w.$])(parseInt|parseFloat|isNaN|isFinite|encodeURIComponent"
    r"|decodeURIComponent|encodeURI|decodeURI|escape|unescape|btoa|atob"
    r"|structuredClone|fetch|setTimeout|setInterval|clearTimeout"
    r"|clearInterval|alert|confirm|prompt|globalThis"
    r"|document|navigator|location|history|localStorage|sessionStorage"
    r"|crypto|performance)\b"
)


def find_disallowed_global(stripped):
    """Return the offending identifier, or None. `stripped` has string
    literals already removed by the caller (STRING_LIT_RE.sub)."""
    for m in PASCAL_GLOBAL_RE.finditer(stripped):
        if m.group(1) not in OWL_RESERVED_WORDS:
            return m.group(1)
    m = LOWERCASE_GLOBAL_FN_RE.search(stripped)
    return m.group(1) if m else None

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
    # Bug class 3: any `\` in a t-* attr value is almost certainly a
    # JS-style escape attempt that breaks XML attribute parsing. The
    # ATTR_RE regex stops at the first `"` (or `'`), so if the captured
    # value ends in `\`, the user wrote `\"` (or `\'`) thinking it would
    # escape — but JS template-literal evaluation strips the `\` and the
    # resulting bare `"` closes the XML attribute prematurely. Apply
    # check before the per-class branch so it catches t-attf-* too.
    if "\\" in value:
        yield ("JS-style backslash escape (probably \\\" or \\')",
               "use &quot; / &apos; XML entities instead of \\\" / \\'")

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
            gd = find_disallowed_global(stripped)
            if gd:
                yield (f"bare global '{gd}' not on OWL's "
                       f"RESERVED_WORDS allowlist inside interpolation",
                       f"move the call into a component method and "
                       f"reference it via this._method()")
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
        gd = find_disallowed_global(stripped)
        if gd:
            yield (f"bare global '{gd}' not on OWL's "
                   f"RESERVED_WORDS allowlist (Math/RegExp/Array/Object/"
                   f"Date pass through; this one resolves to an "
                   f"undefined component-context lookup instead)",
                   f"move the call into a component method and "
                   f"reference it via this._method()")


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

    # Whole-text scan (not per-line): a t-* attribute value CAN span
    # multiple physical lines (a wrapped long expression). `[^"]*` /
    # `[^']*` already match across newlines regardless of re.DOTALL —
    # only iterating line-by-line was hiding that. Line number is
    # recovered from the match's start offset via newline counting, same
    # technique scan_js_file() already uses for JS-embedded templates.
    text = "".join(lines)
    for match in ATTR_RE.finditer(text):
        name = match.group(1)
        if not is_t_expr_attr(name):
            continue
        lineno = _offset_to_lineno(text, match.start())
        if not in_owl_range(lineno):
            continue
        value = match.group(2) if match.group(2) is not None else match.group(3)
        for kind, fix in violations_for_attr(name, value):
            yield (lineno, name, value, kind, fix)


# ─────────────────────────────────────────────────────────────────────
# 2026-06-27 — JS-embedded OWL template scan.
#
# Adds coverage for OWL templates written inside `xml`-tagged template
# literals in .esm.js / .js files. The XML-only scan above misses these
# because they live inside JS source. The bug class is identical:
# Python word ops + JS regex literals throw at OWL template-compile
# time in the browser.
#
# Two latent `and` operators inside such literals in portal_boot.esm.js
# broke OrderBuilder mount in production on 2026-06-27 (commit 3af970d)
# despite the XML-only scan coming back clean. This block closes the gap.
# ─────────────────────────────────────────────────────────────────────

# `xml` tagged template literal start. Anchored on a preceding non-word
# char so we don't match identifiers like `someXml\``. The opening
# backtick is captured; the matching close-backtick is found by a
# forward scan that respects escaped backticks (\`) and ${...} interp.
JS_XML_TEMPLATE_RE = re.compile(r"(?<![\w$])xml\s*`")


def _find_xml_blocks(text: str):
    """Yield (start_offset, end_offset) for each `xml`...` block in text.

    Skip escaped backticks (\\`). Respect ${...} interpolation depth so
    a `${...}` whose body contains a backtick doesn't terminate the
    outer template. OWL templates rarely use ${...} but we handle the
    case for forward-compat.
    """
    for m in JS_XML_TEMPLATE_RE.finditer(text):
        body_start = m.end()  # position right after the opening backtick
        i = body_start
        depth = 0  # ${...} nesting depth
        while i < len(text):
            ch = text[i]
            if ch == "\\":
                i += 2  # skip the escaped char (handles \` and \$)
                continue
            if ch == "$" and i + 1 < len(text) and text[i + 1] == "{":
                depth += 1
                i += 2
                continue
            if ch == "}" and depth > 0:
                depth -= 1
                i += 1
                continue
            if ch == "`" and depth == 0:
                yield (body_start, i)
                break
            i += 1


def _offset_to_lineno(text: str, offset: int) -> int:
    """1-based line number of `offset` in `text`. Cheap newline count."""
    return text.count("\n", 0, offset) + 1


def scan_js_file(path: Path):
    """Scan a .js/.esm.js file for OWL `t-*` violations inside
    `xml`-tagged template literals. Yields the same shape as
    scan_file() so the caller can pretty-print uniformly.
    """
    if not is_static_src(path):
        return  # OWL components only live under static/src/
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"{path}: cannot read ({exc})", file=sys.stderr)
        return

    for start, end in _find_xml_blocks(text):
        block = text[start:end]
        block_start_line = _offset_to_lineno(text, start)
        # Walk attribute matches relative to block, recover absolute line.
        for match in ATTR_RE.finditer(block):
            name = match.group(1)
            if not is_t_expr_attr(name):
                continue
            value = (
                match.group(2)
                if match.group(2) is not None
                else match.group(3)
            )
            # Match-relative line within the block + block's starting line.
            attr_line_in_block = block.count("\n", 0, match.start())
            lineno = block_start_line + attr_line_in_block
            for kind, fix in violations_for_attr(name, value):
                yield (lineno, name, value, kind, fix)


def iter_files(targets):
    """Yield XML + JS files for scanning. Vendored addons skipped."""
    js_suffixes = (".js", ".esm.js")
    for target in targets:
        if not target.exists():
            print(f"warning: {target} does not exist", file=sys.stderr)
            continue
        if target.is_file():
            if is_vendored(target):
                continue
            if target.suffix == ".xml":
                yield target
            elif target.name.endswith(js_suffixes):
                yield target
        else:
            for f in sorted(target.rglob("*.xml")):
                if not is_vendored(f):
                    yield f
            for pattern in ("*.esm.js", "*.js"):
                for f in sorted(target.rglob(pattern)):
                    if is_vendored(f):
                        continue
                    # rglob *.js also matches *.esm.js; dedupe by name.
                    # We rely on the (start, end) of `xml` blocks to
                    # find OWL templates — non-OWL JS just yields no
                    # matches and is silently skipped.
                    yield f


# Keep the old name as an alias so external callers (and a stale
# pre-commit hook) keep working until they're updated.
iter_xml = iter_files


def main(argv):
    if any(arg in ("-h", "--help") for arg in argv[1:]):
        print(__doc__)
        return 0

    targets = [Path(p) for p in argv[1:]] if len(argv) > 1 else [Path("addons")]
    total = 0
    files_seen = 0
    js_files_seen = 0
    files_with_violations = 0
    seen_paths = set()

    for f in iter_files(targets):
        # rglob("*.js") matches *.esm.js too — dedupe by resolved path.
        rp = f.resolve()
        if rp in seen_paths:
            continue
        seen_paths.add(rp)

        # Pick the right scanner by suffix.
        if f.suffix == ".xml":
            files_seen += 1
            violations = list(scan_file(f))
        elif f.name.endswith((".esm.js", ".js")):
            js_files_seen += 1
            violations = list(scan_js_file(f))
        else:
            continue

        if violations:
            files_with_violations += 1
            for lineno, name, value, kind, fix in violations:
                print(f'{f}:{lineno}: {kind} in {name}="{value}"')
                print(f"    fix: {fix}")
                total += 1

    if total:
        print(
            f"\nFAIL: {total} OWL violation(s) across "
            f"{files_with_violations} file(s) "
            f"(scanned {files_seen} XML + {js_files_seen} JS files in "
            f"OWL contexts).",
            file=sys.stderr,
        )
        print("See memory note: owl-tokenizer-constraints", file=sys.stderr)
        return 1

    print(
        f"OK: no OWL tokenizer violations "
        f"({files_seen} XML + {js_files_seen} JS files scanned, "
        f"OWL contexts only)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
