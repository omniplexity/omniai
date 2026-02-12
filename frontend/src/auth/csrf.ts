import {
  __resetApiClientForTest,
  bootstrapCsrf,
  clearCsrfTokenCache,
  getCsrfToken,
  readCookie,
  requestMutating,
  requestSession,
} from "../core/api/client";

export { bootstrapCsrf, getCsrfToken, readCookie };

export async function withCsrfHeaders(
  init: RequestInit | undefined,
  baseUrl: string
): Promise<RequestInit> {
  const token = await getCsrfToken(baseUrl);
  const headers = new Headers(init?.headers ?? {});
  headers.set("X-CSRF-Token", token);
  return {
    ...init,
    headers,
    credentials: "include",
  };
}

export async function fetchWithCsrf(
  url: string,
  init: RequestInit | undefined,
  opts: { baseUrl: string; retryOnE2002?: boolean }
): Promise<Response> {
  return requestMutating(url, init, opts);
}

export async function fetchWithSession(
  url: string,
  init: RequestInit | undefined,
  opts: { baseUrl: string }
): Promise<Response> {
  return requestSession(url, init, opts);
}

export function __resetCsrfCacheForTest(): void {
  clearCsrfTokenCache();
  __resetApiClientForTest();
}
