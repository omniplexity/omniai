import { expect, test } from "@playwright/test";

function systemConfigBody() {
  return {
    notify_tool_errors: true,
    notify_tool_errors_only_codes: ["E_TOOL_TIMEOUT"],
    notify_tool_errors_only_bindings: ["mcp_remote"],
    notify_tool_errors_max_per_run: 5,
    sse_max_replay: 500,
    sse_heartbeat_seconds: 15,
    artifact_max_bytes: 26214400,
    artifact_part_size: 524288,
    session_ttl_seconds: 86400,
    session_sliding_enabled: true,
    session_sliding_window_seconds: 1800,
    max_events_per_run: 10000,
    max_bytes_per_run: 10485760,
    generated_at: "2026-02-13T00:00:00Z",
    contract_version: "0.1.0",
    runtime_version: "omni-backend-0.4.0",
  };
}

async function mockBootstrap(page: { addInitScript: (arg0: () => void) => Promise<void>; route: (arg0: string, arg1: (route: any) => Promise<any>) => Promise<void> }) {
  await page.addInitScript(() => {
    localStorage.setItem("omniai.phase1.context", JSON.stringify({ projectId: "", threadId: "", runId: "" }));
  });
  await page.route("**/v1/me", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user_id: "u1", display_name: "User One", created_at: "2026-02-13T00:00:00Z" }) }));
  await page.route("**/v1/auth/csrf", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ csrf_token: "csrf-token" }) }));
  await page.route("**/v1/projects", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ projects: [] }) }));
  await page.route("**/v1/tools", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ tools: [] }) }));
  await page.route("**/v1/mcp/servers", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ servers: [] }) }));
  await page.route("**/v1/memory/items", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [] }) }));
  await page.route("**/v1/workflows", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ workflows: [] }) }));
  await page.route("**/v1/registry/packages", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ packages: [] }) }));
  await page.route("**/v1/tools/metrics", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ tools: [] }) }));
  await page.route("**/v1/notifications/unread_count", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ unread_count: 0, last_seen_notification_seq: 0 }) }));
  await page.route("**/v1/notifications/state", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ last_seen_notification_seq: 0, updated_at: "2026-02-13T00:00:00Z" }) }));
  await page.route("**/v1/notifications", async (route) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ notifications: [] }) }));
  await page.route("**/v1/notifications/stream", async (route) => {
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: heartbeat\ndata: {"ts":"2026-02-13T00:00:00Z"}\n\n' });
  });
  await page.route("**/v1/**/events/stream", async (route) => route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: heartbeat\ndata: {"ts":"2026-02-13T00:00:00Z"}\n\n' }));
  await page.route("**/v1/**/activity/stream", async (route) => route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: heartbeat\ndata: {"ts":"2026-02-13T00:00:00Z"}\n\n' }));
}

test("system config panel renders grouped config on 200", async ({ page }) => {
  await mockBootstrap(page);

  await page.route("**/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const p = url.pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (p === "/v1/me") return json({ user_id: "u1", display_name: "User One", created_at: "2026-02-13T00:00:00Z" });
    if (p === "/v1/auth/csrf") return json({ csrf_token: "csrf-token" });
    if (p === "/v1/projects") return json({ projects: [] });
    if (p === "/v1/tools") return json({ tools: [] });
    if (p === "/v1/mcp/servers") return json({ servers: [] });
    if (p === "/v1/memory/items") return json({ items: [] });
    if (p === "/v1/workflows") return json({ workflows: [] });
    if (p === "/v1/registry/packages") return json({ packages: [] });
    if (p === "/v1/tools/metrics") return json({ tools: [] });
    if (p === "/v1/notifications/unread_count") return json({ unread_count: 0, last_seen_notification_seq: 0 });
    if (p === "/v1/notifications/state") return json({ last_seen_notification_seq: 0, updated_at: "2026-02-13T00:00:00Z" });
    if (p === "/v1/notifications") return json({ notifications: [] });
    if (p === "/v1/notifications/stream") {
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: heartbeat\ndata: {"ts":"2026-02-13T00:00:00Z"}\n\n' });
    }
    if (p.endsWith("/events/stream") || p.endsWith("/activity/stream")) {
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: heartbeat\ndata: {"ts":"2026-02-13T00:00:00Z"}\n\n' });
    }
    if (p === "/v1/system/config" && req.method() === "GET") return json(systemConfigBody());
    return json({});
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Show System Panel" }).click();
  const panel = page.locator(".ops-panel");
  await expect(panel.getByRole("button", { name: "Refresh System Config" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Copy System Config JSON" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Show Raw JSON" })).toBeVisible();
  await expect(panel.getByText(/Fetched:/)).toBeVisible();
  await expect(page.getByText("notify_tool_errors: true")).toBeVisible();
  await expect(page.getByText("sse_max_replay: 500")).toBeVisible();
  await expect(page.getByText(/artifact_part_size: 524288/)).toBeVisible();
  await expect(page.getByText("session_ttl_seconds: 86400")).toBeVisible();
  await expect(page.getByText("max_events_per_run: 10000")).toBeVisible();
  await expect(page.getByText("contract_version: 0.1.0")).toBeVisible();
  await expect(page.getByRole("button", { name: "Copy System Config JSON" })).toBeVisible();
});

test("system config panel handles 403 without crashing", async ({ page }) => {
  await mockBootstrap(page);
  await page.route("**/v1/system/config", async (route) => {
    await route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "forbidden" }) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Show System Panel" }).click();
  await expect(page.getByText("Not authorized")).toBeVisible();
});

test("closing and reopening ops triggers system config refetch", async ({ page }) => {
  await mockBootstrap(page);
  let hits = 0;
  await page.route("**/v1/system/config", async (route) => {
    hits += 1;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(systemConfigBody()) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Show System Panel" }).click();
  await expect(page.getByText("notify_tool_errors: true")).toBeVisible();
  await expect.poll(() => hits).toBe(1);

  await page.getByRole("button", { name: "Hide System Panel" }).click();
  await page.getByRole("button", { name: "Show System Panel" }).click();
  await expect(page.getByText("notify_tool_errors: true")).toBeVisible();
  await expect.poll(() => hits).toBe(2);
});

test("system config sections can collapse and expand", async ({ page }) => {
  await mockBootstrap(page);
  await page.route("**/v1/system/config", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(systemConfigBody()) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Show System Panel" }).click();
  await expect(page.getByText("sse_max_replay: 500")).toBeVisible();
  await page.getByRole("button", { name: "SSE", exact: true }).click();
  await expect(page.getByText("sse_max_replay: 500")).not.toBeVisible();
  await page.getByRole("button", { name: "SSE", exact: true }).click();
  await expect(page.getByText("sse_max_replay: 500")).toBeVisible();
});

test("system config search filters rows", async ({ page }) => {
  await mockBootstrap(page);
  await page.route("**/v1/system/config", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(systemConfigBody()) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Show System Panel" }).click();
  await page.getByLabel("Search system config").fill("artifact_part_size");
  await expect(page.getByText(/artifact_part_size: 524288/)).toBeVisible();
  await expect(page.getByText("sse_max_replay: 500")).not.toBeVisible();
});

test("system config sticky header remains visible while scrolling inside ops panel", async ({ page }) => {
  // Force smaller viewport to guarantee internal panel scrolling
  await page.setViewportSize({ width: 1280, height: 420 });
  await mockBootstrap(page);
  await page.route("**/v1/system/config", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(systemConfigBody()) });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Show System Panel" }).click();

  const panel = page.locator(".ops-panel");
  const header = page.locator(".ops-sticky-header");
  await expect(header).toBeVisible();

  const scrollable = await panel.evaluate((el) => el.scrollHeight > el.clientHeight);
  expect(scrollable).toBeTruthy();

  const b0 = await header.boundingBox();
  expect(b0).not.toBeNull();

  await panel.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });

  const b1 = await header.boundingBox();
  expect(b1).not.toBeNull();
  // y should be ~stable if header is sticky within panel scroll
  expect(Math.abs((b1?.y ?? 0) - (b0?.y ?? 0))).toBeLessThan(4);

  await expect(header.getByRole("button", { name: "Refresh System Config" })).toBeVisible();
});
