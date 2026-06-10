#!/usr/bin/env python3
"""Ingest crawled Marathon product JSON into a hardware_catalog seed XML.

Picks up every marathon_*.json file in this directory, deduplicates
against the templates already shipping in southbrook_hardware_catalog,
infers brand + category + finishes from each product's fields, and
emits a single XML seed ready to drop into the addon's data/ directory.

Usage:
    python3 ingest.py                       # writes marathon_<date>_seed.xml here
    python3 ingest.py --addon /path/to/addon  # writes into addon's data/
    python3 ingest.py --dry-run             # print summary, no write

The XML is idempotent on re-install (noupdate=1) and uses xml_ids
keyed on the Marathon SKU so the next crawl's deltas merge cleanly.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_ADDON = Path.home() / "southbrook-v19cr" / "addons" / "southbrook_hardware_catalog"


# ---------- brand inference -------------------------------------------------

# Lower-cased substring → brand xml_id (in southbrook_hardware_catalog).
# Order matters: more specific patterns first.
BRAND_RULES = [
    ("l&s", "brand_ls_lighting"),
    ("l & s ", "brand_ls_lighting"),
    ("ls lighting", "brand_ls_lighting"),
    ("moove", "brand_ls_lighting"),
    ("mec lite", "brand_ls_lighting"),
    ("flexspot", "brand_ls_lighting"),
    ("triac", "brand_ls_lighting"),
    ("k push tech", "brand_italiana_ferramenta"),
    ("gola", "brand_italiana_ferramenta"),
    ("italfit", "brand_italiana_ferramenta"),
    ("italiana", "brand_italiana_ferramenta"),
    ("salice", "brand_salice"),
    ("dtc ", "brand_dtc"),
    ("legacy endura", "brand_dtc"),
    ("blum", "brand_blum"),
    ("blumotion", "brand_blum"),
    ("movento", "brand_blum"),
    ("legrabox", "brand_blum"),
    ("tandem", "brand_blum"),
    ("hettich", "brand_hettich"),
    ("actro", "brand_hettich"),
    ("sensys", "brand_hettich"),
    ("accuride", "brand_accuride"),
    ("king slide", "brand_king_slide"),
    ("kingslide", "brand_king_slide"),
    ("hafele", "brand_hafele"),
    ("häfele", "brand_hafele"),
    ("knape", "brand_kv"),
    ("k&v", "brand_kv"),
    ("grass", "brand_grass"),
    ("sugatsune", "brand_sugatsune"),
    ("amerock", "brand_amerock"),
    ("emtek", "brand_emtek"),
    ("schaub", "brand_schaub"),
    ("citterio", "brand_citterio_giulio"),
    ("viefe", "brand_viefe"),
    ("roberto marella", "brand_roberto_marella"),
    ("vibo", "brand_vibo"),
    ("fastcap", "brand_fastcap"),
    ("true position", "brand_true_position_tools"),
    ("robertson", "brand_robertson"),
    ("3m", "brand_3m"),
    ("klingspor", "brand_klingspor"),
    ("eureka", "brand_eureka"),
    ("richelieu", "brand_richelieu"),
    ("berenson", "brand_berenson"),
    ("top knobs", "brand_top_knobs"),
    ("liberty", "brand_liberty"),
    ("belwith", "brand_belwith"),
    ("rev-a-shelf", "brand_rev_a_shelf"),
    ("lama", "brand_lama"),
    ("mepla", "brand_mepla"),
    ("ridder", "brand_ridder"),
]


def infer_brand(name: str, declared_brand: str | None) -> str:
    if declared_brand:
        lo = declared_brand.lower().strip()
        for pat, ref in BRAND_RULES:
            if pat in lo:
                return ref
    n = (name or "").lower()
    for pat, ref in BRAND_RULES:
        if pat in n:
            return ref
    return "brand_marathon"  # house brand fallback


# ---------- category inference ----------------------------------------------

CATEGORY_RULES = [
    (re.compile(r"\b(hinge|hinges)\b", re.I), "hinge"),
    (re.compile(r"\b(slide|slides|undermount|legrabox|movento)\b", re.I), "slide"),
    (re.compile(r"\b(shelf pin|shelf pins)\b", re.I), "pin"),
    (re.compile(r"\b(screw|fastener|robertson)\b", re.I), "screw"),
    (re.compile(r"\b(pull|knob|handle|appliance pull)\b", re.I), "handle"),
    (re.compile(r"\b(leveler|levellers?)\b", re.I), "leveler"),
    (re.compile(r"\b(cam ?lock|rta)\b", re.I), "cam_lock"),
    (re.compile(r"\b(bumper|stop|dot)\b", re.I), "bumper"),
]


def infer_category(name: str, declared_category: str | None) -> str:
    text = " ".join(filter(None, [name, declared_category or ""]))
    for pat, slot in CATEGORY_RULES:
        if pat.search(text):
            return slot
    return "other"


# ---------- helpers --------------------------------------------------------

def slug(s: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", (s or "").lower())).strip("_")


def primary_image(product: dict) -> str:
    images = product.get("images") or product.get("image_urls") or []
    if not images:
        return ""
    # marathon_crawler shape: list of {url, alt}.
    # marathon_browser shape: list of url strings.
    candidates: list[str] = []
    for item in images:
        if isinstance(item, str):
            candidates.append(item)
        elif isinstance(item, dict) and item.get("url"):
            candidates.append(item["url"])
    for url in candidates:
        if "productPageSlider" in url:
            return url
    return candidates[0] if candidates else ""


def xml_escape(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# Templates already shipped in southbrook_hardware_catalog/data/ —
# loaded once and used as a dedup baseline so re-ingests don't recreate
# the same xml_ids.
def existing_marathon_skus(addon_path: Path) -> set[str]:
    skus: set[str] = set()
    for xml_path in (addon_path / "data").glob("*.xml"):
        try:
            for m in re.finditer(r"<field name=\"x_marathon_sku\">([^<]+)</field>", xml_path.read_text(encoding="utf-8")):
                skus.add(m.group(1).strip())
        except Exception:
            continue
    return skus


# ---------- main -----------------------------------------------------------

def find_inputs() -> list[Path]:
    return sorted(p for p in HERE.glob("marathon_*.json") if p.is_file() and p.stat().st_size > 4)


def harvest_finishes(product: dict) -> list[str]:
    raw = product.get("finish") or []
    out: list[str] = []
    if isinstance(raw, list):
        for v in raw:
            if isinstance(v, str) and v.strip() and len(v) < 60 and "Continue" not in v:
                if v not in out:
                    out.append(v)
    return out


def build_seed(products: list[dict], known_skus: set[str]) -> tuple[str, dict]:
    """Return (xml_text, stats)."""
    seen: set[str] = set()
    skipped_existing = 0
    skipped_no_sku = 0
    finishes_universe: dict[str, None] = {}
    out_records: list[str] = []

    for p in products:
        sku = (p.get("sku") or p.get("part_number") or "").strip()
        if not sku:
            skipped_no_sku += 1
            continue
        if sku in known_skus or sku in seen:
            skipped_existing += 1
            continue
        seen.add(sku)
        name = xml_escape(p.get("product_name") or p.get("name") or sku)
        brand_ref = infer_brand(p.get("product_name") or "", p.get("brand"))
        category = infer_category(p.get("product_name") or "", p.get("category"))
        img = primary_image(p)
        finishes = harvest_finishes(p)
        for f in finishes:
            finishes_universe.setdefault(f, None)

        sku_slug = slug(sku)
        lines = [
            f'    <record id="tmpl_marathon_{sku_slug}" model="product.template">',
            f'        <field name="name">{name}</field>',
            f'        <field name="default_code">{xml_escape(sku)}</field>',
            f'        <field name="x_marathon_sku">{xml_escape(sku)}</field>',
            f'        <field name="type">consu</field>',
            f'        <field name="is_storable" eval="True"/>',
            f'        <field name="x_hardware_category">{category}</field>',
            f'        <field name="x_hardware_brand_id" ref="{brand_ref}"/>',
            f'        <field name="x_pricing_pending" eval="True"/>',
        ]
        if img:
            lines.append(f'        <field name="x_marathon_image_url">{xml_escape(img)}</field>')

        # When finishes were captured cleanly, attach the attribute line
        # so variants spawn. This only fires for crawler-quality data
        # (~/marathon_crawler) — browser_20-quality skips per harvest_finishes.
        if finishes:
            refs = ",\n                                    ".join(
                f"ref('value_finish_{slug(f)}')" for f in finishes
            )
            lines.append('        <field name="attribute_line_ids" eval="[(5, 0, 0), (0, 0, {')
            lines.append("            'attribute_id': ref('attr_marathon_finish'),")
            lines.append(f"            'value_ids': [(6, 0, [{refs}])]")
            lines.append('        })]"/>')

        lines.append('    </record>')
        out_records.append("\n".join(lines))

    # Emit any NEW finish values not already declared in marathon_knob_seed.xml.
    known_finishes = {
        slug(v) for v in [
            "Antique Copper Bronze Highlight", "Antique Pewter", "Black Nickel",
            "Bronze Champagne", "Brushed Brass", "Brushed Chrome",
            "Brushed Nickel", "Brushed Satin Nickel", "Gold Champagne",
            "Golden Champagne", "Golden Cymbal", "Graphite", "Matte Black",
            "Matte White", "Oil-Rubbed Bronze", "Polished Chrome",
            "Satin Gold", "Stone Grey", "Weathered Iron", "Weathered Steel",
        ]
    }
    new_finish_values: list[tuple[str, str]] = []
    for f in finishes_universe:
        s = slug(f)
        if s not in known_finishes:
            new_finish_values.append((s, f))

    finish_xml: list[str] = []
    next_seq = 1000  # leave room above the existing 10..200 range
    for s, label in new_finish_values:
        finish_xml.append(
            f'    <record id="value_finish_{s}" model="product.attribute.value">\n'
            f'        <field name="attribute_id" ref="attr_marathon_finish"/>\n'
            f'        <field name="name">{xml_escape(label)}</field>\n'
            f'        <field name="sequence">{next_seq}</field>\n'
            f'    </record>'
        )
        next_seq += 10

    date_tag = datetime.date.today().isoformat()
    header = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<odoo noupdate="1">\n'
        f'    <!-- Marathon catalog ingest {date_tag}. {len(out_records)} new\n'
        f'         product.template records, {len(new_finish_values)} new\n'
        f'         attribute values. Re-running the ingest is safe: SKUs\n'
        f'         that already exist in any data/*.xml are skipped via\n'
        f'         x_marathon_sku dedup. -->\n'
    )
    parts: list[str] = [header]
    if finish_xml:
        parts.append(
            '\n    <!-- New finishes discovered in this crawl batch -->\n'
        )
        parts.extend(x + "\n" for x in finish_xml)
    if out_records:
        parts.append('\n    <!-- Product templates -->\n')
        parts.extend(x + "\n" for x in out_records)
    parts.append('</odoo>\n')

    stats = {
        "products_seen": len(products),
        "templates_emitted": len(out_records),
        "skipped_existing": skipped_existing,
        "skipped_no_sku": skipped_no_sku,
        "new_finish_values": len(new_finish_values),
    }
    return "\n".join(parts), stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--addon", type=Path, default=DEFAULT_ADDON,
                        help="Path to southbrook_hardware_catalog addon dir.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print stats; don't write the XML.")
    parser.add_argument("--out", type=Path, default=None,
                        help="Override output file. Default: addon/data/marathon_ingest_<date>.xml")
    args = parser.parse_args()

    inputs = find_inputs()
    if not inputs:
        print("No marathon_*.json found in", HERE, file=sys.stderr)
        return 2

    print(f"[ingest] reading {len(inputs)} JSON file(s):")
    products: list[dict] = []
    for p in inputs:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  skip {p.name}: {e}", file=sys.stderr)
            continue
        if isinstance(data, list):
            products.extend(data)
            print(f"  + {p.name}: {len(data)} products")
        elif isinstance(data, dict):
            products.append(data)
            print(f"  + {p.name}: 1 product")

    known = existing_marathon_skus(args.addon) if args.addon.exists() else set()
    print(f"[ingest] {len(known)} SKUs already in addon data — will dedup")

    xml_text, stats = build_seed(products, known)
    print(f"[ingest] stats: {stats}")

    if args.dry_run:
        print("[ingest] --dry-run; no file written.")
        return 0

    if stats["templates_emitted"] == 0 and stats["new_finish_values"] == 0:
        print("[ingest] nothing new to write.")
        return 0

    out_path = args.out or (
        args.addon / "data" / f"marathon_ingest_{datetime.date.today().isoformat()}.xml"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(xml_text, encoding="utf-8")
    print(f"[ingest] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
