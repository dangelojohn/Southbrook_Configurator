# Flutter ↔ Odoo Contract (G6)

> Stateless REST API between the Southbrook customer Flutter app and
> the SAMI Odoo backend. Closing this contract is the G6 gate from the
> init doc — Flutter code MUST NOT exist before the contract does.

**Version:** `southbrook.flutter.v1`
**Status:** GREEN — gate closed 2026-06-09
**Schema URI for runtime validation:** `southbrook.flutter.api.v1`
**Pairs with:** the G3 Gemini contract (the Flutter app's `/analyze`
call eventually invokes Module 6 server-side) and Module 5's project
state machine.

---

## 1. Design principles

The Flutter app runs offline-capable on consumer mobile devices, so the
API must be:

1. **Stateless** — every request carries its own auth. No session
   cookies. Auth via `X-Api-Key` header (one key per customer
   res.users record).
2. **Self-describing** — every response includes `schema` + version so
   the app can detect server upgrades and prompt for a self-update.
3. **Idempotent on writes** — every mutating endpoint accepts an
   optional `Idempotency-Key` header; replays return the original
   response.
4. **Multipart for media** — photos upload as `multipart/form-data`
   (consumer cellular network reliability beats JSON+base64).
5. **Versioned** — the URL prefix `/api/v1/` makes a v2 a side-by-side
   addition, not a breaking change.
6. **No N+1** — list endpoints include enough fields to render a card
   without per-record drill-down. Detail endpoints add the rest.

---

## 2. Auth

### 2.1 Issuance

A customer creates an API key in the portal (or via this API):

```
POST /api/v1/auth/login
Body: {"email": "...", "password": "..."}
Response: {"schema":"southbrook.flutter.api.v1",
           "api_key":"<32-hex>","expires_at":"2026-09-09T..."}
```

The app stores the key in the OS keychain (iOS Keychain / Android
Keystore — `flutter_secure_storage`). The key has 90-day expiry; the
app warns at 7 days remaining and silently refreshes via
`/api/v1/auth/refresh` if the user opens the app within the window.

### 2.2 Header

Every request EXCEPT `/auth/login` sends:

```
X-Api-Key: <key>
```

Missing or invalid → 401 `{"error":"invalid_api_key"}`.

Revoked (user clicked "sign out everywhere") → 401
`{"error":"revoked_api_key"}` — app deletes its keychain entry +
returns to login screen.

---

## 3. Endpoints

All responses are JSON unless noted. All timestamps are ISO 8601 UTC.

### 3.0 GET /api/v1/health  (no auth)

Liveness probe for monitors, load balancers, and pre-deploy smoke. No
`X-Api-Key` required; does no DB writes or model loads, so it's safe
for high-frequency polling.

```jsonc
{
  "schema": "southbrook.flutter.api.v1",
  "status": "ok",
  "service": "southbrook_api",
  "api_version": "v1",
  "schema_version": "southbrook.flutter.api.v1",
  "db": "southbrook"   // db name or null when the request context lacks one
}
```

