import { createStore } from "../state/store";
import type { ProviderInfo } from "./types";
import { listProviders } from "./providerApi";

export type ProviderState = {
  loading: boolean;
  providers: ProviderInfo[];
  error?: string;
  loadedAt?: number;
};

export const providerStore = createStore<ProviderState>({
  loading: false,
  providers: []
});

export async function hydrateProviders(): Promise<void> {
  if (providerStore.get().loading) return;
  providerStore.patch({ loading: true, error: undefined });

  try {
    const providers = await listProviders();
    providerStore.patch({ loading: false, providers, loadedAt: Date.now() });
  } catch (e: any) {
    providerStore.patch({
      loading: false,
      error: String(e?.message ?? e),
      providers: []
    });
  }
}
