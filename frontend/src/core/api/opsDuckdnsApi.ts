import { ensureCsrfToken, getCsrfToken } from "./csrf";
import { endpoints } from "./endpoints";
import { ApiError, type ApiErrorCode } from "./errors";
import { fetchWithTimeout, readErrorBody, tryPaths } from "./http";

export type DuckDnsStatus = {
  token_present: boolean;
  subdomain: string;
  scheduler_enabled: boolean;
  scheduler_interval_minutes: number;
  scheduler_last_run_unix: number | null;
  scheduler_stale: boolean;
  scheduler_stale_threshold_minutes: number;
  next_scheduled_run_unix: number | null;
  last_update: null | {
    id: string;
    created_at: string | null;
    ip: string | null;
    response: string | null;
    success: boolean;
    error_code: string | null;
    error_message: string | null;
    latency_ms: number | null;
    source: string;
  };
};

export type DuckDnsLog = {
  id: string;
  created_at: string | null;
  subdomain: string;
  ip: string | null;
  response: string | null;
  success: boolean;
  error_code: string | null;
  error_message: string | null;
  latency_ms: number | null;
  actor_user_id: string | null;
  source: string;
};

async function parseOrThrow(res: Response): Promise<any> {
  if (!res.ok) {
    const bodyText = await readErrorBody(res);
    let code: ApiErrorCode = "server_error";
    let message = `Request failed (${res.status})`;
    try {
      const payload = JSON.parse(bodyText);
      if (typeof payload?.error?.code === "string") {
        const raw = String(payload.error.code).toLowerCase();
        if (raw === "unauthorized") code = "unauthorized";
        else if (raw === "forbidden") code = "forbidden";
        else if (raw === "csrf_failed") code = "csrf_failed";
        else if (raw === "rate_limited") code = "rate_limited";
        else code = "server_error";
      }
      if (typeof payload?.error?.message === "string") message = payload.error.message;
    } catch {
      // ignore non-JSON bodies
    }
    throw new ApiError(code, message, res.status, bodyText);
  }
  return await res.json();
}

export async function getDuckDnsStatus(): Promise<DuckDnsStatus> {
  return tryPaths(endpoints.opsDuckdnsStatus, async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
      timeoutMs: 15000
    });
    return parseOrThrow(res);
  });
}

export async function getDuckDnsLogs(limit = 200): Promise<DuckDnsLog[]> {
  return tryPaths(endpoints.opsDuckdnsLogs, async (base) => {
    const url = `${base}?limit=${encodeURIComponent(String(limit))}`;
    const res = await fetchWithTimeout(url, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
      timeoutMs: 15000
    });
    const payload = await parseOrThrow(res);
    return Array.isArray(payload?.logs) ? payload.logs : [];
  });
}

export async function postDuckDnsUpdate(force: boolean): Promise<any> {
  await ensureCsrfToken();
  return tryPaths(endpoints.opsDuckdnsUpdate, async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRF-Token": getCsrfToken() ?? ""
      },
      body: JSON.stringify({ force }),
      timeoutMs: 30000
    });
    return parseOrThrow(res);
  });
}

export async function postDuckDnsTest(ip?: string): Promise<any> {
  await ensureCsrfToken();
  return tryPaths(endpoints.opsDuckdnsTest, async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRF-Token": getCsrfToken() ?? ""
      },
      body: JSON.stringify(ip ? { ip } : {}),
      timeoutMs: 30000
    });
    return parseOrThrow(res);
  });
}
