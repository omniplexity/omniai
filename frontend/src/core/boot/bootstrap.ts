import { getMeta } from "../meta/metaApi";
import type { MetaResponse } from "../meta/metaApi";
import { loadRuntimeConfigSafe, setRuntimeConfig, type RuntimeConfig } from "../config/runtimeConfig";

export type BootResult = {
  runtimeConfig: RuntimeConfig;
  metaLoaded: boolean;
  meta?: MetaResponse;
  bootError?: string;
};

function errMessage(err: unknown): string {
  const msg = String((err as any)?.message ?? err ?? "unknown error");
  return msg.trim() || "unknown error";
}

export async function bootstrapApp(): Promise<BootResult> {
  const runtimeConfig = await loadRuntimeConfigSafe();
  setRuntimeConfig(runtimeConfig);

  try {
    const meta = await getMeta();
    return { runtimeConfig, metaLoaded: true, meta };
  } catch (err) {
    return {
      runtimeConfig,
      metaLoaded: false,
      bootError: `Backend unavailable: ${errMessage(err)}`
    };
  }
}
