import { useEffect, useMemo, useState } from "preact/hooks";
import { providerStore, hydrateProviders } from "../core/providers/providerStore";
import { uiPrefsStore, setPrefs, resetPrefs } from "../core/prefs/uiPrefsStore";
import type { ProviderInfo, ModelInfo } from "../core/providers/types";
import { Banner } from "./Banner";

function useStore<T>(store: { get: () => T; subscribe: (fn: () => void) => () => void }) {
  const [v, setV] = useState(store.get());
  useEffect(() => store.subscribe(() => setV(store.get())), []);
  return v;
}

function findProvider(providers: ProviderInfo[], id: string | null): ProviderInfo | null {
  if (!providers.length) return null;
  if (!id) return providers[0] ?? null;
  return providers.find((p) => p.id === id) ?? null;
}

function findModel(provider: ProviderInfo | null, id: string | null): ModelInfo | null {
  if (!provider) return null;
  if (!provider.models.length) return null;
  if (!id) return provider.models[0] ?? null;
  return provider.models.find((m) => m.id === id) ?? null;
}

export function ModelSettingsForm(props: { compact?: boolean }) {
  const prefs = useStore(uiPrefsStore);
  const provState = useStore(providerStore);

  useEffect(() => {
    void hydrateProviders();
  }, []);

  const provider = useMemo(
    () => findProvider(provState.providers, prefs.providerId),
    [provState.providers, prefs.providerId]
  );

  const models = provider?.models ?? [];
  const model = useMemo(
    () => findModel(provider, prefs.modelId),
    [provider, prefs.modelId]
  );

  // Ensure prefs remain valid after providers load / change.
  useEffect(() => {
    if (!provState.providers.length) return;

    const p = provider ?? provState.providers[0];
    const m = p?.models?.[0] ?? null;

    // If current selection doesn't exist, normalize to first available.
    const providerValid = prefs.providerId ? provState.providers.some((x) => x.id === prefs.providerId) : true;
    const modelValid =
      !prefs.modelId ? true :
      Boolean(p?.models?.some((x) => x.id === prefs.modelId));

    if (!providerValid) setPrefs({ providerId: p?.id ?? null });
    if (!modelValid) setPrefs({ modelId: m?.id ?? null });
  }, [provState.providers.length]);

  return (
    <div class={props.compact ? "settingsForm compact" : "settingsForm"}>
      <div class="settingsHeader">
        <div>
          <div class="settingsTitle">Model & chat settings</div>
          <div class="muted" style="font-size:12px;">
            Preferences are stored locally only (no chat content).
          </div>
        </div>
        <div class="row">
          <button class="btn" onClick={() => void hydrateProviders()} disabled={provState.loading}>
            {provState.loading ? "Loading…" : "Reload"}
          </button>
          <button class="btn" onClick={() => resetPrefs()}>
            Defaults
          </button>
        </div>
      </div>

      {provState.error ? <Banner kind="error" text={`Providers unavailable: ${provState.error}`} /> : null}

      <div class="grid2">
        <div>
          <label class="label">Provider</label>
          {provState.providers.length ? (
            <select
              class="select"
              value={prefs.providerId ?? ""}
              onChange={(e) => {
                const id = (e.target as any).value || null;
                // If provider changes, reset model selection (so it stays valid).
                setPrefs({ providerId: id, modelId: null });
              }}
            >
              {/* empty => auto */}
              <option value="">Auto</option>
              {provState.providers.map((p) => (
                <option value={p.id}>{p.name}</option>
              ))}
            </select>
          ) : (
            <input
              class="input"
              placeholder="Auto"
              value={prefs.providerId ?? ""}
              onInput={(e) => setPrefs({ providerId: (e.target as any).value || null })}
            />
          )}
        </div>

        <div>
          <label class="label">Model</label>
          {models.length ? (
            <select
              class="select"
              value={prefs.modelId ?? ""}
              onChange={(e) => setPrefs({ modelId: (e.target as any).value || null })}
            >
              <option value="">Auto</option>
              {models.map((m) => (
                <option value={m.id}>{m.name}</option>
              ))}
            </select>
          ) : (
            <input
              class="input"
              placeholder={model?.name ?? "Auto"}
              value={prefs.modelId ?? ""}
              onInput={(e) => setPrefs({ modelId: (e.target as any).value || null })}
            />
          )}
        </div>
      </div>

      <div class="grid3">
        <div>
          <label class="label">Temperature</label>
          <input
            class="input"
            type="number"
            min="0"
            max="2"
            step="0.05"
            value={prefs.temperature}
            onInput={(e) => setPrefs({ temperature: Number((e.target as any).value) })}
          />
        </div>

        <div>
          <label class="label">Top P</label>
          <input
            class="input"
            type="number"
            min="0"
            max="1"
            step="0.05"
            value={prefs.topP}
            onInput={(e) => setPrefs({ topP: Number((e.target as any).value) })}
          />
        </div>

        <div>
          <label class="label">Max tokens</label>
          <input
            class="input"
            type="number"
            min="1"
            max="8192"
            step="64"
            value={prefs.maxTokens}
            onInput={(e) => setPrefs({ maxTokens: Number((e.target as any).value) })}
          />
        </div>
      </div>

      <div class="muted" style="font-size:12px;margin-top:10px;">
        Current: {prefs.providerId ?? "Auto"} / {prefs.modelId ?? "Auto"}
      </div>
    </div>
  );
}
