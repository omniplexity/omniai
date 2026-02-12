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
});
