import { expect, test } from "@playwright/test";

test("fresh boot does not auto-create projects", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("omniai.phase1.context", JSON.stringify({ projectId: "", threadId: "", runId: "" }));
  });

  let createProjectCalls = 0;
  await page.route("**/v1/**", async (route) => {
    const req = route.request();
    const p = new URL(req.url()).pathname;
    const method = req.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (p === "/v1/me") return json({ user_id: "u1", display_name: "User One", created_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/auth/login" && method === "POST") return json({ user_id: "u1", display_name: "User One", created_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/auth/csrf") return json({ csrf_token: "csrf-token" });
    if (p === "/v1/projects" && method === "GET") return json({ projects: [] });
    if (p === "/v1/projects" && method === "POST") {
      createProjectCalls += 1;
      return json({ id: "unexpected", name: "unexpected", created_at: "2026-01-01T00:00:00Z" }, 201);
    }
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
  expect(createProjectCalls).toBe(0);
});

test("chat/project deletion persists across reload and no project auto-creation occurs", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("omniai.phase1.context", JSON.stringify({ projectId: "p1", threadId: "t1", runId: "r1" }));
  });

  let projects = [{ id: "p1", name: "project-one", created_at: "2026-01-01T00:00:00Z" }];
  let threads = [
    { id: "t1", project_id: "p1", title: "project-thread", created_at: "2026-01-01T00:00:00Z" },
  ];
  let runs = [
    { id: "r1", thread_id: "t1", status: "active", created_at: "2026-01-01T00:00:00Z", pins: {} },
  ];
  let createProjectCalls = 0;

  await page.route("**/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const p = url.pathname;
    const method = req.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (p === "/v1/me") return json({ user_id: "u1", display_name: "User One", created_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/auth/login" && method === "POST") return json({ user_id: "u1", display_name: "User One", created_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/auth/csrf") return json({ csrf_token: "csrf-token" });
    if (p === "/v1/projects" && method === "GET") return json({ projects });
    if (p === "/v1/projects" && method === "POST") {
      createProjectCalls += 1;
      return json({ id: "unexpected", name: "unexpected", created_at: "2026-01-01T00:00:00Z" }, 201);
    }
    if (p === "/v1/threads" && method === "GET") return json({ threads });
    if (p === "/v1/projects/p1" && method === "DELETE") {
      projects = projects.filter((proj) => proj.id !== "p1");
      threads = threads.filter((t) => t.project_id !== "p1");
      runs = runs.filter((r) => r.thread_id !== "t1");
      return json({ deleted: true });
    }
    if (p === "/v1/projects/p1/threads") return json({ threads: threads.filter((t) => t.project_id === "p1") });
    if (p === "/v1/projects/p1/tools/pins") return json({ pins: [] });
    if (p === "/v1/projects/p1/members") return json({ members: [] });
    if (p === "/v1/projects/p1/activity") return json({ activity: [] });
    if (p === "/v1/projects/p1/activity/unread") return json({ unread_count: 0 });
    if (p === "/v1/projects/p1/comments") return json({ comments: [] });
    if (p === "/v1/threads/t1/runs") {
      if (!threads.some((t) => t.id === "t1")) return json({ detail: "thread not found" }, 404);
      return json({ runs: runs.filter((r) => r.thread_id === "t1") });
    }
    if (p === "/v1/runs/r1/events") return json({ events: [] });
    if (p === "/v1/runs/r1/artifacts") return json({ artifacts: [] });
    if (p === "/v1/runs/r1/summary") return json({ run_id: "r1", status: "active", created_at: "2026-01-01T00:00:00Z", event_count: 0, last_seq: 0, pins: {} });
    if (p === "/v1/runs/r1/approvals") return json({ approvals: [] });
    if (p === "/v1/runs/r1/metrics") return json({ run_id: "r1", created_at: "2026-01-01T00:00:00Z", completed_at: null, duration_ms: null, event_count: 0, tool_calls: 0, tool_errors: 0, artifacts_count: 0, bytes_in: 0, bytes_out: 0 });
    if (p === "/v1/runs/r1/provenance") return json({ run_id: "r1", events_count: 0, artifacts_count: 0, research_sources_count: 0, report_artifact_ids: [] });
    if (p === "/v1/runs/r1/provenance/graph") return json({ run_id: "r1", generated_at: "2026-01-01T00:00:00Z", truncated: false, truncation: { node_cap_hit: false, edge_cap_hit: false, depth_cap_hit: false }, nodes: [], edges: [] });
    if (p.endsWith("/events/stream") || p.endsWith("/activity/stream") || p === "/v1/notifications/stream") {
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: heartbeat\ndata: {"ts":"2026-01-01T00:00:00Z"}\n\n' });
    }
    if (p === "/v1/tools") return json({ tools: [] });
    if (p === "/v1/mcp/servers") return json({ servers: [] });
    if (p === "/v1/memory/items") return json({ items: [] });
    if (p === "/v1/workflows") return json({ workflows: [] });
    if (p === "/v1/registry/packages") return json({ packages: [] });
    if (p === "/v1/tools/metrics") return json({ tools: [] });
    if (p === "/v1/notifications/unread_count") return json({ unread_count: 0, last_seen_notification_seq: 0 });
    if (p === "/v1/notifications/state") return json({ last_seen_notification_seq: 0, updated_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/notifications") return json({ notifications: [] });
    return json({});
  });

  page.on("dialog", (dialog) => dialog.accept());

  await page.goto("/");
  const signIn = page.getByRole("button", { name: "Sign In" });
  if ((await signIn.count()) > 0 && (await signIn.first().isVisible().catch(() => false))) {
    await signIn.first().click();
  }
  await expect(page.getByText("project-one")).toBeVisible();

  await page.locator(".sb-project-row:has-text('project-one') .sb-project-dots").click();
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText("project-one")).toHaveCount(0);

  await page.reload();
  await expect(page.getByText("project-one")).toHaveCount(0);
  const persisted = await page.evaluate(() => localStorage.getItem("omniai.phase1.context"));
  expect(persisted).toBeTruthy();
  const parsed = JSON.parse(String(persisted)) as { projectId?: string; threadId?: string; runId?: string };
  expect(parsed.projectId || "").toBe("");
  expect(parsed.threadId || "").toBe("");
  expect(createProjectCalls).toBe(0);
});

