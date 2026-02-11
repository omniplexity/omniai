#!/usr/bin/env node
const fs = require("fs");
const crypto = require("crypto");

const targetPath = process.argv[2];
if (!targetPath) {
  console.error("Usage: node scripts/inject-build-info.js <runtime-config-path> [backendBaseUrl]");
  process.exit(1);
}

const backendBaseUrlArg = process.argv[3];

function readJson(path) {
  if (!fs.existsSync(path)) return {};
  try {
    return JSON.parse(fs.readFileSync(path, "utf8"));
  } catch (err) {
    console.error(`Invalid JSON at ${path}: ${err.message}`);
    process.exit(1);
  }
}

const base = readJson(targetPath);
const merged = {
  BACKEND_BASE_URL:
    backendBaseUrlArg !== undefined
      ? backendBaseUrlArg
      : typeof base.BACKEND_BASE_URL === "string"
        ? base.BACKEND_BASE_URL
        : "",
  FEATURE_FLAGS:
    base.FEATURE_FLAGS && typeof base.FEATURE_FLAGS === "object"
      ? base.FEATURE_FLAGS
      : {},
  ADAPTER_MODE: base.ADAPTER_MODE === "mock" ? "mock" : "sse",
  ...base,
};

const configHash = crypto
  .createHash("sha256")
  .update(JSON.stringify({ ...merged, BUILD_INFO: undefined }))
  .digest("hex")
  .slice(0, 12);

merged.BUILD_INFO = {
  ...(merged.BUILD_INFO || {}),
  build_sha: process.env.GITHUB_SHA || "local-dev",
  build_timestamp: new Date().toISOString(),
  runtime_config_hash: configHash,
};

fs.writeFileSync(targetPath, `${JSON.stringify(merged, null, 2)}\n`, "utf8");
console.log(`Injected BUILD_INFO into ${targetPath}`);

