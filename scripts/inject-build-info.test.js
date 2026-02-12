const test = require("node:test");
const assert = require("node:assert/strict");

const { mergeRuntimeConfig } = require("./inject-build-info.lib.js");

test("cli backend override wins over existing and env", () => {
  const existing = {
    BACKEND_BASE_URL: "https://old.example.com",
    FEATURE_FLAGS: { memoryPanel: false },
    ADAPTER_MODE: "sse",
  };
  const envOverrides = { BACKEND_BASE_URL: "https://env.example.com" };
  const cliOverrides = { BACKEND_BASE_URL: "http://127.0.0.1:8000/" };

  const merged = mergeRuntimeConfig(existing, {}, envOverrides, cliOverrides);
  assert.equal(merged.BACKEND_BASE_URL, "http://127.0.0.1:8000");
});

test("invalid backend override protocol is rejected", () => {
  const existing = { BACKEND_BASE_URL: "https://old.example.com" };
  assert.throws(
    () => mergeRuntimeConfig(existing, {}, {}, { BACKEND_BASE_URL: "ftp://invalid.example.com" }),
    /BACKEND_BASE_URL must start with http:\/\/ or https:\/\//
  );
});
