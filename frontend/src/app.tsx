import { useEffect, useState } from "preact/hooks";
import type { RuntimeConfig } from "./core/config/runtimeConfig";
import { setRuntimeConfig } from "./core/config/runtimeConfig";
import { getFlags, setFlagsFromRuntime } from "./core/config/featureFlags";
import { useHashLocation, Link } from "./core/router/hashRouter";
import { Layout } from "./components/Layout";
import { ErrorScreen } from "./components/ErrorScreen";
import { Banner } from "./components/Banner";

import { LoginRoute } from "./routes/login";
import { ChatRoute } from "./routes/chat";
import { SettingsRoute } from "./routes/settings";
import { AdminRoute } from "./routes/admin";
import { OpsRoute } from "./routes/ops";

import { authStore, hydrateAuth } from "./core/auth/authStore";
import { ConversationSidebar } from "./components/ConversationSidebar";

function parseRoute(path: string): { name: string; threadId?: string } {
  const clean = path.split("?")[0].split("#")[0];
  if (clean === "/" || clean === "") return { name: "login" };
  if (clean === "/login") return { name: "login" };
  if (clean === "/settings") return { name: "settings" };
  if (clean === "/admin") return { name: "admin" };
  if (clean === "/ops") return { name: "ops" };
  if (clean.startsWith("/chat")) {
    const parts = clean.split("/").filter(Boolean);
    return { name: "chat", threadId: parts[1] };
  }
  return { name: "login" };
}

function routeRequiresAuth(name: string): boolean {
  return name === "chat" || name === "settings" || name === "admin" || name === "ops";
}

export function App(props: { runtimeConfig: RuntimeConfig }) {
  setRuntimeConfig(props.runtimeConfig);
  setFlagsFromRuntime(props.runtimeConfig);
  const flags = getFlags();

  const [path] = useHashLocation();
  const r = parseRoute(path);

  const [auth, setAuth] = useState(authStore.get());
  useEffect(() => authStore.subscribe(() => setAuth(authStore.get())), []);

  useEffect(() => {
    void hydrateAuth();
  }, []);

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
          <Link class="navItem" to="/settings">Settings</Link>
          <Link class="navItem" to="/admin">Admin</Link>
          {flags.adminOps ? <Link class="navItem" to="/ops">Ops</Link> : null}
        </div>
      }
      sidebar={
        auth.status === "authenticated" ? <ConversationSidebar /> : undefined
      }
    >
      {auth.lastError ? <Banner kind="error" text={auth.lastError} /> : null}

      {r.name === "login" && <LoginRoute />}
      {r.name === "chat" && auth.status === "authenticated" && <ChatRoute threadId={r.threadId} />}
      {r.name === "settings" && auth.status === "authenticated" && <SettingsRoute />}

      {r.name === "admin" && auth.status === "authenticated" ? (
        isAdmin ? <AdminRoute /> : <ErrorScreen title="Forbidden" detail="Admin role required." />
      ) : null}

      {r.name === "ops" && auth.status === "authenticated" ? (
        flags.adminOps ? (isAdmin ? <OpsRoute /> : <ErrorScreen title="Forbidden" detail="Admin role required." />)
                      : <ErrorScreen title="Not enabled" detail="Ops is disabled by feature flag." />
      ) : null}
    </Layout>
  );
}
