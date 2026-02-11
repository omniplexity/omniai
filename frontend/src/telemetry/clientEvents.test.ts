import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setRuntimeConfig } from "../config/runtimeConfig";
import { __resetCsrfCacheForTest } from "../auth/csrf";
import { __resetClientEventsForTest, emitClientEvent } from "./clientEvents";

describe("clientEvents telemetry sink", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.restoreAllMocks();
    __resetClientEventsForTest();
    __resetCsrfCacheForTest();
    setRuntimeConfig({
      BACKEND_BASE_URL: "http://localhost:8000",
      FEATURE_FLAGS: {},
    });
    (globalThis as any).document = { cookie: "omni_csrf=testcsrf" };
  });

  afterEach(() => {
    vi.useRealTimers();
    delete (globalThis as any).document;
  });

  it("does not POST when CLIENT_EVENTS_HTTP is disabled", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    emitClientEvent({ type: "run_start", runId: "r1" });
    await vi.runAllTimersAsync();
    expect(fetchMock).toHaveBeenCalledTimes(0);
  });

  it("posts batched events when CLIENT_EVENTS_HTTP is enabled", async () => {
    setRuntimeConfig({
      BACKEND_BASE_URL: "http://localhost:8000",
      FEATURE_FLAGS: { CLIENT_EVENTS_HTTP: true } as Record<string, boolean>,
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);

    emitClientEvent({ type: "run_start", runId: "r1" });
    await vi.advanceTimersByTimeAsync(2100);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const headers = new Headers((fetchMock.mock.calls[0]?.[1] as RequestInit).headers);
    expect(headers.get("X-Client-Events-Sample-Rate")).toBe("1");
    const body = JSON.parse((fetchMock.mock.calls[0]?.[1] as RequestInit).body as string);
    expect(body.events[0].run_id).toBe("r1");
  });

  it("retries once then degrades on sink failure", async () => {
    setRuntimeConfig({
      BACKEND_BASE_URL: "http://localhost:8000",
      FEATURE_FLAGS: { CLIENT_EVENTS_HTTP: true } as Record<string, boolean>,
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("{}", { status: 503 }))
      .mockResolvedValueOnce(new Response("{}", { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);

    emitClientEvent({ type: "run_error", runId: "r1", code: "E_NETWORK" });
    await vi.advanceTimersByTimeAsync(3000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
