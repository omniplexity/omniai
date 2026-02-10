import { getRuntimeConfig } from "../config/runtimeConfig";
import { ApiError } from "./errors";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export async function fetchWithTimeout(
  url: string,
  init: RequestInit & { timeoutMs?: number } = {}
): Promise<Response> {
  const timeoutMs = init.timeoutMs ?? 30000;

  const ctrl = new AbortController();
  const signal = init.signal ?? ctrl.signal;

  let t: any = null;
  if (timeoutMs > 0) {
    t = setTimeout(() => ctrl.abort(), timeoutMs);
  }

  try {
    const res = await fetch(url, { ...init, signal });
    return res;
  } catch (e: any) {
    if (e?.name === "AbortError") throw new ApiError("timeout", "Request timed out");
    throw new ApiError("network_error", "Network error", undefined, String(e?.message ?? e));
  } finally {
    if (t) clearTimeout(t);
  }
}

export async function tryPaths<T>(
  paths: string[],
  fn: (absoluteUrl: string) => Promise<T>
): Promise<T> {
  const { BACKEND_BASE_URL } = getRuntimeConfig();
  let lastErr: unknown;

  for (const path of paths) {
    try {
      return await fn(`${BACKEND_BASE_URL}${path}`);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr ?? new ApiError("unknown", "All endpoint paths failed");
}

export async function readErrorBody(res: Response): Promise<string> {
  try {
    return await res.text();
  } catch {
    return "";
  }
}

export function classifyHttpError(res: Response): ApiError {
  if (res.status === 401) return new ApiError("unauthorized", "Unauthorized", 401);
  if (res.status === 403) return new ApiError("forbidden", "Forbidden", 403);
  if (res.status === 429) return new ApiError("rate_limited", "Rate limited", 429);
  if (res.status >= 500) return new ApiError("server_error", `Server error (${res.status})`, res.status);
  return new ApiError("unknown", `HTTP ${res.status}`, res.status);
}
