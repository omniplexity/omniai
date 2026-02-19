import { expect, test } from "@playwright/test";

test("right sidebar removed and remaining utility tabs are reachable from left nav", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("omniai.phase1.context", JSON.stringify({ projectId: "", threadId: "", runId: "" }));
  });

  await page.route("**/v1/**", async (route) => {
    const req = route.request();
    const p = new URL(req.url()).pathname;
    const method = req.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (p === "/v1/me") return json({ user_id: "u1", display_name: "User One", created_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/auth/login" && method === "POST") return json({ user_id: "u1", display_name: "User One", created_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/auth/csrf") return json({ csrf_token: "csrf-token" });
    if (p === "/v1/projects") return json({ projects: [] });
    if (p === "/v1/threads") return json({ threads: [] });
    if (p === "/v1/tools") return json({ tools: [] });
    if (p === "/v1/mcp/servers") return json({ servers: [] });
    if (p === "/v1/memory/items") return json({ items: [] });
    if (p === "/v1/workflows") return json({ workflows: [] });
    if (p === "/v1/registry/packages") return json({ packages: [] });
    if (p === "/v1/tools/metrics") return json({ tools: [] });
    if (p === "/v1/notifications/unread_count") return json({ unread_count: 0, last_seen_notification_seq: 0 });
    if (p === "/v1/notifications/state") return json({ last_seen_notification_seq: 0, updated_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/notifications") return json({ notifications: [] });
    if (p.endsWith("/events/stream") || p.endsWith("/activity/stream") || p === "/v1/notifications/stream") {
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: heartbeat\ndata: {"ts":"2026-01-01T00:00:00Z"}\n\n' });
    }
    return json({});
  });

  await page.goto("/");
  const signIn = page.getByRole("button", { name: "Sign In" });
  if ((await signIn.count()) > 0 && (await signIn.first().isVisible().catch(() => false))) {
    await signIn.first().click();
  }

  await expect(page.locator(".right-sidebar")).toHaveCount(0);

  await page.getByRole("button", { name: "Tools" }).click();
  await expect(page.locator(".center-content").getByText("Tools", { exact: false })).toBeVisible();
  await expect(page.locator(".center-content").getByRole("button", { name: "Invoke" })).toBeVisible();

  await page.getByRole("button", { name: "Memory" }).click();
  await expect(page.locator(".center-content").getByText("Memory", { exact: false })).toBeVisible();
  await expect(page.locator(".center-content").getByRole("button", { name: "Create" })).toBeVisible();

  await page.getByRole("button", { name: "Marketplace" }).click();
  await expect(page.locator(".center-content").getByText("Marketplace", { exact: false })).toBeVisible();
  await expect(page.locator(".center-content").getByRole("button", { name: "Install" })).toBeVisible();
});
