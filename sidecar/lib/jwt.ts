// HS256 JWT verification using `jose`. The secret must match Odoo's
// southbrook_hermes.jwt_secret config_parameter exactly — set it on Vercel
// as HERMES_JWT_SECRET.
import { jwtVerify } from "jose";

import type { Claims } from "./types";

function getSecret(): Uint8Array {
  const raw = process.env.HERMES_JWT_SECRET;
  if (!raw) {
    throw new Error(
      "HERMES_JWT_SECRET is not set. Set it on Vercel and mirror the value in Odoo's southbrook_hermes.jwt_secret config_parameter.",
    );
  }
  return new TextEncoder().encode(raw);
}

export async function verifyJwt(token: string): Promise<Claims | null> {
  // Pull the secret OUTSIDE the try so a missing/misconfigured env var
  // surfaces as a thrown Error to the caller (→ 503 hermes_not_configured),
  // not as a silent null (→ 401 invalid_token). Otherwise a mis-rotated
  // secret looks indistinguishable from "attacker sent garbage" — bad for
  // ops debugging.
  const secret = getSecret();
  try {
    const { payload } = await jwtVerify(token, secret, {
      algorithms: ["HS256"],
      clockTolerance: 5, // seconds — Odoo's clock may drift slightly.
    });
    if (typeof payload.tenant !== "string") return null;
    if (typeof payload.persona !== "string") return null;
    if (typeof payload.partner_id !== "number") return null;
    if (typeof payload.tier !== "string") return null;
    return payload as unknown as Claims;
  } catch {
    return null;
  }
}

export function extractBearer(authHeader: string | null): string | null {
  if (!authHeader) return null;
  if (!authHeader.startsWith("Bearer ")) return null;
  return authHeader.slice("Bearer ".length).trim();
}
