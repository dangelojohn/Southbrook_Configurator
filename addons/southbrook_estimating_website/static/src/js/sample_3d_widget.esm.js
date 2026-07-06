/** @odoo-module **/
/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Southbrook 3D Sample Preview — public homepage hero widget.
 * ---------------------------------------------------------------------
 * A non-persisting, client-side-only "taste" of the real Order Builder
 * (/my/southbrook/order-builder/:id, logged-in only). An anonymous
 * visitor can:
 *   - orbit / zoom the room (OrbitControls, or the 1-6 / R / +- view
 *     toolbar mirrored from the real configurator),
 *   - drag the cabinets around to reposition them,
 *   - drag two sample cabinets in from the inventory list, and
 *   - toggle a Wireframe/measurement view.
 * NOTHING here calls the backend, reads/writes any Odoo model, or
 * persists across reload. The clear CTA is "Sign in to save →".
 *
 * Kiosk hygiene: 30s after the visitor's last interaction the scene
 * resets to the default 6 cabinets + default (persp/#6) camera framing,
 * wireframe off — so the next visitor always sees a clean sample.
 *
 * Provenance: scene logic is a browser-validated reference, adapted:
 *   1. r128 → r160 color API (this repo vendors r160 as window.THREE +
 *      THREE.OrbitControls in web.assets_frontend). r152+ removed the
 *      old encoding API, so outputEncoding/texture.encoding =
 *      THREE.sRGBEncoding became outputColorSpace/texture.colorSpace =
 *      THREE.SRGBColorSpace (THREE.sRGBEncoding is undefined in r160).
 *   2. Dependency-free self-mount on `.o_sb_sample3d_host`; no-ops on
 *      every other frontend page.
 *   3. Host-friendly lifecycle: lazy WebGL init on scroll-into-view,
 *      render loop paused offscreen, devicePixelRatio capped at 2, a
 *      complete teardown, and a static fallback if WebGL is absent.
 *
 * The drop-target raycast intentionally uses an INFINITE math plane, not
 * the bounded floor mesh, to avoid the finite-mesh drop dead-zone.
 */

const HOST_SELECTOR = ".o_sb_sample3d_host";

const ROOM_W = 96;
const ROOM_D = 72;
const ROOM_H = 96;
const IDLE_MS = 30000;   // 30s kiosk idle reset

// Camera presets — mirror the real configurator's 1-6 views, approximated
// on this widget's single perspective camera (no separate ortho camera).
const VIEWS = {
    iso:   { pos: [115, 108, 140], target: [0, 40, -8] },
    top:   { pos: [0, 300, 0.001], target: [0, 0, -8] },
    front: { pos: [0, 58, 205],    target: [0, 46, -22] },
    left:  { pos: [-205, 60, 70],  target: [-10, 44, -18] },
    right: { pos: [205, 60, 70],   target: [10, 44, -18] },
    persp: { pos: [128, 100, 148], target: [0, 45, 0] },
};
// Same glyphs + numbering as the backend/portal view toolbar.
const VIEW_BTNS = [
    { key: "iso",   n: "1", icon: "⬡", label: "Isometric" },   // ⬡
    { key: "top",   n: "2", icon: "▦", label: "Top / Plan" },  // ▦
    { key: "front", n: "3", icon: "▮", label: "Front" },       // ▮
    { key: "left",  n: "4", icon: "◧", label: "Left" },        // ◧
    { key: "right", n: "5", icon: "◨", label: "Right" },       // ◨
    { key: "persp", n: "6", icon: "◉", label: "Perspective" }, // ◉
];

// ---------------------------------------------------------------------
// Static fallback — shown when WebGL/THREE is unavailable so the hero
// card is never an empty void. Minimal, on-brand, keeps the CTA.
// ---------------------------------------------------------------------
function renderFallback(host) {
    host.innerHTML = `
      <div style="display:flex;flex-direction:column;height:100%;">
        <div style="display:flex;align-items:center;justify-content:space-between;background:#6b4a30;color:#fff;padding:8px 14px;font-family:sans-serif;">
          <span style="background:rgba(255,255,255,0.22);padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;letter-spacing:0.06em;">SAMPLE</span>
          <a href="/web/login" style="color:#fff;font-weight:700;text-decoration:none;font-size:11px;">Sign in to save &rarr;</a>
        </div>
        <div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:24px;text-align:center;font-family:sans-serif;background:#efece6;color:#4a3c2e;">
          <div style="font-size:16px;font-weight:600;">Design your kitchen in 3D</div>
          <div style="font-size:13px;opacity:0.8;max-width:220px;line-height:1.5;">Configure cabinets, see live pricing, and request a quote — all in your browser.</div>
          <a href="/my/southbrook/order-builder/new" style="margin-top:6px;background:#6b4a30;color:#fff;text-decoration:none;font-size:13px;font-weight:600;padding:8px 16px;border-radius:6px;">Design Your Kitchen &rarr;</a>
        </div>
      </div>`;
}

function webglSupported() {
    try {
        const c = document.createElement("canvas");
        return !!(window.WebGLRenderingContext &&
            (c.getContext("webgl") || c.getContext("experimental-webgl")));
    } catch (_e) {
        return false;
    }
}

// ---------------------------------------------------------------------
// The scene. Returns { play, pause, destroy }. Only built once visible.
// ---------------------------------------------------------------------
function buildScene(host) {
    const THREE = window.THREE;

    // ----- DOM scaffold (minimal: header + canvas + 2 inventory cards) -
    host.innerHTML = "";
    Object.assign(host.style, {
        padding: "0",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        height: "480px",
        background: "#efece6",
        position: "relative",
    });
    host.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;background:#6b4a30;color:#fff;padding:8px 14px;font-family:sans-serif;">
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="background:rgba(255,255,255,0.22);padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;letter-spacing:0.06em;">SAMPLE</span>
          <button type="button" class="o_sb_sample3d_wire" style="background:transparent;color:#fff;border:1px solid rgba(255,255,255,0.45);border-radius:4px;padding:2px 8px;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;">Wireframe</button>
        </div>
        <a href="/web/login" style="color:#fff;font-weight:700;text-decoration:none;font-size:11px;">Sign in to save &rarr;</a>
      </div>
      <div style="display:flex;flex:1;min-height:0;">
        <div class="o_sb_sample3d_canvas" style="flex:1;position:relative;background:#f4f1ec;"></div>
        <div style="width:180px;background:#fff;border-left:1px solid #ddd;padding:10px;font-family:sans-serif;overflow-y:auto;">
          <div class="o_sb_sample3d_item" draggable="true" data-type="base" style="cursor:grab;border:1px solid #e0d9cf;border-radius:6px;padding:6px 8px;margin-bottom:8px;background:#fdfaf6;">
            <div style="font-size:12px;font-weight:700;color:#333;">Base Cabinet 24"</div>
            <div style="font-size:11px;color:#888;">B24 &middot; $180.00</div>
          </div>
          <div class="o_sb_sample3d_item" draggable="true" data-type="wall" style="cursor:grab;border:1px solid #e0d9cf;border-radius:6px;padding:6px 8px;margin-bottom:8px;background:#fdfaf6;">
            <div style="font-size:12px;font-weight:700;color:#333;">Wall Cabinet 24"</div>
            <div style="font-size:11px;color:#888;">W24 &middot; $150.00</div>
          </div>
        </div>
      </div>`;

    const wrap = host.querySelector(".o_sb_sample3d_canvas");
    const wireBtn = host.querySelector(".o_sb_sample3d_wire");

    // ----- Scene / camera / renderer --------------------------------
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf0ece2);

    const camera = new THREE.PerspectiveCamera(
        42, wrap.clientWidth / wrap.clientHeight, 0.1, 2000);
    camera.position.set(128, 100, 148);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(wrap.clientWidth, wrap.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2)); // cap for mobile GPUs
    renderer.outputColorSpace = THREE.SRGBColorSpace;                   // r160 (was outputEncoding)
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    wrap.appendChild(renderer.domElement);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 45, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 45;
    controls.maxDistance = 340;
    controls.maxPolarAngle = Math.PI / 2 - 0.02;
    controls.update();

    // ----- Kiosk idle-reset + wireframe state -----------------------
    let wireframe = false;
    let idleTimer = null;
    let suppressArm = false;
    let currentView = "persp";

    // ----- Lighting -------------------------------------------------
    scene.add(new THREE.HemisphereLight(0xffffff, 0xcfc6b4, 0.65));
    scene.add(new THREE.AmbientLight(0xffffff, 0.4));

    const sun = new THREE.DirectionalLight(0xfff6e8, 1.15);
    sun.position.set(95, 165, 115);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    sun.shadow.camera.left = -70; sun.shadow.camera.right = 70;
    sun.shadow.camera.top = 70; sun.shadow.camera.bottom = -70;
    sun.shadow.camera.near = 10; sun.shadow.camera.far = 350;
    sun.shadow.bias = -0.0015;
    scene.add(sun);

    const fill = new THREE.DirectionalLight(0xdfeeff, 0.3);
    fill.position.set(-80, 60, -40);
    scene.add(fill);

    // ----- Procedural textures (canvas-generated; no external assets) -
    function makeWoodTexture() {
        const c = document.createElement("canvas"); c.width = 256; c.height = 256;
        const ctx = c.getContext("2d");
        const plankH = 32;
        for (let y = 0; y < 256; y += plankH) {
            const shade = 205 + Math.floor(Math.random() * 18) - 9;
            ctx.fillStyle = `rgb(${shade + 24},${shade + 4},${shade - 28})`;
            ctx.fillRect(0, y, 256, plankH - 2);
            ctx.fillStyle = "rgba(60,40,20,0.18)";
            ctx.fillRect(0, y + plankH - 2, 256, 2);
            for (let i = 0; i < 5; i++) {
                ctx.strokeStyle = "rgba(110,80,50,0.12)";
                ctx.beginPath();
                const yy = y + 3 + Math.random() * (plankH - 6);
                ctx.moveTo(0, yy);
                ctx.lineTo(256, yy + (Math.random() * 5 - 2.5));
                ctx.stroke();
            }
        }
        const tex = new THREE.CanvasTexture(c);
        tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
        tex.repeat.set(5, 4);
        tex.colorSpace = THREE.SRGBColorSpace;   // r160 (was tex.encoding)
        return tex;
    }

    function makeTileTexture() {
        const c = document.createElement("canvas"); c.width = 128; c.height = 128;
        const ctx = c.getContext("2d");
        ctx.fillStyle = "#f4f2ee"; ctx.fillRect(0, 0, 128, 128);
        ctx.strokeStyle = "rgba(0,0,0,0.16)"; ctx.lineWidth = 2.5;
        const tileW = 64, tileH = 28;
        let row = 0;
        for (let y = -tileH; y < 128 + tileH; y += tileH) {
            const offset = row % 2 === 0 ? 0 : tileW / 2;
            for (let x = -tileW; x < 128 + tileW; x += tileW) {
                ctx.strokeRect(x + offset, y, tileW, tileH);
            }
            row++;
        }
        const tex = new THREE.CanvasTexture(c);
        tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
        tex.repeat.set(3.2, 1.4);
        tex.colorSpace = THREE.SRGBColorSpace;   // r160 (was tex.encoding)
        return tex;
    }

    // Shared, scene-lifetime resources → disposed once in destroy().
    const disposables = [];
    const track = (obj) => { disposables.push(obj); return obj; };

    // ----- Room shell -----------------------------------------------
    const floorTex = track(makeWoodTexture());
    const floor = new THREE.Mesh(
        track(new THREE.PlaneGeometry(ROOM_W, ROOM_D)),
        track(new THREE.MeshStandardMaterial({
            map: floorTex, roughness: 0.55, metalness: 0.04, side: THREE.DoubleSide })));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    const backWall = new THREE.Mesh(
        track(new THREE.PlaneGeometry(ROOM_W, ROOM_H)),
        track(new THREE.MeshStandardMaterial({
            color: 0xd9d0bd, roughness: 1, metalness: 0, side: THREE.DoubleSide })));
    backWall.position.set(0, ROOM_H / 2, -ROOM_D / 2);
    backWall.receiveShadow = true;
    scene.add(backWall);

    const leftWall = new THREE.Mesh(
        track(new THREE.PlaneGeometry(ROOM_D, ROOM_H)),
        track(new THREE.MeshStandardMaterial({
            color: 0xcdc3ad, roughness: 1, metalness: 0, side: THREE.DoubleSide })));
    leftWall.rotation.y = Math.PI / 2;
    leftWall.position.set(-ROOM_W / 2, ROOM_H / 2, 0);
    leftWall.receiveShadow = true;
    scene.add(leftWall);

    const baseboardMat = track(new THREE.MeshStandardMaterial({
        color: 0xfbfaf7, roughness: 0.85 }));
    const bbBack = new THREE.Mesh(track(new THREE.BoxGeometry(ROOM_W, 4, 1)), baseboardMat);
    bbBack.position.set(0, 2, -ROOM_D / 2 + 0.5);
    scene.add(bbBack);
    const bbLeft = new THREE.Mesh(track(new THREE.BoxGeometry(1, 4, ROOM_D)), baseboardMat);
    bbLeft.position.set(-ROOM_W / 2 + 0.5, 2, 0);
    scene.add(bbLeft);

    const backsplash = new THREE.Mesh(
        track(new THREE.PlaneGeometry(72, 18)),
        track(new THREE.MeshStandardMaterial({
            map: track(makeTileTexture()), roughness: 0.35, metalness: 0.05 })));
    backsplash.position.set(0, 45, -ROOM_D / 2 + 0.15);
    scene.add(backsplash);

    // Simple "window" for a soft daylight accent.
    const windowFrame = new THREE.Mesh(
        track(new THREE.BoxGeometry(1, 30, 26)),
        track(new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.6 })));
    windowFrame.position.set(-ROOM_W / 2 + 0.4, 66, 8);
    scene.add(windowFrame);

    const windowGlow = new THREE.Mesh(
        track(new THREE.PlaneGeometry(24, 26)),
        track(new THREE.MeshStandardMaterial({
            color: 0xeaf4ff, emissive: 0xcfe8ff, emissiveIntensity: 0.9, roughness: 0.9 })));
    windowGlow.rotation.y = Math.PI / 2;
    windowGlow.position.set(-ROOM_W / 2 + 0.9, 66, 8);
    scene.add(windowGlow);

    const winLight = new THREE.PointLight(0xdcebff, 0.4, 140);
    winLight.position.set(-ROOM_W / 2 + 10, 66, 8);
    scene.add(winLight);

    // ----- Cabinets --------------------------------------------------
    // Per-cabinet UNIQUE resources (box + edge geo/mat, decor geos, label
    // tex/mat) are disposed when that cabinet is removed — the 30s kiosk
    // reset recreates the defaults repeatedly, so this prevents a leak.
    // SHARED decor materials are created once and tracked for teardown.
    const placed = [];
    const cabinetMat = () => new THREE.MeshStandardMaterial({
        color: 0xffffff, roughness: 0.32, metalness: 0.04 });
    const knobMat = track(new THREE.MeshStandardMaterial({
        color: 0xb9bdc4, metalness: 0.9, roughness: 0.18 }));
    const counterMat = track(new THREE.MeshStandardMaterial({
        color: 0xe7e4de, roughness: 0.12, metalness: 0.08 }));
    const crownMat = track(new THREE.MeshStandardMaterial({
        color: 0xfbfaf7, roughness: 0.5 }));
    const grooveMat = track(new THREE.MeshStandardMaterial({
        color: 0xdedad0, roughness: 0.6 }));
    const kickMat = track(new THREE.MeshStandardMaterial({
        color: 0xe3e0d8, roughness: 0.8 }));

    const fmt = (n) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

    // Dimension label sprite (canvas texture — no external font asset).
    function makeLabel(text) {
        const c = document.createElement("canvas"); c.width = 170; c.height = 46;
        const ctx = c.getContext("2d");
        ctx.fillStyle = "rgba(24,22,18,0.85)"; ctx.fillRect(0, 0, 170, 46);
        ctx.strokeStyle = "rgba(255,255,255,0.35)"; ctx.lineWidth = 2;
        ctx.strokeRect(1, 1, 168, 44);
        ctx.fillStyle = "#fff";
        ctx.font = "bold 20px sans-serif";
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText(text, 85, 24);
        const tex = new THREE.CanvasTexture(c);
        tex.colorSpace = THREE.SRGBColorSpace;
        const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true });
        const sp = new THREE.Sprite(mat);
        sp.scale.set(23, 6.2, 1);
        sp.userData.isLabel = true;
        sp.userData.tex = tex;
        return sp;
    }

    function addEdges(mesh, color, owned) {
        const eg = new THREE.EdgesGeometry(mesh.geometry);
        const em = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.4 });
        const seg = new THREE.LineSegments(eg, em);
        seg.userData.edge = true;
        mesh.add(seg);
        owned.push(eg, em);
    }

    function addHardware(mesh, w, d, h, type, owned) {
        const grooveGeo = new THREE.BoxGeometry(0.12, h * 0.92, 0.25);
        const groove = new THREE.Mesh(grooveGeo, grooveMat);
        groove.position.set(0, 0, d / 2 + 0.05);
        groove.userData.decor = true;
        mesh.add(groove); owned.push(grooveGeo);

        const knobGeo = new THREE.CylinderGeometry(0.35, 0.35, 1.3, 12);
        const yOff = type === "wall" ? -h * 0.32 : h * 0.34;
        [-1, 1].forEach((side) => {
            const knob = new THREE.Mesh(knobGeo, knobMat);
            knob.rotation.x = Math.PI / 2;
            knob.position.set(side * (w * 0.09), yOff, d / 2 + 0.7);
            knob.castShadow = true;
            knob.userData.decor = true;
            mesh.add(knob);
        });
        owned.push(knobGeo);

        if (type === "base") {
            const kickGeo = new THREE.BoxGeometry(w * 0.98, h * 0.08, d * 0.9);
            const kick = new THREE.Mesh(kickGeo, kickMat);
            kick.position.set(0, -h / 2 + h * 0.04, 0);
            kick.userData.decor = true;
            mesh.add(kick); owned.push(kickGeo);

            const counterGeo = new THREE.BoxGeometry(w + 2.5, 1.6, d + 1.5);
            const counter = new THREE.Mesh(counterGeo, counterMat);
            counter.position.set(0, h / 2 + 0.8, 0);
            counter.castShadow = true;
            counter.receiveShadow = true;
            counter.userData.decor = true;
            mesh.add(counter); owned.push(counterGeo);
        } else {
            const crownGeo = new THREE.BoxGeometry(w + 1.4, 1.4, d + 1.4);
            const crown = new THREE.Mesh(crownGeo, crownMat);
            crown.position.set(0, h / 2 + 0.7, 0);
            crown.castShadow = true;
            crown.userData.decor = true;
            mesh.add(crown); owned.push(crownGeo);
        }
    }

    // Apply / remove wireframe + dimension label for one cabinet.
    function styleCabinet(mesh, wf) {
        mesh.material.wireframe = wf;
        mesh.children.forEach((ch) => {
            if (ch.userData.decor) ch.visible = !wf;
        });
        const existing = mesh.children.find((ch) => ch.userData.isLabel);
        if (wf && !existing) {
            const { w, h, d } = mesh.userData;
            const sp = makeLabel(`${fmt(w)}×${fmt(h)}×${fmt(d)}`);
            sp.position.set(0, h / 2 + 8, 0);
            mesh.add(sp);
        } else if (!wf && existing) {
            mesh.remove(existing);
            if (existing.userData.tex) { try { existing.userData.tex.dispose(); } catch (_e) { /* noop */ } }
            if (existing.material) { try { existing.material.dispose(); } catch (_e) { /* noop */ } }
        }
    }

    function createCabinet(type, x, z) {
        let w = 24, d, h, y;
        if (type === "wall") { d = 12; h = 30; y = 54 + h / 2; }
        else { d = 24; h = 34.5; y = h / 2; }

        const owned = [];
        const geo = new THREE.BoxGeometry(w, h, d);
        const mat = cabinetMat();
        owned.push(geo, mat);
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(x, y, z);
        mesh.userData = { type, w, d, h, owned };
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        addEdges(mesh, 0xc9c3b4, owned);
        addHardware(mesh, w, d, h, type, owned);
        scene.add(mesh);
        placed.push(mesh);
        styleCabinet(mesh, wireframe);   // match current mode (e.g. added while in wireframe)
        return mesh;
    }

    function removeCabinet(mesh) {
        scene.remove(mesh);
        mesh.traverse((o) => {
            if (o.isSprite) {
                if (o.userData.tex) { try { o.userData.tex.dispose(); } catch (_e) { /* noop */ } }
                if (o.material) { try { o.material.dispose(); } catch (_e) { /* noop */ } }
            }
        });
        (mesh.userData.owned || []).forEach((o) => {
            try { o.dispose(); } catch (_e) { /* noop */ }
        });
        const i = placed.indexOf(mesh);
        if (i >= 0) placed.splice(i, 1);
    }

    function applyWireframe(on) {
        wireframe = on;
        placed.forEach((m) => styleCabinet(m, on));
        if (wireBtn) {
            wireBtn.textContent = on ? "Solid" : "Wireframe";
            wireBtn.style.background = on ? "#fff" : "transparent";
            wireBtn.style.color = on ? "#6b4a30" : "#fff";
        }
    }

    function createDefaults() {
        [-24, 0, 24].forEach((x) => createCabinet("base", x, -ROOM_D / 2 + 12));
        [-24, 0, 24].forEach((x) => createCabinet("wall", x, -ROOM_D / 2 + 6));
    }

    // ----- Camera view toolbar (1-6 / R / +- — mirrors the real one) -
    const bar = document.createElement("div");
    bar.className = "o_sb_sample3d_viewbar";
    Object.assign(bar.style, {
        position: "absolute", bottom: "10px", left: "50%",
        transform: "translateX(-50%)", display: "flex", alignItems: "center",
        gap: "2px", padding: "3px", background: "rgba(255,255,255,0.94)",
        border: "1px solid #ddd6c9", borderRadius: "8px",
        boxShadow: "0 1px 4px rgba(0,0,0,0.14)", fontFamily: "sans-serif",
    });
    const viewBtnEls = {};
    function makeBarBtn(icon, sub, title) {
        const b = document.createElement("button");
        b.type = "button";
        b.title = title;
        Object.assign(b.style, {
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", width: "30px", height: "30px", padding: "0",
            border: "none", borderRadius: "5px", background: "transparent",
            color: "#2c2620", cursor: "pointer", lineHeight: "1", fontFamily: "inherit",
        });
        b.innerHTML = `<span style="font-size:13px;">${icon}</span>` +
            (sub ? `<span style="font-size:8px;opacity:0.75;">${sub}</span>` : "");
        return b;
    }
    function makeSep() {
        const s = document.createElement("div");
        Object.assign(s.style, {
            width: "1px", alignSelf: "stretch", margin: "3px 2px", background: "#ddd6c9" });
        return s;
    }
    VIEW_BTNS.forEach((v) => {
        const b = makeBarBtn(v.icon, v.n, `${v.label} (${v.n})`);
        b.addEventListener("click", () => { setView(v.key); armReset(); });
        viewBtnEls[v.key] = b;
        bar.appendChild(b);
    });
    bar.appendChild(makeSep());
    const resetBtn = makeBarBtn("⌂", "R", "Reset view (R)");   // ⌂
    resetBtn.addEventListener("click", () => { setView("iso"); armReset(); });
    bar.appendChild(resetBtn);
    bar.appendChild(makeSep());
    const zoomInBtn = makeBarBtn("+", "", "Zoom in");
    zoomInBtn.addEventListener("click", () => { zoomBy(0.85); armReset(); });
    bar.appendChild(zoomInBtn);
    const zoomOutBtn = makeBarBtn("−", "", "Zoom out");        // −
    zoomOutBtn.addEventListener("click", () => { zoomBy(1.18); armReset(); });
    bar.appendChild(zoomOutBtn);
    wrap.appendChild(bar);

    function highlightView() {
        Object.keys(viewBtnEls).forEach((k) => {
            const b = viewBtnEls[k];
            const on = k === currentView;
            b.style.background = on ? "#6b4a30" : "transparent";
            b.style.color = on ? "#fff" : "#2c2620";
        });
    }

    function setView(key) {
        const v = VIEWS[key];
        if (!v) return;
        camera.position.set(v.pos[0], v.pos[1], v.pos[2]);
        controls.target.set(v.target[0], v.target[1], v.target[2]);
        controls.update();
        currentView = key;
        highlightView();
    }

    function zoomBy(factor) {
        const off = camera.position.clone().sub(controls.target);
        let dist = off.length() * factor;
        dist = Math.max(controls.minDistance, Math.min(controls.maxDistance, dist));
        off.setLength(dist);
        camera.position.copy(controls.target).add(off);
        controls.update();
    }

    // ----- Kiosk idle reset -----------------------------------------
    function resetToDefaults() {
        suppressArm = true;
        [...placed].forEach(removeCabinet);
        applyWireframe(false);
        createDefaults();
        setView("persp");   // default framing (#6), also updates highlight
        if (idleTimer) { clearTimeout(idleTimer); idleTimer = null; }
        suppressArm = false;
    }

    function armReset() {
        if (suppressArm) return;
        if (idleTimer) clearTimeout(idleTimer);
        idleTimer = setTimeout(resetToDefaults, IDLE_MS);
    }

    createDefaults();
    highlightView();   // #6 (persp) active initially

    // ----- Interaction: orbit, drag-to-reposition, drag-to-add ------
    const clampX = (x) => Math.max(-ROOM_W / 2 + 12, Math.min(ROOM_W / 2 - 12, x));
    const clampZ = (z) => Math.max(-ROOM_D / 2 + 12, Math.min(ROOM_D / 2 - 12, z));

    const raycaster = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    const dragPlane = new THREE.Plane();
    const dragPoint = new THREE.Vector3();
    const floorMathPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0); // infinite → no dead-zone
    let dragging = null;

    function setNDC(evt) {
        const r = renderer.domElement.getBoundingClientRect();
        ndc.x = ((evt.clientX - r.left) / r.width) * 2 - 1;
        ndc.y = -((evt.clientY - r.top) / r.height) * 2 + 1;
    }

    const onPointerDown = (evt) => {
        setNDC(evt);
        raycaster.setFromCamera(ndc, camera);
        const hits = raycaster.intersectObjects(placed);
        if (hits.length) {
            dragging = hits[0].object;
            controls.enabled = false;
            dragPlane.setFromNormalAndCoplanarPoint(
                new THREE.Vector3(0, 1, 0),
                new THREE.Vector3(0, dragging.position.y, 0));
            renderer.domElement.style.cursor = "grabbing";
        }
    };
    const onPointerMove = (evt) => {
        if (!dragging) return;
        setNDC(evt);
        raycaster.setFromCamera(ndc, camera);
        if (raycaster.ray.intersectPlane(dragPlane, dragPoint)) {
            if (dragging.userData.type === "wall") {
                dragging.position.x = clampX(dragPoint.x); // wall cabs slide along X only
            } else {
                dragging.position.x = clampX(dragPoint.x);
                dragging.position.z = clampZ(dragPoint.z);
            }
        }
    };
    const onPointerUp = () => {
        if (dragging) {
            dragging = null;
            controls.enabled = true;
            renderer.domElement.style.cursor = "";
            armReset();
        }
    };

    const itemEls = Array.from(host.querySelectorAll(".o_sb_sample3d_item"));
    const itemHandlers = itemEls.map((item) => {
        const h = (evt) => evt.dataTransfer.setData("text/plain", item.dataset.type);
        item.addEventListener("dragstart", h);
        return [item, h];
    });

    const onDragOver = (evt) => evt.preventDefault();
    const onDrop = (evt) => {
        evt.preventDefault();
        const type = evt.dataTransfer.getData("text/plain");
        if (!type) return;
        setNDC(evt);
        raycaster.setFromCamera(ndc, camera);
        const p = new THREE.Vector3();
        if (raycaster.ray.intersectPlane(floorMathPlane, p)) {
            createCabinet(
                type, clampX(p.x),
                type === "wall" ? -ROOM_D / 2 + 6 : clampZ(p.z));
            armReset();
        }
    };

    // controls "end" fires once per user orbit/zoom gesture (not per frame,
    // and NOT on programmatic controls.update()), so arming the idle reset
    // here can never create a reset loop.
    const onControlsEnd = () => armReset();
    const onWireClick = () => { applyWireframe(!wireframe); armReset(); };

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    renderer.domElement.addEventListener("dragover", onDragOver);
    renderer.domElement.addEventListener("drop", onDrop);
    controls.addEventListener("end", onControlsEnd);
    if (wireBtn) wireBtn.addEventListener("click", onWireClick);

    // ----- Resize + render loop (pausable while offscreen) ----------
    function onResize() {
        if (!wrap.clientWidth || !wrap.clientHeight) return;
        camera.aspect = wrap.clientWidth / wrap.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(wrap.clientWidth, wrap.clientHeight);
    }
    window.addEventListener("resize", onResize);

    let rafId = null;
    function animate() {
        rafId = requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    function play() { if (rafId === null) animate(); }
    function pause() {
        if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null; }
    }

    // ----- Teardown (complete: timers + listeners + GPU + GL context) -
    function destroy() {
        pause();
        if (idleTimer) { clearTimeout(idleTimer); idleTimer = null; }
        window.removeEventListener("resize", onResize);
        window.removeEventListener("pointermove", onPointerMove);
        window.removeEventListener("pointerup", onPointerUp);
        renderer.domElement.removeEventListener("pointerdown", onPointerDown);
        renderer.domElement.removeEventListener("dragover", onDragOver);
        renderer.domElement.removeEventListener("drop", onDrop);
        controls.removeEventListener("end", onControlsEnd);
        if (wireBtn) wireBtn.removeEventListener("click", onWireClick);
        itemHandlers.forEach(([el, h]) => el.removeEventListener("dragstart", h));
        [...placed].forEach(removeCabinet);    // frees per-cabinet geo/mat + labels
        controls.dispose();
        disposables.forEach((o) => { try { o.dispose(); } catch (_e) { /* noop */ } });
        renderer.dispose();
        if (renderer.forceContextLoss) {
            try { renderer.forceContextLoss(); } catch (_e) { /* noop */ }
        }
        if (renderer.domElement && renderer.domElement.parentNode) {
            renderer.domElement.parentNode.removeChild(renderer.domElement);
        }
    }

    return { play, pause, destroy };
}

// ---------------------------------------------------------------------
// Host lifecycle — lazy-init on visibility, pause offscreen, tear down
// on pagehide. If WebGL/THREE unavailable, render the static fallback.
// ---------------------------------------------------------------------
function mount(host) {
    if (host.dataset.sbSample3dBooted === "1") return;
    host.dataset.sbSample3dBooted = "1";

    if (!window.THREE || !window.THREE.OrbitControls || !webglSupported()) {
        renderFallback(host);
        return;
    }

    let handle = null;
    const init = () => {
        if (handle) return;
        try {
            handle = buildScene(host);
            handle.play();
        } catch (_e) {
            renderFallback(host);
        }
    };

    const onPageHide = () => { if (handle) { handle.destroy(); handle = null; } };
    window.addEventListener("pagehide", onPageHide, { once: true });

    if ("IntersectionObserver" in window) {
        const io = new IntersectionObserver((entries) => {
            for (const entry of entries) {
                if (entry.isIntersecting) {
                    init();
                    if (handle) handle.play();
                } else if (handle) {
                    handle.pause();   // stop GPU work while scrolled away
                }
            }
        }, { threshold: 0.05 });
        io.observe(host);
    } else {
        init();
    }
}

function boot() {
    document.querySelectorAll(HOST_SELECTOR).forEach(mount);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
} else {
    boot();
}
