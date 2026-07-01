/* SPDX-License-Identifier: LGPL-3.0-only */
/**
 * HermesChat — OWL 2 component for the Order Builder portal page.
 *
 * Mounts on the first <div data-hermes-chat-mount> it finds. Reads
 * data-order-id from the mount to attach order context to each turn.
 *
 * Conversation flow per turn:
 *   1. User types a question, hits "Ask Hermes".
 *   2. POST /hermes/v1/ask with {q, order_id}.
 *   3. Response is a text stream (sidecar SSE → text stream); append
 *      tokens to the in-progress assistant message as they arrive.
 *   4. When the stream ends, mark the message non-streaming.
 *
 * The sidecar already fire-and-forgets the conversation log back to
 * Odoo, so we don't double-log from the client.
 */
import { Component, mount, useRef, useState, whenReady, xml } from "@odoo/owl";
import { getTemplate } from "@web/core/templates";

const ENDPOINT = "/hermes/v1/ask";

export class HermesChat extends Component {
    static template = "southbrook_hermes.HermesChat";

    setup() {
        this.state = useState({
            messages: [],
            inputValue: "",
            sending: false,
            error: null,
        });
        this.inputRef = useRef("input");
        this.scrollRef = useRef("scroll");
    }

    get orderId() {
        const raw = this.props.orderId;
        if (!raw || raw === "") return null;
        const n = Number(raw);
        return Number.isFinite(n) && n > 0 ? n : null;
    }

    async submit() {
        const q = (this.state.inputValue || "").trim();
        if (!q || this.state.sending) return;
        this.state.error = null;
        this.state.sending = true;
        this.state.messages.push({ role: "user", content: q, streaming: false });
        const assistant = { role: "assistant", content: "", streaming: true };
        this.state.messages.push(assistant);
        this.state.inputValue = "";
        this._scrollToBottom();

        try {
            const resp = await fetch(ENDPOINT, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ q, order_id: this.orderId }),
            });
            if (!resp.ok) {
                let detail = "";
                try {
                    const j = await resp.json();
                    detail = j.detail || j.error || "";
                } catch (e) {
                    detail = await resp.text();
                }
                assistant.content = `(Hermes is unavailable: ${detail || resp.status})`;
                assistant.streaming = false;
                this.state.error = detail || `HTTP ${resp.status}`;
                return;
            }
            // Detect stub-mode (B1 stub returns JSON, not a stream).
            const ct = resp.headers.get("content-type") || "";
            if (ct.includes("application/json")) {
                const j = await resp.json();
                if (j.stub) {
                    assistant.content = j.answer || "(stub answer)";
                } else if (typeof j.answer === "string") {
                    assistant.content = j.answer;
                } else {
                    assistant.content = JSON.stringify(j);
                }
                assistant.streaming = false;
                this._scrollToBottom();
                return;
            }
            // Streaming text response from the sidecar.
            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                assistant.content += decoder.decode(value, { stream: true });
                this._scrollToBottom();
            }
            // Flush any UTF-8 bytes still buffered in the decoder (split
            // multi-byte sequences in the final chunk would otherwise be
            // silently dropped — affects accented characters, em-dashes,
            // currency symbols).
            assistant.content += decoder.decode();
            assistant.streaming = false;
        } catch (e) {
            assistant.content = `(Hermes request failed: ${e.message})`;
            assistant.streaming = false;
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

    _scrollToBottom() {
        // Defer to next tick so the DOM has reflowed.
        Promise.resolve().then(() => {
            const el = this.scrollRef.el;
            if (el) el.scrollTop = el.scrollHeight;
        });
    }
}

/**
 * Auto-mount: find any <div data-hermes-chat-mount> on the page and mount
 * a HermesChat into it. Lets us drop the panel anywhere in QWeb without
 * a JS edit.
 *
 * 2026-07-01 fix — the root cause of the recurring
 *   `OwlError: Missing template: "southbrook_hermes.HermesChat"`
 *   `TypeError: Cannot read properties of undefined (reading 'add')`
 * was that raw OWL's `mount()` creates an `App` with no template
 * registry. Named string templates (`static template = "module.Name"`)
 * therefore never resolve; only inline `xml\`\`` templates work. The
 * fix passes Odoo's `getTemplate` from `@web/core/templates` to the
 * mount config so OWL can look up the registered XML template.
 *
 * The prior 2026-06-22 sync `try/catch` around `mount()` also didn't
 * work: OWL's `mount()` returns a Promise, so any error thrown inside
 * OWL becomes a Promise rejection that escapes a synchronous catch.
 * The rewrite uses `await` inside an `async` `autoMount` so caught +
 * uncaught paths are consistent.
 */
async function autoMount() {
    const mounts = document.querySelectorAll("[data-hermes-chat-mount]");
    for (const el of mounts) {
        if (el.dataset.hermesMounted === "1") continue;
        const orderId = el.dataset.orderId || null;
        try {
            el.dataset.hermesMounted = "1";
            await mount(HermesChat, el, {
                props: { orderId },
                getTemplate,
            });
        } catch (err) {
            // Clear the guard so a future re-invocation (SPA-style nav
            // or a defensive retry) can try again — keeping it set on
            // failure was leaving the mount-point permanently blocked.
            delete el.dataset.hermesMounted;
            // Strip the mount-point from the DOM so a half-broken
            // wrapper doesn't push the surrounding layout around.
            el.style.display = "none";
            // eslint-disable-next-line no-console
            console.warn(
                "[southbrook_hermes] HermesChat mount failed — "
                + "hiding the chat panel and leaving the page intact:",
                err,
            );
        }
    }
}

// Use OWL's `whenReady` so autoMount fires once DOM+template
// registration is done. Chain `.catch()` because the pre-try setup
// (querySelectorAll, dataset writes) sits outside the per-mount
// try/catch — its rejection would otherwise be an unhandled promise.
whenReady(autoMount).catch((err) => {
    // eslint-disable-next-line no-console
    console.warn("[southbrook_hermes] autoMount failed before mount:", err);
});
