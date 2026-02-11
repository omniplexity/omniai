import { beforeEach, describe, expect, it, vi } from "vitest";
import { SSEBackendAdapter } from "./SSEBackendAdapter";
import { setRuntimeConfig } from "../config/runtimeConfig";
import { __resetCsrfCacheForTest } from "../auth/csrf";

describe("SSEBackendAdapter.createRun", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    __resetCsrfCacheForTest();
    (globalThis as { document?: { cookie?: string } }).document = { cookie: "omni_csrf=t1" };
    setRuntimeConfig({ BACKEND_BASE_URL: "http://localhost:8000" });
  });

  it("parses successful run response", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: "r1", status: "running" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const adapter = new SSEBackendAdapter();
    await expect(
      adapter.createRun({
        conversationId: "c1",
        input: "hello",
        signal: new AbortController().signal,
      })
    ).resolves.toEqual({ runId: "r1", status: "running" });
  });

  it("retries once on E2002 and succeeds", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ error: { code: "E2002", message: "CSRF validation failed" } }),
          { status: 403 }
        )
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "fresh" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ run_id: "r2", status: "running" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const adapter = new SSEBackendAdapter();
    await expect(
      adapter.createRun({
        conversationId: "c1",
        input: "hello",
        signal: new AbortController().signal,
      })
    ).resolves.toEqual({ runId: "r2", status: "running" });
  });

  it("throws on malformed create-run payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ bad: true }), { status: 200 }))
    );
    const adapter = new SSEBackendAdapter();
    await expect(
      adapter.createRun({
        conversationId: "c1",
        input: "hello",
        signal: new AbortController().signal,
      })
    ).rejects.toThrow("Malformed create-run response");
  });
});
