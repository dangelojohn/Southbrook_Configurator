/** @odoo-module **/
// SPDX-License-Identifier: LGPL-3.0-only
/*
 * southbrook_room_capture — STAFF QR scanner (installers / shipping /
 * factory). A full-screen, mobile-first page at /southbrook/scan.
 *
 * JTBD: "I'm holding a physical cabinet with a Southbrook QR label —
 * scan it with my phone and show me EVERYTHING about this package
 * (customer/order, manufacturing, shipping, placement, scan history) so
 * I can verify/route/install the right item without opening the
 * backend."
 *
 * Distinct from the customer QrScanDialog (qr_scan.esm.js): this is a
 * standalone page (mounted via web's public_components registry, the
 * sanctioned no-double-startServices path), it hits the INTERNAL
 * /southbrook/api/scan/lookup endpoint (staff-gated server-side), and it
 * renders FULL internal detail instead of customer-safe fields. The
 * camera + jsQR decode machinery mirrors the proven customer dialog but
 * is kept self-contained so the two trust levels never share code paths.
 *
 * PRIVACY/HYGIENE: the camera frame never leaves the browser — only the
 * decoded QR STRING is POSTed. Frames are drawn to a throwaway in-memory
 * canvas; every teardown path stops all MediaStream tracks.
 */
import { Component, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import jsQR from "@southbrook_room_capture/lib/jsqr";

const SB_PACKAGE_PREFIX = "sb-package:";
const SB_SIGNED_PREFIX = "sb://pkg/";

function _isSouthbrookPayload(value) {
    return (
        typeof value === "string"
        && (value.startsWith(SB_PACKAGE_PREFIX) || value.startsWith(SB_SIGNED_PREFIX))
    );
}

function _errorMessage(res) {
    const messages = {
        invalid: "That QR isn't a Southbrook cabinet label.",
        not_found: "No package found for that label.",
        forbidden: "This scanner is for Southbrook staff only.",
        rate_limited: "Too many scans — wait a moment and try again.",
        lookup_failed: "Couldn't read that package. Try again.",
    };
    if (res && res.error && messages[res.error]) return messages[res.error];
    if (res && res.detail) return String(res.detail);
    return "Couldn't read that label. Please try again.";
}

export class StaffQrScanner extends Component {
    static template = "southbrook_room_capture.StaffQrScanner";
    static props = {};

    setup() {
        this.state = useState({
            // starting | scanning | fallback | fallback_busy | looking_up
            // | result | error
            phase: "starting",
            hint: "Point your camera at a Southbrook cabinet label",
            flashMessage: null,
            error: null,
            info: null,
        });
        this.videoRef = useRef("sb_staff_video");
        this._stream = null;
        this._rafId = null;
        this._stopped = true;
        this._barcodeDetector = null;
        this._flashTimer = null;
        this._destroyed = false;
        this._canvas = null;

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
        this.state.error = null;
        this.state.info = null;
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this._enableFallback(
                "Camera unavailable on this device — take or choose a "
                + "photo of the label instead.");
            return;
        }
        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: "environment" } },
                audio: false,
            });
        } catch (err) {
            this._enableFallback(
                "Camera access denied — take or choose a photo of the "
                + "label instead.");
            return;
        }
        if (this._destroyed) {
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
            await video.play();
        } catch (err) {
            // autoplay usually delivers frames anyway — non-fatal
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
            for (const track of this._stream.getTracks()) track.stop();
            this._stream = null;
        }
        const video = this.videoRef.el;
        if (video) video.srcObject = null;
        this._barcodeDetector = null;
        this._canvas = null;
    }

    _enableFallback(hint) {
        this._stopCamera();
        if (this._destroyed) return;
        this.state.phase = "fallback";
        this.state.hint = hint;
    }

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
                        // fall through to jsQR
                    }
                }
                if (!decoded) decoded = this._decodeFrame(video);
                if (decoded) {
                    if (_isSouthbrookPayload(decoded)) {
                        await this._handleDecoded(decoded);
                        if (this._stopped || this._destroyed) return;
                    } else {
                        this._flashInvalid();
                    }
                }
            } catch (err) {
                // never let a per-frame error kill the loop
            }
        }
        if (!this._stopped) {
            this._rafId = requestAnimationFrame(() => this._scanLoop());
        }
    }

    _decodeFrame(video) {
        if (!this._canvas) this._canvas = document.createElement("canvas");
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
        this.state.flashMessage = "Not a Southbrook label — keep scanning.";
        if (this._flashTimer) clearTimeout(this._flashTimer);
        this._flashTimer = setTimeout(() => {
            this.state.flashMessage = null;
        }, 1600);
    }

    // ------------------------------------------------------------------
    // Still-photo fallback
    // ------------------------------------------------------------------
    _onFallbackFileChange = async (ev) => {
        const input = ev.target;
        const file = input.files && input.files[0];
        input.value = "";
        if (!file) return;
        this.state.phase = "fallback_busy";
        this.state.error = null;
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
                this.state.error = decoded
                    ? "That QR isn't a Southbrook label — try again."
                    : "No QR detected — center the label and try again.";
            }
        } catch (err) {
            this.state.phase = "fallback";
            this.state.error = "Couldn't read that photo — try again.";
        }
    };

    async _loadImageFile(file) {
        if (typeof window.createImageBitmap === "function") {
            try {
                return await window.createImageBitmap(file);
            } catch (err) {
                // fall through
            }
        }
        return new Promise((resolve, reject) => {
            const img = new Image();
            const url = URL.createObjectURL(file);
            img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
            img.onerror = (err) => { URL.revokeObjectURL(url); reject(err); };
            img.src = url;
        });
    }

    // ------------------------------------------------------------------
    // Server round-trip
    // ------------------------------------------------------------------
    async _handleDecoded(payload) {
        this._stopCamera();
        if (this._destroyed) return;
        this.state.phase = "looking_up";
        this.state.flashMessage = null;
        try {
            const res = await rpc("/southbrook/api/scan/lookup", { payload });
            if (this._destroyed) return;
            if (res && res.ok) {
                this.state.info = res.info;
                this.state.phase = "result";
            } else {
                this.state.error = _errorMessage(res);
                this.state.phase = "error";
            }
        } catch (err) {
            if (this._destroyed) return;
            this.state.error = _errorMessage(null);
            this.state.phase = "error";
        }
    }

    // ------------------------------------------------------------------
    // Actions
    // ------------------------------------------------------------------
    _onScanAnother = () => {
        this.state.info = null;
        this.state.error = null;
        this._startCamera();
    };

    _onRetryCamera = () => {
        this._startCamera();
    };

    // Small display helpers used by the template.
    _mm(value) {
        return (typeof value === "number") ? value.toLocaleString() + " mm" : "—";
    }
    _or(value) {
        return (value === null || value === undefined || value === "") ? "—" : value;
    }
    _hasShipping() {
        const s = this.state.info && this.state.info.shipping;
        return !!(s && s.pickings && s.pickings.length);
    }
    _hasScans() {
        const h = this.state.info && this.state.info.scan_history;
        return !!(h && h.length);
    }
    _workorders() {
        const m = this.state.info && this.state.info.manufacturing;
        return (m && m.workorders) || [];
    }
}

registry
    .category("public_components")
    .add("southbrook_room_capture.StaffQrScanner", StaffQrScanner);
