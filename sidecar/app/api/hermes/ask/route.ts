// POST /api/hermes/ask — main Hermes agent loop.
//
// Flow per request:
//   1. Verify the JWT (Plan B1's proxy minted it from the live session).
//   2. Pull tool registry from the tenant's Odoo (cached per cold start).
//   3. Retrieve top-K RAG hits from the per-tenant index.
//   4. Compose messages: persona-voice system + RAG injection + user q.
//   5. streamText with tools — the AI SDK handles tool roundtrips for us.
//   6. After stream completes, fire-and-forget the conversation log to
//      Odoo so the Q+A persists alongside Fabio v0 records.
import { streamText } from "ai";
import type { CoreMessage } from "ai";

import { getModel } from "@/lib/ai";
import { extractBearer, verifyJwt } from "@/lib/jwt";
import { ragInjectionMessage, buildSystemPrompt } from "@/lib/prompts";
import { retrieveTopK } from "@/lib/rag";
import { isKnownTenant } from "@/lib/tenants";
import { fetchToolRegistry, toAiSdkTools } from "@/lib/tools";
import type { Persona } from "@/lib/types";

interface AskBody {
  q: string;
  order_id?: number;
}

function jsonResp(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function POST(req: Request): Promise<Response> {
  const token = extractBearer(req.headers.get("authorization"));
  if (!token) return jsonResp({ error: "missing_bearer_token" }, 401);

  let claims;
  try {
    claims = await verifyJwt(token);
  } catch (e) {
    return jsonResp({ error: "jwt_config", detail: (e as Error).message }, 503);
  }
  if (!claims) return jsonResp({ error: "invalid_token" }, 401);
  if (!isKnownTenant(claims.tenant)) {
    return jsonResp({ error: "unknown_tenant", tenant: claims.tenant }, 403);
  }

  let body: AskBody;
  try {
    body = (await req.json()) as AskBody;
  } catch {
    return jsonResp({ error: "invalid_json" }, 400);
  }
  const q = (body.q || "").trim();
  if (!q) return jsonResp({ error: "empty_question" }, 400);

  // (2) Tool registry — cached per (tenant, persona, tier).
  const registry = await fetchToolRegistry(claims.tenant, token, {
    persona: claims.persona,
    tier: claims.tier,
  });
  const tools = toAiSdkTools(registry.tools, claims.tenant, token);

  // (3) RAG retrieval.
  const hits = await retrieveTopK(claims.tenant, q, 5);
  const ragMsg = ragInjectionMessage(hits);

  // (4) Compose messages.
  const messages: CoreMessage[] = [
    { role: "system", content: buildSystemPrompt(claims.persona as Persona, claims.tenant) },
  ];
  if (ragMsg) messages.push(ragMsg);
  if (body.order_id) {
    messages.push({
      role: "system",
      content: `The user is currently looking at order ID ${body.order_id}. Default to it when they say "this order" / "my kitchen" without naming a different one.`,
    });
  }
  messages.push({ role: "user", content: q });

  // (5) Stream the answer + handle tool roundtrips. streamText accepts
  // CoreMessage[] directly; convertToModelMessages is for the UI-message
  // layer (id/parts/createdAt) → CoreMessage, NOT for already-typed
  // CoreMessage[]. Passing through it can silently drop our system
  // messages (RAG injection, persona voice).
  const result = streamText({
    model: getModel("default"),
    messages,
    tools,
    // Cap tool use so a runaway loop is bounded. 5 covers the worst-case
    // realistic chain (list_my_orders → get_order_status → get_order_line
    // → get_os_section → propose_recommendation).
    stopWhen: ({ steps }) => steps.length >= 5,
    // After stream completes, log the Q+A back to Odoo. Fire-and-forget.
    onFinish: ({ text }) => {
      // No await on purpose — we don't want logging to block the stream.
      logConversation(claims.tenant, token, {
        question: q,
        answer: text,
        order_id: body.order_id,
      }).catch((e) => {
        // eslint-disable-next-line no-console
        console.error("Conversation log failed:", e);
      });
    },
  });

  return result.toTextStreamResponse({
    headers: { "Cache-Control": "no-store" },
  });
}

async function logConversation(
  tenant: string,
  jwt: string,
  body: { question: string; answer: string; order_id?: number },
): Promise<void> {
  const { getOdooUrl } = await import("@/lib/tenants");
  await fetch(`${getOdooUrl(tenant)}/api/hermes/conversation/log`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${jwt}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question: body.question,
      answer: body.answer,
      scope: "customer",
      // Pass order_id through so the persisted question record stays
      // linked to whichever order the chat was about. Odoo's
      // log_conversation method ignores unknown kwargs, so this stays
      // forward-compatible if the Odoo side adds the column later.
      order_id: body.order_id ?? null,
    }),
  });
}
