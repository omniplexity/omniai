import { beforeEach, describe, expect, it } from "vitest";

import { bootstrapApp } from "./bootstrap";
import { __resetRuntimeConfigForTest } from "../config/runtimeConfig";

describe("bootstrapApp", () => {
  beforeEach(() => {
    __resetRuntimeConfigForTest();
  });

  it("loads runtime config and meta successfully", async () => {
    (globalThis as any).fetch = async (url: string) => {
      if (url.includes("runtime-config.json")) {
        return new Response(JSON.stringify({ BACKEND_BASE_URL: "https://api.example.test" }), { status: 200 });
      }
      if (url === "https://api.example.test/v1/meta") {
        return new Response(JSON.stringify({ meta_version: 1, auth: { authenticated: false } }), { status: 200 });
      }
      return new Response("Not Found", { status: 404 });
    };

    const boot = await bootstrapApp();
    expect(boot.metaLoaded).toBe(true);
    expect(boot.runtimeConfig.BACKEND_BASE_URL).toBe("https://api.example.test");
    expect(boot.meta?.meta_version).toBe(1);
    expect(boot.bootError).toBeUndefined();
  });

  it("returns persistent boot error when backend meta is unreachable", async () => {
    (globalThis as any).fetch = async (url: string) => {
      if (url.includes("runtime-config.json")) {
        return new Response(JSON.stringify({ BACKEND_BASE_URL: "https://api.example.test" }), { status: 200 });
      }
      throw new Error("connection refused");
    };

    const boot = await bootstrapApp();
    expect(boot.metaLoaded).toBe(false);
    expect(boot.runtimeConfig.BACKEND_BASE_URL).toBe("https://api.example.test");
    expect(boot.bootError).toContain("Backend unavailable");
  });
});
