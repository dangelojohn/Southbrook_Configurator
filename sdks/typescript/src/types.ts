// SPDX-License-Identifier: LGPL-3.0-only
// Shared types for the KitchenForge agent surface.

export const SCHEMA_FS = "kitchenforge.agent.fs.v1" as const;
export const SCHEMA_TOOLS = "kitchenforge.agent.tools.v1" as const;
export const SCHEMA_API = "southbrook.flutter.api.v1" as const;

// ----------------------------------------------------------------------
// Error envelope
// ----------------------------------------------------------------------
export interface ErrorEnvelope {
  error: string;
  message: string;
  schema: typeof SCHEMA_API;
  details?: Record<string, unknown>;
}

// ----------------------------------------------------------------------
// Filesystem
// ----------------------------------------------------------------------
export interface FsEntry {
  name: string;
  kind: "dir" | "file";
  path: string;
  id?: number;
  desc?: string;
  label?: string;
  [extra: string]: unknown;
}

export interface FsDirListing {
  kind: "dir";
  path: string;
  schema: typeof SCHEMA_FS;
  entries: FsEntry[];
}

export interface FsFile<TContent = Record<string, unknown>> {
  kind: "file";
  path: string;
  etag?: string;
  schema: typeof SCHEMA_FS;
  content: TContent;
}

export type FsResult<TContent = Record<string, unknown>> =
  | FsDirListing
  | FsFile<TContent>;

// ----------------------------------------------------------------------
// Tool catalog
// ----------------------------------------------------------------------
export interface ToolDescriptor {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  endpoint: string;
}

export interface ToolCatalog {
  schema: typeof SCHEMA_TOOLS;
  tools: ToolDescriptor[];
}

// ----------------------------------------------------------------------
// Tool requests + results
// ----------------------------------------------------------------------
export interface RoomDims {
  room_width_mm?: number;
  room_depth_mm?: number;
  ceiling_height_mm?: number;
}

export interface InstantiateRequest {
  template_id: number;
  partner_id: number;
  dims?: RoomDims;
  target_date?: string;
}

export interface InstantiateResult {
  ok: boolean;
  project_id: number;
  project_path: string;
  sale_order_id: number;
  sale_order_name: string;
  quote_path: string;
  schema?: typeof SCHEMA_API;
  [extra: string]: unknown;
}

export interface Zone {
  product_id: number;
  quantity?: number;
  width_mm?: number;
  height_mm?: number;
  depth_mm?: number;
  preselected_attribute_values?: Record<string, unknown>;
}

export interface AddZoneRequest {
  project_id: number;
  zone: Zone;
}

export interface AddZoneResult {
  ok: boolean;
  project_id: number;
  zones_path: string;
  line_count: number;
  schema?: typeof SCHEMA_API;
}

export interface ConfirmQuoteRequest {
  project_id: number;
}

export interface ConfirmQuoteResult {
  ok: boolean;
  sale_order?: string;
  state?: string;
  mo_path?: string;
  already_confirmed?: boolean;
  schema?: typeof SCHEMA_API;
}

export interface ReleaseMosRequest {
  project_id: number;
}

export interface ReleasedMo {
  id: number;
  name: string;
  state: string;
}

export interface ReleaseMosResult {
  ok: boolean;
  released_count: number;
  mos: ReleasedMo[];
  schema?: typeof SCHEMA_API;
}

export interface RaiseEcoRequest {
  title: string;
  reason?: string;
  project_id?: number;
  target_bom_id?: number;
}

export interface RaiseEcoResult {
  ok: boolean;
  eco_id: number;
  stage: string | null;
  requires_approver: boolean;
  schema?: typeof SCHEMA_API;
}

// ----------------------------------------------------------------------
// Marathon
// ----------------------------------------------------------------------
export interface SpecEvent {
  id: number;
  ts: string;
  product_default_code: string | null;
  product_name: string;
  qty: number;
  cabinet_family: string | null;
  pull_finish: string | null;
  pull_size_mm: number | null;
  sale_order: string | null;
}

export interface MarathonTelemetry {
  schema: "kitchenforge.marathon.telemetry.v1";
  tenant: string;
  count: number;
  events: SpecEvent[];
}

export interface RebateSummary {
  schema: "kitchenforge.marathon.rebates.v1";
  tenant: string;
  summary: Record<string, unknown>;
}

// ----------------------------------------------------------------------
// Manifest
// ----------------------------------------------------------------------
export interface AgentManifest {
  schema_version: string;
  name_for_model: string;
  name_for_human?: string;
  description_for_human?: string;
  description_for_model?: string;
  auth: {
    type: string;
    header_name: string;
    issuance?: string;
  };
  filesystem: {
    base_url: string;
    verbs: string[];
    namespaces?: Array<{ path: string; writable: boolean; desc?: string }>;
    etag_concurrency?: boolean;
  };
  tools_url: string;
  [extra: string]: unknown;
}

// ----------------------------------------------------------------------
// Client options
// ----------------------------------------------------------------------
export interface KitchenForgeClientOptions {
  baseUrl: string;
  apiKey: string;
  timeoutMs?: number;
  fetch?: typeof fetch;
}

export interface RequestOptions {
  idempotencyKey?: string;
  ifMatch?: string;
}
