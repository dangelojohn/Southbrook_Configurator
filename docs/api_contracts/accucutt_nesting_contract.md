# Accucutt ↔ Odoo Nesting Contract (Phase 4 Sprint 1)

> Cut-list hand-off and nesting-result ingest between Odoo and the
> Accucutt nesting service. Closes the Phase 4 deliverable from
> CLAUDE.md §8: "Accucutt hand-off: export the panel list as the
> agreed JSON envelope; ingest the nest result."

**Schema:** `southbrook.nesting.v1`
**Status:** GREEN — shipped 2026-06-11
**Pairs with:** the G6 Flutter API auth model (X-Api-Key header,
shared `southbrook.api.key` issuance flow).

---

## 1. Design principles

The cutting/nesting division is a separate machine-to-machine consumer
of the Odoo MRP pipeline. It needs:

1. **Read access to the cut list** by id, returned as a deterministic
   envelope (panel-by-panel) with versioned schema.
2. **Write access for the nesting result** back to the same cut list,
   advancing its state to `nested`.

Both endpoints sit under the existing `/api/v1/` surface so the
auth + idempotency + error-envelope machinery is shared with the
Flutter API.

Schema versioning: the envelope's `schema` field is
`southbrook.nesting.v1`. A future v2 lands as a side-by-side route
prefix (`/api/v2/cutlist/...`) per the Flutter contract §6.

---

## 2. Auth

Both endpoints require the standard `X-Api-Key` header. The Accucutt
operator generates a key by hitting `/api/v1/auth/login` with a
manufacturing-role user's credentials (`mrp.group_mrp_user`); the
key is stored in the cutting-service config alongside the Odoo URL.

Missing or invalid → `401 {"error":"invalid_api_key", ...}`.

The cut list itself is record-rule scoped to the authenticated user.
A key issued for a partner without manufacturing access can still
hit the endpoint but the cut list resolves to an `AccessError` →
`403 {"error":"forbidden", ...}`.

---

## 3. Endpoints

### 3.1 GET /api/v1/cutlist/{id}/envelope

Return the cut list as a Accucutt-consumable envelope.

```jsonc
{
  "schema": "southbrook.nesting.v1",
  "envelope": {
    "schema":         "southbrook.nesting.v1",
    "cutlist_id":     42,
    "cutlist_name":   "CL/2026/000042",
    "mo_id":          184,
    "panels": [
      {
        "panel_name":    "side_L",
        "qty":           2,
        "length_mm":     720.0,
        "width_mm":      580.0,
        "thickness_mm":  15.875,
        "substrate":     "melamine_white_5_8",
        "grain_dir":     "no_grain",
        "edge_banding":  {}
      }
    ]
  }
}
```

Status codes:
- `200 OK` — envelope returned.
- `401 invalid_api_key` — missing or revoked `X-Api-Key`.
- `403 forbidden` — key not authorized for this cut list.
- `404 not_found` — no cut list with that id.

### 3.2 POST /api/v1/cutlist/{id}/nesting-result

Push the nesting outcome back. Idempotent via `Idempotency-Key`.

Request body:
```jsonc
{
  "schema":       "southbrook.nesting.v1",
  "sheets_used":  1,
  "yield_pct":    91.4,
  "waste_pct":    8.6,
  // implementation-defined extras allowed under the same schema —
  // Odoo stores the whole JSON blob in sb.cutlist.nesting_result_json
  "sheets": [
    { "sheet_no": 1, "panels_placed": [42, 43, 44] }
  ]
}
```

Response on success:
```jsonc
{
  "schema":     "southbrook.flutter.api.v1",
  "ok":         true,
  "cutlist_id": 42,
  "state":      "nested"
}
```

Status codes:
- `200 OK` — result accepted, cutlist state advanced to `nested`.
- `400 bad_json` — body is not a JSON object.
- `401 invalid_api_key`
- `403 forbidden`
- `404 not_found`
- `422 nesting_rejected` — schema mismatch or model-level
  validation failure. The `message` field carries the specific
  reason from `sb.cutlist.from_nesting_result`.

The endpoint is a thin wrapper around
`sb.cutlist.from_nesting_result(payload)` — the validation rules
live on the model, not the controller, so internal callers
(manual ECO repair, scheduled retry jobs) honor the same contract.

---

## 4. Sequence

A typical round-trip:

```text
1. Odoo Manufacturing Order confirms; sb.production.package.generate_from_mo()
   creates a draft sb.cutlist with the panel rows.
2. The cutting division picks up new cut lists by polling, or via a
   webhook the production package optionally emits.
3. Accucutt: GET /api/v1/cutlist/42/envelope
4. Accucutt runs its nesting algorithm on the envelope's panels.
5. Accucutt: POST /api/v1/cutlist/42/nesting-result
   body = {schema, sheets_used, yield_pct, waste_pct, sheets: [...]}
6. Odoo: state=draft → state=nested. The nesting JSON is stored on
   cutlist.nesting_result_json for the Phase-1 polish that surfaces
   sheets_used + yield_pct on the sb.production.package detail view.
```

---

## 5. Out of scope for v1

- Multi-pass nesting (Accucutt re-submits an improved result for the
  same cut list). For now a re-POST overwrites the prior result.
- Realtime status updates back to the customer portal (the nesting
  state is dealer-only by record rules).
- Costing math from the yield_pct. Future Phase 4 sprint converts
  yield/waste into a costing adjustment on the MO.

---

## 6. Test coverage

See `addons/southbrook_api/tests/test_cutlist_nesting.py` —
7 HttpCase tests covering:
- envelope returns nesting schema + panels (200)
- envelope without X-Api-Key (401)
- envelope on unknown id (404)
- nesting-result advances state to 'nested' (200)
- nesting-result with bad schema (422)
- nesting-result with bad JSON (400)
- nesting-result without X-Api-Key (401)

The model-layer round-trip is covered separately by
`addons/southbrook_kitchen_mrp/tests/test_nesting_io.py`.
