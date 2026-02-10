export type RuntimeConfig = {
  BACKEND_BASE_URL: string;
  FEATURE_FLAGS?: Record<string, boolean>;
};

let _cfg: RuntimeConfig | null = null;

export function setRuntimeConfig(cfg: RuntimeConfig) {
  _cfg = {
    ...cfg,
    BACKEND_BASE_URL: normalizeBaseUrl(cfg.BACKEND_BASE_URL)
  };
}

export function getRuntimeConfig(): RuntimeConfig {
  if (!_cfg) throw new Error("Runtime config not set");
  return _cfg;
}

function normalizeBaseUrl(u: string): string {
  const trimmed = (u ?? "").trim();
  if (!trimmed) throw new Error("BACKEND_BASE_URL is empty");
  // remove trailing slash
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
}

export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  const url = `./runtime-config.json?ts=${Date.now()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Missing runtime-config.json (${res.status})`);
  const cfg = (await res.json()) as RuntimeConfig;
  if (!cfg?.BACKEND_BASE_URL) throw new Error("runtime-config.json missing BACKEND_BASE_URL");
  return {
    BACKEND_BASE_URL: cfg.BACKEND_BASE_URL,
    FEATURE_FLAGS: cfg.FEATURE_FLAGS ?? {}
  };
}
