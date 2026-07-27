// Pull the tool registry from Odoo and dispatch tool calls back through
// the same JWT. The Odoo controllers (Plan B1 Task 8) enforce persona +
// tier ACL and run each tool with env(user=portal_user), so record rules
// transparently scope what the partner can see.
import { tool } from "ai";
import { z } from "zod";

import { getOdooUrl } from "./tenants";
import type { ToolDef, ToolResult } from "./types";

interface RegistryResponse {
  tenant: string;
  persona: string;
  tier: string;
  tools: ToolDef[];
}

const registryCache = new Map<string, RegistryResponse>();

export async function fetchToolRegistry(
  tenant: string,
  jwt: string,
  claims: { persona: string; tier: string },
): Promise<RegistryResponse> {
  // Cache by what actually affects the response shape: tenant + persona +
  // tier mask. NOT the JWT suffix — that changes per request (so cache
  // never warmed) AND could collide between users whose token tails match.
  const key = `${tenant}::${claims.persona}::${claims.tier}`;
  const cached = registryCache.get(key);
  if (cached) return cached;
  const resp = await fetch(`${getOdooUrl(tenant)}/api/hermes/tools`, {
    headers: { Authorization: `Bearer ${jwt}` },
  });
  if (!resp.ok) {
    throw new Error(
      `Tool registry fetch failed: HTTP ${resp.status} ${await resp.text()}`,
    );
  }
  const reg = (await resp.json()) as RegistryResponse;
  registryCache.set(key, reg);
  return reg;
}

export async function callTool(
  tenant: string,
  slug: string,
  args: Record<string, unknown>,
  jwt: string,
): Promise<ToolResult> {
  const resp = await fetch(
    `${getOdooUrl(tenant)}/api/hermes/tools/${encodeURIComponent(slug)}`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jwt}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(args),
    },
  );
  if (!resp.ok) {
    let detail = "";
    try {
      const j = await resp.json();
      detail = JSON.stringify(j);
    } catch {
      detail = await resp.text();
    }
    return { error: `tool_http_${resp.status}`, detail };
  }
  return (await resp.json()) as ToolResult;
}

// Convert a JSON-schema-fragment from the Odoo registry into a zod schema
// the AI SDK can ingest. Only the basic types we use in Plan B1 tools.
function jsonSchemaToZod(schema: ToolDef["parameters"]): z.ZodObject<z.ZodRawShape> {
  const shape: z.ZodRawShape = {};
  for (const [name, prop] of Object.entries(schema.properties)) {
    let s: z.ZodTypeAny;
    switch (prop.type) {
      case "integer": s = z.number().int(); break;
      case "number": s = z.number(); break;
      case "boolean": s = z.boolean(); break;
      case "object": s = z.record(z.any()); break;
      case "array": s = z.array(z.any()); break;
      default: s = z.string();
    }
    if (!schema.required.includes(name)) s = s.optional();
    shape[name] = s;
  }
  return z.object(shape);
}

export function toAiSdkTools(
  registry: ToolDef[],
  tenant: string,
  jwt: string,
): Record<string, ReturnType<typeof tool>> {
  const out: Record<string, ReturnType<typeof tool>> = {};
  for (const def of registry) {
    out[def.slug] = tool({
      description: def.description,
      inputSchema: jsonSchemaToZod(def.parameters),
      execute: async (args) => {
        return callTool(tenant, def.slug, args as Record<string, unknown>, jwt);
      },
    });
  }
  return out;
}
