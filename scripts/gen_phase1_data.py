#!/usr/bin/env python3
"""
scripts/gen_phase1_data.py — one-shot generator for the per-template
attribute_line and product.config.line records.

Run during the commit-7 author session to produce:
  - addons/southbrook_estimating/data/product_templates.xml
  - the per-template product.config.line block appended to
    addons/southbrook_estimating/data/config_rules.xml

Kept in scripts/ as documentation of generation intent — if Phase 2 or
later needs to add/remove templates or change the rule expansion, this
script is the spec; the XML is the artifact.

Generation logic mirrors:
  - Q2 11-attribute list + Q8 accessory_type + Q22(a) door_count + Q23(b) family_subtype
  - Q8 12 locked xml_ids: wall_1dr/wall_2dr/base_1dr/base_2dr/drawer_bank/
    sink_base/tall_pantry/tall_oven/corner/vanity/accessory/worktop
  - Mapping section 3.1 widths per template
  - Mapping section 3.4 four declarative rules

Run via:
    cd ~/southbrook-v19cr && python3 scripts/gen_phase1_data.py
"""
from textwrap import dedent

# ---------------------------------------------------------------------
# Per-template attribute_line composition.
#
# Each template ships an attribute_line for each attribute it semantically
# exposes. The value_ids on each attribute_line are the SUBSET of the
# attribute's global values that this template offers.
#
# Width snap-grids per Mapping section 3.1:
#   narrow widths: 9, 12, 15, 18, 21
#   wide widths:   24, 27, 30, 33, 36
#   drawer_bank:   12, 15, 18, 24, 30
#   sink_base:     30, 33, 36
#   tall_pantry:   18, 24, 30
#   tall_oven:     27, 30
#   corner:        33, 36
#   vanity:        deferred to Phase 2 (Vanity Program tab of #5/#8)
#   accessory:     no width snap-grid
#   worktop:       length-based, parametric (no width attribute_line)
# ---------------------------------------------------------------------

NARROW_WIDTHS = ["9", "12", "15", "18", "21"]
WIDE_WIDTHS = ["24", "27", "30", "33", "36"]

# Per Q23(b): only corner has family_subtype.
# Per Q22(a): door_count on every template with door-or-drawer fronts.
# Per accessory shape: only accessory has accessory_type.
TEMPLATES = [
    {
        "xml_id": "wall_1dr", "name": "Wall 1-Door", "default_code": "SB-WALL-1DR",
        "family_value": "wall", "widths": NARROW_WIDTHS,
        "has_door_style": True, "has_door_count": True, "has_full_accessory_attrs": True,
        "hinge_sides": ["left", "right"],
    },
    {
        "xml_id": "wall_2dr", "name": "Wall 2-Door", "default_code": "SB-WALL-2DR",
        "family_value": "wall", "widths": WIDE_WIDTHS,
        "has_door_style": True, "has_door_count": True, "has_full_accessory_attrs": True,
        "hinge_sides": ["left", "right", "na"],
    },
    {
        "xml_id": "base_1dr", "name": "Base 1-Door", "default_code": "SB-BASE-1DR",
        "family_value": "base", "widths": NARROW_WIDTHS,
        "has_door_style": True, "has_door_count": True, "has_full_accessory_attrs": True,
        "hinge_sides": ["left", "right"],
    },
    {
        "xml_id": "base_2dr", "name": "Base 2-Door", "default_code": "SB-BASE-2DR",
        "family_value": "base", "widths": WIDE_WIDTHS,
        "has_door_style": True, "has_door_count": True, "has_full_accessory_attrs": True,
        "hinge_sides": ["left", "right", "na"],
    },
    {
        "xml_id": "drawer_bank", "name": "Drawer Bank", "default_code": "SB-DRAWER",
        "family_value": "drawer",
        "widths": ["12", "15", "18", "24", "30"],
        "has_door_style": True, "has_door_count": True, "has_full_accessory_attrs": True,
        "hinge_sides": ["na"],
    },
    {
        "xml_id": "sink_base", "name": "Sink Base", "default_code": "SB-SINK-BASE",
        "family_value": "sink", "widths": ["30", "33", "36"],
        "has_door_style": True, "has_door_count": True, "has_full_accessory_attrs": True,
        "hinge_sides": ["left", "right", "na"],
    },
    {
        "xml_id": "tall_pantry", "name": "Tall Pantry", "default_code": "SB-TALL-PANTRY",
        "family_value": "tall", "widths": ["18", "24", "30"],
        "has_door_style": True, "has_door_count": True, "has_full_accessory_attrs": True,
        "hinge_sides": ["left", "right"],
    },
    {
        "xml_id": "tall_oven", "name": "Tall Oven Housing", "default_code": "SB-TALL-OVEN",
        "family_value": "tall", "widths": ["27", "30"],
        "has_door_style": True, "has_door_count": True, "has_full_accessory_attrs": True,
        "hinge_sides": ["left", "right"],
    },
    {
        "xml_id": "corner", "name": "Corner Cabinet", "default_code": "SB-CORNER",
        "family_value": "corner", "widths": ["33", "36"],
        "has_door_style": True, "has_door_count": True, "has_full_accessory_attrs": True,
        "hinge_sides": ["left", "right"],
        "has_family_subtype": True,   # Q23(b) — only corner
    },
    {
        "xml_id": "vanity", "name": "Vanity", "default_code": "SB-VANITY",
        "family_value": "vanity", "widths": ["18", "24", "30"],  # Phase 1 subset
        "has_door_style": True, "has_door_count": True, "has_full_accessory_attrs": True,
        "hinge_sides": ["left", "right"],
        "series_subset": ["contemporary", "elegance"],  # Mapping section 1
    },
    {
        "xml_id": "accessory", "name": "Accessory", "default_code": "SB-ACCESSORY",
        "family_value": "accessory", "widths": [],  # No width snap-grid
        "has_door_style": False, "has_door_count": False, "has_full_accessory_attrs": False,
        "hinge_sides": [],
        "has_accessory_type": True,  # Q8 — only accessory
    },
    {
        "xml_id": "worktop", "name": "Worktop", "default_code": "SB-WORKTOP",
        "family_value": "worktop", "widths": [],  # Length-based, parametric
        "has_door_style": False, "has_door_count": False, "has_full_accessory_attrs": False,
        "hinge_sides": [],
        "is_minimal": True,
    },
]

