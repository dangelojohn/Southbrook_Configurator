// SPDX-License-Identifier: LGPL-3.0-only
//
// W037 (R8.4, 2026-06-27) — Wi-Fi offline scan queue Service Worker.
//
// JTBD: "When the shop wifi drops for 30 seconds while I scan 5
// cabinets, I want those scans queued locally and synced when wifi
// returns — no manual re-scan."
//
// Scope: ONLY intercepts POSTs whose path starts with `/sb/qr/`.
// Anything else passes through untouched. (Constraint per W037 spec
// — we are NOT a general offline framework.)
//
// Flow:
//   * Online + 2xx response  → pass-through.
//   * `!navigator.onLine` OR fetch throws (network error) OR 5xx →
//     enqueue payload to IndexedDB FIFO; reply to caller with a
//     synthetic 200 + {ok:true, queued:true, queued_at:<iso>}.
//   * `online` event OR explicit `{type:'sb-drain'}` postMessage →
//     dequeue head, POST it; on 2xx delete from store; on net error
//     stop draining and wait for next online event.
//
// Server-side dedup: every payload carries `client_uuid` (uuid v4
// minted in the caller). The controller's `_dispatch` consults a
// short-lived cache; replays return the original result, not a
// double-action. See controllers/qr_scan.py `_seen_client_uuid`.
//
// Cap: at most 500 queued entries by default (overridable in caller
// via the `sb-queue-cap` postMessage). Beyond the cap the OLDEST
// entry is dropped to make room — the operator gets the most-recent
// scans preserved (FIFO eviction at the head, FIFO drain at the head;
// net effect is a sliding window of the last 500 outage scans).
//
// Storage: IndexedDB store name `sb-offline-scan-queue` / object
// store `q`. Keyed by auto-increment id (insertion order = FIFO).
//
// Why a Service Worker (vs a plain fetch wrapper):
//   * Survives navigations and tab refresh — the queue keeps
//     draining even after the operator closes the scan modal.
//   * One install covers EVERY caller — the OWL Order Builder,
//     the floor traveler PWA, the POD page, the Bin/Load-Unit
//     screens shipping in W073 — all behind one fetch interceptor.
//   * Returning a synthetic 200 needs Response objects, which is
//     a SW primitive.

const SCOPE_PREFIX = "/sb/qr/";
const STORE_DB = "sb-offline-scan-queue";
const STORE_NAME = "q";
const STORE_VERSION = 1;
let queueCap = 500;

// ----------------------------------------------------------------------
// IndexedDB helpers (Promise-wrapped). No external deps — this file
// loads as a classic Service Worker; we cannot import OWL utils.
// ----------------------------------------------------------------------
function openDb() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(STORE_DB, STORE_VERSION);
        req.onupgradeneeded = () => {
            const db = req.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, {
                    keyPath: "id",
                    autoIncrement: true,
                });
            }
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

function tx(db, mode) {
    return db.transaction(STORE_NAME, mode).objectStore(STORE_NAME);
}

