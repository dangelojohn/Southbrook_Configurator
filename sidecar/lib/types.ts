// Shared types for the Hermes sidecar.

export type Persona = "trade_partner" | "sales_rep" | "mfg_manager";

export interface Claims {
  tenant: string;
  persona: Persona;
  partner_id: number;
  tier: string; // "T0+T1" etc.
  order_id?: number;
  iat: number;
  exp: number;
}

export interface ToolDef {
  slug: string;
  qualified_slug: string;
  personas: Persona[];
  tier: "T0" | "T1" | "T2";
  scope: string;
  description: string;
  parameters: {
    type: "object";
    properties: Record<string, { type: string }>;
    required: string[];
  };
}

export type ToolResult = Record<string, unknown> | { error: string; detail?: string };

export interface OsSectionRaw {
  slug: string;
  name: string;
  version: number;
  source: "canonical" | "generated";
  audience_tags?: string;
  body: string;
  last_updated_at?: string | null;
}

export interface OsBundle {
  tenant: string;
  publication: { calendar_key: string; build_hash: string; built_at: string };
  sections: OsSectionRaw[];
}

export interface RagChunk {
  slug: string;
  name: string;
  ord: number;
  text: string;
  embedding: number[];
}

export interface RagIndex {
  tenant: string;
  build_hash: string;
  built_at: string;
  chunks: RagChunk[];
}

export interface RagHit {
  slug: string;
  name: string;
  text: string;
  score: number;
}
