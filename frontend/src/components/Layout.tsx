import { useEffect, useState } from "preact/hooks";
import { authStore, doLogout } from "../core/auth/authStore";
import { uiPrefsStore } from "../core/prefs/uiPrefsStore";
import { SettingsDrawer } from "./SettingsDrawer";

function useStore<T>(store: { get: () => T; subscribe: (fn: () => void) => () => void }) {
  const [v, setV] = useState(store.get());
  useEffect(() => store.subscribe(() => setV(store.get())), []);
  return v;
}

export function Layout(props: { nav: any; children: any; sidebar?: any }) {
  const auth = useStore(authStore);
  const prefs = useStore(uiPrefsStore);
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div class="shell">
      <aside class="sidebar">
        <div class="brandRow">
          <div class="brand">OmniAI</div>
          <div class={`pill ${auth.status}`}>{auth.status}</div>
        </div>

        {props.sidebar ? (
          <div class="sidebarContent">
            {props.sidebar}
          </div>
        ) : (
          props.nav
        )}

        <div class="sidebarFooter muted">
          {auth.status === "authenticated" ? (
            <button class="btn" onClick={() => void doLogout()}>Logout</button>
          ) : null}
        </div>
      </aside>

      <main class="main">
        <div class="topbar">
          <div class="topbarTitle">OmniAI</div>
          <div class="topbarRight">
            <div class="topbarBadge mono">
              {prefs.providerId ?? "Auto"} / {prefs.modelId ?? "Auto"}
            </div>
            <button class="btn" onClick={() => setDrawerOpen(true)} aria-label="Open settings">
              ⚙
            </button>
          </div>
        </div>

        <div class="content">{props.children}</div>

        <SettingsDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      </main>
    </div>
  );
}
