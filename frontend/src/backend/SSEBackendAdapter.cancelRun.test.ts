import { beforeEach, describe, expect, it, vi } from "vitest";
import { SSEBackendAdapter } from "./SSEBackendAdapter";
import { setRuntimeConfig } from "../config/runtimeConfig";
import { __resetCsrfCacheForTest } from "../auth/csrf";

describe("SSEBackendAdapter.cancelRun", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    __resetCsrfCacheForTest();
    (globalThis as { document?: { cookie?: string } }).document = { cookie: "omni_csrf=t1" };
    setRuntimeConfig({ BACKEND_BASE_URL: "http://localhost:8000" });
  });

  it("posts run_id with csrf and credentials", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "cancelled" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const adapter = new SSEBackendAdapter();
    await adapter.cancelRun({ runId: "r1" });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/v1/chat/cancel");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    expect(String(init.body)).toContain("\"run_id\":\"r1\"");
  });
});
