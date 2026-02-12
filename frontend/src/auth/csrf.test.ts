import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  __resetCsrfCacheForTest,
  bootstrapCsrf,
  fetchWithSession,
  fetchWithCsrf,
  getCsrfToken,
  readCookie,
} from "./csrf";

describe("csrf helpers", () => {
  beforeEach(() => {
    __resetCsrfCacheForTest();
    vi.restoreAllMocks();
    (globalThis as { document?: { cookie?: string } }).document = { cookie: "" };
    Object.defineProperty((globalThis as { document: { cookie: string } }).document, "cookie", {
      configurable: true,
      writable: true,
      value: "",
    });
  });

  it("reads cookie by name", () => {
    (globalThis as { document: { cookie: string } }).document.cookie = "omni_csrf=test-token";
    expect(readCookie("omni_csrf")).toBe("test-token");
  });

  it("bootstraps csrf token from endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ csrf_token: "boot-token" }), { status: 200 }))
    );
    await expect(bootstrapCsrf("http://localhost:8000")).resolves.toBe("boot-token");
  });

  it("retries once on E2002", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "boot-token" }), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ error: { code: "E2002", message: "CSRF validation failed" } }),
          { status: 403 }
        )
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "boot-token-2" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    vi.stubGlobal("fetch", fetchMock);

    const res = await fetchWithCsrf(
      "http://localhost:8000/v1/chat",
      { method: "POST" },
      { baseUrl: "http://localhost:8000", retryOnE2002: true }
    );
    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("uses cached token on subsequent calls", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ csrf_token: "cache-token" }), { status: 200 }))
    );
    await expect(getCsrfToken("http://localhost:8000")).resolves.toBe("cache-token");
    await expect(getCsrfToken("http://localhost:8000")).resolves.toBe("cache-token");
  });

  it("syncs auth via /v1/meta on unauthorized session fetch", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("unauthorized", { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ auth: { authenticated: false } }), { status: 200 }));

    vi.stubGlobal("fetch", fetchMock);

    const res = await fetchWithSession(
      "http://localhost:8000/v1/conversations",
      { method: "GET" },
      { baseUrl: "http://localhost:8000" }
    );

    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/v1/meta");
  });
});
