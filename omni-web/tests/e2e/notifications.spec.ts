import { expect, test } from "@playwright/test";

test("notifications panel shows unread, mark read, and merges SSE updates", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("omniai.phase1.context", JSON.stringify({ projectId: "", threadId: "", runId: "" }));
  });

  let notifications = [
    {
      notification_id: "n1",
      notification_seq: 1,
      user_id: "u1",
      project_id: "p1",
      run_id: "r1",
      activity_seq: 1,
      kind: "comment_created",
      created_at: "2026-02-13T00:00:00Z",
      payload: { summary: "Comment one", actor_user_id: "u2" },
      read_at: null,
    },
    {
      notification_id: "n2",
      notification_seq: 2,
      user_id: "u1",
      project_id: "p1",
      run_id: "r1",
      activity_seq: 2,
      kind: "comment_created",
      created_at: "2026-02-13T00:01:00Z",
      payload: { summary: "Comment two", actor_user_id: "u3" },
      read_at: null,
    },
  ];

  let emitSseNotification = false;
  let sseSent = false;
  let markReadUpToSeqPayload: number | null = null;
  let markReadIdempotencyHeader: string | null = null;
  await page.route("**/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const p = url.pathname;
    const json = (body: unknown) =>
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

    if (p === "/v1/me") return json({ user_id: "u1", display_name: "User One", created_at: "2026-02-13T00:00:00Z" });
    if (p === "/v1/auth/csrf") return json({ csrf_token: "csrf-token" });
    if (p === "/v1/projects") return json({ projects: [] });
    if (p === "/v1/tools") return json({ tools: [] });
    if (p === "/v1/mcp/servers") return json({ servers: [] });
    if (p === "/v1/memory/items") return json({ items: [] });
    if (p === "/v1/workflows") return json({ workflows: [] });
    if (p === "/v1/registry/packages") return json({ packages: [] });
    if (p === "/v1/tools/metrics") return json({ tools: [] });

    if (p === "/v1/notifications/unread_count") {
      return json({ unread_count: notifications.filter((n) => !n.read_at).length, last_seen_notification_seq: 0 });
    }
    if (p === "/v1/notifications/state") {
      return json({ last_seen_notification_seq: 0, updated_at: "2026-02-13T00:00:00Z" });
    }
    if (p === "/v1/notifications" && req.method() === "GET") {
      return json({ notifications });
    }
    if (p === "/v1/notifications/mark_read" && req.method() === "POST") {
      const body = (req.postDataJSON() || {}) as { notification_ids?: string[]; up_to_seq?: number };
      markReadIdempotencyHeader = req.headers()["x-omni-idempotency-key"] || null;
      if (Array.isArray(body.notification_ids)) {
        const ids = new Set(body.notification_ids);
        notifications = notifications.map((n) => (ids.has(n.notification_id) ? { ...n, read_at: "2026-02-13T00:02:00Z" } : n));
        emitSseNotification = true;
      } else if (typeof body.up_to_seq === "number") {
        markReadUpToSeqPayload = body.up_to_seq;
        notifications = notifications.map((n) =>
          n.notification_seq <= body.up_to_seq ? { ...n, read_at: "2026-02-13T00:03:00Z" } : n,
        );
      }
      return json({
        changed: 1,
        unread_count: notifications.filter((n) => !n.read_at).length,
        last_seen_notification_seq: 0,
      });
    }
    if (p === "/v1/notifications/stream") {
      if (!emitSseNotification || sseSent) {
        return route.fulfill({
          status: 200,
          contentType: "text/event-stream",
          body: 'event: heartbeat\ndata: {"ts":"2026-02-13T00:04:00Z"}\n\n',
        });
      }
      sseSent = true;
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body:
          'event: notification\nid: 3\ndata: {"notification_id":"n3","notification_seq":3,"user_id":"u1","project_id":"p1","run_id":"r1","activity_seq":3,"kind":"comment_created","created_at":"2026-02-13T00:05:00Z","payload":{"summary":"Comment three","actor_user_id":"u4"},"read_at":null}\n\n' +
          'event: heartbeat\ndata: {"ts":"2026-02-13T00:05:00Z"}\n\n',
      });
    }
    if (p.endsWith("/events/stream") || p.endsWith("/activity/stream")) {
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: 'event: heartbeat\ndata: {"ts":"2026-02-13T00:00:00Z"}\n\n',
      });
    }

    return json({});
  });

  await page.goto("/");

  const bellButton = page.getByRole("button", { name: /Bell/ });
  const readBadgeCount = async () => {
    const txt = (await bellButton.innerText()).trim();
    const m = txt.match(/\((\d+)\)/);
    return m ? Number(m[1]) : 0;
  };
  await expect(bellButton).toContainText("(2)");
  await bellButton.click();
  const initialUnread = await readBadgeCount();

  await expect(page.getByText("Comment one")).toBeVisible();
  await expect(page.getByText("Comment two")).toBeVisible();
  await expect(page.getByText("newest_notification_seq: 2")).toBeVisible();
  await expect(page.getByText("last_seen_notification_seq: 0")).toBeVisible();
  await expect(page.getByText("next_mark_all_up_to_seq: 2")).toBeVisible();

  await page.locator("li", { hasText: "Comment one" }).getByRole("button", { name: "Mark Read" }).click();
  await expect.poll(readBadgeCount).toBeLessThan(initialUnread);
  const unreadAfterMarkOne = await readBadgeCount();

  await expect.poll(async () => await page.locator("li", { hasText: "Comment three" }).count()).toBeGreaterThan(0);
  await expect.poll(readBadgeCount).toBeGreaterThan(unreadAfterMarkOne);
  await expect(page.getByText("newest_notification_seq: 3")).toBeVisible();
  await expect(page.getByText("next_mark_all_up_to_seq: 3")).toBeVisible();

  await page.getByRole("button", { name: "Mark All Read (Up To Newest Unread)" }).click();
  await expect.poll(() => markReadUpToSeqPayload).toBe(3);
  await expect.poll(() => Boolean(markReadIdempotencyHeader && markReadIdempotencyHeader.length > 0)).toBeTruthy();
  await expect(bellButton).toContainText("(0)");
  await expect(page.locator("li", { hasText: "Comment three" })).toHaveCount(1);
});
