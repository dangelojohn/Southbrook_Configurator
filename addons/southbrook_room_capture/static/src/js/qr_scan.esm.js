/** @odoo-module **/
// SPDX-License-Identifier: LGPL-3.0-only
/*
 * southbrook_room_capture — "scan a Southbrook cabinet QR" frontend.
 *
 * A customer/estimator scans the QR printed on a physical cabinet's
 * Floor-Traveler label from the Order Lines estimate. This file owns
 * the ENTIRE client-side surface for that feature:
 *   * the camera (getUserMedia, rear camera preferred),
 *   * the QR decode loop (jsQR primary/fallback path; BarcodeDetector
 *     as an optional faster path on browsers that support it),
 *   * a still-photo fallback (file input, capture="environment") for
 *     browsers/situations where getUserMedia is unavailable or denied,
 *   * the POST to this addon's own
 *     /southbrook/api/order/<id>/scan-part endpoint, and
 *   * the result / error card shown to the user.
 *
 * CROSS-ADDON MECHANISM (read before touching the opener below):
 *
 * The "Scan part QR" button lives on the customer Order Builder's
 * Order Lines tab, which is `class OrderBuilder extends Component` in
 * southbrook_estimating_website/static/src/js/portal_boot.esm.js. That
 * class is declared with `static template = TEMPLATE` where TEMPLATE
 * is an inline owl `xml\`...\`` tagged-template literal — Odoo's
 * `xml()` helper auto-generates an unstable per-page-load template
 * name for such literals, so there is no stable qweb template name for
 * a cross-addon t-inherit to extend, and OrderBuilder is not exported,
 * so there is no class reference for patch() either. This is the
 * SAME constraint the "AI ROOM CAPTURE" photo-upload hook (also in
 * this addon, room_capture.esm.js) hit first — see that file's
 * top-of-file comment for the full write-up.
 *
 * Rather than fork OrderBuilder's template into this addon (fragile —
 * any future edit there would silently desync), this addon instead
 * REGISTERS an opener function that portal_boot.esm.js can look up at
 * click time WITHOUT importing anything from this addon:
 *
 *   import { registry } from "@web/core/registry";
 *   registry.category("sb_qr_scanner").add("open", openScanner);
 *
 * portal_boot.esm.js's button handler does:
 *
 *   const opener = registry.category("sb_qr_scanner").get("open", null);
 *   if (opener) { const res = await opener({ orderId, env: this.env }); }
 *
 * No JS import exists in either direction — southbrook_estimating_website
 * keeps installing/working standalone whether or not this addon is
 * installed (the button just no-ops with a "scanner unavailable"
 * toast if this addon isn't there); all of the QR/camera/API logic
 * stays owned here.
 *
 * WHY env.services.dialog.add(...) AND NOT A FRESH mount()/mountComponent():
 * this codebase hit `DuplicatedKeyError: NotificationContainer` twice
 * mounting a second OWL root with its own startServices() on this same
 * public/portal page (see room_capture.esm.js's sibling commit history
 * and the project's odoo19_mountcomponent_startservices_trap note).
 * OrderBuilder is ALREADY mounted on the frontend's public-root env
 * (services + template registry started exactly once, for the whole
 * page, via the `public_components` registry). Because portal_boot's
 * click handler passes us THAT SAME `env` (as `this.env`, since the
 * handler is itself a method the click fires on the live OrderBuilder
 * instance), `env.services.dialog.add(QrScanDialog, ...)` mounts our
 * dialog as an ordinary descendant of the SAME already-started env via
 * the sanctioned `dialog`/`overlay` services (`OverlayContainer` is
 * registered into `main_components` exactly once, at the one real
 * startServices() call for the page) — no second env, no double
 * service-start, no collision.
 *
 * PRIVACY: the camera image never leaves this browser tab. Only the
 * decoded QR STRING is POSTed to scan-part. Frames are drawn to a
 * throwaway, in-memory <canvas> created here (never inserted in the
 * template, never persisted); nothing image-related is ever assigned
 * to `state`, localStorage, or a console.log. Every path that ends
 * the scan (a successful decode, Cancel/×, or the component simply
 * unmounting) stops every MediaStreamTrack on the active getUserMedia
 * stream — see `_stopCamera()`, called from onWillUnmount as the
 * final safety net.
 */
