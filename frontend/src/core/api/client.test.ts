import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  __resetApiClientForTest,
  requestMutating,
  requestSession,
  toApiError,
} from "./client";

describe("api client", () => {
  beforeEach(() => {
    __resetApiClientForTest();
    vi.restoreAllMocks();
    (globalThis as { document?: { cookie?: string } }).document = { cookie: "omni_csrf=cached-token" };
  });

  it("injects CSRF header for mutating request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await requestMutating("http://localhost:8000/v1/chat", { method: "POST" }, { baseUrl: "http://localhost:8000" });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = new Headers(init?.headers);
    expect(headers.get("X-CSRF-Token")).toBe("cached-token");
  });

  it("retries once on E2002 after csrf bootstrap", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "E2002" } }), { status: 403 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "fresh-token" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const res = await requestMutating(
      "http://localhost:8000/v1/chat",
      { method: "POST" },
      { baseUrl: "http://localhost:8000", retryOnE2002: true }
    );
    expect(res.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("fails deterministically when E2002 occurs twice", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "E2002" } }), { status: 403 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "fresh-token" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "E2002" } }), { status: 403 }));
    vi.stubGlobal("fetch", fetchMock);

    const res = await requestMutating(
      "http://localhost:8000/v1/chat",
      { method: "POST" },
      { baseUrl: "http://localhost:8000", retryOnE2002: true }
    );

    expect(res.status).toBe(403);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not refresh CSRF on E2003 or E2004", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "E2003" } }), { status: 403 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: "E2004" } }), { status: 403 }));
    vi.stubGlobal("fetch", fetchMock);

    const resA = await requestMutating(
      "http://localhost:8000/v1/chat",
      { method: "POST" },
      { baseUrl: "http://localhost:8000", retryOnE2002: true }
    );
    const resB = await requestMutating(
      "http://localhost:8000/v1/chat",
      { method: "POST" },
      { baseUrl: "http://localhost:8000", retryOnE2002: true }
    );

    expect(resA.status).toBe(403);
    expect(resB.status).toBe(403);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("syncs auth with /v1/meta on 401 session request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("unauthorized", { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ auth: { authenticated: false } }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const res = await requestSession(
      "http://localhost:8000/v1/conversations",
      { method: "GET" },
      { baseUrl: "http://localhost:8000" }
    );

    expect(res.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://localhost:8000/v1/meta");
  });

  it("deduplicates concurrent 401 meta sync calls", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("unauthorized", { status: 401 }))
      .mockResolvedValueOnce(new Response("unauthorized", { status: 401 }))
      .mockImplementationOnce(async () => {
        await new Promise((resolve) => setTimeout(resolve, 5));
        return new Response(JSON.stringify({ auth: { authenticated: false } }), { status: 200 });
      });
    vi.stubGlobal("fetch", fetchMock);

    const [a, b] = await Promise.all([
      requestSession("http://localhost:8000/v1/conversations", { method: "GET" }, { baseUrl: "http://localhost:8000" }),
      requestSession("http://localhost:8000/v1/conversations", { method: "GET" }, { baseUrl: "http://localhost:8000" }),
    ]);

    expect(a.status).toBe(401);
    expect(b.status).toBe(401);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls.filter((call) => call[0] === "http://localhost:8000/v1/meta")).toHaveLength(1);
  });

  it("maps backend code and request id in ApiError", async () => {
    const res = new Response(
      JSON.stringify({ error: { code: "E2004", message: "Origin blocked", request_id: "req-123" } }),
      { status: 403 }
    );

    const err = await toApiError(res, "server_error");
    expect(err.code).toBe("forbidden");
    expect(err.backendCode).toBe("E2004");
    expect(err.requestId).toBe("req-123");
  });
});
