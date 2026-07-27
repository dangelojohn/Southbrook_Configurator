// POST /api/hermes/conversation/log — outbound proxy back to Odoo.
//
// The main /ask route logs Q+A turns automatically via onFinish. This
// endpoint exists so external callers (e.g., the OWL panel posting an
// edited reply) can also log without going through the streaming loop.
import { extractBearer, verifyJwt } from "@/lib/jwt";
import { getOdooUrl, isKnownTenant } from "@/lib/tenants";

interface LogBody {
  question: string;
  answer: string;
  scope?: string;
  project_id?: number;
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

  let body: LogBody;
  try {
    body = (await req.json()) as LogBody;
  } catch {
    return jsonResp({ error: "invalid_json" }, 400);
  }

  const upstream = await fetch(
    `${getOdooUrl(claims.tenant)}/api/hermes/conversation/log`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    },
  );

  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
