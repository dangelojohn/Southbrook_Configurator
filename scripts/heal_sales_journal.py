# SPDX-License-Identifier: LGPL-3.0-only
"""One-shot prod-DB unblocker for REG-C1 (missing Sales journal).

Run this from the Odoo container shell to seed a default Sales journal
for every company that lacks one — same logic as the southbrook_estimating
post_init_hook, but invokable WITHOUT a module upgrade. Use this when:

  - The live DB is broken right now (Create Invoice → "No journal …
    for any of those types: sale") and you can't afford the 4-minute
    deploy cycle.
  - The deploy is failing for an unrelated reason and you need the
    invoicing leg up first.

Once southbrook_estimating 19.0.2.4.0+ is deployed, this script becomes
redundant — the post_init_hook does the same work on every -u.

Usage (on the QNAP):

    docker exec -i southbrook-odoo odoo shell \\
      -d odoo --no-http --stop-after-init < scripts/heal_sales_journal.py

Or copy into shell and paste:

    docker exec -it southbrook-odoo odoo shell -d odoo --no-http
    # Then paste the contents of this file.

Idempotent: safe to re-run. Companies that already have a sale journal
are skipped silently.
"""
Journal = env["account.journal"].sudo()  # noqa: F821 — env injected by odoo shell
Company = env["res.company"].sudo()  # noqa: F821

created_for = []
skipped_for = []

for company in Company.search([]):
    existing = Journal.search(
        [("company_id", "=", company.id), ("type", "=", "sale")],
        limit=1,
    )
    if existing:
        skipped_for.append((company.display_name, existing.code))
        continue
    new = Journal.create({
        "name": "Customer Invoices",
        "code": "INV",
        "type": "sale",
        "company_id": company.id,
        "show_on_dashboard": True,
    })
    created_for.append((company.display_name, new.code, new.id))

print("REG-C1 heal_sales_journal results:")
print(f"  created: {len(created_for)}")
for name, code, jid in created_for:
    print(f"    {name!r} → journal '{code}' (id={jid})")
print(f"  skipped (already had a sale journal): {len(skipped_for)}")
for name, code in skipped_for:
    print(f"    {name!r} → kept existing '{code}'")

env.cr.commit()  # noqa: F821
print("committed.")
