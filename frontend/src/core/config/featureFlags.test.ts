import { beforeEach, describe, expect, it } from "vitest";
import { getFlags, setFlagsFromMeta, setFlagsFromRuntime } from "./featureFlags";

describe("feature flags precedence", () => {
  beforeEach(() => {
    setFlagsFromRuntime({ FEATURE_FLAGS: {} });
  });

  it("uses runtime workspace flag when meta is absent", () => {
    setFlagsFromRuntime({ FEATURE_FLAGS: { workspace: true } });
    setFlagsFromMeta(undefined);
    expect(getFlags().workspace).toBe(true);
  });

  it("meta effective workspace overrides runtime fallback", () => {
    setFlagsFromRuntime({ FEATURE_FLAGS: { workspace: false } });
    setFlagsFromMeta({ flags: { effective: { workspace: true } } });
    expect(getFlags().workspace).toBe(true);
  });

  it("backend effective false overrides runtime true", () => {
    setFlagsFromRuntime({ FEATURE_FLAGS: { workspace: true } });
    setFlagsFromMeta({ flags: { effective: { workspace: false } } });
    expect(getFlags().workspace).toBe(false);
  });

  it("retains backend-effective overrides across runtime rehydrate", () => {
    setFlagsFromRuntime({ FEATURE_FLAGS: { workspace: false, tools: false } });
    setFlagsFromMeta({ flags: { effective: { workspace: true, tools: true } } });
    expect(getFlags().workspace).toBe(true);
    expect(getFlags().tools).toBe(true);

    // Simulate logout/login runtime refresh followed by backend meta refresh.
    setFlagsFromRuntime({ FEATURE_FLAGS: { workspace: false, tools: false } });
    expect(getFlags().workspace).toBe(false);
    expect(getFlags().tools).toBe(false);

    setFlagsFromMeta({ flags: { effective: { workspace: true, tools: true } } });
    expect(getFlags().workspace).toBe(true);
    expect(getFlags().tools).toBe(true);
  });
});
