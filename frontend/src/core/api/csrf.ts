import { endpoints } from "./endpoints";
import { fetchWithTimeout, readErrorBody } from "./http";

let _csrfToken: string | null = null;

export function getCsrfToken(): string | null {
  return _csrfToken;
}

export function clearCsrfToken() {
  _csrfToken = null;
}

export async function ensureCsrfToken(): Promise<void> {
  if (_csrfToken) return;

  for (const path of endpoints.csrfBootstrap) {
    const url = `${import.meta.env.VITE_BACKEND_BASE_URL || ""}${path}`;
    try {
      const res = await fetchWithTimeout(url, {
        method: "GET",
        credentials: "include",
        headers: { "Accept": "application/json" },
        timeoutMs: 15000
      });

      if (!res.ok) {
        const body = await readErrorBody(res);
        throw new Error(`CSRF bootstrap failed (${res.status}): ${body}`);
      }

      // Accept either:
      // - JSON: { token: "..." }
      // - Header: X-CSRF-Token: ...
      // - Cookie-only: double-submit strategy
      const headerToken = res.headers.get("x-csrf-token");
      if (headerToken) _csrfToken = headerToken;

      const text = await res.text();
      try {
        const json = JSON.parse(text);
        if (typeof json?.token === "string") _csrfToken = json.token;
      } catch {
        // non-JSON is fine
      }

      return;
    } catch {
      continue;
    }
  }
  throw new Error("All CSRF bootstrap endpoints failed");
}
