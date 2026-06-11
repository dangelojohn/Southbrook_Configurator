# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "Southbrook PLM ↔ ProductGraph Bridge",
    "summary": "Closes the loop — applying a Southbrook ECO also triggers "
               "a ProductGraph release on a linked engineering BOM.",
    "description": """
Southbrook PLM ↔ ProductGraph Bridge
====================================

Glue module wiring the two PLM layers Southbrook runs:

* ``southbrook_plm`` — the in-house cabinet-shop ECO/cut-spec authority.
* ``product_graph_*`` — the generic OpenBOM-mirror engineering catalog +
  release-to-MRP gate.

The bridge is intentionally **one-way**: applying a Southbrook ECO MAY
trigger a ProductGraph release. ProductGraph never reaches back into
Southbrook code — that direction is forbidden by ProductGraph's
Decision D1 so the generic addons remain publishable.

What this module adds to ``southbrook.eco``
-------------------------------------------

* ``pg_ebom_id`` — optional pointer to a released ``pg.ebom``. When set,
  the ECO can release that EBOM to MRP at apply time.
* ``pg_release_id`` — read-only handle to the resulting ``pg.release``
  record so the audit trail is double-linked.
* ``pg_auto_release`` — opt-in toggle (default True).

Behavior
--------

``action_apply`` is wrapped, not replaced. The Southbrook PLM side runs
first (state machine, ``_apply_<kind>``, stamps ``applied_date``). If
``pg_auto_release`` is on and ``pg_ebom_id`` is set, a ``pg.release`` is
created and ``action_execute_release`` is called — this is the only
documented way Southbrook code triggers writes to ``mrp.bom`` through
ProductGraph.

A bridge failure does NOT roll back the ECO. The ECO stays in ``applied``
state and a chatter note records the failure; an Approver can manually
re-trigger the release via the EBOM's wizard.

License: LGPL-3.0 (same as both parents).
    """,
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry",
    "website": "https://southbrookcabinetry.space",
    "category": "Manufacturing/Product Lifecycle Management",
    "depends": [
        "southbrook_plm",
        "product_graph_release",
    ],
    "data": [
        # noupdate=1 data — bumps base.group_user.api_key_duration to 5y
        # so the MCP service account can mint long-lived keys without
        # group elevation. Load before any view that might be inspected
        # by admin-settings prefetch on first install.
        "data/api_key_policy.xml",
        "views/southbrook_eco_views.xml",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
