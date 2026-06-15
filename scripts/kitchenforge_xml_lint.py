#!/usr/bin/env python3
"""XML well-formed check across kitchenforge_* addons.

Standalone so the `make lint` recipe can call it without smuggling a Python
script through Make's recipe-line quoting (which breaks list-comprehension
scoping for the `fail` flag).
"""
import glob
import sys

try:
    from lxml import etree
except ImportError:
    print("lxml not installed — pip install lxml", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    fail = 0
    paths = glob.glob("addons/kitchenforge_*/**/*.xml", recursive=True)
    for path in paths:
        try:
            etree.parse(path)
        except Exception as exc:  # noqa: BLE001 — any parse error is a lint fail
            print(f"XML FAIL: {path}: {exc}")
            fail = 1
    if fail == 0:
        print(f"XML OK: {len(paths)} file(s) parsed cleanly")
    return fail


if __name__ == "__main__":
    sys.exit(main())
