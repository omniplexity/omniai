import { expect, test } from "@playwright/test";

const FRONTEND_URL = process.env.FRONTEND_URL || "http://localhost:5173";

test.describe("Ops Console", () => {
  test("renders status/logs and allows actions in mock mode", async ({ page }) => {
    await page.route("**/runtime-config.json*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          BACKEND_BASE_URL: "http://localhost:5173",
          FEATURE_FLAGS: { adminOps: true }
        })
      });
    });

    await page.route("**/v1/**", async (route) => {
      const req = route.request();
      const url = new URL(req.url());
      const path = url.pathname;

      if (path === "/v1/meta") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            auth: {
              authenticated: true,
              user: { id: "u1", username: "admin", is_admin: true }
            }
          })
        });
        return;
      }
      if (path === "/v1/conversations") {
        await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
        return;
      }
      if (path === "/v1/auth/csrf/bootstrap") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: { "x-csrf-token": "csrf-test" },
          body: JSON.stringify({ csrf_token: "csrf-test" })
        });
        return;
      }
      if (path === "/v1/ops/duckdns/status") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            token_present: true,
            subdomain: "omniplexity",
            scheduler_enabled: true,
            scheduler_interval_minutes: 5,
            scheduler_last_run_unix: Math.floor(Date.now() / 1000) - 120,
            scheduler_last_ok_unix: Math.floor(Date.now() / 1000) - 120,
            scheduler_stale: false,
            scheduler_stale_threshold_minutes: 10,
            next_scheduled_run_unix: Math.floor(Date.now() / 1000) + 300,
            last_update: {
              id: "evt1",
              created_at: new Date().toISOString(),
              ip: "1.2.3.4",
              response: "OK",
              success: true,
              error_code: null,
              error_message: null,
              latency_ms: 42,
              source: "scheduler"
            }
          })
        });
        return;
      }
      if (path === "/v1/ops/duckdns/logs") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            logs: [
              {
                id: "evt1",
                created_at: new Date().toISOString(),
                subdomain: "omniplexity",
                ip: "1.2.3.4",
                response: "OK",
                success: true,
                error_code: null,
                error_message: null,
                latency_ms: 42,
                actor_user_id: null,
                source: "scheduler"
              }
            ]
          })
        });
        return;
      }
      if (path === "/v1/ops/duckdns/test" || path === "/v1/ops/duckdns/update") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ success: true, response: "OK", ip: "1.2.3.4" })
        });
        return;
      }

      await route.fulfill({ status: 404, body: "Not found" });
    });

    await page.goto(`${FRONTEND_URL}/#/ops`);

    await expect(page.locator("[data-testid='ops-page']")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Ops Console" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Test DuckDNS now" })).toBeVisible();

    await page.getByRole("button", { name: "Test DuckDNS now" }).click();
    await expect(page.getByText(/Test executed/i)).toBeVisible();
  });
});
