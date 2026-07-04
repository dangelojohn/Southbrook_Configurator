/** @odoo-module **/
// SPDX-License-Identifier: LGPL-3.0-only
/**
 * RoomChatWidget — conversational AI room-builder panel for the Order
 * Builder portal page.
 *
 * Mounts on the first <div data-room-chat-mount> it finds (mirrors
 * southbrook_hermes's HermesChat auto-mount convention). Each turn POSTs
 * {message, order_id} to /southbrook/api/order/<id>/room/chat, which runs
 * a Claude tool-calling loop server-side and returns {reply, room} — where
 * `room` is a DRAFT in the same shape southbrook_room_capture's
 * `existing_room` payload already uses (no `id` fields; nothing has been
 * persisted). This widget renders that draft live via the reused
 * RoomOutlinePreview component so the shape visibly fills in as the
 * conversation progresses.
 *
 * This widget does NOT reach into OrderBuilder's state directly — that
 * component has an inline (non-exported) template and can't be imported,
 * the same constraint southbrook_room_capture already documented and
 * worked around. Instead, "Looks good — finish in Room Setup" dispatches
 * a bubbling CustomEvent("sb:room-chat-review", {detail: draft}); a small
 * additive listener in portal_boot.esm.js (search for "AI ROOM CHAT")
 * picks it up and opens the existing wizard pre-filled, reusing the
 * idless-draft detection southbrook_room_capture's RoomSetupWizard patch
 * already established.
 */
import { Component, mount, useRef, useState, whenReady } from "@odoo/owl";
import { getTemplate } from "@web/core/templates";
import { rpcJsonCall } from "@southbrook_estimating_website/js/portal_boot.esm";
import { RoomOutlinePreview } from "@southbrook_estimating_website/js/room_setup_wizard.esm";

function _blankDraft() {
    return {
        name: "Main Kitchen",
        room_type: "kitchen",
        layout_shape: null,
        ceiling_height_mm: 2400,
        unit_preference: "mm",
        walls: [],
        assumptions: [],
        warnings: [],
        confidence: 0.0,
    };
}

export class RoomChatWidget extends Component {
    static template = "southbrook_room_chat.RoomChatWidget";
    static components = { RoomOutlinePreview };

    setup() {
        this.state = useState({
            messages: [],
            inputValue: "",
            sending: false,
            error: null,
            draft: _blankDraft(),
            reviewSent: false,
        });
        // `this.el` is NOT a valid API for a component mounted via raw
        // `mount()` the way this widget is (see autoMount() below) — it
        // threw `Cannot read properties of undefined (reading
        // 'dispatchEvent')` in production. useRef is the correct way to
        // reach the root DOM node here, same as HermesChat's own refs.
        this.rootRef = useRef("root");
    }

    get orderId() {
        const raw = this.props.orderId;
        if (!raw || raw === "") return null;
        const n = Number(raw);
        return Number.isFinite(n) && n > 0 ? n : null;
    }

    get hasDraftContent() {
        return !!(this.state.draft && this.state.draft.walls
            && this.state.draft.walls.length > 0);
    }

    // RoomOutlinePreview expects a FLAT constraints array with a
    // wall_index back-reference (the same shape RoomSetupWizard's own
    // state.constraints uses) — our draft nests constraints under each
    // wall (the existing_room / _estimate_to_existing_room shape), so
    // flatten here rather than changing that shared contract.
    get flatConstraints() {
        const walls = (this.state.draft && this.state.draft.walls) || [];
        const out = [];
        walls.forEach((wall, wallIndex) => {
            (wall.constraints || []).forEach((c) => {
                out.push({ ...c, wall_index: wallIndex });
            });
        });
        return out;
    }

    async submit() {
        const message = (this.state.inputValue || "").trim();
        if (!message || this.state.sending) return;
        this.state.error = null;
        this.state.sending = true;
        this.state.messages.push({ role: "user", content: message });
        this.state.inputValue = "";

        try {
            const result = await rpcJsonCall(
                `/southbrook/api/order/${encodeURIComponent(this.orderId)}/room/chat`,
                { order_id: this.orderId, message },
            );
            if (result && result.ok) {
                this.state.messages.push({ role: "assistant", content: result.reply });
                if (result.room) {
                    this.state.draft = result.room;
                }
            } else {
                const detail = (result && (result.detail || result.error)) || "unknown error";
                this.state.messages.push({
                    role: "assistant",
                    content: `(Couldn't process that: ${detail})`,
                });
                this.state.error = detail;
            }
        } catch (e) {
            this.state.messages.push({
                role: "assistant",
                content: `(Room chat request failed: ${e.message})`,
            });
            this.state.error = e.message;
        } finally {
            this.state.sending = false;
        }
    }

    async startOver() {
        if (this.state.sending) return;
        this.state.sending = true;
        try {
            const result = await rpcJsonCall(
                `/southbrook/api/order/${encodeURIComponent(this.orderId)}/room/chat`,
                { order_id: this.orderId, reset: true },
            );
            this.state.messages = [];
            this.state.draft = (result && result.room) ? result.room : _blankDraft();
            this.state.reviewSent = false;
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.sending = false;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) {
            ev.preventDefault();
            this.submit();
        }
    }

    reviewInWizard() {
        if (!this.hasDraftContent) return;
        this.state.reviewSent = true;
        const root = this.rootRef.el;
        if (!root) return;
        root.dispatchEvent(new CustomEvent("sb:room-chat-review", {
            detail: this.state.draft,
            bubbles: true,
        }));
    }
}

/**
 * Auto-mount, mirroring southbrook_hermes's HermesChat convention exactly
 * (including the getTemplate registry fix and the fail-safe hide-on-error
 * behavior — see that file's comment for why both are needed).
 */
async function autoMount() {
    const mounts = document.querySelectorAll("[data-room-chat-mount]");
    for (const el of mounts) {
        if (el.dataset.roomChatMounted === "1") continue;
        const orderId = el.dataset.orderId || null;
        try {
            el.dataset.roomChatMounted = "1";
            await mount(RoomChatWidget, el, {
                props: { orderId },
                getTemplate,
            });
        } catch (err) {
            delete el.dataset.roomChatMounted;
            el.style.display = "none";
            // eslint-disable-next-line no-console
            console.warn(
                "[southbrook_room_chat] RoomChatWidget mount failed — "
                + "hiding the chat panel and leaving the page intact:",
                err,
            );
        }
    }
}

whenReady(autoMount).catch((err) => {
    // eslint-disable-next-line no-console
    console.warn("[southbrook_room_chat] autoMount failed before mount:", err);
});
