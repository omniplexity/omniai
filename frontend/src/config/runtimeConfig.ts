export type AdapterMode = "sse" | "mock";

export type RuntimeConfig = {
  BACKEND_BASE_URL: string;
  FEATURE_FLAGS?: Record<string, boolean>;
  ADAPTER_MODE?: AdapterMode;
  BUILD_INFO?: {
    build_sha?: string;
    build_timestamp?: string;
    runtime_config_hash?: string;
  };
};

const DEFAULT_CONFIG: RuntimeConfig = {
  BACKEND_BASE_URL: "",
  FEATURE_FLAGS: {},
  ADAPTER_MODE: "sse",
};

let config: RuntimeConfig | null = null;

export function mergeRuntimeConfig(
  base: Partial<RuntimeConfig>,
  patch: Partial<RuntimeConfig>
): RuntimeConfig {
  const mergedBaseUrlRaw = (patch.BACKEND_BASE_URL ?? base.BACKEND_BASE_URL ?? "").trim();
  return {
    BACKEND_BASE_URL: mergedBaseUrlRaw ? normalizeBaseUrl(mergedBaseUrlRaw) : "",
    FEATURE_FLAGS: {
      ...(base.FEATURE_FLAGS ?? {}),
      ...(patch.FEATURE_FLAGS ?? {}),
    },
    ADAPTER_MODE:
      patch.ADAPTER_MODE ??
      base.ADAPTER_MODE ??
      "sse",
    BUILD_INFO: {
      ...(base.BUILD_INFO ?? {}),
      ...(patch.BUILD_INFO ?? {}),
    },
  };
}

export function setRuntimeConfig(next: RuntimeConfig): void {
  const raw = (next.BACKEND_BASE_URL ?? "").trim();
  config = {
    ...mergeRuntimeConfig(DEFAULT_CONFIG, next),
    BACKEND_BASE_URL: raw ? normalizeBaseUrl(raw) : "",
  };
}

export function getRuntimeConfig(): RuntimeConfig {
  if (!config) throw new Error("Runtime config not set");
  return config;
}

export function normalizeBaseUrl(url: string): string {
  const trimmed = (url ?? "").trim();
  if (!trimmed) throw new Error("BACKEND_BASE_URL is empty");
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
}

export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  const res = await fetch(`./runtime-config.json?ts=${Date.now()}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Missing runtime-config.json (${res.status})`);
  const raw = (await res.json()) as Partial<RuntimeConfig> & {
    FEATURE_FLAGS?: Record<string, boolean>;
    ADAPTER_MODE?: string;
  };
  if (!raw.BACKEND_BASE_URL) {
    throw new Error("runtime-config.json missing BACKEND_BASE_URL");
  }
  return mergeRuntimeConfig(
    { ...DEFAULT_CONFIG, BACKEND_BASE_URL: normalizeBaseUrl(raw.BACKEND_BASE_URL) },
    {
      FEATURE_FLAGS: raw.FEATURE_FLAGS ?? {},
      ADAPTER_MODE: raw.ADAPTER_MODE === "mock" ? "mock" : "sse",
      BUILD_INFO: raw.BUILD_INFO ?? undefined,
    }
  );
}

export async function loadRuntimeConfigSafe(): Promise<RuntimeConfig> {
  try {
    return await loadRuntimeConfig();
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

export function __resetRuntimeConfigForTest(): void {
  config = null;
}
