// Per-tenant Odoo URL resolution. Source of truth: TENANT_REGISTRY env var,
// a JSON object keyed by tenant slug.
type TenantRegistry = Record<string, string>;

let cached: TenantRegistry | null = null;

function loadRegistry(): TenantRegistry {
  if (cached) return cached;
  const raw = process.env.TENANT_REGISTRY;
  if (!raw) {
    throw new Error(
      "TENANT_REGISTRY env var is missing. Set it to a JSON object like " +
        '{"southbrook":"https://southbrookcabinetry.space"}.',
    );
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new Error(`TENANT_REGISTRY is not valid JSON: ${(e as Error).message}`);
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("TENANT_REGISTRY must be a non-null JSON object.");
  }
  // Validate every value is a non-empty string. A malformed-but-parseable
  // entry like {"southbrook": null} would otherwise poison the module
  // cache and crash getOdooUrl with a confusing TypeError on every
  // subsequent request.
  for (const [k, v] of Object.entries(parsed)) {
    if (typeof v !== "string" || !v) {
      throw new Error(
        `TENANT_REGISTRY entry '${k}' must be a non-empty string URL, got ${typeof v}.`,
      );
    }
  }
  cached = parsed as TenantRegistry;
  return cached;
}

export function getOdooUrl(tenant: string): string {
  const reg = loadRegistry();
  const url = reg[tenant];
  if (!url) {
    throw new Error(
      `Unknown tenant '${tenant}'. Add it to TENANT_REGISTRY.`,
    );
  }
  return url.replace(/\/$/, "");
}

export function isKnownTenant(tenant: string): boolean {
  const reg = loadRegistry();
  return tenant in reg;
}

export function listTenants(): string[] {
  return Object.keys(loadRegistry());
}
