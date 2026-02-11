import { endpoints } from "./endpoints";
import { fetchWithTimeout, readErrorBody, tryPaths } from "./http";

let _csrfToken: string | null = null;

export function getCsrfToken(): string | null {
  return _csrfToken;
}

export function clearCsrfToken() {
  _csrfToken = null;
}

export async function ensureCsrfToken(): Promise<void> {
  if (_csrfToken) return;

  const res = await tryPaths(endpoints.csrfBootstrap, async (url) => {
    return fetchWithTimeout(url, {
      method: "GET",
      credentials: "include",
      headers: { "Accept": "application/json" },
      timeoutMs: 15000
    });
  });

  if (!res.ok) {
    const body = await readErrorBody(res);
    throw new Error(`CSRF bootstrap failed (${res.status}): ${body}`);
  }

  const headerToken = res.headers.get("x-csrf-token");
  if (headerToken) _csrfToken = headerToken;

  const text = await res.text();
  try {
    const json = JSON.parse(text);
    if (typeof json?.csrf_token === "string") _csrfToken = json.csrf_token;
    if (typeof json?.csrfToken === "string") _csrfToken = json.csrfToken;
    if (typeof json?.csrf === "string") _csrfToken = json.csrf;
    if (typeof json?.token === "string") _csrfToken = json.token;
  } catch {
    // non-JSON is fine
  }

  if (!_csrfToken) {
    throw new Error("CSRF bootstrap succeeded but no csrf token was returned");
  }
}
