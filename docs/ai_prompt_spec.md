# AI Prompt Spec (Module 6 — companion to G3)

> The prompt template Module 6 sends to Gemini alongside the room photo.
> Designed against the G3 response schema so the model returns
> structurally-conformant JSON the validator can land without fragile
> heuristic parsing.

**Version:** `default_v1`
**Pairs with:** `docs/api_contracts/gemini_odoo_contract.md`

---

## 1. Prompt structure

The prompt is plain text, sent as the second part of the request body
(image part is first). It explains the task, names the schema, and
caps the model with the negative-space rules from the contract.

```text
You are analyzing a photograph of a kitchen room (or an empty room
intended for a kitchen). Your job is to produce a structured room
analysis — NOT a kitchen design.

Return JSON exactly matching the schema "southbrook.gemini.room_analysis.v1".

Rules you MUST follow:

1. NEVER recommend cabinets. The cabinet placement happens downstream.
2. Mark sink_detected: true ONLY when you can SEE a sink fixture (basin
   + tap). If you see a stovetop, fridge, or empty corner where a sink
   could go, leave it false.
3. All numeric dimensions are approximate — provide your best guess but
   ASSUME a human will re-measure. Do not over-claim precision.
4. Wall segments: identify the room outline as a sequence of straight
   walls. Use ids "wall_north", "wall_east", etc. (cardinal directions
   chosen so the longest wall is north).
5. Appliances: list ONLY appliances you can see. Do not invent. A
   stove must be on a wall_segment_id (or null if free-standing in the
   middle of the room — island).
6. position_pct_along_wall is 0.0 at the leftmost end of the wall as
   the viewer faces it, 1.0 at the rightmost.
7. For ANY dimension you are <50% confident about, return the dimension
   AND set the corresponding dimensions_confidence entry to your true
   confidence (do not inflate to keep the field populated).
8. If a person, prop, or shadow makes a measurement impossible, return
   null for that dimension and add a string to model_warnings naming
   the issue.

Plausibility bounds (out-of-range dimensions will be rejected):
  wall length:     300 mm  ≤  L  ≤  15 000 mm
  appliance:       100 mm  ≤  D  ≤   2 000 mm
  ceiling height: 1 500 mm  ≤  H  ≤   4 500 mm

If the image is not a kitchen photo, return an empty room object and an
empty appliances list, with model_warnings = ["image_not_a_kitchen"].

DO NOT include any prose outside the JSON. DO NOT wrap the JSON in
backticks. The entire response body must be parseable as JSON.
```

---

## 2. Why this prompt is shaped the way it is

- **No cabinet recommendations** (rule 1): keeps Gemini in its lane and
  prevents a downstream pipeline from accidentally rendering Gemini-
  imagined cabinets.
- **Sink-detection caution** (rule 2): the hallucinated-sink failure
  mode is mentioned by name in the init doc's Module 6 test set —
  forcing Gemini to anchor on visible fixtures suppresses it.
- **Cardinal-direction wall ids** (rule 4): gives the Configuration
  Engine a stable spatial reference frame independent of camera
  orientation.
- **Conservative confidences** (rule 7): the alternative — Gemini
  always returning 0.99 — would make the dimensions_confidence field
  useless for triaging which dimensions need re-measurement.
- **Plausibility bounds in the prompt** (rule 8): out-of-range numbers
  cost ALL of Gemini's time on a re-validate cycle if they happen.
  Telling Gemini the bounds up-front pushes that work to the producer.

---

## 3. Prompt storage in Odoo

Module 6 stores prompts as `sb.gemini.prompt.template` records so a
prompt rev can be authored without a code deploy. Each template has:

- `code` (Char, indexed) — e.g. `default_v1`
- `body` (Text) — the prompt above
- `active` (Boolean) — only one active per code-prefix
- `model` (Char) — `gemini-2.5-pro` or `gemini-2.5-flash`
- `temperature`, `top_k`, `top_p`, `max_output_tokens` (numeric)
- `version_note` (Char) — short changelog string

The default prompt above is seeded as code `default_v1`. Authoring a
v2 (e.g. to tighten the sink-detection rule) means:

1. Insert a `default_v2` template with the new body.
2. Set `default_v1.active = False`.
3. The next analysis call picks v2 automatically.

The old v1 stays for audit / regression diff.

---

## 4. Test prompt fixtures

`addons/southbrook_ai_design/tests/fixtures/` ships:

- `kitchen_with_visible_sink.jpg` + golden JSON `sink_true_v1.json`
- `empty_room_no_appliances.jpg` + golden `empty_v1.json`
- `not_a_kitchen.jpg` (e.g. a living room) + golden
  `not_a_kitchen_v1.json` with `image_not_a_kitchen` warning
- `kitchen_with_occluding_person.jpg` + golden showing null dimensions
  + occlusion warning

These are used by the mock-Gemini test mode (see Module 6 README) so
schema-validation tests run without network access or API spend.
