# Southbrook Kitchen — Flutter Customer App

> Mobile customer experience for the SAMI / Southbrook AI Kitchen
> Platform. Implements the G6 contract at
> `docs/api_contracts/flutter_odoo_contract.md`.

**Status:** skeleton — proves the contract; full UI lands once an Odoo
`/api/v1/*` implementation is live.

## Scope

What this skeleton ships:

- `lib/api_client.dart` — every endpoint from the G6 contract,
  typed Dart. The reference implementation other Southbrook clients
  (web SPA, native iOS, React Native) wire against.
- `lib/main.dart` — login screen + project list. Enough surface to
  prove the contract end-to-end against a stub backend.
- `pubspec.yaml` — `http`, `flutter_secure_storage`, `image_picker`
  pinned to current Flutter 3.24 / Dart 3.5 SDK.

What lands in subsequent phases:

- Photo capture + multipart upload (api_client already implements the
  endpoint; UI is missing).
- Concept review cards + select / approve flow.
- Three.js / model-viewer preview from `placement_data` (Module 7
  output) — sharing geometry with the web Three.js KitchenCanvas via
  `shared/southbrook_dims.js`.
- Push notifications (FCM/APNs) for "concepts ready" + "design
  approved" events.

## Run

```bash
cd flutter_app
flutter pub get
flutter run -d <device>
```

Login URL defaults to `https://southbrookcabinetry.space`; override
on the login screen for dev.

## Test

```bash
flutter test
```

Test scope currently: api_client error decoding + schema validation.
Integration tests (against a live Odoo dev stack) land with the
`/api/v1/*` Odoo addon.