import { Component, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import jsQR from "@southbrook_room_capture/lib/jsqr";

// ----------------------------------------------------------------------
// Payload recognition — client-side gate so the camera loop only ever
// POSTs a value that at least LOOKS like a Southbrook cabinet-label QR.
// Anything else (a random QR the camera happens to see) is silently
// ignored and scanning continues; the server independently re-validates
// the format regardless (never trust the client), this is purely to
// avoid spamming the endpoint with obviously-unrelated QR content and
// to give the user better in-camera feedback ("that's not one of ours").
// ----------------------------------------------------------------------
const SB_PACKAGE_PREFIX = "sb-package:";
const SB_SIGNED_PREFIX = "sb://pkg/";

function _isSouthbrookPayload(value) {
    return (
        typeof value === "string"
        && (value.startsWith(SB_PACKAGE_PREFIX) || value.startsWith(SB_SIGNED_PREFIX))
    );
}

// Distinct from portal_boot.esm.js's fmtUsd (which rounds to whole
// dollars for order/zone totals) — a single scanned part's unit price
// reads better with cents, so this is a deliberately separate,
// deliberately-not-shared helper rather than a cross-addon import for
// a five-line formatter.
function _fmtUsd(value) {
    if (typeof value !== "number") return "—";
    return "$" + value.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function _fmtMm(value) {
    if (typeof value !== "number") return "—";
    return value.toLocaleString() + " mm";
}

// Maps the controller's flat {"error": "<code>", "detail": "..."} shape
// to a plain-language message. Any code/shape not covered here (including
// no `error` key at all on a thrown network exception) falls back to a
// generic "couldn't read that part" message per the brief.
function _lookupErrorMessage(res, networkFallback) {
    if (!res) {
        return networkFallback || "Couldn't reach the server. Check your connection and try again.";
    }
    const messages = {
        invalid: "That QR isn't a Southbrook cabinet label.",
        not_found: "Couldn't find that part on your account.",
        forbidden: "That part isn't on an order you have access to.",
        rate_limited: "Too many scans — please wait a moment and try again.",
    };
    if (res.error && messages[res.error]) {
        return messages[res.error];
    }
    if (res.detail) {
        return String(res.detail);
    }
    return "Couldn't read that part. Please try again.";
}

// ----------------------------------------------------------------------
// QrScanDialog — the whole scanner UI (camera / fallback / busy /
// result / error), mounted via the `dialog` service (see the top-of-
// file comment for why). `props.close` is injected automatically by
// the dialog service; calling it with a value settles the opener's
// Promise with that value (see `openScanner` below) — calling it with
// no argument (Cancel / ×) settles with null.
// ----------------------------------------------------------------------
export class QrScanDialog extends Component {
    static template = "southbrook_room_capture.QrScanDialog";
    static props = {
        orderId: { type: [String, Number] },
        close: Function,
    };
    _fmtUsd = _fmtUsd;
    _fmtMm = _fmtMm;

    setup() {
        this.state = useState({
            // "starting" | "scanning" | "fallback" | "fallback_busy"
            // | "looking_up" | "result" | "error"
            phase: "starting",
            hint: "Point your camera at a Southbrook cabinet label",
            flashMessage: null,
            lookupError: null,
            result: null,
        });
        this.videoRef = useRef("sb_qr_video");
        this._stream = null;
        this._rafId = null;
        this._stopped = true;
        this._barcodeDetector = null;
        this._flashTimer = null;
        this._destroyed = false;

        onMounted(() => this._startCamera());
        onWillUnmount(() => {
            this._destroyed = true;
            this._stopCamera();
            if (this._flashTimer) {
                clearTimeout(this._flashTimer);
                this._flashTimer = null;
            }
        });
    }

    // ------------------------------------------------------------------
    // Camera lifecycle
    // ------------------------------------------------------------------

    async _startCamera() {
        this.state.phase = "starting";
        this.state.lookupError = null;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this._enableFallback(
                "Camera isn't available on this device or browser — "
                + "take or choose a photo of the label instead.",
            );
            return;
        }
        let stream;
        try {
            // iOS Safari rear-camera priority per the brief: `ideal`
            // (not `exact`) so devices with only a front camera still
            // get SOME stream rather than a hard failure.
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: "environment" } },
                audio: false,
            });
        } catch (err) {
            this._enableFallback(
                "Camera access was denied or unavailable — take or "
                + "choose a photo of the label instead.",
            );
            return;
        }
        if (this._destroyed) {
            // Dialog was closed while getUserMedia was pending — don't
            // leak the stream we just opened.
            for (const track of stream.getTracks()) track.stop();
            return;
        }
        this._stream = stream;
        const video = this.videoRef.el;
        if (!video) {
            this._stopCamera();
            return;
        }
        video.srcObject = stream;
        try {
            // Playing may reject if the click-to-open gesture chain was
            // broken by an intervening await; scanning still starts —
            // most browsers begin delivering frames on autoplay anyway,
            // and a failed play() here is not fatal.
            await video.play();
        } catch (err) {
            // no-op — see comment above.
        }
        if (this._destroyed) return;

        if (typeof window.BarcodeDetector === "function") {
            try {
                this._barcodeDetector = new window.BarcodeDetector({ formats: ["qr_code"] });
            } catch (err) {
                this._barcodeDetector = null;
            }
        }

        this.state.phase = "scanning";
        this.state.hint = "Point your camera at a Southbrook cabinet label";
        this._stopped = false;
        this._rafId = requestAnimationFrame(() => this._scanLoop());
    }

    _stopCamera() {
        this._stopped = true;
        if (this._rafId) {
            cancelAnimationFrame(this._rafId);
            this._rafId = null;
        }
        if (this._stream) {
            for (const track of this._stream.getTracks()) {
                track.stop();
            }
            this._stream = null;
        }
        const video = this.videoRef.el;
        if (video) {
            video.srcObject = null;
        }
        this._barcodeDetector = null;
    }

    // Fallback UI (no camera / permission denied). `capture="environment"`
    // on the file input still opens the rear camera on mobile even
    // without getUserMedia — see the <input> in qr_scan.xml.
    _enableFallback(hint) {
        this._stopCamera();
        if (this._destroyed) return;
        this.state.phase = "fallback";
        this.state.hint = hint;
    }

    // ------------------------------------------------------------------
    // Live-camera decode loop. Runs at most once per animation frame —
    // the next frame is only scheduled after this one's (possibly
    // async, if BarcodeDetector is in play) work finishes, so there is
    // never more than one decode in flight.
    // ------------------------------------------------------------------

    async _scanLoop() {
        if (this._stopped) return;
        const video = this.videoRef.el;
        if (video && video.videoWidth && video.readyState >= video.HAVE_CURRENT_DATA) {
            try {
                let decoded = null;
                if (this._barcodeDetector) {
                    try {
                        const barcodes = await this._barcodeDetector.detect(video);
                        if (barcodes && barcodes.length && barcodes[0].rawValue) {
                            decoded = barcodes[0].rawValue;
                        }
                    } catch (err) {
                        // BarcodeDetector hiccup on this frame — fall
                        // through to the jsQR path below, same frame.
                    }
                }
                if (!decoded) {
                    decoded = this._decodeVideoFrameWithJsQr(video);
                }
                if (decoded) {
                    if (_isSouthbrookPayload(decoded)) {
                        await this._handleDecoded(decoded);
                        if (this._stopped || this._destroyed) return;
                    } else {
                        this._flashInvalid();
                    }
                }
            } catch (err) {
                // Never let a per-frame decode error kill the loop —
                // just keep scanning.
            }
        }
        if (!this._stopped) {
            this._rafId = requestAnimationFrame(() => this._scanLoop());
        }
    }

    // Draws the current video frame to a throwaway in-memory canvas
    // (never attached to the DOM, never stored on `state`) and runs
    // jsQR against it. Returns the decoded string or null.
    _decodeVideoFrameWithJsQr(video) {
        if (!this._canvas) {
            this._canvas = document.createElement("canvas");
        }
        const canvas = this._canvas;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const code = jsQR(imageData.data, imageData.width, imageData.height, {
            inversionAttempts: "dontInvert",
        });
        return (code && code.data) ? code.data : null;
    }

    _flashInvalid() {
        this.state.flashMessage = "That's not a Southbrook cabinet label — keep scanning.";
        if (this._flashTimer) clearTimeout(this._flashTimer);
        this._flashTimer = setTimeout(() => {
            this.state.flashMessage = null;
        }, 1600);
    }

    // ------------------------------------------------------------------
    // Still-photo fallback path
    // ------------------------------------------------------------------

    // Arrow-function class field (not a prototype method) — this
    // project has hit real `this`-binding failures passing plain
    // methods to `t-on-*` in this Odoo version (see portal_boot.esm.js
    // 2026-06-01 note); every handler bound directly from this
    // component's own template below follows the same established,
    // verified-safe pattern.
    _onFallbackFileChange = async (ev) => {
        const input = ev.target;
        const file = input.files && input.files[0];
        input.value = ""; // allow re-picking the same file later
        if (!file) return;

        this.state.phase = "fallback_busy";
        this.state.lookupError = null;
        try {
            const image = await this._loadImageFile(file);
            const canvas = document.createElement("canvas");
            canvas.width = image.width;
            canvas.height = image.height;
            const ctx = canvas.getContext("2d", { willReadFrequently: true });
            ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            const code = jsQR(imageData.data, imageData.width, imageData.height, {
                inversionAttempts: "dontInvert",
            });
            const decoded = (code && code.data) ? code.data : null;
            if (decoded && _isSouthbrookPayload(decoded)) {
                await this._handleDecoded(decoded);
            } else {
                this.state.phase = "fallback";
                this.state.lookupError = decoded
                    ? "That QR isn't a Southbrook cabinet label — try again."
                    : "No QR detected — try again with the label centered and in focus.";
            }
        } catch (err) {
            this.state.phase = "fallback";
            this.state.lookupError = "Couldn't read that photo — try again.";
        }
    };

    // ImageBitmap when available (fast, no extra DOM node); a plain
    // <img> decode otherwise. Both expose .width/.height and work with
    // ctx.drawImage, so the caller doesn't need to care which path ran.
    async _loadImageFile(file) {
        if (typeof window.createImageBitmap === "function") {
            try {
                return await window.createImageBitmap(file);
            } catch (err) {
                // fall through to the <img> path below
            }
        }
        return new Promise((resolve, reject) => {
            const img = new Image();
            const url = URL.createObjectURL(file);
            img.onload = () => {
                URL.revokeObjectURL(url);
                resolve(img);
            };
            img.onerror = (err) => {
                URL.revokeObjectURL(url);
                reject(err);
            };
            img.src = url;
        });
    }

    // ------------------------------------------------------------------
    // Server round-trip
    // ------------------------------------------------------------------

    async _handleDecoded(payload) {
        // Stop the camera the moment we have a Southbrook-shaped decode
        // — no need to keep the stream open during the lookup, and it
        // avoids a second decode of the same label firing mid-request.
        this._stopCamera();
        if (this._destroyed) return;
        this.state.phase = "looking_up";
        this.state.flashMessage = null;
        try {
            const res = await rpc(
                "/southbrook/api/order/" + encodeURIComponent(this.props.orderId) + "/scan-part",
                { payload },
            );
            if (this._destroyed) return;
            if (res && res.ok) {
                this.state.result = res;
                this.state.phase = "result";
            } else {
                this.state.lookupError = _lookupErrorMessage(res);
                this.state.phase = "error";
            }
        } catch (err) {
            if (this._destroyed) return;
            this.state.lookupError = _lookupErrorMessage(null);
            this.state.phase = "error";
        }
    }

    // ------------------------------------------------------------------
    // Footer / header actions
    // ------------------------------------------------------------------

    _onCancelClick = () => {
        this.props.close();
    };

    _onDoneClick = () => {
        this.props.close(this.state.result);
    };

    _onScanAnotherClick = () => {
        this.state.result = null;
        this.state.lookupError = null;
        this._startCamera();
    };

    _onRetryCameraClick = () => {
        this._startCamera();
    };
}

// ----------------------------------------------------------------------
// Opener — the entire public surface portal_boot.esm.js touches.
// Resolves with the scan-part response (`{ok, part, in_current_order,
// line_id, quote_number}`) on Done, or null on Cancel/×/no successful
// scan. `options.onClose` is the dialog service's own removal hook —
// it fires for EVERY removal path (not just the ones this file wrote),
// so the returned Promise is guaranteed to settle even if some future
// change adds another way to close the dialog.
// ----------------------------------------------------------------------
function openScanner({ orderId, env }) {
    return new Promise((resolve) => {
        let settled = false;
        const settle = (value) => {
            if (settled) return;
            settled = true;
            resolve(value || null);
        };
        if (!env || !env.services || !env.services.dialog) {
            // No dialog service on this env for some reason (e.g. this
            // addon's assets loaded on a page with no started public
            // root) — resolve null so the caller can show its own
            // "scanner unavailable" message instead of hanging.
            settle(null);
            return;
        }
        env.services.dialog.add(
            QrScanDialog,
            { orderId },
            { onClose: (result) => settle(result) },
        );
    });
}

registry.category("sb_qr_scanner").add("open", openScanner);
