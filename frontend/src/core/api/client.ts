import { getRuntimeConfig } from "../../config/runtimeConfig";
import { ApiError } from "./errors";
import { endpoints } from "./endpoints";

const CSRF_COOKIE_NAME = "omni_csrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";

let cachedCsrfToken: string | null = null;
let inFlightMetaSync: Promise<void> | null = null;

type RequestOpts = {
  baseUrl?: string;
  retryOnE2002?: boolean;
};

type BackendErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
  };
  detail?: string;
  request_id?: string;
};

function resolveBaseUrl(baseUrl?: string): string {
  return baseUrl ?? getRuntimeConfig().BACKEND_BASE_URL;
}

function normalizeUrl(pathOrUrl: string, baseUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  if (pathOrUrl.startsWith("/")) return `${baseUrl}${pathOrUrl}`;
  return `${baseUrl}/${pathOrUrl}`;
}

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const parts = document.cookie ? document.cookie.split("; ") : [];
  for (const part of parts) {
    const [k, ...rest] = part.split("=");
    if (k === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

export async function bootstrapCsrf(baseUrl?: string): Promise<string> {
  const root = resolveBaseUrl(baseUrl);
  const csrfPath = endpoints.csrfBootstrap[0] ?? "/v1/auth/csrf/bootstrap";
  const url = normalizeUrl(csrfPath, root);
  const res = await fetch(url, {
    method: "GET",
    credentials: "include",
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw await toApiError(res, "csrf_failed", "CSRF bootstrap failed");
  }

  const body = (await res.json().catch(() => ({}))) as { csrf_token?: string };
  const token = body.csrf_token ?? readCookie(CSRF_COOKIE_NAME);
  if (!token) {
    throw new ApiError("csrf_failed", "CSRF bootstrap returned no token");
  }
  cachedCsrfToken = token;
  return token;
}

export async function getCsrfToken(baseUrl?: string): Promise<string> {
  if (cachedCsrfToken) return cachedCsrfToken;
  const fromCookie = readCookie(CSRF_COOKIE_NAME);
  if (fromCookie) {
    cachedCsrfToken = fromCookie;
    return fromCookie;
  }
  return bootstrapCsrf(baseUrl);
}

export function clearCsrfTokenCache(): void {
  cachedCsrfToken = null;
}

export async function syncAuthFromMeta(baseUrl?: string): Promise<void> {
  if (inFlightMetaSync) {
    return inFlightMetaSync;
  }

  const root = resolveBaseUrl(baseUrl);
  const metaPath = endpoints.meta[0] ?? "/v1/meta";
  const url = normalizeUrl(metaPath, root);
  inFlightMetaSync = (async () => {
    try {
      await fetch(url, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
    } catch {
      // Best-effort auth-state sync; caller handles original response.
    }
  })();

  try {
    await inFlightMetaSync;
  } finally {
    inFlightMetaSync = null;
  }
}

export async function requestSession(
  pathOrUrl: string,
  init: RequestInit | undefined = {},
  opts: RequestOpts = {}
): Promise<Response> {
  const root = resolveBaseUrl(opts.baseUrl);
  const url = normalizeUrl(pathOrUrl, root);
  const req: RequestInit = {
    ...init,
    credentials: init?.credentials ?? "include",
  };
  const res = await fetch(url, req);
  if (res.status === 401) {
    await syncAuthFromMeta(root);
  }
  return res;
}

export async function requestMutating(
  pathOrUrl: string,
  init: RequestInit | undefined = {},
  opts: RequestOpts = {}
): Promise<Response> {
  const root = resolveBaseUrl(opts.baseUrl);
  const url = normalizeUrl(pathOrUrl, root);
  const retryOnE2002 = opts.retryOnE2002 ?? true;

  const token = await getCsrfToken(root);
  const headers = new Headers(init?.headers ?? {});
  headers.set(CSRF_HEADER_NAME, token);

  let res = await fetch(url, {
    ...init,
    headers,
    credentials: init?.credentials ?? "include",
  });

  if (res.status === 401) {
    await syncAuthFromMeta(root);
    return res;
  }

  if (!retryOnE2002 || res.status !== 403) {
    return res;
  }

  const code = await readBackendCode(res.clone());
  if (code !== "E2002") {
    return res;
  }

  clearCsrfTokenCache();
  const fresh = await bootstrapCsrf(root);
  const retryHeaders = new Headers(init?.headers ?? {});
  retryHeaders.set(CSRF_HEADER_NAME, fresh);
  res = await fetch(url, {
    ...init,
    headers: retryHeaders,
    credentials: init?.credentials ?? "include",
  });

  if (res.status === 401) {
    await syncAuthFromMeta(root);
  }
  return res;
}

async function readBackendCode(res: Response): Promise<string | null> {
  try {
    const json = (await res.json()) as BackendErrorEnvelope;
    return json.error?.code ?? null;
  } catch {
    return null;
  }
}

export async function toApiError(
  res: Response,
  fallbackCode: ApiError["code"] = "server_error",
  fallbackMessage?: string
): Promise<ApiError> {
  let payload: BackendErrorEnvelope | null = null;
  let bodyText = "";
  try {
    bodyText = await res.text();
    payload = bodyText ? (JSON.parse(bodyText) as BackendErrorEnvelope) : null;
  } catch {
    payload = null;
  }

  const backendCode = payload?.error?.code ?? null;
  const requestId = payload?.error?.request_id ?? payload?.request_id ?? null;
  const message =
    payload?.error?.message ??
    payload?.detail ??
    fallbackMessage ??
    `HTTP ${res.status}`;

  let code: ApiError["code"] = fallbackCode;
  if (res.status === 401) code = "unauthorized";
  else if (res.status === 403 && backendCode === "E2002") code = "csrf_failed";
  else if (res.status === 403) code = "forbidden";
  else if (res.status === 429) code = "rate_limited";
  else if (res.status >= 500) code = "server_error";

  const detail = payload ?? (bodyText || undefined);
  return new ApiError(code, message, res.status, detail, {
    backendCode,
    requestId,
  });
}

export function __resetApiClientForTest(): void {
  cachedCsrfToken = null;
  inFlightMetaSync = null;
}