test("delete failure surfaces error and keeps item", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("omniai.phase1.context", JSON.stringify({ projectId: "p1", threadId: "", runId: "" }));
  });
  let projects = [{ id: "p1", name: "project-one", created_at: "2026-01-01T00:00:00Z" }];
  await page.route("**/v1/**", async (route) => {
    const req = route.request();
    const p = new URL(req.url()).pathname;
    const method = req.method();
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (p === "/v1/me") return json({ user_id: "u1", display_name: "User One", created_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/auth/login" && method === "POST") return json({ user_id: "u1", display_name: "User One", created_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/auth/csrf") return json({ csrf_token: "csrf-token" });
    if (p === "/v1/projects" && method === "GET") return json({ projects });
    if (p === "/v1/projects/p1" && method === "DELETE") return json({ detail: "boom" }, 500);
    if (p === "/v1/threads") return json({ threads: [] });
    if (p === "/v1/projects/p1/threads") return json({ threads: [] });
    if (p === "/v1/projects/p1/tools/pins") return json({ pins: [] });
    if (p === "/v1/projects/p1/members") return json({ members: [] });
    if (p === "/v1/projects/p1/activity") return json({ activity: [] });
    if (p === "/v1/projects/p1/activity/unread") return json({ unread_count: 0 });
    if (p === "/v1/projects/p1/comments") return json({ comments: [] });
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

  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/");
  const signIn = page.getByRole("button", { name: "Sign In" });
  if ((await signIn.count()) > 0 && (await signIn.first().isVisible().catch(() => false))) {
    await signIn.first().click();
  }
  await expect(page.getByText("project-one")).toBeVisible();
  await page.locator(".sb-project-row:has-text('project-one') .sb-project-dots").click();
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("alert")).toContainText("Failed to delete project");
  await expect(page.getByText("project-one")).toBeVisible();
});

