import { beforeEach, describe, expect, it, vi } from "vitest";

import { setRuntimeConfig } from "../../config/runtimeConfig";
import { getHealthStatus } from "../healthApi";

describe("healthApi", () => {
  beforeEach(() => {
    setRuntimeConfig({ BACKEND_BASE_URL: "https://api.example.test", FEATURE_FLAGS: {} });
    vi.restoreAllMocks();
  });

  it("fetches health build metadata", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch" as any).mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "ok",
          build_sha: "b9ef74c",
          build_time: "2026-02-11T07:12:34Z",
          environment: "production"
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      ) as any
    );

    const out = await getHealthStatus();
    expect(out.environment).toBe("production");
    expect(out.build_sha).toBe("b9ef74c");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.test/health",
      expect.objectContaining({ method: "GET" })
    );
  });
});