ALL_SERIES = ["contractor", "contemporary", "elegance", "signature"]
ALL_DOOR_STYLES = ["thermofoil_slab_white", "five_piece_woodgrain", "custom"]
ALL_BOX_MATERIALS = ["white_melamine", "maple"]
ALL_FINISHED_SIDES = ["none", "left", "right", "both"]
ALL_GABLES = ["standard", "finished", "decorative"]
ALL_ACCESSORIES = ["soft_close", "drawer_organisers", "pull_outs"]
ALL_DOOR_COUNTS = ["1", "2"]


# ---------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------

def render_template_record(t):
    """Emit the product.template <record> for a given template dict."""
    return dedent(f"""\
        <record id="{t['xml_id']}" model="product.template">
          <field name="name">{t['name']}</field>
          <field name="default_code">{t['default_code']}</field>
          <field name="config_ok" eval="True"/>
          <field name="type">consu</field>
          <field name="list_price">0.0</field>
        </record>
    """)


def render_attr_line(t, attr_xml_id, value_xml_ids):
    """Emit a <product.template.attribute.line> record."""
    short_attr = attr_xml_id.replace("attr_", "")
    line_id = f"attr_line_{t['xml_id']}_{short_attr}"
    value_refs = ",\n      ".join(f"ref('{v}')" for v in value_xml_ids)
    return dedent(f"""\
        <record id="{line_id}" model="product.template.attribute.line">
          <field name="product_tmpl_id" ref="{t['xml_id']}"/>
          <field name="attribute_id" ref="{attr_xml_id}"/>
          <field name="value_ids" eval="[(6, 0, [
      {value_refs}
          ])]"/>
        </record>
    """)


