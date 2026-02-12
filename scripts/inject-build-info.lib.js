const URL_PATTERN = /^https?:\/\//i;

function normalizeBaseUrl(url) {
  const value = String(url ?? "").trim();
  if (!value) return "";
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function pickAllowedOverrides(input) {
  const overrides = {};
  if (!input || typeof input !== "object") return overrides;

  if (typeof input.BACKEND_BASE_URL === "string") {
    const normalized = normalizeBaseUrl(input.BACKEND_BASE_URL);
    if (normalized && !URL_PATTERN.test(normalized)) {
      throw new Error("BACKEND_BASE_URL must start with http:// or https://");
    }
    if (normalized) overrides.BACKEND_BASE_URL = normalized;
  }

  return overrides;
}

function mergeRuntimeConfig(existing, buildInfo, envOverrides, cliOverrides) {
  const safeExisting =
    existing && typeof existing === "object" && !Array.isArray(existing) ? existing : {};

  const merged = {
    ...safeExisting,
    ...(buildInfo || {}),
    ...pickAllowedOverrides(envOverrides),
    ...pickAllowedOverrides(cliOverrides),
  };

  if (typeof merged.BACKEND_BASE_URL === "string") {
    merged.BACKEND_BASE_URL = normalizeBaseUrl(merged.BACKEND_BASE_URL);
  }

  if (!merged.BACKEND_BASE_URL) {
    merged.BACKEND_BASE_URL = "";
  }

  if (!merged.FEATURE_FLAGS || typeof merged.FEATURE_FLAGS !== "object") {
    merged.FEATURE_FLAGS = {};
  }

  merged.ADAPTER_MODE = merged.ADAPTER_MODE === "mock" ? "mock" : "sse";

  return merged;
}

module.exports = {
  mergeRuntimeConfig,
  normalizeBaseUrl,
  pickAllowedOverrides,
};
