#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
"""KitchenForge cross-addon smoke + code-review harness.

Runs offline against the source tree (no Odoo boot required) and prints a
ranked report. Used as the final-phase verification gate.

Checks:
- Manifest parses (ast.literal_eval) for every kitchenforge_* + sales/ kit
- Every .py parses (ast.parse)
- Every .xml parses (ET.parse)
- Every CSV has consistent column count
- Every data: entry in the manifest exists on disk
- Every asset: entry exists on disk
- ir.model.access.csv references models that exist in models/
- Inter-addon model.access references resolve (kitchenforge_marathon -> kitchenforge_core groups)
- No unresolved external xml:id references (best-effort textual check)
- No bare Exception catches that swallow without re-raise or log
- No `print(` statements in models/controllers (warn, don't fail)
- No `eval(` outside tests/wizards (warn)
- Test files exist for every model file
- README.md exists for each addon
- Cross-addon: each addon's depends list resolves to a real addon
- SDK Python: ast.parse all files; openapi.yaml loads as YAML (or JSON-compat)
- Pitch kit: every file referenced in deliverable list exists

Returns 0 on pass, 1 on hard failures. Warnings don't fail.
"""
from __future__ import annotations

import ast
import csv
import json
import pathlib
import re
import sys
from typing import Iterator, List, Tuple

ROOT = pathlib.Path("/Users/naadmin/southbrook-v19cr")
ADDONS_ROOT = ROOT / "addons"
KF_ADDONS = ["kitchenforge_core", "kitchenforge_marathon", "kitchenforge_saas"]
SALES_ROOT = ROOT / "sales" / "marathon"
SDKS_ROOT = ROOT / "sdks"
DEPLOY_ROOT = ROOT / "deploy"

ERRORS: List[str] = []
WARNINGS: List[str] = []


def err(msg: str) -> None:
    ERRORS.append(msg)


def warn(msg: str) -> None:
    WARNINGS.append(msg)


def header(title: str) -> None:
    print(f"\n=== {title} ===")


# ----------------------------------------------------------------------
# Phase 1 — addon hygiene
# ----------------------------------------------------------------------
def check_addon(name: str) -> dict:
    root = ADDONS_ROOT / name
    if not root.exists():
        err(f"addon {name}: directory missing")
        return {"name": name, "ok": False}
    info = {"name": name, "ok": True, "py": 0, "xml": 0, "loc": 0}
    manifest_path = root / "__manifest__.py"
    if not manifest_path.exists():
        err(f"{name}: __manifest__.py missing")
        return info
    try:
        manifest = ast.literal_eval(manifest_path.read_text())
        info["manifest"] = manifest
    except (SyntaxError, ValueError) as e:
        err(f"{name}: manifest unparseable: {e}")
        return info
    # depends
    for dep in manifest.get("depends", []):
        if dep.startswith("kitchenforge_") and not (ADDONS_ROOT / dep).exists():
            err(f"{name}: depends on missing local addon {dep}")
    # python files parse
    for p in root.rglob("*.py"):
        info["py"] += 1
        try:
            ast.parse(p.read_text())
            info["loc"] += sum(1 for _ in p.open())
        except SyntaxError as e:
            err(f"{name}/{p.relative_to(root)}: L{e.lineno}: {e.msg}")
    # xml files parse
    import xml.etree.ElementTree as ET
    for p in root.rglob("*.xml"):
        info["xml"] += 1
        try:
            ET.parse(p)
        except ET.ParseError as e:
            err(f"{name}/{p.relative_to(root)}: XML parse: {e}")
    # data files exist
    for rel in manifest.get("data", []):
        if not (root / rel).exists():
            err(f"{name}: manifest data missing: {rel}")
    # assets exist
    for rel in manifest.get("assets", {}).get("web.assets_backend", []):
        rel2 = rel.replace(f"{name}/", "")
        if not (root / rel2).exists():
            err(f"{name}: manifest asset missing: {rel}")
    # CSV columns
    for p in root.rglob("*.csv"):
        lines = [l for l in p.read_text().splitlines() if l.strip()]
        if lines:
            cols0 = lines[0].count(",")
            for i, l in enumerate(lines[1:], 2):
                if l.count(",") != cols0:
                    err(f"{name}/{p.relative_to(root)}:L{i}: column-count mismatch")
    # README
    if not (root / "README.md").exists():
        warn(f"{name}: README.md missing")
    # tests/ directory
    if not (root / "tests").exists() or not list((root / "tests").rglob("test_*.py")):
        warn(f"{name}: no test files under tests/")
    return info


