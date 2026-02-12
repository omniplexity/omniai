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

test.describe("workspace smoke", () => {
  test("login -> workspace route -> panes render -> chat route reachable", async ({ page }) => {
    await login(page);

    await page.goto(`${FRONTEND_URL}/#/workspace`);
    await expect(page.locator('[data-testid="workspace-shell"]')).toBeVisible();
    await expect(page.locator('[data-testid="workspace-pane-chat"]')).toBeVisible();
    await expect(page.locator('[data-testid="workspace-pane-editor"]')).toBeVisible();
    await expect(page.locator('[data-testid="workspace-pane-results"]')).toBeVisible();

    await page.goto(`${FRONTEND_URL}/#/chat`);
    await expect(page.locator('[data-testid="chat-shell"]')).toBeVisible();
  });
});
