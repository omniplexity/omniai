import { createStore } from "../state/store";
import type { MetaResponse } from "./metaApi";

export type MetaState = {
  snapshot: MetaResponse | null;
  environment: string;
  effectiveFlags: Record<string, boolean>;
  showRequestIds: boolean;
};

const initialState: MetaState = {
  snapshot: null,
  environment: "unknown",
  effectiveFlags: {},
  showRequestIds: false,
};

export const metaStore = createStore<MetaState>(initialState);

function normalizeBooleanFlags(value: unknown): Record<string, boolean> {
  if (!value || typeof value !== "object") return {};
  const raw = value as Record<string, unknown>;
  const out: Record<string, boolean> = {};
  for (const [key, flag] of Object.entries(raw)) {
    if (typeof flag === "boolean") out[key] = flag;
  }
  return out;
}

export function applyMetaSnapshot(meta: MetaResponse | null | undefined): void {
  const snapshot = meta ?? null;
  const server = (snapshot as any)?.server ?? {};
  const environment = typeof server.environment === "string" ? server.environment : "unknown";
  const effectiveFlags = normalizeBooleanFlags((snapshot as any)?.flags?.effective);
  metaStore.patch({
    snapshot,
    environment,
    effectiveFlags,
  });
}

export function setRequestIdVisibility(show: boolean): void {
  metaStore.patch({ showRequestIds: show });
}

export function resetMetaState(): void {
  metaStore.set(initialState);
}