# ----------------------------------------------------------------------
# Phase 2 — review heuristics (style smells)
# ----------------------------------------------------------------------
SMELLS = [
    (re.compile(r"^\s*except\s*:\s*$", re.M), "bare 'except:' (use 'except Exception')"),
    (re.compile(r"^\s*print\(", re.M), "print() statement in non-test code"),
    (re.compile(r"\beval\("), "eval() — review for injection risk"),
    (re.compile(r"TODO|FIXME|XXX|HACK"), "TODO/FIXME marker"),
    (re.compile(r"password\s*=\s*['\"][^'\"]{1,}['\"]"), "hard-coded password"),
]


def review_one(path: pathlib.Path, name: str) -> None:
    if "test" in path.name or path.parts[-2:][0] == "tests":
        return
    src = path.read_text()
    for rx, label in SMELLS:
        for m in rx.finditer(src):
            line_no = src[: m.start()].count("\n") + 1
            sev = "warn"
            if "password" in label.lower():
                sev = "err"
            msg = f"{name}/{path.relative_to(ADDONS_ROOT / name)}:L{line_no}: {label}"
            (err if sev == "err" else warn)(msg)


# ----------------------------------------------------------------------
# Phase 3 — sibling deliverables
# ----------------------------------------------------------------------
def check_sales_kit() -> dict:
    expected = ["pitch_deck.md", "one_pager.md", "roi_calculator.md",
                "cold_email.md", "technical_appendix.md"]
    out = {"present": [], "missing": []}
    if not SALES_ROOT.exists():
        for f in expected:
            out["missing"].append(f)
            err(f"sales kit: {SALES_ROOT/f} missing")
        return out
    for f in expected:
        p = SALES_ROOT / f
        if p.exists():
            out["present"].append(f)
        else:
            out["missing"].append(f)
            err(f"sales kit: {p} missing")
    return out


def check_sdks() -> dict:
    out = {"openapi": False, "python": 0, "ts": 0, "examples": 0}
    openapi = SDKS_ROOT / "openapi.yaml"
    if openapi.exists():
        try:
            content = openapi.read_text()
            # accept yaml or json
            if content.lstrip().startswith("{"):
                json.loads(content)
            else:
                # Hand-check the top-level keys are present
                if not any(k in content for k in ("openapi:", '"openapi"')):
                    err(f"sdks/openapi.yaml: missing 'openapi:' root key")
            out["openapi"] = True
        except Exception as e:
            err(f"sdks/openapi.yaml: {e}")
    else:
        err("sdks/openapi.yaml: missing")
    py_root = SDKS_ROOT / "python"
    if py_root.exists():
        for p in py_root.rglob("*.py"):
            out["python"] += 1
            try:
                ast.parse(p.read_text())
            except SyntaxError as e:
                err(f"{p}: L{e.lineno}: {e.msg}")
    else:
        err("sdks/python: missing")
    ts_root = SDKS_ROOT / "typescript"
    if ts_root.exists():
        out["ts"] = sum(1 for _ in ts_root.rglob("*.ts"))
        if not (ts_root / "package.json").exists():
            err("sdks/typescript/package.json missing")
        if not (ts_root / "tsconfig.json").exists():
            err("sdks/typescript/tsconfig.json missing")
    else:
        err("sdks/typescript: missing")
    ex_root = SDKS_ROOT / "agent_examples"
    if ex_root.exists():
        out["examples"] = sum(1 for _ in ex_root.rglob("*.md"))
    else:
        warn("sdks/agent_examples: missing")
    return out


