#!/usr/bin/env node
const fs = require("fs");
const crypto = require("crypto");
const { mergeRuntimeConfig } = require("./inject-build-info.lib.js");

const args = process.argv.slice(2);
const targetPath = args[0];
if (!targetPath) {
  console.error(
    "Usage: node scripts/inject-build-info.js <runtime-config-path> [backendBaseUrl] [--backend-base-url <url>]"
  );
  process.exit(1);
}

function parseCliOverrides(cliArgs) {
  const overrides = {};
  const positionalBackend = cliArgs[1];
  if (typeof positionalBackend === "string" && !positionalBackend.startsWith("--")) {
    overrides.BACKEND_BASE_URL = positionalBackend;
  }

  for (let i = 1; i < cliArgs.length; i += 1) {
    const token = cliArgs[i];
    if (token === "--backend-base-url") {
      const value = cliArgs[i + 1];
      if (!value) {
        throw new Error("Missing value for --backend-base-url");
      }
      overrides.BACKEND_BASE_URL = value;
      i += 1;
    }
  }

  return overrides;
}

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
const envOverrides = {
  BACKEND_BASE_URL: process.env.BACKEND_BASE_URL,
};
const cliOverrides = parseCliOverrides(args);
const merged = mergeRuntimeConfig(base, {}, envOverrides, cliOverrides);

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
