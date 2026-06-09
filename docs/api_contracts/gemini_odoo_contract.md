# Gemini ↔ Odoo Contract (G3)

> The signed-off JSON wire format between Module 6 (`southbrook_ai_design`)
> and the rest of the platform. Closing this contract is the G3 gate from
> the init doc — Module 6 cannot start without it.

**Version:** `southbrook.gemini.v1`
**Status:** GREEN — gate closed 2026-06-09
**Schema URI for runtime validation:** `southbrook.gemini.room_analysis.v1`

---

## 1. Why this contract exists

Gemini sees a kitchen photo and produces a *room understanding* — appliance
positions, sink presence, approximate dimensions. None of that output is
manufacturing-accurate by itself. Two failure modes are unacceptable:

1. **Manufacturing geometry trusts a Gemini number.** Cabinets cut to a
   width Gemini estimated, the customer's kitchen is the wrong width by
   30 mm, the panels don't fit. Per init-doc GAP-02 every dimensional
   field carries `confirmed_by_human: bool` and the Configuration
   Engine refuses to run while any required dimension is unconfirmed.

2. **Hallucinated fixtures.** Gemini reports `sink_detected: true` when
   the photo shows a corner stovetop. The contract distinguishes
   *detected* facts (Gemini's best guess) from *confirmed* facts
   (designer signed off). Modules 7+ consume the *confirmed* surface
   only.

The contract is the schema both sides agree on so each can fail loud at
its own boundary instead of silently propagating bad data.

---

## 2. Endpoint

The bridge from Odoo to Gemini is one-way: Odoo POSTs an image + prompt
to the Gemini API; Gemini returns JSON. There is no callback. Module 6
parses the JSON inside the request handler that initiated the call.

```
POST  https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent
Auth  ?key=<GEMINI_API_KEY> (Studio) or service-account-derived token (Vertex AI)
Body  { "contents": [{ "parts": [<image_part>, { "text": <prompt> }] }] }
```

Model: `gemini-2.5-pro` for production; `gemini-2.5-flash` allowed for dev/
smoke tests. Image part is inline base64 PNG/JPG, max 7 MB (Gemini limit
is 20 MB; we hold the 7 MB ceiling to keep room-photo uploads from the
customer portal reasonable).

The prompt template is the separate `docs/ai_prompt_spec.md` contract.

---

## 3. Request envelope (Odoo → Gemini)

Module 6's `_call_gemini(image_bytes, prompt_template_id) -> dict` packs
the request as:

```jsonc
{
  "contents": [{
    "parts": [
      {
        "inline_data": {
          "mime_type": "image/jpeg",
          "data": "<base64>"
        }
      },
      { "text": "<rendered prompt template>" }
    ]
  }],
  "generationConfig": {
    "temperature": 0.1,
    "topK": 16,
    "topP": 0.7,
    "maxOutputTokens": 4096,
    "responseMimeType": "application/json",
    "responseSchema": { /* the schema in §4 below, inlined */ }
  }
}
```

`temperature: 0.1` because we want *consistent* room readings, not
creative ones. `responseSchema` is the structured-output contract Gemini
enforces on its side — it short-circuits the bad-JSON failure mode at
the source.

---

## 4. Response schema (Gemini → Odoo)

The response body's `candidates[0].content.parts[0].text` is a JSON
document matching this schema verbatim:

```jsonc
{
  "schema": "southbrook.gemini.room_analysis.v1",   // string, must equal this literal
  "model": "gemini-2.5-pro",                        // echo of the model used
  "ts": "2026-06-09T17:42:00Z",                     // ISO 8601 UTC
  "image_hash": "sha256:...",                       // hash of the input image
  "room": {
    "sink_detected":          false,                // bool
    "window_count":           1,                    // int
    "room_door_count":        1,                    // int (DOORS INTO the room)
    "floor_area_m2_approx":   18.5,                 // float | null
    "ceiling_height_mm_approx": 2400,               // float | null
    "wall_segments": [                              // 0..N — the run topology
      {
        "id": "wall_north",
        "length_mm_approx": 4200,
        "has_windows":  [true],
        "has_doors":    [false]
      },
      { "id": "wall_east", "length_mm_approx": 2800, "has_windows": [false], "has_doors": [true] }
    ]
  },
  "appliances": [                                   // 0..N
    {
      "kind": "stove",                              // enum: stove|fridge|dishwasher|sink|microwave|oven_wall|hood|other
      "label": "Gas range, 30\"",                   // free-text Gemini caption
      "wall_segment_id": "wall_north",              // m2o the wall it sits on (nullable for islands)
      "position_pct_along_wall": 0.62,              // 0..1; how far along the wall (left→right)
      "width_mm_approx":  762,                      // 30" = 762 mm
      "height_mm_approx": 914,                      // 36" base
      "depth_mm_approx":  610,                      // 24" base
      "requires_clearance_mm": 30,                  // Gemini's guess; revised on confirm
      "confidence": 0.86                            // Gemini's per-appliance confidence 0..1
    }
  ],
  "dimensions_confidence": {
    "wall_lengths":        0.55,                    // overall confidence per category
    "appliance_widths":    0.78,
    "ceiling_height":      0.40
  },
  "model_warnings": [                               // free-text strings Gemini emits when uncertain
    "Sink position partly occluded by a person — re-measure manually."
  ]
}
```

### 4.1 Validation rules (enforced by Module 6 BEFORE writing to Odoo)

| Rule | Failure mode → action |
|---|---|
| `schema == "southbrook.gemini.room_analysis.v1"` | Reject; raise `UserError("schema_mismatch")` |
| All numeric dimensions in plausible ranges (300 mm ≤ wall length ≤ 15 000 mm; 100 mm ≤ appliance ≤ 2 000 mm; 1 500 mm ≤ ceiling ≤ 4 500 mm) | Out-of-range → record kept, dimension nulled, warning added to `model_warnings` |
| `appliances[*].kind` ∈ Module-5 appliance type selection | Unknown kind → coerce to `other`, store original label in `notes` |
| `appliances[*].wall_segment_id` references an existing entry in `room.wall_segments` (when non-null) | Orphan reference → analysis rejected; raise `UserError("orphan_wall_segment_id")` |
| `confidence` ∈ [0, 1] | Out of range → clamp + warning |
| `dimensions_confidence` values ∈ [0, 1] | Out of range → clamp + warning |
| `ts` parses as ISO 8601 | Unparseable → store NOW() + warning |

### 4.2 What the schema deliberately does NOT include

- **Cabinet recommendations.** Gemini is a *room understanding* layer, not
  a *kitchen designer*. Cabinet placement is the Configuration Engine's
  job (Module 7).
- **Color / material / theme.** Themes are picked by the customer in
  the workspace, not inferred from photos.
- **Pricing.** Out of scope for Module 6.
- **Confirmed flags.** These are set by humans in Odoo *after* the
  analysis lands — Gemini never sets `confirmed_by_human: true`.

---

## 5. Persistence — landing the response in Odoo

Module 6 receives the validated payload and lands it as one
`sb.kitchen.ai.analysis` record + N `sb.kitchen.appliance` records via
`sb.kitchen.project.consume_gemini_analysis(payload)`:

| Payload field | Destination field |
|---|---|
| `room.sink_detected` | `sb.kitchen.ai.analysis.sink_detected` |
| `room.window_count` | `.window_count` |
| `room.room_door_count` | `.room_door_count` |
| `room.floor_area_m2_approx` | `.floor_area_m2_approx` |
| `room.ceiling_height_mm_approx` | `.ceiling_height_mm_approx` |
| (entire payload) | `.raw_response_json` (escaped) |
| `appliances[*]` | `.detected_appliances_json` AND one `sb.kitchen.appliance` per item |
| Each appliance | dimensions copied to `sb.kitchen.appliance.{width,height,depth}_mm`; `confirmed_by_human` left **False** |

**Crucially:** every newly-created record lands with
`confirmed_by_human = False`. The designer must visit the workspace and
confirm each one before the Configuration Engine will proceed.

---

## 6. Failure modes & retry policy

| Mode | Detection | Module-6 action |
|---|---|---|
| Network error / timeout | `httpx.ConnectError` etc. | Up to 3 retries with exponential backoff (250 ms / 1 s / 4 s). Then mark project state unchanged + log a chatter message + raise `UserError("gemini_unavailable")`. |
| Auth failure (401/403) | HTTP status | No retries; surface `gemini_auth_failed` to the user immediately. |
| Quota exhaustion (429) | HTTP status | 1 retry after `Retry-After` header; then surface `gemini_quota_exhausted`. |
| Malformed JSON | `json.JSONDecodeError` | No retries (Gemini's structured-output mode should make this impossible; if it happens, something is very wrong). Raise `gemini_malformed_response` + attach the raw text to the chatter. |
| Schema mismatch | §4.1 rule | Reject the analysis; raise `gemini_schema_mismatch`. Do NOT partially land. |
| Out-of-range dimensions | §4.1 rule | Land the rest of the analysis, null the offending field, add a model_warning. |

---

## 7. Idempotency

Module 6 keys analyses by `(project_id, image_hash)`. Re-calling
`consume_gemini_analysis(payload)` with the same image hash is a no-op
that returns the existing analysis record. This makes it safe for the
caller (the workspace) to retry on transient errors without producing
duplicate analyses.

---

## 8. Auth & secret handling

- `GEMINI_API_KEY` env var (read at Module-6 init via
  `ir.config_parameter`). Never echoed in logs or error messages.
- Production must use a separate Vertex AI service account, not the
  Studio key, so quota + billing are scoped per project.
- The bridge service (`services/freecad_bridge`) does **not** need the
  Gemini key. Only the Odoo-side Module-6 worker calls Gemini.

---

## 9. End-to-end worked example

**Input:** customer uploads `kitchen_north_wall.jpg` to project KP/2026/000017.

**Workspace action:** the "Analyze Photo" button on the project form
calls `sb.kitchen.project.analyze_photo(attachment_id=…)`. That handler
reads the image, computes its SHA-256, and dispatches Module 6's
`_call_gemini(image_bytes, prompt_template_id="default_v1")`.

**Gemini response** (abridged):

```json
{
  "schema": "southbrook.gemini.room_analysis.v1",
  "model": "gemini-2.5-pro",
  "ts": "2026-06-09T17:42:00Z",
  "image_hash": "sha256:a1b2c3...",
  "room": {
    "sink_detected": true, "window_count": 1, "room_door_count": 1,
    "floor_area_m2_approx": 18.5, "ceiling_height_mm_approx": 2400,
    "wall_segments": [
      {"id": "wall_north", "length_mm_approx": 4200, "has_windows":[true], "has_doors":[false]},
      {"id": "wall_east",  "length_mm_approx": 2800, "has_windows":[false], "has_doors":[true]}
    ]
  },
  "appliances": [
    {"kind":"stove","label":"Gas range, 30\"","wall_segment_id":"wall_north",
     "position_pct_along_wall":0.62,"width_mm_approx":762,"height_mm_approx":914,
     "depth_mm_approx":610,"requires_clearance_mm":30,"confidence":0.86}
  ],
  "dimensions_confidence":{"wall_lengths":0.55,"appliance_widths":0.78,"ceiling_height":0.40},
  "model_warnings": []
}
```

**Module 6 lands:** 1 `sb.kitchen.ai.analysis` record (sink_detected=true,
window_count=1, etc., `confirmed_by_human=false`) + 1 `sb.kitchen.appliance`
record for the stove with `confirmed_by_human=false`. Designer reviews in
the workspace, confirms each, then
`sb.kitchen.project.is_ready_for_config_engine()` returns True and
Module 7 may proceed.

---

## 10. Versioning rule

Any change to a field name or type bumps the schema version. The
`schema` field literal becomes `southbrook.gemini.room_analysis.v2`.
Module 6's validator MUST accept the new version AND continue accepting
v1 for one release cycle (one Phase). Producers (the Gemini prompt
template + `responseSchema`) update first; consumers (Module 7) follow.
