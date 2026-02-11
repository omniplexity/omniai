import { beforeEach, describe, expect, it, vi } from "vitest";

import { setRuntimeConfig } from "../../config/runtimeConfig";
import { clearCsrfToken } from "../csrf";
import { getDuckDnsStatus, postDuckDnsUpdate } from "../opsDuckdnsApi";

describe("opsDuckdnsApi", () => {
  beforeEach(() => {
    setRuntimeConfig({ BACKEND_BASE_URL: "https://api.example.test", FEATURE_FLAGS: {} });
    clearCsrfToken();
    vi.restoreAllMocks();
  });

  it("fetches DuckDNS status", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch" as any).mockResolvedValue(
      new Response(
        JSON.stringify({
          token_present: true,
          subdomain: "omniplexity",
          scheduler_enabled: false,
          scheduler_interval_minutes: 5,
          scheduler_last_run_unix: null,
          scheduler_last_ok_unix: null,
          scheduler_stale: false,
          scheduler_stale_threshold_minutes: 10,
          next_scheduled_run_unix: null,
          last_update: null
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      ) as any
    );

    const out = await getDuckDnsStatus();
    expect(out.token_present).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.test/v1/ops/duckdns/status",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("posts force update with csrf", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch" as any);
    fetchMock
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ csrf_token: "csrf-1" }),
          { status: 200, headers: { "Content-Type": "application/json", "x-csrf-token": "csrf-1" } }
        ) as any
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ success: true, response: "OK" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        ) as any
      );

    const out = await postDuckDnsUpdate(true);
    expect(out.success).toBe(true);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.example.test/v1/auth/csrf/bootstrap",
      expect.objectContaining({ method: "GET" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.example.test/v1/ops/duckdns/update",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-1" })
      })
    );
  });
});
