/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * cabinet_glb_loader.esm.js — Tier-1 cabinet GLB loader.
 *
 * Bridges the four-tier image cascade (CLAUDE.md §4.5) so the Three.js
 * kitchen viewport renders vendor-supplied GLB models (designed in
 * SketchUp Free / Blender / etc., dropped into
 *   addons/southbrook_estimating/static/lib/cabinets/<sku>.glb
 * and registered in cabinets.json) in place of the per-panel
 * BoxGeometry fallback.
 *
 * Public API:
 *
 *   await GlbRegistry.load()
 *       Fetch + cache the cabinets.json manifest. Idempotent — the
 *       second call awaits the first promise. Returns the manifest
 *       object; subsequent findGlbUrlFor() calls are synchronous.
 *
 *   GlbRegistry.findGlbUrlFor(sku)
 *       Two-tier lookup: exact SKU first, then template-key fallback
 *       (strips trailing -<width> / -<variant> token). Returns the
 *       absolute URL to the .glb asset, or null when nothing matches.
 *
 *   await GlbRegistry.loadCabinet(THREE, url)
 *       Returns a Promise that resolves to a THREE.Group (the loaded
 *       gltf.scene) ready to add to the viewport scene. Caches results
 *       per URL — second call for the same url resolves instantly with
 *       a CLONE of the cached scene so callers can safely mutate
 *       position / scale without affecting other instances. Resolves
 *       to null (never rejects) when THREE.GLTFLoader is unavailable
 *       or the fetch fails; the caller falls back to BoxGeometry.
 *
 * Why a single helper that never throws: this is an opt-in visual
 * upgrade. A missing vendor library, a malformed GLB, a 404 — any of
 * them must NOT take down the order-builder's 3D Kitchen tab. The
 * caller (kitchen_viewport.esm.js) treats `null` returns as "no
 * GLB this time, render boxes".
 */

const MANIFEST_URL =
    "/southbrook_estimating/static/lib/cabinets/cabinets.json";
const ASSET_BASE =
    "/southbrook_estimating/static/lib/cabinets/";

class _GlbRegistry {
    constructor() {
        this._manifest = null;          // resolved manifest object
        this._loadPromise = null;       // in-flight manifest fetch
        this._sceneCache = new Map();   // url -> THREE.Group (master, never mutated)
        this._loadCabinetCache = new Map(); // url -> Promise<THREE.Group|null>
        this._warnedMissingLib = false;
    }

    /**
     * Fetch + cache cabinets.json. Returns the manifest object (or an
     * empty {models: {}} stub on any failure — the loader stays
     * functional, just with zero registered models).
     */
    async load() {
        if (this._manifest !== null) return this._manifest;
        if (this._loadPromise) return this._loadPromise;
        this._loadPromise = (async () => {
            try {
                const resp = await fetch(MANIFEST_URL, {
                    credentials: "same-origin",
                });
                if (!resp.ok) throw new Error("HTTP " + resp.status);
                const json = await resp.json();
                this._manifest = (json && typeof json === "object")
                    ? json : { models: {} };
                if (!this._manifest.models
                    || typeof this._manifest.models !== "object") {
                    this._manifest.models = {};
                }
            } catch (err) {
                // eslint-disable-next-line no-console
                console.warn(
                    "[sb_cfg] cabinet GLB manifest unavailable — "
                    + "falling back to BoxGeometry for every cabinet:",
                    err,
                );
                this._manifest = { models: {} };
            }
            return this._manifest;
        })();
        return this._loadPromise;
    }

    /**
     * Two-step lookup with template-key fallback.
     *
     *   findGlbUrlFor("SB-BASE-1DR-30")
     *     1. exact:    "sb-base-1dr-30"  -> models["sb-base-1dr-30"]
     *     2. template: "sb-base-1dr"     -> models["sb-base-1dr"]
     *     3. null
     *
     * Synchronous — caller MUST await load() first.
     */
    findGlbUrlFor(sku) {
        if (!sku || !this._manifest || !this._manifest.models) return null;
        const key = String(sku).trim().toLowerCase();
        if (!key) return null;
        const models = this._manifest.models;
        const exact = models[key];
        if (exact && exact.file) return ASSET_BASE + exact.file;
        // Strip trailing -<token> repeatedly so sb-base-1dr-30-maple
        // tries sb-base-1dr-30 then sb-base-1dr.
        let trimmed = key;
        while (true) {
            const dash = trimmed.lastIndexOf("-");
            if (dash <= 0) return null;
            trimmed = trimmed.slice(0, dash);
            const entry = models[trimmed];
            if (entry && entry.file) return ASSET_BASE + entry.file;
        }
    }

    /**
     * Load a GLB and return its scene as a fresh THREE.Group the caller
     * can mutate freely. Resolves to null on any failure so the caller
     * falls back to BoxGeometry without special-casing.
     */
    async loadCabinet(THREE, url) {
        if (!THREE || !url) return null;
        if (!THREE.GLTFLoader) {
            if (!this._warnedMissingLib) {
                this._warnedMissingLib = true;
                // eslint-disable-next-line no-console
                console.warn(
                    "[sb_cfg] THREE.GLTFLoader not loaded — vendor "
                    + "addons/southbrook_estimating/static/lib/three/"
                    + "GLTFLoader.js to enable Tier-1 cabinet models. "
                    + "See static/lib/cabinets/README.md.",
                );
            }
            return null;
        }
        // Single in-flight fetch per URL — concurrent loadCabinet()
        // calls for the same URL share one promise.
        if (this._loadCabinetCache.has(url)) {
            const master = await this._loadCabinetCache.get(url);
            return master ? master.clone(true) : null;
        }
        const promise = new Promise((resolve) => {
            const loader = new THREE.GLTFLoader();
            loader.load(
                url,
                (gltf) => {
                    if (gltf && gltf.scene) {
                        this._sceneCache.set(url, gltf.scene);
                        resolve(gltf.scene);
                    } else {
                        resolve(null);
                    }
                },
                undefined,
                (err) => {
                    // eslint-disable-next-line no-console
                    console.warn(
                        "[sb_cfg] failed to load cabinet GLB " + url
                        + " — using BoxGeometry fallback:", err,
                    );
                    resolve(null);
                },
            );
        });
        this._loadCabinetCache.set(url, promise);
        const master = await promise;
        return master ? master.clone(true) : null;
    }

    // Test-only — drop all caches so a unit test can reset state
    // between cases. Never call from production code.
    _resetForTests() {
        this._manifest = null;
        this._loadPromise = null;
        this._sceneCache.clear();
        this._loadCabinetCache.clear();
        this._warnedMissingLib = false;
    }
}

export const GlbRegistry = new _GlbRegistry();
