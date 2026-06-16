// AI Gateway client. Default model is openai/gpt-4o for the main agent
// loop. The Gateway resolution lets us swap providers (OpenAI primary,
// Gemini/free fallback) without changing call-sites.
import { google } from "@ai-sdk/google";
import { openai } from "@ai-sdk/openai";
import type { LanguageModel } from "ai";

export type Intent = "default" | "long_context";

function pickFromEnv(intent: Intent): string {
  const fromEnv = intent === "long_context"
    ? process.env.LONG_CONTEXT_MODEL
    : process.env.DEFAULT_MODEL;
  if (fromEnv) return fromEnv;
  return intent === "long_context"
    ? "google/gemini-2.5-flash"
    : "openai/gpt-4o";
}

export function getModel(intent: Intent = "default"): LanguageModel {
  const slug = pickFromEnv(intent);
  const [provider, model] = slug.split("/", 2);
  if (!provider || !model) {
    throw new Error(
      `Invalid model slug '${slug}'. Expected '<provider>/<model>' e.g. 'openai/gpt-4o'.`,
    );
  }
  switch (provider) {
    case "openai":
      return openai(model);
    case "google":
      return google(model);
    default:
      throw new Error(`Unknown provider '${provider}'. Add to lib/ai.ts.`);
  }
}
