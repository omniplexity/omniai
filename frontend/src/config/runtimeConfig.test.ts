import { describe, expect, it } from "vitest";
import { mergeRuntimeConfig } from "./runtimeConfig";

describe("runtimeConfig mergeRuntimeConfig", () => {
  it("preserves routing fields while merging build info additively", () => {
    const merged = mergeRuntimeConfig(
      {
        BACKEND_BASE_URL: "https://example.com",
        FEATURE_FLAGS: { A: true, B: false },
        ADAPTER_MODE: "mock",
      },
      {
        BUILD_INFO: {
          build_sha: "abc",
        },
      }
    );

    expect(merged.BACKEND_BASE_URL).toBe("https://example.com");
    expect(merged.ADAPTER_MODE).toBe("mock");
    expect(merged.FEATURE_FLAGS).toEqual({ A: true, B: false });
    expect(merged.BUILD_INFO?.build_sha).toBe("abc");
  });

  it("overrides base values when patch provides them", () => {
    const merged = mergeRuntimeConfig(
      {
        BACKEND_BASE_URL: "https://old.example.com",
        FEATURE_FLAGS: { A: true },
        ADAPTER_MODE: "sse",
      },
      {
        BACKEND_BASE_URL: "https://new.example.com",
        FEATURE_FLAGS: { B: true },
        ADAPTER_MODE: "mock",
      }
    );
    expect(merged.BACKEND_BASE_URL).toBe("https://new.example.com");
    expect(merged.ADAPTER_MODE).toBe("mock");
    expect(merged.FEATURE_FLAGS).toEqual({ A: true, B: true });
  });
});

