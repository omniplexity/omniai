import { expect, test } from "@playwright/test";
import { apiLogin } from "./helpers/auth";
import { resolveE2ECredsOrSkip } from "./support/creds";

const FRONTEND_URL = process.env.FRONTEND_URL || "http://127.0.0.1:5173";
const BACKEND_URL = process.env.E2E_BASE_URL || process.env.BACKEND_BASE_URL || "http://127.0.0.1:8000";
async function login(page: import("@playwright/test").Page) {
  const { username, password } = resolveE2ECredsOrSkip();
  const frontendOrigin = new URL(FRONTEND_URL).origin;
  await apiLogin({
    request: page.request,
    context: page.context(),
    backendUrl: BACKEND_URL,
    username,
    password,
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
    const transcript = page.locator('[data-testid="transcript"]');
    await expect(transcript).toContainText("E_CANCELLED");
    await expect(transcript.getByText("E_CANCELLED")).toHaveCount(1);
  });

  test("retry triggers new run path with no duplicate cancellation markers", async ({ page }) => {
    await login(page);
    await page.goto(`${FRONTEND_URL}/#/chat`);
    await page.locator('[data-testid="composer-input"]').fill("retry test");
    await page.locator('[data-testid="send-btn"]').click();
    await expect(page.locator('[data-testid="run-status"]')).toContainText(/Streaming|Idle/);
    await page.locator('[data-testid="cancel-btn"]').click();
    await expect(page.locator('[data-testid="transcript"]')).toContainText("E_CANCELLED");
    await page.locator('[data-testid="retry-btn"]').click();
    await expect(page.locator('[data-testid="run-status"]')).toContainText(/Streaming|Idle/);
    await expect(page.locator('[data-testid="transcript"]').getByText("E_CANCELLED")).toHaveCount(1);
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
