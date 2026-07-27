/**
 * pnpm verify — sanity-check sidecar env vars before deploy.
 *
 * Exits non-zero if anything required is missing or malformed.
 */
import { listTenants } from "../lib/tenants";

function check(name: string, present: boolean, detail = ""): boolean {
  const status = present ? "ok" : "MISSING";
  console.log(`  ${name}: ${status}${detail ? ` (${detail})` : ""}`);
  return present;
}

function main(): void {
  console.log("Hermes sidecar config check\n");
  const errors: string[] = [];

  if (!check("HERMES_JWT_SECRET", !!process.env.HERMES_JWT_SECRET)) {
    errors.push("HERMES_JWT_SECRET is required.");
  }
  const hasGateway = !!process.env.AI_GATEWAY_KEY;
  const hasOpenAI = !!process.env.OPENAI_API_KEY;
  check("AI_GATEWAY_KEY", hasGateway);
  check("OPENAI_API_KEY", hasOpenAI);
  if (!hasGateway && !hasOpenAI) {
    errors.push(
      "Either AI_GATEWAY_KEY or OPENAI_API_KEY must be set for the agent loop to call a model.",
    );
  }

  try {
    const tenants = listTenants();
    check("TENANT_REGISTRY", true, `tenants: ${tenants.join(", ")}`);
  } catch (e) {
    check("TENANT_REGISTRY", false, (e as Error).message);
    errors.push((e as Error).message);
  }

  check("DEFAULT_MODEL", !!process.env.DEFAULT_MODEL, process.env.DEFAULT_MODEL || "(falls back to openai/gpt-4o)");
  check("LONG_CONTEXT_MODEL", !!process.env.LONG_CONTEXT_MODEL, process.env.LONG_CONTEXT_MODEL || "(optional)");

  if (errors.length > 0) {
    console.error("\nErrors:");
    for (const e of errors) console.error(`  - ${e}`);
    process.exit(1);
  }
  console.log("\nAll required env vars present.");
}

main();
