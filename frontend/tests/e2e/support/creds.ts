import { test } from "@playwright/test";

export type E2ECreds = { username: string; password: string };

function parseHost(value: string | undefined): string | null {
  if (!value) return null;
  try {
    return new URL(value).host.toLowerCase();
  } catch {
    return null;
  }
}

function assertHostAlignment(): void {
  const frontendHost = parseHost(process.env.FRONTEND_URL ?? "http://127.0.0.1:5173");
  const backendHost = parseHost(process.env.E2E_BASE_URL ?? process.env.BACKEND_BASE_URL ?? "http://127.0.0.1:8000");
  if (!frontendHost || !backendHost) {
    throw new Error("Invalid FRONTEND_URL or E2E_BASE_URL/BACKEND_BASE_URL; must be absolute URLs.");
  }
  const frontendName = frontendHost.split(":")[0];
  const backendName = backendHost.split(":")[0];
  if (frontendName !== backendName) {
    throw new Error(
      `Host mismatch: FRONTEND_URL=${process.env.FRONTEND_URL} and E2E_BASE_URL/BACKEND_BASE_URL=${process.env.E2E_BASE_URL ?? process.env.BACKEND_BASE_URL}. Use matching hosts (prefer 127.0.0.1).`
    );
  }
}

export function resolveE2ECredsOrSkip(): E2ECreds {
  const env = process.env.ENVIRONMENT;
  const seed = process.env.E2E_SEED_USER === "1";
  if (env === "test" && seed) {
    assertHostAlignment();
  }

  if (env === "test" && seed) {
    return {
      username: process.env.E2E_USERNAME ?? "e2e@example.com",
      password: process.env.E2E_PASSWORD ?? "e2e-password",
    };
  }

  const username = process.env.E2E_USERNAME;
  const password = process.env.E2E_PASSWORD;
  if (!username || !password) {
    test.skip(true, "Missing E2E_USERNAME/E2E_PASSWORD (and not in deterministic test seed mode)");
  }
  return { username: username!, password: password! };
}
