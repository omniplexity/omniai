import { useEffect, useState } from "preact/hooks";
import type { RuntimeConfig } from "./config/runtimeConfig";
import { setRuntimeConfig } from "./config/runtimeConfig";
import { getFlags, setFlagsFromMeta, setFlagsFromRuntime } from "./core/config/featureFlags";
import { getMeta } from "./core/meta/metaApi";
import type { MetaResponse } from "./core/meta/metaApi";
import { useHashLocation, Link } from "./core/router/hashRouter";
import { Layout } from "./components/Layout";
import { ErrorScreen } from "./components/ErrorScreen";
import { Banner } from "./components/Banner";

import { LoginRoute } from "./routes/login";
import { ChatRoute } from "./routes/chat";
import { SettingsRoute } from "./routes/settings";
import { AdminRoute } from "./routes/admin";
import { OpsRoute } from "./routes/ops";
import { WorkspaceRoute } from "./routes/workspace";

import { authStore, hydrateAuth } from "./core/auth/authStore";
import { ConversationSidebar } from "./components/ConversationSidebar";

function parseRoute(path: string): { name: string; threadId?: string; projectId?: string } {
  const clean = (path.split("?")[0] ?? "").split("#")[0] ?? "";
  if (clean === "/" || clean === "") return { name: "login" };
  if (clean === "/login") return { name: "login" };
  if (clean === "/settings") return { name: "settings" };
  if (clean === "/admin") return { name: "admin" };
  if (clean === "/ops") return { name: "ops" };
  if (clean === "/workspace") return { name: "workspace" };
  if (clean.startsWith("/workspace/")) {
    const parts = clean.split("/").filter(Boolean);
    return { name: "workspace", projectId: parts[1] };
  }
  if (clean.startsWith("/chat")) {
    const parts = clean.split("/").filter(Boolean);
    return { name: "chat", threadId: parts[1] };
  }
  return { name: "login" };
}

function routeRequiresAuth(name: string): boolean {
  return (
    name === "chat" ||
    name === "workspace" ||
    name === "settings" ||
    name === "admin" ||
    name === "ops"
  );
}

export function App(props: { runtimeConfig: RuntimeConfig; initialBootError?: string; initialMeta?: MetaResponse }) {
  setRuntimeConfig(props.runtimeConfig);
  setFlagsFromRuntime(props.runtimeConfig);
  setFlagsFromMeta(props.initialMeta);
  const [bootError, setBootError] = useState<string | null>(props.initialBootError ?? null);
  const [bootRetrying, setBootRetrying] = useState(false);
  const [workspaceEnabled, setWorkspaceEnabled] = useState<boolean>(getFlags().workspace);

  const [path] = useHashLocation();
  const r = parseRoute(path);

  const [auth, setAuth] = useState(authStore.get());
  useEffect(() => authStore.subscribe(() => setAuth(authStore.get())), []);

  useEffect(() => {
    void hydrateAuth();
  }, []);

  async function retryBackendCheck() {
    setBootRetrying(true);
    try {
      const meta = await getMeta();
      setFlagsFromMeta(meta);
      setWorkspaceEnabled(getFlags().workspace);
      setBootError(null);
      await hydrateAuth();
    } catch (e: any) {
      setBootError(String(e?.message ?? e));
    } finally {
      setBootRetrying(false);
    }
  }

  // Block on auth only for protected routes; allow login page to render while meta is pending.
  if (routeRequiresAuth(r.name) && auth.status === "unknown") {
    return (
      <Layout
        nav={
          <div class="nav">
            <Link class="navItem" to="/login">Login</Link>
          </div>
        }
      >
        <div class="page pad">
          <div class="card wide">
            <h1 class="h1">Loading session…</h1>
            <p class="muted">Checking authentication with backend.</p>
          </div>
        </div>
      </Layout>
    );
  }

  // Gate protected routes
  if (routeRequiresAuth(r.name) && auth.status !== "authenticated") {
    if (r.name !== "login") {
      window.location.hash = "#/login";
    }
  }

  // Role-gate admin/ops
  const role = String(auth.role ?? "").toLowerCase();
  const isAdmin = role === "admin" || role === "owner" || role === "root";

  return (
    <Layout
      nav={
        <div class="nav">
          <Link class="navItem" to="/login">Login</Link>
          <Link class="navItem" to="/chat">Chat</Link>
          {workspaceEnabled ? <Link class="navItem" to="/workspace">Workspace</Link> : null}
          <Link class="navItem" to="/settings">Settings</Link>
          {isAdmin ? <Link class="navItem" to="/admin">Admin</Link> : null}
          {isAdmin ? <Link class="navItem" to="/ops">Ops</Link> : null}
        </div>
      }
      sidebar={
        auth.status === "authenticated" ? <ConversationSidebar /> : undefined
      }
    >
      {bootError ? (
        <div class="banner error" role="alert" data-testid="backend-error-banner">
          <span>{bootError}</span>
          <button
            class="btn"
            data-testid="backend-error-retry"
            disabled={bootRetrying}
            onClick={() => void retryBackendCheck()}
            style="margin-left:12px;"
          >
            {bootRetrying ? "Retrying..." : "Retry"}
          </button>
        </div>
      ) : null}
      {auth.lastError ? <Banner kind="error" text={auth.lastError} /> : null}

      {r.name === "login" && <LoginRoute />}
      {r.name === "chat" && auth.status === "authenticated" && <ChatRoute threadId={r.threadId} />}
      {r.name === "workspace" && auth.status === "authenticated" ? (
        workspaceEnabled ? (
          <WorkspaceRoute projectId={r.projectId} />
        ) : (
          <ErrorScreen title="Workspace Disabled" detail="Workspace feature is not enabled." />
        )
      ) : null}
      {r.name === "settings" && auth.status === "authenticated" && <SettingsRoute />}

      {r.name === "admin" && auth.status === "authenticated" ? (
        isAdmin ? <AdminRoute /> : <ErrorScreen title="Forbidden" detail="Admin role required." />
      ) : null}

      {r.name === "ops" && auth.status === "authenticated" ? (
        isAdmin ? <OpsRoute /> : <ErrorScreen title="Forbidden" detail="Admin role required." />
      ) : null}
    </Layout>
  );
}
