import { expect, test } from "@playwright/test";

test("provenance graph view loads and why-path renders for artifact node", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("omniai.phase1.context", JSON.stringify({ projectId: "p1", threadId: "t1", runId: "r1" }));
  });

  await page.route("**/v1/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const p = url.pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });

    if (p === "/v1/auth/login" && req.method() === "POST") return json({ user_id: "dev-user", display_name: "dev-user", created_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/auth/csrf") return json({ csrf_token: "csrf-token" });
    if (p === "/v1/me") return json({ user_id: "dev-user", display_name: "dev-user", created_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/projects") return json({ projects: [{ id: "p1", name: "p1", created_at: "2026-01-01T00:00:00Z" }] });
    if (p === "/v1/projects/p1/threads") return json({ threads: [{ id: "t1", project_id: "p1", title: "t1", created_at: "2026-01-01T00:00:00Z" }] });
    if (p === "/v1/threads/t1/runs") return json({ runs: [{ id: "r1", thread_id: "t1", status: "active", created_at: "2026-01-01T00:00:00Z", pins: {} }] });
    if (p === "/v1/runs/r1/events") return json({ events: [] });
    if (p === "/v1/runs/r1/artifacts") return json({ artifacts: [] });
    if (p === "/v1/runs/r1/summary") return json({ run_id: "r1", status: "active", created_at: "2026-01-01T00:00:00Z", event_count: 2, last_seq: 2, pins: {} });
    if (p === "/v1/runs/r1/approvals") return json({ approvals: [] });
    if (p === "/v1/runs/r1/metrics") return json({ run_id: "r1", created_at: "2026-01-01T00:00:00Z", completed_at: null, duration_ms: null, event_count: 2, tool_calls: 1, tool_errors: 0, artifacts_count: 1, bytes_in: 0, bytes_out: 0 });
    if (p === "/v1/runs/r1/provenance") return json({ run_id: "r1", events_count: 2, artifacts_count: 1, research_sources_count: 1, report_artifact_ids: [] });
    if (p === "/v1/runs/r1/provenance/graph") {
      return json({
        run_id: "r1",
        generated_at: "2026-01-01T00:00:00Z",
        truncated: false,
        truncation: { node_cap_hit: false, edge_cap_hit: false, depth_cap_hit: false },
        nodes: [
          { id: "event:e1", type: "event", label: "tool_result", meta: {} },
          { id: "artifact:a1", type: "artifact", label: "a1", meta: {} },
          { id: "source:s1", type: "research_source", label: "s1", meta: {} },
        ],
        edges: [
          { from: "event:e1", to: "artifact:a1", kind: "artifact_ref", meta: {} },
          { from: "artifact:a1", to: "source:s1", kind: "citation", meta: {} },
        ],
      });
    }
    if (p === "/v1/runs/r1/provenance/why") {
      return json({
        artifact_id: "a1",
        truncated: false,
        paths: [{ nodes: ["artifact:a1", "event:e1"], edges: [{ from: "event:e1", to: "artifact:a1", kind: "artifact_ref", meta: {} }] }],
      });
    }
    if (p.endsWith("/events/stream") || p.endsWith("/activity/stream")) {
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: heartbeat\ndata: {\"ts\":\"2026-01-01T00:00:00Z\"}\n\n" });
    }
    if (p === "/v1/tools") return json({ tools: [] });
    if (p === "/v1/mcp/servers") return json({ servers: [] });
    if (p === "/v1/memory/items") return json({ items: [] });
    if (p === "/v1/workflows") return json({ workflows: [] });
    if (p === "/v1/registry/packages") return json({ packages: [] });
    if (p === "/v1/tools/metrics") return json({ tools: [] });
    if (p === "/v1/projects/p1/tools/pins") return json({ pins: [] });
    if (p === "/v1/projects/p1/members") return json({ members: [] });
    if (p === "/v1/projects/p1/activity") return json({ activity: [] });
    if (p === "/v1/projects/p1/comments") return json({ comments: [] });
    if (p === "/v1/notifications/unread_count") return json({ unread_count: 0, last_seen_notification_seq: 0 });
    if (p === "/v1/notifications/state") return json({ last_seen_notification_seq: 0, updated_at: "2026-01-01T00:00:00Z" });
    if (p === "/v1/notifications" && req.method() === "GET") return json({ notifications: [] });
    if (p === "/v1/notifications/stream") {
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: heartbeat\ndata: {\"ts\":\"2026-01-01T00:00:00Z\"}\n\n" });
    }
    return json({});
  });

  await page.goto("/");
  const loginButton = page.getByRole("button", { name: "Login" });
  if ((await loginButton.count()) > 0 && (await loginButton.first().isVisible().catch(() => false))) {
    await loginButton.first().click();
  }
  await page.getByRole("button", { name: /^p1/ }).click();
  await page.getByRole("button", { name: "t1" }).click();
  await page.getByRole("button", { name: /r1 \(active\)/i }).click();
  await page.getByRole("button", { name: "Dashboard" }).click();
  await page.getByRole("button", { name: "Graph view" }).click();
  await expect(page.getByLabel("Provenance graph canvas")).toBeVisible();
  await page.getByRole("button", { name: /Select node artifact:a1/i }).click();
  await expect(page.getByText("Why Is This Here?")).toBeVisible();
  await expect(page.getByText("Path 1")).toBeVisible();
});
