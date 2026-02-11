import type { ChatApiAdapter } from "./ChatApiAdapter";
import { SSEBackendAdapter } from "./SSEBackendAdapter";
import { PlaceholderAdapter } from "./PlaceholderAdapter";
import { getRuntimeConfig } from "../config/runtimeConfig";

export function createChatAdapter(): ChatApiAdapter {
  const cfg = getRuntimeConfig();
  if (cfg.ADAPTER_MODE === "mock") return new PlaceholderAdapter();
  return new SSEBackendAdapter();
}
