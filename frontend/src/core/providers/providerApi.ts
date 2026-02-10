import { endpoints } from "../api/endpoints";
import { fetchWithTimeout, tryPaths } from "../api/http";
import type { ProviderInfo, ModelInfo } from "./types";

// Flexible normalization: supports a variety of backend responses without requiring changes.
function normStr(x: any, fallback: string) {
  return typeof x === "string" && x.trim() ? x.trim() : fallback;
}

function normalizeModel(x: any): ModelInfo | null {
  const id = normStr(x?.id ?? x?.model_id ?? x?.name, "");
  const name = normStr(x?.name ?? x?.display_name ?? x?.id, id);
  if (!id) return null;

  const ctx = x?.context_length ?? x?.contextLength ?? x?.ctx_len ?? x?.n_ctx;
  const contextLength = typeof ctx === "number" ? ctx : (typeof ctx === "string" ? Number(ctx) : undefined);

  return { id, name, contextLength };
}

function normalizeProvider(x: any): ProviderInfo | null {
  const id = normStr(x?.id ?? x?.provider_id ?? x?.name, "");
  const name = normStr(x?.name ?? x?.display_name ?? x?.id, id);
  if (!id) return null;

  const modelsRaw = x?.models ?? x?.model_list ?? x?.items ?? [];
  const models = Array.isArray(modelsRaw)
    ? modelsRaw.map(normalizeModel).filter(Boolean) as ModelInfo[]
    : [];

  return { id, name, models };
}

function wrapFlatModels(models: ModelInfo[]): ProviderInfo[] {
  // If backend only returns models, expose as a single "auto" provider bucket
  return [{ id: "auto", name: "Auto", models }];
}

export async function listProviders(): Promise<ProviderInfo[]> {
  // Try /providers first
  try {
    const data = await tryPaths(endpoints.providers, async (url) => {
      const res = await fetchWithTimeout(url, {
        method: "GET",
        credentials: "include",
        headers: { "Accept": "application/json" },
        timeoutMs: 15000
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    });

    const providersRaw =
      Array.isArray(data) ? data :
      Array.isArray((data as any)?.providers) ? (data as any).providers :
      Array.isArray((data as any)?.items) ? (data as any).items :
      null;

    if (providersRaw) {
      const providers = providersRaw.map(normalizeProvider).filter(Boolean) as ProviderInfo[];
      if (providers.length) return providers;
    }

    // Maybe the providers endpoint returns {models:[...]} only
    const modelsRaw = (data as any)?.models;
    if (Array.isArray(modelsRaw)) {
      const models = modelsRaw.map(normalizeModel).filter(Boolean) as ModelInfo[];
      return wrapFlatModels(models);
    }
  } catch {
    // fallthrough to /models
  }

  // Fallback: /models
  const modelData = await tryPaths(endpoints.models, async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "GET",
      credentials: "include",
      headers: { "Accept": "application/json" },
      timeoutMs: 15000
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  });

  const modelsRaw =
    Array.isArray(modelData) ? modelData :
    Array.isArray((modelData as any)?.models) ? (modelData as any).models :
    Array.isArray((modelData as any)?.items) ? (modelData as any).items :
    [];

  const models = (Array.isArray(modelsRaw) ? modelsRaw : [])
    .map(normalizeModel)
    .filter(Boolean) as ModelInfo[];

  return wrapFlatModels(models);
}
