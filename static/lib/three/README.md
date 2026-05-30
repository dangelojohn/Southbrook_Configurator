# Three.js library — vendoring instructions

The 3D cabinet viewport (`static/src/js/cabinet_viewport.esm.js`)
requires Three.js loaded as `window.THREE` plus `window.THREE.OrbitControls`.
This directory holds the vendored bundle.

## Status

**Not vendored yet.** The OWL component detects the absence of
`window.THREE` at mount time and shows a friendly placeholder instead
of crashing.

## To vendor (one-time)

Run on your workstation (NOT inside the QNAP container; the bundle ships
in the addon and rides along to the QNAP via the normal sync):

```bash
cd ~/southbrook-v19cr/addons/southbrook_estimating/static/lib/three/

# Three.js core, UMD build, minified.
curl -L -o three.min.js \
  https://unpkg.com/three@0.160.0/build/three.min.js

# OrbitControls — UMD/legacy build (the ESM-only newer build is harder
# to consume from Odoo's asset bundler without import maps; the r147
# examples/js/ UMD build works against r160's core).
curl -L -o OrbitControls.js \
  https://cdn.jsdelivr.net/gh/mrdoob/three.js@r147/examples/js/controls/OrbitControls.js

# MIT license — required to accompany the redistributed bundle.
curl -L -o LICENSE.txt \
  https://raw.githubusercontent.com/mrdoob/three.js/r160/LICENSE
```

Verify file sizes (approximate):

| File             | Size    | Notes |
|------------------|--------:|-------|
| `three.min.js`   | ~600 KB | UMD, minified |
| `OrbitControls.js` | ~25 KB | UMD shim that decorates `window.THREE` |
| `LICENSE.txt`    | ~1 KB   | MIT license |

## After vendoring — wire the bundle

Edit `addons/southbrook_estimating/__manifest__.py`. In the
`"assets" → "web.assets_backend"` list, uncomment the two `static/lib/three/`
entries that already sit at the TOP of the list (they MUST load before
`cabinet_viewport.esm.js`):

```python
"assets": {
    "web.assets_backend": [
        # Three.js — load before the OWL component that consumes it.
        "southbrook_estimating/static/lib/three/three.min.js",
        "southbrook_estimating/static/lib/three/OrbitControls.js",
        # OWL viewport component + template + styles.
        "southbrook_estimating/static/src/scss/cabinet_viewport.scss",
        "southbrook_estimating/static/src/js/cabinet_viewport.esm.js",
        "southbrook_estimating/static/src/xml/cabinet_viewport.xml",
    ],
},
```

Then restart the Odoo workers + hard-refresh your browser. The
"Three.js bundle not loaded" placeholder will be replaced by the live
3D viewport.

## Why r160?

Stable, ships UMD and ESM, lands well after Odoo 19's JS toolchain.
r161+ moved more components to ESM-only; r160 keeps the UMD path open
for clean Odoo asset bundling without import-map plumbing.

## License compliance

Three.js is MIT-licensed. Keep `LICENSE.txt` in this directory.
Re-distributing Three.js without the license file would be an MIT
violation.

## Track 1 status

Build Spec / Charter trail:

- `docs/PHASE_2_CHARTER.md` amendment 1 introduces Track 1.
- `models/product_config_line.py::get_3d_payload` produces the
  per-panel layout from Phase-1 routine #1.
- `static/src/js/cabinet_viewport.esm.js` consumes the payload.
- `views/product_configurator_3d_view.xml` injects the widget into
  the OCA wizard form.
- The "not loaded" placeholder in the component template links back
  to this README.