def render_template_block(t):
    """Emit all records for one template: the template + all its attribute_lines."""
    lines = [render_template_record(t)]
    # 1 · family — always present, always a single value
    lines.append(render_attr_line(t, "attr_family", [f"value_family_{t['family_value']}"]))

    # 2 · width
    if t.get("widths"):
        lines.append(render_attr_line(t, "attr_width",
                                      [f"value_width_{w}" for w in t["widths"]]))

    # 3 · series
    series_to_use = t.get("series_subset", ALL_SERIES)
    lines.append(render_attr_line(t, "attr_series",
                                  [f"value_series_{s}" for s in series_to_use]))

    if t.get("is_minimal"):
        # worktop: also box_material + finish + finished_sides
        lines.append(render_attr_line(t, "attr_box_material",
                                      [f"value_box_{b}" for b in ALL_BOX_MATERIALS]))
        lines.append(render_attr_line(t, "attr_finish", []))  # values seed Phase 2
        lines.append(render_attr_line(t, "attr_finished_sides",
                                      [f"value_finished_{f}" for f in ALL_FINISHED_SIDES]))
        return "\n".join(lines)

    # 4 · box_material — every template except worktop's minimal shape
    lines.append(render_attr_line(t, "attr_box_material",
                                  [f"value_box_{b}" for b in ALL_BOX_MATERIALS]))

    # 5 · door_style — only templates with door faces
    if t.get("has_door_style"):
        lines.append(render_attr_line(t, "attr_door_style",
                                      [f"value_door_{d}" for d in ALL_DOOR_STYLES]))

    # 6 · finish — empty value_ids; populated when #5 Finish palette lands
    lines.append(render_attr_line(t, "attr_finish", []))

    # 7 · hinge_side
    if t.get("hinge_sides"):
        lines.append(render_attr_line(t, "attr_hinge_side",
                                      [f"value_hinge_{h}" for h in t["hinge_sides"]]))

    # 8 · finished_sides
    lines.append(render_attr_line(t, "attr_finished_sides",
                                  [f"value_finished_{f}" for f in ALL_FINISHED_SIDES]))

    # 9 · gables — only templates with full accessory shape
    if t.get("has_full_accessory_attrs"):
        lines.append(render_attr_line(t, "attr_gables",
                                      [f"value_gables_{g}" for g in ALL_GABLES]))

    # 10 · handle — empty value_ids; populated when handle catalog lands
    if t.get("has_full_accessory_attrs"):
        lines.append(render_attr_line(t, "attr_handle", []))

    # 11 · accessories — multi-select
    if t.get("has_full_accessory_attrs"):
        lines.append(render_attr_line(t, "attr_accessories",
                                      [f"value_accessory_{a}" for a in ALL_ACCESSORIES]))

    # 12 · door_count — hidden, Q22(a)
    if t.get("has_door_count"):
        lines.append(render_attr_line(t, "attr_door_count",
                                      [f"value_door_count_{d}" for d in ALL_DOOR_COUNTS]))

    # Q23(b) · family_subtype — corner only
    if t.get("has_family_subtype"):
        lines.append(render_attr_line(t, "attr_family_subtype",
                                      ["value_family_subtype_standard",
                                       "value_family_subtype_bifold"]))

    # Q8 · accessory_type — accessory only
    if t.get("has_accessory_type"):
        lines.append(render_attr_line(t, "attr_accessory_type",
                                      [f"value_accessory_type_{at}" for at in
                                       ["end_panel", "filler", "cornice", "pelmet", "plinth"]]))

    return "\n".join(lines)


# ---------------------------------------------------------------------
# Rule renderers
# ---------------------------------------------------------------------

def render_config_line(rule_num, t_xml_id, attr_short, value_xml_ids, domain_xml_id, sequence):
    """Emit a product.config.line record."""
    attr_line_ref = f"attr_line_{t_xml_id}_{attr_short}"
    line_id = f"rule{rule_num}_{domain_xml_id.replace('domain_', '')}_{attr_short}_{t_xml_id}"
    value_refs = ", ".join(f"ref('{v}')" for v in value_xml_ids)
    return dedent(f"""\
        <record id="{line_id}" model="product.config.line">
          <field name="product_tmpl_id" ref="{t_xml_id}"/>
          <field name="attribute_line_id" ref="{attr_line_ref}"/>
          <field name="value_ids" eval="[(6, 0, [{value_refs}])]"/>
          <field name="domain_id" ref="{domain_xml_id}"/>
          <field name="sequence">{sequence}</field>
        </record>
    """)