async function enqueue(entry) {
    const db = await openDb();
    // Cap enforcement: count first, evict head if at limit.
    const count = await new Promise((resolve, reject) => {
        const req = tx(db, "readonly").count();
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
    if (count >= queueCap) {
        // Drop oldest entry to make room.
        const oldest = await peekHead(db);
        if (oldest) {
            await new Promise((resolve, reject) => {
                const r = tx(db, "readwrite").delete(oldest.id);
                r.onsuccess = () => resolve();
                r.onerror = () => reject(r.error);
            });
        }
    }
    return new Promise((resolve, reject) => {
        const req = tx(db, "readwrite").add(entry);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

function peekHead(db) {
    return new Promise((resolve, reject) => {
        const req = tx(db, "readonly").openCursor();
        req.onsuccess = () => {
            const cursor = req.result;
            resolve(cursor ? cursor.value : null);
        };
        req.onerror = () => reject(req.error);
    });
}

async function deleteEntry(id) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
        const req = tx(db, "readwrite").delete(id);
        req.onsuccess = () => resolve();
        req.onerror = () => reject(req.error);
    });
}

async function queueSize() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
        const req = tx(db, "readonly").count();
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

// ----------------------------------------------------------------------
// Broadcast queue depth + draining state to all clients so UI badges
// stay in sync without polling.
// ----------------------------------------------------------------------
async function broadcast(state) {
    const clients = await self.clients.matchAll({includeUncontrolled: true});
    const size = await queueSize().catch(() => -1);
    for (const c of clients) {
        c.postMessage({type: "sb-queue", state: state, size: size});
    }
}

// ----------------------------------------------------------------------
// Drain loop — pulls head, POSTs, deletes on success.
// Stops on first network failure (operator is still offline / flaky).
// ----------------------------------------------------------------------
let draining = false;
async function drainQueue() {
    if (draining) {
        return;
    }
    draining = true;
    await broadcast("draining");
    try {
        while (true) {
            const db = await openDb();
            const head = await peekHead(db);
            if (!head) {
                break;
            }
            let response;
            try {
                response = await fetch(head.url, {
                    method: head.method,
                    headers: head.headers,
                    body: head.body,
                    credentials: "include",
                });
            } catch (e) {
                // Net error — still offline. Bail and wait for next
                // `online` event.
                break;
            }
            if (response.status >= 200 && response.status < 300) {
                await deleteEntry(head.id);
                await broadcast("draining");
            } else if (response.status >= 400 && response.status < 500) {
                // 4xx is a client error — replaying it will fail
                // again forever. Drop the entry; log via broadcast.
                await deleteEntry(head.id);
                await broadcast("draining");
            } else {
                // 5xx — server is reachable but unhappy. Bail and
                // retry on next drain trigger.
                break;
            }
        }
    } finally {
        draining = false;
        await broadcast("idle");
    }
}

// ----------------------------------------------------------------------
// Fetch interceptor.
// ----------------------------------------------------------------------
self.addEventListener("install", (event) => {
    // Activate immediately on first install so we don't miss the
    // next outage.
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener("message", (event) => {
    const data = event.data || {};
    if (data.type === "sb-drain") {
        event.waitUntil(drainQueue());
    } else if (data.type === "sb-queue-cap") {
        queueCap = Math.max(1, Math.min(parseInt(data.cap, 10) || 500, 10000));
    } else if (data.type === "sb-queue-size") {
        event.waitUntil(broadcast("idle"));
    }
});

// `online` event in a SW fires when the network connection is
// restored at the OS level. We piggyback on it to drain.
self.addEventListener("online", () => {
    drainQueue();
});

self.addEventListener("fetch", (event) => {
    const req = event.request;
    if (req.method !== "POST") {
        return;
    }
    const url = new URL(req.url);
    if (url.origin !== self.location.origin) {
        return;
    }
    if (!url.pathname.startsWith(SCOPE_PREFIX)) {
        return;
    }
    event.respondWith(handleScanPost(req));
});

async function handleScanPost(req) {
    // Clone request body so we can both forward and queue it.
    const clone = req.clone();
    const body = await clone.text();
    const headers = {};
    req.headers.forEach((v, k) => {
        headers[k] = v;
    });
    // If we already know we're offline, skip the fetch attempt
    // entirely — saves the browser an inevitable timeout.
    if (!self.navigator.onLine) {
        return await queueAndAck(req.url, body, headers);
    }
    try {
        const response = await fetch(req.url, {
            method: "POST",
            headers: headers,
            body: body,
            credentials: "include",
        });
        // 5xx = server reachable but degraded; queue so the operator
        // doesn't see a UI error during an Odoo restart.
        if (response.status >= 500) {
            return await queueAndAck(req.url, body, headers);
        }
        return response;
    } catch (e) {
        // Network error — queue + synthetic ack.
        return await queueAndAck(req.url, body, headers);
    }
}

async function queueAndAck(url, body, headers) {
    const queuedAt = new Date().toISOString();
    try {
        await enqueue({
            url: url,
            method: "POST",
            headers: headers,
            body: body,
            queued_at: queuedAt,
        });
    } catch (e) {
        // IndexedDB failed — return a real failure so the UI can
        // surface it instead of silently dropping the scan.
        return new Response(
            JSON.stringify({
                ok: false,
                queued: false,
                error: "offline queue unavailable: " + (e && e.message),
            }),
            {
                status: 503,
                headers: {"Content-Type": "application/json"},
            },
        );
    }
    await broadcast("queued");
    // The callers POST either JSON-RPC (Odoo `type=json`) or plain
    // JSON. Wrap our synthetic ack in `{jsonrpc:"2.0", id:null,
    // result:{...}}` so the JSON-RPC parser on the client side is
    // happy either way; plain-JSON callers tolerate the extra
    // envelope by reading `.result` when present (the convention in
    // controllers/qr_scan.py already does this).
    const payload = {
        ok: true,
        queued: true,
        queued_at: queuedAt,
        result: "queued",
    };
    return new Response(
        JSON.stringify({jsonrpc: "2.0", id: null, result: payload}),
        {
            status: 200,
            headers: {"Content-Type": "application/json"},
        },
    );
}