Status codes:
- `200 OK` — service up; the response is enough for an external monitor
  to distinguish "service running but DB unreachable" (the controller
  itself wouldn't respond, so a 5xx or connect-refused) from "service down".

The body leaks nothing an unauthenticated caller couldn't already
discover from the public site (the db name is implied by the URL
hostname most of the time). Don't add anything sensitive here.

### 3.1 GET /api/v1/me

Returns the authenticated user's profile.

```jsonc
{
  "schema": "southbrook.flutter.api.v1",
  "user": {
    "id": 17, "name": "Alice Customer", "email": "alice@…",
    "is_dealer": false,
    "currency": "CAD"
  }
}
```

### 3.2 GET /api/v1/kitchen-projects

List the customer's projects. Pagination via `?limit=20&before=<cursor>`.

```jsonc
{
  "schema": "southbrook.flutter.api.v1",
  "projects": [
    {
      "id": 42, "code": "KP/2026/000042", "name": "Coastal Kitchen",
      "state": "awaiting_customer", "theme": "signature",
      "date_target": "2026-08-15",
      "cover_attachment_id": 7891,        // null if no photo yet
      "concept_count": 3,
      "has_unread_messages": false
    }
  ],
  "next_cursor": null
}
```

### 3.3 GET /api/v1/kitchen-projects/{id}

Full project detail.

```jsonc
{
  "schema": "southbrook.flutter.api.v1",
  "project": {
    "id": 42, "code": "KP/2026/000042", "name": "Coastal Kitchen",
    "state": "awaiting_customer", "theme": "signature",
    "salesperson": {"id": 8, "name": "Sam Designer", "email": "sam@…"},
    "ai_ready": true,                      // is_ready_for_config_engine()
    "selected_design_option_id": null,
    "photo_attachment_ids": [7891, 7892],
    "concept_ids": [501, 502, 503],
    "approval_history": [
      {"id":99,"type":"concept","state":"approved","date":"2026-06-09T…"}
    ]
  }
}
```

### 3.4 POST /api/v1/kitchen-projects/{id}/photos

Multipart upload of a room photo. Triggers AI analysis via Module 6
(synchronous within the request lifetime; mobile clients should set a
30s timeout and show a progress UI).

```
POST multipart/form-data
  photo: <file>
  prompt_template_code: default_v1   (optional)
Response:
  {"schema":"southbrook.flutter.api.v1",
   "attachment_id": 7893,
   "analysis_id": 184,
   "appliance_count": 2,
   "warnings": []}
```

Failure modes:
- 413 `payload_too_large` if photo > 7 MB
- 415 `unsupported_media_type` if not jpg/png
- 502 `gemini_unavailable` if Module 6's retry path exhausts

### 3.5 GET /api/v1/kitchen-projects/{id}/concepts

The A/B/C design options for review.

```jsonc
{
  "schema": "southbrook.flutter.api.v1",
  "concepts": [
    {
      "id": 501, "name": "Option A — Coastal Walnut",
      "description_html": "<p>…</p>",
      "estimated_price": 12450.00,
      "estimated_lead_time_days": 28,
      "preview_attachment_id": 7901,
      "is_selected": false,
      // Three.js scene payload, identical to placement_data_json from
      // Module 7. Apps that render in-app use this; apps that delegate
      // to /web/ via a WebView ignore it.
      "placement_data": { /* Module-7 envelope per G4 §2 */ }
    }
  ]
}
```

### 3.6 POST /api/v1/kitchen-projects/{id}/concepts/{option_id}/select

Flips `is_selected`. Module 5 one-of-N enforcement clears siblings.

```
Response: {"schema":"southbrook.flutter.api.v1","ok":true,
           "selected_id": 502}
```

### 3.7 POST /api/v1/kitchen-projects/{id}/approve

Records customer approval + advances state to `approved`. Pre-condition:
a concept is selected.

```
Optional body: {"notes": "Looks great!"}
Response on success:
  {"schema":"southbrook.flutter.api.v1","ok":true,
   "approval_id": 99, "project_state": "approved"}
Response if no concept selected: 409 'no_concept_selected'
Response if wrong state:        409 'invalid_state'
```

### 3.8 GET /api/v1/attachments/{id}

Stream the actual bytes. Auth + record-rule scoped (the customer can
only download attachments on their own projects). For Three.js rendering
the app pulls placement_data (§3.5) not raw STEP files — per init-doc
D-FC-06 "do not serve STEP files for customer preview."

---

## 4. Error envelope

Every error response is:

```jsonc
{
  "schema": "southbrook.flutter.api.v1",
  "error": "<machine_code>",
  "message": "<human_string, locale-aware>",
  "details": { /* optional */ }
}
```

Error codes are stable strings the app branches on; messages are
localised server-side from the `Accept-Language` header.

---

## 5. Idempotency contract

For every POST endpoint the client MAY send:

```
Idempotency-Key: <uuid v4>
```

The server stores `(api_key, idempotency_key) → response` for 24 hours.
Replays return the original status code + body. Different keys with the
same payload create separate records.

Critical for mobile: photo uploads on flaky cellular often retry; the
key ensures one analysis is created per real upload, not one per HTTP
retry.

---

## 6. Versioning rule

- Additive changes (new optional field) — no version bump.
- Breaking changes (rename, remove, type change) — new URL prefix
  `/api/v2/`. v1 and v2 coexist for at least one Phase cycle.
- The `schema` field literal in every response evolves with the URL
  prefix: `/api/v2/` returns `"schema": "southbrook.flutter.api.v2"`.

---

## 7. Out of scope for G6

- Push notifications (FCM/APNs). Future; the app polls /me for now.
- Real-time chat with the designer. Phase 2.
- Payment processing. Init-doc defers payment entirely to v2.
- Three.js geometry sharing across customers. Privacy/IP boundary —
  every customer sees only their own placement_data.

---

## 8. Worked example — happy path

```text
1. App opens, no key in keychain.
   POST /api/v1/auth/login  {email, password}
   → keychain.set("api_key", "<key>")

2. GET /api/v1/me → render header
   GET /api/v1/kitchen-projects → list page with 1 project

3. User taps project, app navigates to detail.
   GET /api/v1/kitchen-projects/42
   → state=draft, no concepts yet

4. User takes a kitchen photo, uploads.
   POST /api/v1/kitchen-projects/42/photos (multipart)
   → 200, analysis_id returned, ai_ready=false (designer must confirm)

5. (Designer in Odoo backend confirms appliances)
   User pulls-to-refresh.
   GET /api/v1/kitchen-projects/42
   → state=awaiting_customer, concept_count=3, ai_ready=true

6. GET /api/v1/kitchen-projects/42/concepts
   → 3 cards, app renders A/B/C

7. User picks B.
   POST .../concepts/502/select
   → ok, selected_id=502

8. User taps Approve.
   POST .../approve  {notes: "Looks great!"}
   → project_state=approved
```

End-to-end this is 6 round-trips for a brand-new customer; 4 for one
already authenticated. Each is < 200 KB except the photo upload.

---

## 9. Reference implementation

`flutter_app/lib/api_client.dart` implements every endpoint in this
document. The Flutter app's other files (UI, state management) consume
the client. Anyone shipping a competing front-end (web SPA, native iOS,
React Native) wires against this same contract.