def generate_rule_records():
    """Emit Rules 1-4 as ~65 product.config.line records."""
    out = []

    # Rule 1 — Series → door_style. 10 templates with door_style × 2 restrictions.
    rule1_templates = [t for t in TEMPLATES if t.get("has_door_style")]
    seq = 10
    out.append("  <!-- ============================================================== -->")
    out.append("  <!-- RULE 1 — Series → Door Style                                   -->")
    out.append("  <!-- Contractor: thermofoil_slab_white only                         -->")
    out.append("  <!-- Elegance:   five_piece_woodgrain only                          -->")
    out.append("  <!-- ============================================================== -->")
    for t in rule1_templates:
        out.append(render_config_line(
            1, t["xml_id"], "door_style",
            ["value_door_thermofoil_slab_white"],
            "domain_series_is_contractor",
            seq,
        ))
        seq += 10
    for t in rule1_templates:
        out.append(render_config_line(
            1, t["xml_id"], "door_style",
            ["value_door_five_piece_woodgrain"],
            "domain_series_is_elegance",
            seq,
        ))
        seq += 10

    # Rule 2 — Box material → series. 11 templates with box_material × 2 restrictions.
    rule2_templates = [t for t in TEMPLATES if t["xml_id"] != "accessory"]  # NF check: accessory has box_material in template; revise if not
    # Actually per the renderer, all non-worktop-minimal templates get box_material.
    # worktop has it via is_minimal branch. accessory has box_material? Re-check renderer:
    # accessory has neither is_minimal nor has_full_accessory_attrs but gets box_material
    # via the unconditional line after the minimal branch.
    # So all 12 templates have box_material.
    rule2_templates = TEMPLATES
    seq = 10000  # different seq band so Rule 1 sequences stay clean
    out.append("  <!-- ============================================================== -->")
    out.append("  <!-- RULE 2 — Box Material → Series                                 -->")
    out.append("  <!-- Contractor: white_melamine only                                -->")
    out.append("  <!-- Signature:  maple only                                         -->")
    out.append("  <!-- (Contemporary + Elegance: no restriction, both options shown)  -->")
    out.append("  <!-- ============================================================== -->")
    for t in rule2_templates:
        out.append(render_config_line(
            2, t["xml_id"], "box_material",
            ["value_box_white_melamine"],
            "domain_series_is_contractor",
            seq,
        ))
        seq += 10
    for t in rule2_templates:
        out.append(render_config_line(
            2, t["xml_id"], "box_material",
            ["value_box_maple"],
            "domain_series_is_signature",
            seq,
        ))
        seq += 10

    # Rule 3 — Width → door_count. 10 templates with door_count × 2 width bands.
    rule3_templates = [t for t in TEMPLATES if t.get("has_door_count")]
    seq = 20000
    out.append("  <!-- ============================================================== -->")
    out.append("  <!-- RULE 3 — Width → Door Count (Q22(a))                           -->")
    out.append("  <!-- Narrow (9-21 in) → door_count=1                                -->")
    out.append("  <!-- Wide (24-36 in)  → door_count=2                                -->")
    out.append("  <!-- ============================================================== -->")
    for t in rule3_templates:
        out.append(render_config_line(
            3, t["xml_id"], "door_count",
            ["value_door_count_1"],
            "domain_width_narrow",
            seq,
        ))
        seq += 10
    for t in rule3_templates:
        out.append(render_config_line(
            3, t["xml_id"], "door_count",
            ["value_door_count_2"],
            "domain_width_wide",
            seq,
        ))
        seq += 10

    # Rule 4 — Family subtype → no soft_close on bifold corner. 1 record.
    seq = 30000
    out.append("  <!-- ============================================================== -->")
    out.append("  <!-- RULE 4 — Family Subtype → Soft-Close (Q23(b))                  -->")
    out.append("  <!-- When family_subtype=bifold on corner: restrict accessories     -->")
    out.append("  <!-- to {drawer_organisers, pull_outs} — omits soft_close (hides). -->")
    out.append("  <!-- ============================================================== -->")
    out.append(render_config_line(
        4, "corner", "accessories",
        ["value_accessory_drawer_organisers", "value_accessory_pull_outs"],
        "domain_family_subtype_bifold",
        seq,
    ))

    return "\n".join(out)


def main():
    # --- 1. Emit product_templates.xml -------------------------------
    template_blocks = "\n".join(render_template_block(t) for t in TEMPLATES)
    templates_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<!--\n"
        "  The 12 cabinet templates per Q8 locked xml_ids + their attribute_lines.\n"
        "\n"
        "  Generated by scripts/gen_phase1_data.py. Edit the generator and re-run\n"
        "  if Phase 2 surfaces template changes; do not hand-edit this file.\n"
        "\n"
        "  Per Q6: every attribute uses create_variant='dynamic'. Variants only\n"
        "  materialise when actually ordered.\n"
        "-->\n"
        '<odoo noupdate="0">\n\n'
        + template_blocks +
        "\n\n</odoo>\n"
    )
    with open("addons/southbrook_estimating/data/product_templates.xml", "w") as f:
        f.write(templates_xml)
    print("wrote: addons/southbrook_estimating/data/product_templates.xml")

    # --- 2. Append Rule 1-4 records to config_rules.xml --------------
    rules_block = generate_rule_records()

    with open("addons/southbrook_estimating/data/config_rules.xml") as f:
        existing = f.read()

    # Replace the NOTE comment block at the bottom with the actual records.
    note_marker = "  <!--\n    NOTE: product.config.line records (the per-template restrictions) are"
    if note_marker in existing:
        head = existing.split(note_marker)[0]
        new = head + "\n" + rules_block + "\n\n</odoo>\n"
    else:
        # Fallback: append before </odoo>
        new = existing.replace("</odoo>", "\n" + rules_block + "\n\n</odoo>")

    with open("addons/southbrook_estimating/data/config_rules.xml", "w") as f:
        f.write(new)
    print("wrote: addons/southbrook_estimating/data/config_rules.xml (rules appended)")


if __name__ == "__main__":
    main()
