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

test.describe("workspace smoke", () => {
  test("login -> workspace route -> panes render -> chat route reachable", async ({ page }) => {
    await login(page);

    await page.goto(`${FRONTEND_URL}/#/workspace`);
    await expect(page.locator('[data-testid="workspace-shell"]')).toBeVisible();
    await expect(page.locator('[data-testid="workspace-pane-chat"]')).toBeVisible();
    await expect(page.locator('[data-testid="workspace-pane-editor"]')).toBeVisible();
    await expect(page.locator('[data-testid="workspace-pane-results"]')).toBeVisible();

    await page.goto(`${FRONTEND_URL}/#/chat`);
    await expect(page.locator('[data-testid="composer-input"]')).toBeVisible();
  });
});
