import { endpoints } from "./endpoints";
import { ApiError, type ApiErrorCode } from "./errors";
import { fetchWithTimeout, readErrorBody, tryPaths } from "./http";
import { requestMutating, requestSession } from "./client";

export type DuckDnsStatus = {
  token_present: boolean;
  subdomain: string;
  scheduler_enabled: boolean;
  scheduler_interval_minutes: number;
  scheduler_last_run_unix: number | null;
  scheduler_last_ok_unix: number | null;
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
    const res = await requestSession(url, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    return parseOrThrow(res);
  });
}

export async function getDuckDnsLogs(limit = 200): Promise<DuckDnsLog[]> {
  return tryPaths(endpoints.opsDuckdnsLogs, async (base) => {
    const url = `${base}?limit=${encodeURIComponent(String(limit))}`;
    const res = await requestSession(url, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    const payload = await parseOrThrow(res);
    return Array.isArray(payload?.logs) ? payload.logs : [];
  });
}

export async function postDuckDnsUpdate(force: boolean): Promise<any> {
  return tryPaths(endpoints.opsDuckdnsUpdate, async (url) => {
    const res = await requestMutating(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify({ force }),
    });
    return parseOrThrow(res);
  });
}

export async function postDuckDnsTest(ip?: string): Promise<any> {
  return tryPaths(endpoints.opsDuckdnsTest, async (url) => {
    const res = await requestMutating(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      body: JSON.stringify(ip ? { ip } : {}),
    });
    return parseOrThrow(res);
  });
}
