// RAG retrieval over flat per-tenant index.json.
//
// At v1.0 corpus size (~30 KB markdown, ~50 chunks) cosine in JS is fine.
// Revisit at 10× growth.
import { openai } from "@ai-sdk/openai";
import { embed } from "ai";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

import type { RagHit, RagIndex } from "./types";

const cache = new Map<string, RagIndex>();

async function loadIndex(tenant: string): Promise<RagIndex> {
  const cached = cache.get(tenant);
  if (cached) return cached;
  const path = join(process.cwd(), "data", "index", tenant, "index.json");
  const raw = await readFile(path, "utf-8");
  const idx = JSON.parse(raw) as RagIndex;
  if (idx.tenant !== tenant) {
    throw new Error(
      `Index file for '${tenant}' contains tenant='${idx.tenant}'.`,
    );
  }
  cache.set(tenant, idx);
  return idx;
}

function cosine(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  if (na === 0 || nb === 0) return 0;
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

export async function retrieveTopK(
  tenant: string,
  query: string,
  k = 5,
): Promise<RagHit[]> {
  const idx = await loadIndex(tenant);
  const { embedding } = await embed({
    model: openai.embedding("text-embedding-3-small"),
    value: query,
  });
  const scored = idx.chunks.map((c) => ({
    slug: c.slug,
    name: c.name,
    text: c.text,
    score: cosine(embedding, c.embedding),
  }));
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, k);
}
