// SPDX-License-Identifier: LGPL-3.0-only
// KitchenForge HTTP client (ESM, Node 18+ / browser fetch).

import type {
  AddZoneRequest,
  AddZoneResult,
  AgentManifest,
  ConfirmQuoteRequest,
  ConfirmQuoteResult,
  ErrorEnvelope,
  FsDirListing,
  FsFile,
  FsResult,
  InstantiateRequest,
  InstantiateResult,
  KitchenForgeClientOptions,
  MarathonTelemetry,
  RaiseEcoRequest,
  RaiseEcoResult,
  RebateSummary,
  ReleaseMosRequest,
  ReleaseMosResult,
  RequestOptions,
  ToolCatalog,
  Zone,
} from "./types.js";

// ----------------------------------------------------------------------
// Errors
// ----------------------------------------------------------------------
export class KitchenForgeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "KitchenForgeError";
  }
}

export class ApiError extends KitchenForgeError {
  status: number;
  code: string;
  details?: Record<string, unknown>;
  constructor(status: number, envelope: ErrorEnvelope | { error?: string; message?: string }) {
    const code = envelope.error ?? "unknown";
    const msg = envelope.message ?? code;
    super(`[${status} ${code}] ${msg}`);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = (envelope as ErrorEnvelope).details;
  }
}

export class NotFoundError extends ApiError {
  constructor(envelope: ErrorEnvelope) {
    super(404, envelope);
    this.name = "NotFoundError";
  }
}

export class PreconditionFailedError extends ApiError {
  constructor(status: number, envelope: ErrorEnvelope) {
    super(status, envelope);
    this.name = "PreconditionFailedError";
  }
}

// ----------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------
function uuid4(): string {
  // Prefer crypto.randomUUID where available (Node 18+, modern browsers).
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  // RFC 4122 v4 fallback.
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0"));
  return (
    hex.slice(0, 4).join("") +
    "-" +
    hex.slice(4, 6).join("") +
    "-" +
    hex.slice(6, 8).join("") +
    "-" +
    hex.slice(8, 10).join("") +
    "-" +
    hex.slice(10, 16).join("")
  );
}

function encodeFsPath(path: string): string {
  const trimmed = (path ?? "").replace(/^\/+/, "");
  if (!trimmed) return "";
  return trimmed
    .split("/")
    .filter((seg) => seg.length > 0)
    .map((seg) => encodeURIComponent(seg))
    .join("/");
}

// ----------------------------------------------------------------------
// Sub-clients
// ----------------------------------------------------------------------
class ToolsClient {
  constructor(private parent: KitchenForgeClient) {}

  async list(): Promise<ToolCatalog> {
    return this.parent.request<ToolCatalog>("GET", "/agent/v1/tools");
  }

  async instantiate(
    req: InstantiateRequest,
    options: RequestOptions = {},
  ): Promise<InstantiateResult> {
    return this.parent.request<InstantiateResult>(
      "POST",
      "/agent/v1/tools/instantiate",
      { jsonBody: req, idempotencyKey: options.idempotencyKey ?? uuid4() },
    );
  }

  async addZone(
    req: AddZoneRequest,
    options: RequestOptions = {},
  ): Promise<AddZoneResult> {
    return this.parent.request<AddZoneResult>(
      "POST",
      "/agent/v1/tools/add_zone",
      { jsonBody: req, idempotencyKey: options.idempotencyKey ?? uuid4() },
    );
  }

  async confirmQuote(
    req: ConfirmQuoteRequest,
    options: RequestOptions = {},
  ): Promise<ConfirmQuoteResult> {
    return this.parent.request<ConfirmQuoteResult>(
      "POST",
      "/agent/v1/tools/confirm_quote",
      { jsonBody: req, idempotencyKey: options.idempotencyKey ?? uuid4() },
    );
  }

  async releaseMos(
    req: ReleaseMosRequest,
    options: RequestOptions = {},
  ): Promise<ReleaseMosResult> {
    return this.parent.request<ReleaseMosResult>(
      "POST",
      "/agent/v1/tools/release_mos",
      { jsonBody: req, idempotencyKey: options.idempotencyKey ?? uuid4() },
    );
  }

  async raiseEco(
    req: RaiseEcoRequest,
    options: RequestOptions = {},
  ): Promise<RaiseEcoResult> {
    return this.parent.request<RaiseEcoResult>(
      "POST",
      "/agent/v1/tools/raise_eco",
      { jsonBody: req, idempotencyKey: options.idempotencyKey ?? uuid4() },
    );
  }
}

class MarathonClient {
  constructor(private parent: KitchenForgeClient) {}

