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
  try {
    const parsed = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) {
      throw new Error("TENANT_REGISTRY must be a JSON object.");
    }
    cached = parsed as TenantRegistry;
    return cached;
  } catch (e) {
    throw new Error(`TENANT_REGISTRY is not valid JSON: ${(e as Error).message}`);
  }
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
