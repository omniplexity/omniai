import { expect, test } from "@playwright/test";
import { apiLogin } from "./helpers/auth";

const FRONTEND_URL = process.env.FRONTEND_URL || "http://localhost:5173";
const BACKEND_URL = process.env.E2E_BASE_URL || process.env.BACKEND_BASE_URL || "http://localhost:8000";
const E2E_USERNAME = process.env.E2E_USERNAME;
const E2E_PASSWORD = process.env.E2E_PASSWORD;

async function login(page: import("@playwright/test").Page) {
  if (!E2E_USERNAME || !E2E_PASSWORD) {
    if (process.env.CI) {
      throw new Error("Missing E2E_USERNAME/E2E_PASSWORD in CI");
    }
    test.skip(true, "Missing E2E credentials");
  }
  const frontendOrigin = new URL(FRONTEND_URL).origin;
  await apiLogin({
    request: page.request,
    context: page.context(),
    backendUrl: BACKEND_URL,
    username: E2E_USERNAME!,
    password: E2E_PASSWORD!,
    frontendOrigin,
  });
}

test.describe("chat stream smoke", () => {
  test("login -> send -> stream -> done", async ({ page }) => {
    await login(page);
    await page.goto(`${FRONTEND_URL}/#/chat`);
    await page.locator('[data-testid="composer-input"]').fill("hello");
    await page.locator('[data-testid="send-btn"]').click();
    await expect(page.locator('[data-testid="run-status"]')).toContainText(/Streaming|Idle/);
  });

  test("cancel mid-stream marks cancelled", async ({ page }) => {
    await login(page);
    await page.goto(`${FRONTEND_URL}/#/chat`);
    await page.locator('[data-testid="composer-input"]').fill("please stream a long answer");
    await page.locator('[data-testid="send-btn"]').click();
    await page.locator('[data-testid="cancel-btn"]').click();
    await expect(page.locator('[data-testid="transcript"]')).toContainText("E_CANCELLED");
  });

  test("retry triggers new run path", async ({ page }) => {
    await login(page);
    await page.goto(`${FRONTEND_URL}/#/chat`);
    await page.locator('[data-testid="composer-input"]').fill("retry test");
    await page.locator('[data-testid="send-btn"]').click();
    await page.locator('[data-testid="retry-btn"]').click();
    await expect(page.locator('[data-testid="run-status"]')).toContainText(/Streaming|Idle/);
  });

  test("auth expiry shows sign in hint", async ({ page, context }) => {
    await login(page);
    await context.clearCookies();
    await page.goto(`${FRONTEND_URL}/#/chat`);
    await page.locator('[data-testid="composer-input"]').fill("auth test");
    await page.locator('[data-testid="send-btn"]').click();
    await expect(page.locator('[data-testid="auth-hint"]')).toBeVisible();
  });
});