  async telemetry(limit = 200): Promise<MarathonTelemetry> {
    return this.parent.request<MarathonTelemetry>(
      "GET",
      "/agent/v1/marathon/telemetry",
      { query: { limit: String(limit) } },
    );
  }

  async rebates(period?: string): Promise<RebateSummary> {
    const query: Record<string, string> = {};
    if (period) query.period = period;
    return this.parent.request<RebateSummary>(
      "GET",
      "/agent/v1/marathon/rebates",
      { query },
    );
  }
}

// ----------------------------------------------------------------------
// Client
// ----------------------------------------------------------------------
interface InternalRequestOptions {
  jsonBody?: unknown;
  query?: Record<string, string>;
  idempotencyKey?: string;
  ifMatch?: string;
}

export class KitchenForgeClient {
  readonly baseUrl: string;
  readonly apiKey: string;
  readonly timeoutMs: number;
  private readonly _fetch: typeof fetch;

  readonly tools: ToolsClient;
  readonly marathon: MarathonClient;

  constructor(options: KitchenForgeClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.timeoutMs = options.timeoutMs ?? 30_000;
    this._fetch = options.fetch ?? fetch;
    this.tools = new ToolsClient(this);
    this.marathon = new MarathonClient(this);
  }

  // --------------------- Filesystem ----------------------------------
  async fsGet<T = Record<string, unknown>>(
    path: string = "",
  ): Promise<FsResult<T>> {
    return this.request<FsResult<T>>("GET", this.fsUrl(path));
  }

  async fsPut<T = Record<string, unknown>>(
    path: string,
    body: Record<string, unknown>,
    options: RequestOptions = {},
  ): Promise<FsFile<T>> {
    return this.request<FsFile<T>>("PUT", this.fsUrl(path), {
      jsonBody: body,
      ifMatch: options.ifMatch,
      idempotencyKey: options.idempotencyKey ?? uuid4(),
    });
  }

  async fsHead(path: string): Promise<string | null> {
    const res = await this.rawRequest("HEAD", this.fsUrl(path));
    if (res.status === 404) return null;
    if (res.status >= 400) {
      throw new ApiError(res.status, { error: "head_failed" });
    }
    return res.headers.get("ETag");
  }

  // --------------------- Manifest ------------------------------------
  async manifest(): Promise<AgentManifest> {
    const res = await this.rawRequest("GET", "/.well-known/ai-agent.json", {
      authRequired: false,
    });
    return this.parseJson<AgentManifest>(res);
  }

  // --------------------- Internal ------------------------------------
  fsUrl(path: string): string {
    const encoded = encodeFsPath(path);
    return encoded ? `/agent/v1/files/${encoded}` : `/agent/v1/files`;
  }

  async request<T>(
    method: string,
    path: string,
    options: InternalRequestOptions = {},
  ): Promise<T> {
    const res = await this.rawRequest(method, path, options);
    return this.parseJson<T>(res);
  }

  async rawRequest(
    method: string,
    path: string,
    options: InternalRequestOptions & { authRequired?: boolean } = {},
  ): Promise<Response> {
    let url = `${this.baseUrl}${path}`;
    if (options.query) {
      const qs = new URLSearchParams(options.query).toString();
      if (qs) url += `?${qs}`;
    }
    const headers: Record<string, string> = {
      Accept: "application/json",
    };
    if (options.authRequired !== false) {
      headers["X-Api-Key"] = this.apiKey;
    }
    if (options.jsonBody !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (options.idempotencyKey) {
      headers["Idempotency-Key"] = options.idempotencyKey;
    }
    if (options.ifMatch) {
      headers["If-Match"] = options.ifMatch;
    }
    const init: RequestInit = {
      method,
      headers,
      body: options.jsonBody !== undefined
        ? JSON.stringify(options.jsonBody)
        : undefined,
    };
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    init.signal = controller.signal;
    try {
      return await this._fetch(url, init);
    } finally {
      clearTimeout(timer);
    }
  }

  async parseJson<T>(res: Response): Promise<T> {
    let body: unknown;
    const text = await res.text();
    try {
      body = text ? JSON.parse(text) : {};
    } catch {
      body = { error: "non_json", message: text.slice(0, 500) };
    }
    if (res.status >= 400) {
      const envelope = body as ErrorEnvelope;
      if (res.status === 404) throw new NotFoundError(envelope);
      if (res.status === 409 || res.status === 412) {
        throw new PreconditionFailedError(res.status, envelope);
      }
      throw new ApiError(res.status, envelope);
    }
    return body as T;
  }
}

// Re-export the Zone type for caller ergonomics.
export type { Zone };
