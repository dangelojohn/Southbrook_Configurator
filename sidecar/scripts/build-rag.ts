/**
 * pnpm build:rag <tenant>
 *
 * Fetches /southbrook/os.json (or the tenant's equivalent) from the live
 * Odoo, chunks each section's markdown body, embeds every chunk with
 * text-embedding-3-small, and writes data/index/<tenant>/index.json.
 *
 * The sidecar reads that index at runtime to do RAG retrieval.
 */
import { openai } from "@ai-sdk/openai";
import { embedMany } from "ai";
import { writeFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { createHash } from "node:crypto";

import { getOdooUrl, isKnownTenant } from "../lib/tenants";
import type { OsBundle, OsSectionRaw, RagChunk, RagIndex } from "../lib/types";

const TARGET_TOKENS = 600;
const OVERLAP_TOKENS = 100;
// 4 chars ≈ 1 token is a coarse but stable English approximation that
// avoids pulling in a tokenizer dependency. The agent loop only needs
// roughly-bounded chunks for retrieval; precise tokenization happens
// inside the embedding model.
const CHARS_PER_TOKEN = 4;

function chunkSection(section: OsSectionRaw): RagChunk[] {
  const body = section.body || "";
  const targetChars = TARGET_TOKENS * CHARS_PER_TOKEN;
  const overlapChars = OVERLAP_TOKENS * CHARS_PER_TOKEN;
  if (body.length <= targetChars) {
    return [{
      slug: section.slug,
      name: section.name,
      ord: 0,
      text: body,
      embedding: [], // filled in by embedAll
    }];
  }
  const chunks: RagChunk[] = [];
  let cursor = 0;
  let ord = 0;
  while (cursor < body.length) {
    const end = Math.min(cursor + targetChars, body.length);
    chunks.push({
      slug: section.slug,
      name: section.name,
      ord,
      text: body.slice(cursor, end),
      embedding: [],
    });
    if (end >= body.length) break;
    cursor = end - overlapChars;
    ord += 1;
  }
  return chunks;
}

async function embedAll(chunks: RagChunk[]): Promise<RagChunk[]> {
  if (chunks.length === 0) return chunks;
  const { embeddings } = await embedMany({
    model: openai.embedding("text-embedding-3-small"),
    values: chunks.map((c) => c.text),
  });
  if (embeddings.length !== chunks.length) {
    throw new Error(
      `Embedding count mismatch: got ${embeddings.length}, expected ${chunks.length}.`,
    );
  }
  return chunks.map((c, i) => {
    const vec = embeddings[i];
    if (vec.length !== 1536) {
      throw new Error(
        `Embedding ${i} has ${vec.length} dims, expected 1536 (text-embedding-3-small).`,
      );
    }
    return { ...c, embedding: vec };
  });
}

async function main(): Promise<void> {
  const tenant = process.argv[2];
  if (!tenant) {
    console.error("Usage: pnpm build:rag <tenant>");
    process.exit(1);
  }
  if (!isKnownTenant(tenant)) {
    console.error(
      `Unknown tenant '${tenant}'. Add it to TENANT_REGISTRY.`,
    );
    process.exit(1);
  }

  const url = `${getOdooUrl(tenant)}/southbrook/os.json`;
  console.log(`Fetching ${url}…`);
  const resp = await fetch(url);
  if (!resp.ok) {
    console.error(`Fetch failed: HTTP ${resp.status}`);
    process.exit(1);
  }
  const bundle = (await resp.json()) as OsBundle;
  console.log(
    `Fetched ${bundle.sections.length} sections (publication ${bundle.publication.calendar_key} ${bundle.publication.build_hash})`,
  );

  const allChunks: RagChunk[] = bundle.sections.flatMap(chunkSection);
  console.log(`Chunked into ${allChunks.length} chunks; embedding…`);

  const embedded = await embedAll(allChunks);
  const bodyConcat = embedded.map((c) => c.text).join("|");
  const buildHash = createHash("sha256").update(bodyConcat).digest("hex").slice(0, 16);

  const index: RagIndex = {
    tenant,
    build_hash: buildHash,
    built_at: new Date().toISOString(),
    chunks: embedded,
  };

  const outDir = join(process.cwd(), "data", "index", tenant);
  await mkdir(outDir, { recursive: true });
  const outPath = join(outDir, "index.json");
  await writeFile(outPath, JSON.stringify(index));
  console.log(`Wrote ${outPath} — ${embedded.length} chunks, build_hash ${buildHash}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
