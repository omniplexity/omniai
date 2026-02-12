const CSRF_COOKIE_NAME = "omni_csrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";

let cachedCsrfToken: string | null = null;

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const parts = document.cookie ? document.cookie.split("; ") : [];
  for (const part of parts) {
    const [k, ...rest] = part.split("=");
    if (k === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

export async function bootstrapCsrf(baseUrl: string): Promise<string> {
  const res = await fetch(`${baseUrl}/v1/auth/csrf/bootstrap`, {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`CSRF bootstrap failed (${res.status})`);
  }
  const body = (await res.json()) as { csrf_token?: string };
  const token = body.csrf_token ?? readCookie(CSRF_COOKIE_NAME);
  if (!token) throw new Error("CSRF bootstrap returned no token");
  cachedCsrfToken = token;
  return token;
}

export async function getCsrfToken(baseUrl: string): Promise<string> {
  if (cachedCsrfToken) return cachedCsrfToken;
  const fromCookie = readCookie(CSRF_COOKIE_NAME);
  if (fromCookie) {
    cachedCsrfToken = fromCookie;
    return fromCookie;
  }
  return bootstrapCsrf(baseUrl);
}

export async function withCsrfHeaders(
  init: RequestInit | undefined,
  baseUrl: string
): Promise<RequestInit> {
  const token = await getCsrfToken(baseUrl);
  const headers = new Headers(init?.headers ?? {});
  headers.set(CSRF_HEADER_NAME, token);
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
  const retry = opts.retryOnE2002 ?? true;
  const req = await withCsrfHeaders(init, opts.baseUrl);
  let res = await fetch(url, req);
  if (res.status === 401) {
    await syncAuthViaMeta(opts.baseUrl);
    return res;
  }
  if (!retry || res.status !== 403) return res;

  const code = await readBackendCode(res.clone());
  if (code !== "E2002") return res;

  cachedCsrfToken = null;
  await bootstrapCsrf(opts.baseUrl);
  const retryReq = await withCsrfHeaders(init, opts.baseUrl);
  res = await fetch(url, retryReq);
  if (res.status === 401) {
    await syncAuthViaMeta(opts.baseUrl);
  }
  return res;
}

export async function fetchWithSession(
  url: string,
  init: RequestInit | undefined,
  opts: { baseUrl: string }
): Promise<Response> {
  const req: RequestInit = {
    ...init,
    credentials: init?.credentials ?? "include",
  };
  const res = await fetch(url, req);
  if (res.status === 401) {
    await syncAuthViaMeta(opts.baseUrl);
  }
  return res;
}

async function syncAuthViaMeta(baseUrl: string): Promise<void> {
  try {
    await fetch(`${baseUrl}/v1/meta`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    // Best-effort auth state sync; callers handle original response status.
  }
}

async function readBackendCode(res: Response): Promise<string | null> {
  try {
    const json = (await res.json()) as { error?: { code?: string } };
    return json?.error?.code ?? null;
  } catch {
    return null;
  }
}

export function __resetCsrfCacheForTest(): void {
  cachedCsrfToken = null;
}
