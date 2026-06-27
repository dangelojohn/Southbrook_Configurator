/** @odoo-module **/
// W036 — Audio confirmation on scan success/fail.
//
// R8.7 — in a noisy kitchen shop the operator can't tell from a
// silent JSON response whether the scan landed. This module hooks
// into the global fetch + XHR layers and plays a short Web Audio
// tone whenever a response from one of the Southbrook scan endpoints
// comes back.
//
//   success ->  80ms @ 800Hz  (sine, low gain)
//   failure -> 200ms @ 200Hz  (sine, low gain)
//
// Default = unmuted. The operator can mute by setting
// `localStorage["southbrook.qr_kit.audio_muted"] = "1"` in the
// browser console; the Settings → System Parameters key
// `southbrook.qr_kit.audio_muted` (boolean) is also respected at
// load time so an ops admin can disable site-wide.
//
// Why localStorage + ir.config_parameter (not user prefs):
//   * Tablet kiosks are shared accounts.
//   * The mute decision belongs to the device, not the user.
//   * Site-wide override stays in Odoo for governance.
//
// Why fetch + XHR both:
//   Odoo's jsonrpc helper uses XHR; the fresh OWL controllers and
//   handheld PWAs use fetch. Hooking both keeps cues consistent
//   across all callers without depending on a specific transport.

const STORAGE_KEY = "southbrook.qr_kit.audio_muted";
const SCAN_URL_FRAGMENTS = [
    "/sb/qr/scan",
    "/sb/qr/shipping/load-unit",
    "/sb/qr/inventory/bin-scan",
    "/sb/qr/pod/submit",
    "/southbrook/api/floor-traveler/scan",
];

let audioCtx = null;
let siteMuted = false;

function ensureCtx() {
    if (audioCtx) {
        return audioCtx;
    }
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) {
        return null;
    }
    try {
        audioCtx = new Ctor();
    } catch (e) {
        audioCtx = null;
    }
    return audioCtx;
}

function isMuted() {
    if (siteMuted) {
        return true;
    }
    try {
        return window.localStorage.getItem(STORAGE_KEY) === "1";
    } catch (e) {
        return false;
    }
}

function playTone(freq, durationMs) {
    if (isMuted()) {
        return;
    }
    const ctx = ensureCtx();
    if (!ctx) {
        return;
    }
    // Tablets often suspend the audio context until a user gesture.
    // A scan-event resume() is best-effort; modern Chromium/WebKit
    // allow it after the first user interaction with the page.
    if (ctx.state === "suspended") {
        ctx.resume().catch(() => {});
    }
    try {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = freq;
        // Soft envelope so the tone doesn't click — 5ms attack/release.
        const now = ctx.currentTime;
        const attack = 0.005;
        const release = 0.01;
        gain.gain.setValueAtTime(0.0, now);
        gain.gain.linearRampToValueAtTime(0.18, now + attack);
        gain.gain.setValueAtTime(0.18, now + durationMs / 1000 - release);
        gain.gain.linearRampToValueAtTime(0.0, now + durationMs / 1000);
        osc.connect(gain).connect(ctx.destination);
        osc.start(now);
        osc.stop(now + durationMs / 1000 + 0.02);
    } catch (e) {
        // Audio is decoration, never block scan workflow.
    }
}

function playSuccess() {
    playTone(800, 80);
}

function playFailure() {
    playTone(200, 200);
}

function isScanUrl(url) {
    if (!url) {
        return false;
    }
    const u = typeof url === "string" ? url : url.url || "";
    return SCAN_URL_FRAGMENTS.some((frag) => u.indexOf(frag) !== -1);
}

function evaluateBody(text) {
    // The JSON-RPC envelope wraps controller results in {result: {...}}.
    // Plain JSON controllers return the dict at top level. Cover both
    // shapes; default to "success" if the body parses cleanly and lacks
    // an explicit failure signal (some endpoints return {} on success).
    if (!text) {
        return true;
    }
    try {
        const parsed = JSON.parse(text);
        const r = (parsed && parsed.result) || parsed;
        if (!r || typeof r !== "object") {
            return true;
        }
        if (r.ok === false) {
            return false;
        }
        if (r.error) {
            return false;
        }
        if (typeof r.result === "string" && r.result !== "ok") {
            return false;
        }
        return true;
    } catch (e) {
        return false;
    }
}

function patchFetch() {
    const orig = window.fetch;
    if (!orig || orig.__sbk_qr_audio_patched) {
        return;
    }
    const wrapped = function (...args) {
        const url = args[0];
        const p = orig.apply(this, args);
        if (!isScanUrl(url)) {
            return p;
        }
        return p.then((response) => {
            // Clone so the caller can still .json() / .text() it.
            if (!response.ok) {
                playFailure();
                return response;
            }
            response.clone().text().then((text) => {
                if (evaluateBody(text)) {
                    playSuccess();
                } else {
                    playFailure();
                }
            }).catch(() => playFailure());
            return response;
        }, (err) => {
            playFailure();
            throw err;
        });
    };
    wrapped.__sbk_qr_audio_patched = true;
    window.fetch = wrapped;
}

function patchXHR() {
    const X = window.XMLHttpRequest;
    if (!X || X.prototype.__sbk_qr_audio_patched) {
        return;
    }
    const origOpen = X.prototype.open;
    const origSend = X.prototype.send;
    X.prototype.open = function (method, url, ...rest) {
        this.__sbk_qr_audio_url = url;
        return origOpen.apply(this, [method, url, ...rest]);
    };
    X.prototype.send = function (...args) {
        const xhr = this;
        if (isScanUrl(xhr.__sbk_qr_audio_url)) {
            xhr.addEventListener("loadend", () => {
                if (xhr.status >= 200 && xhr.status < 400) {
                    if (evaluateBody(xhr.responseText)) {
                        playSuccess();
                    } else {
                        playFailure();
                    }
                } else {
                    playFailure();
                }
            });
        }
        return origSend.apply(this, args);
    };
    X.prototype.__sbk_qr_audio_patched = true;
}

function readSiteMuteFromDOM() {
    // Optional: a meta tag the backend can render to disable cues
    // site-wide without each tablet flipping its own localStorage.
    // <meta name="southbrook.qr_kit.audio_muted" content="1">
    const meta = document.querySelector(
        'meta[name="southbrook.qr_kit.audio_muted"]');
    if (meta && meta.getAttribute("content") === "1") {
        siteMuted = true;
    }
}

// Small public helpers so an in-Odoo settings toggle or a console
// session can flip the device mute without spelunking storage.
window.sbkScanAudio = {
    mute() {
        try {
            window.localStorage.setItem(STORAGE_KEY, "1");
        } catch (e) {}
    },
    unmute() {
        try {
            window.localStorage.removeItem(STORAGE_KEY);
        } catch (e) {}
    },
    isMuted,
    testSuccess: playSuccess,
    testFailure: playFailure,
};

readSiteMuteFromDOM();
patchFetch();
patchXHR();