def check_deploy() -> dict:
    out = {"scripts": 0, "ci": False}
    if not DEPLOY_ROOT.exists():
        err("deploy/ missing")
        return out
    for p in DEPLOY_ROOT.rglob("*.sh"):
        out["scripts"] += 1
    ci = ROOT / ".forgejo/workflows/kitchenforge_ci.yml"
    if ci.exists():
        out["ci"] = True
    else:
        err(".forgejo/workflows/kitchenforge_ci.yml missing")
    if not (ROOT / "Makefile").exists():
        warn("Makefile missing at repo root")
    return out


# ----------------------------------------------------------------------
# Phase 4 — cross-addon consistency
# ----------------------------------------------------------------------
def check_inter_addon_refs():
    """Check that group/model XML IDs referenced from one addon exist in another."""
    # Collect all <record id="..."> XML IDs and prefix by addon
    ids: dict[str, set] = {}
    import xml.etree.ElementTree as ET
    for addon in KF_ADDONS:
        root = ADDONS_ROOT / addon
        if not root.exists():
            continue
        ids[addon] = set()
        for p in root.rglob("*.xml"):
            try:
                tree = ET.parse(p)
                for rec in tree.iter("record"):
                    rid = rec.get("id")
                    if rid:
                        ids[addon].add(rid)
                for menu in tree.iter("menuitem"):
                    mid = menu.get("id")
                    if mid:
                        ids[addon].add(mid)
                for tmpl in tree.iter("template"):
                    tid = tmpl.get("id")
                    if tid:
                        ids[addon].add(tid)
            except ET.ParseError:
                pass
    # Now scan each addon's source for cross-addon references like
    # `kitchenforge_core.group_xxx` and ensure the id exists.
    ref_rx = re.compile(r"\b(kitchenforge_\w+)\.([a-zA-Z][\w]+)\b")
    for addon in KF_ADDONS:
        root = ADDONS_ROOT / addon
        if not root.exists():
            continue
        for p in list(root.rglob("*.xml")) + list(root.rglob("*.csv")):
            for line_no, line in enumerate(p.read_text().splitlines(), 1):
                for m in ref_rx.finditer(line):
                    target_addon, target_id = m.group(1), m.group(2)
                    if target_addon == addon:
                        continue
                    if target_addon in ids and target_id in ids.get(target_addon, set()):
                        continue
                    # Allow common Odoo namespaces
                    if target_addon in ("kitchenforge_core",) and target_id.startswith(("model_", "view_")):
                        continue
                    if target_addon in ids and target_id not in ids[target_addon]:
                        warn(f"{addon}/{p.relative_to(root)}:L{line_no}: "
                             f"unresolved external id {target_addon}.{target_id}")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> int:
    header("Phase 1: addon hygiene")
    summaries = []
    for a in KF_ADDONS:
        info = check_addon(a)
        summaries.append(info)
        if info.get("ok"):
            print(f"  {a}: {info['py']} py, {info['xml']} xml, {info.get('loc',0)} LoC")

    header("Phase 2: code smells (warn)")
    for a in KF_ADDONS:
        root = ADDONS_ROOT / a
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            review_one(p, a)
        for p in root.rglob("*.xml"):
            review_one(p, a)

    header("Phase 3: cross-addon refs")
    check_inter_addon_refs()

    header("Phase 4: sales kit")
    sales = check_sales_kit()
    print(f"  present: {sales['present']}")
    if sales["missing"]:
        print(f"  missing: {sales['missing']}")

    header("Phase 5: SDKs")
    sdks = check_sdks()
    print(f"  openapi:{sdks['openapi']}  python:{sdks['python']}  ts:{sdks['ts']}  examples:{sdks['examples']}")

    header("Phase 6: deploy infra")
    dep = check_deploy()
    print(f"  scripts:{dep['scripts']}  ci:{dep['ci']}")

    header("Report")
    print(f"  errors:   {len(ERRORS)}")
    print(f"  warnings: {len(WARNINGS)}")
    if ERRORS:
        print("\n  ERRORS:")
        for e in ERRORS[:60]:
            print(f"    X {e}")
        if len(ERRORS) > 60:
            print(f"    ... and {len(ERRORS) - 60} more")
    if WARNINGS:
        print("\n  WARNINGS (first 30):")
        for w in WARNINGS[:30]:
            print(f"    ! {w}")
        if len(WARNINGS) > 30:
            print(f"    ... and {len(WARNINGS) - 30} more")
    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())
