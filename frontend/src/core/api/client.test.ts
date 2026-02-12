import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  __resetApiClientForTest,
  requestMutating,
  requestSession,
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
});

