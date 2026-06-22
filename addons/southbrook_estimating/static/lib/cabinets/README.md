# Tier-1 cabinet GLB assets

Drop `.glb` model files in this directory + register them in
`cabinets.json` and the Three.js viewport (`kitchen_viewport.esm.js`)
will render them in place of the per-panel BoxGeometry fallback.

Aligns with the four-tier image cascade in `CLAUDE.md` §4.5:

- **Tier 1** — vendor-supplied cabinet renders (this directory)
- Tier 2 — runtime-baked thumbnails from the live Three.js scene
- Tier 3 — hand-authored SVG fallbacks per cabinet code
- Tier 4 — neutral placeholder

## Asset naming convention

Filename = SKU or template key, lower-case, dashes only, `.glb`
extension. Examples:

```
sb-base-1dr.glb          # all widths of base 1-door, scaled at render
sb-base-1dr-30.glb       # 30" override — wins over sb-base-1dr.glb
sb-wall-2dr.glb
sb-tall-pantry.glb
sb-corner.glb
```

Lookup order (see `cabinet_glb_loader.esm.js#findGlbUrlFor`):

1. **Exact SKU match** — `<lower-case sku>.glb`. Used when a
   width/finish-specific master exists (e.g. the 36" sink base has a
   carved-out apron the 24" doesn't).
2. **Template key fallback** — strips the trailing width or variant
   token (e.g. `sb-base-1dr-30` → `sb-base-1dr`). Lets one model cover
   every width of a family; the viewport scales the mesh's X/Z axes
   to match the configured `width_mm` / `depth_mm`.
3. **Null** — no match → caller falls back to BoxGeometry (current
   behaviour for every cabinet, until the first `.glb` lands).

## Authoring in SketchUp Free

1. Open <https://app.sketchup.com/> (free, browser-based).
2. Model the cabinet **with the origin at the BOTTOM-FRONT-LEFT
   corner of the carcass**, X = width, Y = height, Z = depth toward
   the viewer. The Three.js viewport assumes this orientation.
3. **Units = millimetres.** The loader does not rescale; a 600 mm
   wide cabinet must be 600 model units wide.
4. Export → `.glb`. SketchUp Free does not export GLB natively; use
   one of:
   - The free *Universal Importer* extension by Eneroth, or
   - Export to `.skp` → open in Blender (free) → `File → Export → glTF 2.0`.
5. Optimise: target < 1 MB per cabinet. Use Draco compression if your
   exporter supports it; the loader picks up `KHR_draco_mesh_compression`
   automatically when the GLTFLoader+DRACOLoader pair is loaded.
6. Drop the `.glb` in this directory + add an entry to `cabinets.json`:
   ```json
   {
     "models": {
       "sb-base-1dr": { "file": "sb-base-1dr.glb" }
     }
   }
   ```

## Vendoring `THREE.GLTFLoader`

`three.min.js` (r160 UMD) does **not** ship `GLTFLoader` — Three.js
moved it to the `examples/jsm/loaders/` ESM tree post-r147. We need
the legacy UMD build alongside `OrbitControls.js`. Drop these into
`../three/` (same directory as `three.min.js`):

```
curl -L -o ../three/GLTFLoader.js \
  https://unpkg.com/three@0.160.0/examples/js/loaders/GLTFLoader.js
# (optional, for Draco-compressed GLBs)
curl -L -o ../three/DRACOLoader.js \
  https://unpkg.com/three@0.160.0/examples/js/loaders/DRACOLoader.js
mkdir -p ../three/draco
curl -L -o ../three/draco/draco_decoder.js \
  https://unpkg.com/three@0.160.0/examples/jsm/libs/draco/draco_decoder.js
curl -L -o ../three/draco/draco_decoder.wasm \
  https://unpkg.com/three@0.160.0/examples/jsm/libs/draco/draco_decoder.wasm
```

Then register `GLTFLoader.js` (and optionally `DRACOLoader.js`) in
both addon manifests, after `three.min.js` and before
`cabinet_glb_loader.esm.js`. See `__manifest__.py` for the existing
asset declarations.

The loader degrades gracefully when `THREE.GLTFLoader` is missing —
the kitchen viewport will silently fall back to BoxGeometry for every
cabinet, and `console.warn` once per page load that the vendor lib is
absent. So this directory and `cabinets.json` can be populated by
designers before the loader lib is vendored without breaking the
existing UI.

## Why a static manifest instead of auto-discovery

The browser cannot list a directory. Auto-discovery would mean a
HEAD probe per SKU per scene build — wasteful at ~12 cabinets per
order, especially on flaky mobile networks. The JSON manifest is
written once when the asset lands, fetched once per page load, then
served from in-memory cache by `cabinet_glb_loader.esm.js`.
