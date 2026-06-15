# KitchenForge × Marathon Hardware

Channel-partner integration for the Marathon Hardware reseller relationship.
Builds on `kitchenforge_core` to turn Marathon into the default-spec hardware
brand on every cabinet zone, capture demand telemetry in near-real-time, and
auto-draft a Marathon RFQ on every confirmed sale order.

## What it does

- **Default-spec bias.** Marathon SKUs land on every cabinet zone via the
  template `preselected_attribute_values` map. One click vs three for
  competitors — that's the channel moat.
- **Live spec telemetry.** Every `southbrook.hardware.catalog.resolve()`
  call emits a `kitchenforge.marathon.spec.event`. Marathon sees demand
  60+ days before the PO lands. A 15-min cron flushes the queue to the
  Marathon telemetry webhook.
- **Rebate ledger.** `kitchenforge.marathon.rebate` credits $X per
  Marathon-spec'd cabinet on each confirmed SO. Idempotent per SO.
  Monthly reconciliation surfaces a clean number for the channel commission.
- **Auto-RFQ on SO confirm.** A draft `purchase.order` is created against
  the Marathon partner with every Marathon-branded SKU aggregated by qty.
  Hooks via `sale.order._action_confirm` — failures log but never block
  the customer-facing confirm.
- **Channel config.** Singleton `kitchenforge.marathon.channel.config` —
  master enable, branded mode, rebate rate, telemetry URL, min RFQ amount.

## Endpoints (read-only, Marathon-facing)

```
GET /agent/v1/marathon/telemetry   → recent spec events (X-Api-Key)
GET /agent/v1/marathon/rebates     → monthly rebate summary
```

## Dependencies

`kitchenforge_core`, `southbrook_hardware_catalog`, `purchase`

## Tests

```
-i kitchenforge_marathon --test-tags marathon
```

## License

LGPL-3