test("delete chat then create another chat does not resurrect deleted chat", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("omniai.phase1.context", JSON.stringify({ projectId: "", threadId: "t1", runId: "r1" }));
  });
  let threads = [{ id: "t1", project_id: null, user_id: "u1", title: "old-chat", created_at: "2026-01-01T00:00:00Z" }];
  let runs = [{ id: "r1", thread_id: "t1", status: "active", created_at: "2026-01-01T00:00:00Z", pins: {} }];
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
    if (p === "/v1/threads" && method === "GET") return json({ threads });
    if (p === "/v1/threads" && method === "POST") {
      const next = { id: "t2", project_id: null, user_id: "u1", title: "Chat 1", created_at: "2026-01-01T00:00:01Z" };
      threads = [next];
      runs = [{ id: "r2", thread_id: "t2", status: "active", created_at: "2026-01-01T00:00:01Z", pins: {} }];
      return json(next, 201);
    }
    if (p === "/v1/threads/t1" && method === "DELETE") {
      threads = threads.filter((t) => t.id !== "t1");
      runs = runs.filter((r) => r.thread_id !== "t1");
      return json({ deleted: true });
    }
    if (p === "/v1/threads/t2/runs") return json({ runs: runs.filter((r) => r.thread_id === "t2") });
    if (p === "/v1/threads/t1/runs") {
      if (!threads.some((t) => t.id === "t1")) return json({ detail: "thread not found" }, 404);
      return json({ runs: runs.filter((r) => r.thread_id === "t1") });
    }
    if (p === "/v1/runs/r1/events" || p === "/v1/runs/r2/events") return json({ events: [] });
    if (p === "/v1/runs/r1/artifacts" || p === "/v1/runs/r2/artifacts") return json({ artifacts: [] });
    if (p === "/v1/runs/r1/summary" || p === "/v1/runs/r2/summary") return json({ run_id: p.includes("r2") ? "r2" : "r1", status: "active", created_at: "2026-01-01T00:00:00Z", event_count: 0, last_seq: 0, pins: {} });
    if (p === "/v1/runs/r1/approvals" || p === "/v1/runs/r2/approvals") return json({ approvals: [] });
    if (p === "/v1/runs/r1/metrics" || p === "/v1/runs/r2/metrics") return json({ run_id: p.includes("r2") ? "r2" : "r1", created_at: "2026-01-01T00:00:00Z", completed_at: null, duration_ms: null, event_count: 0, tool_calls: 0, tool_errors: 0, artifacts_count: 0, bytes_in: 0, bytes_out: 0 });
    if (p === "/v1/runs/r1/provenance" || p === "/v1/runs/r2/provenance") return json({ run_id: p.includes("r2") ? "r2" : "r1", events_count: 0, artifacts_count: 0, research_sources_count: 0, report_artifact_ids: [] });
    if (p === "/v1/runs/r1/provenance/graph" || p === "/v1/runs/r2/provenance/graph") return json({ run_id: p.includes("r2") ? "r2" : "r1", generated_at: "2026-01-01T00:00:00Z", truncated: false, truncation: { node_cap_hit: false, edge_cap_hit: false, depth_cap_hit: false }, nodes: [], edges: [] });
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
  page.on("dialog", (dialog) => dialog.accept());
  await page.goto("/");
  const signIn = page.getByRole("button", { name: "Sign In" });
  if ((await signIn.count()) > 0 && (await signIn.first().isVisible().catch(() => false))) {
    await signIn.first().click();
  }
  await expect(page.getByText("old-chat")).toBeVisible();
  await page.locator(".sb-thread:has-text('old-chat') .sb-thread-dots").click();
  await page.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText("old-chat")).toHaveCount(0);
  await page.getByRole("button", { name: "New chat" }).first().click();
  await expect(page.getByText("old-chat")).toHaveCount(0);
  await expect(page.getByText("Chat 1")).toBeVisible();
});
