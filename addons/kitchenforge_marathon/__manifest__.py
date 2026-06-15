# SPDX-License-Identifier: LGPL-3.0-only
{
    "name": "KitchenForge × Marathon Hardware",
    "summary": "Channel-partner integration: Marathon catalog auto-loaded as default, "
               "live spec telemetry, auto-RFQ on SO confirm, and per-cabinet rebate tracking.",
    "description": """
KitchenForge × Marathon Hardware
================================

Channel-partner integration for the Marathon Hardware reseller relationship.
Cabinet shops on KitchenForge get Marathon hardware as the default spec one
click away; Marathon gets live telemetry, structured RFQs, and a rebate
mechanic that rewards them for every cabinet using their hardware.

* **Default-spec bias** — Marathon SKUs are pre-selected on every cabinet
  zone via the template's `preselected_attribute_values` map.
* **Live spec telemetry** — every `southbrook.hardware.catalog.resolve()`
  call emits a `kitchenforge.marathon.spec.event` record, aggregated nightly
  into the Marathon partner dashboard.
* **Auto-RFQ on SO confirm** — confirming a project's quote drafts a
  `purchase.requisition` (or `purchase.order` fallback) addressed to the
  Marathon partner, carrying every Marathon-branded hardware SKU resolved
  during the build.
* **Rebate ledger** — `kitchenforge.marathon.rebate` tallies $X per
  cabinet confirmed with Marathon hardware; month-end reconciliation
  surfaces a clean number for the channel-partner commission.
* **Channel branding** — `kitchenforge.marathon.channel.config` model
  lets each tenant flip a single bit to switch the agent surface to
  "KitchenForge powered by Marathon" theming.
""",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Southbrook Cabinetry / OdooIQ",
    "category": "Manufacturing/Project",
    "depends": [
        "kitchenforge_core",
        "southbrook_hardware_catalog",
        "purchase",
    ],
    "data": [
        "security/marathon_security.xml",
        "security/ir.model.access.csv",
        "data/marathon_channel_config.xml",
        "views/spec_event_views.xml",
        "views/rebate_views.xml",
        "views/channel_config_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
