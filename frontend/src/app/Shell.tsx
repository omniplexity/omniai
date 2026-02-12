import { useEffect, useState } from "preact/hooks";
import { authStore, doLogout } from "../core/auth/authStore";
import { uiPrefsStore } from "../core/prefs/uiPrefsStore";
import { metaStore } from "../core/meta/metaStore";
import { SettingsDrawer } from "../components/SettingsDrawer";

function useStore<T>(store: { get: () => T; subscribe: (fn: () => void) => () => void }) {
  const [value, setValue] = useState(store.get());
  useEffect(() => store.subscribe(() => setValue(store.get())), []);
  return value;
}

export function Shell(props: { left?: any; main: any; right?: any }) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const auth = useStore(authStore);
  const prefs = useStore(uiPrefsStore);
  const meta = useStore(metaStore);

  return (
    <div class="shell appShell" data-testid="app-shell">
      <aside class="sidebar appShellLeft">{props.left}</aside>
      <main class="main appShellMain">
        <div class="topbar appShellTopbar">
          <div>
            <div class="topbarTitle">OmniAI</div>
            <div class="muted appShellMetaLine" data-testid="app-shell-meta">
              env={meta.environment} model={prefs.modelId ?? "auto"}
            </div>
          </div>
          <div class="topbarRight">
            <div class="topbarBadge mono" data-testid="app-shell-model-badge">
              {prefs.providerId ?? "auto"} / {prefs.modelId ?? "auto"}
            </div>
            <button class="btn" onClick={() => setDrawerOpen(true)} aria-label="Open settings">
              ⚙
            </button>
          </div>
        </div>
        <div class="content">{props.main}</div>
      </main>
      {props.right ? <aside class="sidebar appShellRight">{props.right}</aside> : null}
      <SettingsDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
      {auth.status === "authenticated" ? (
        <button class="btn appShellLogout" onClick={() => void doLogout()} data-testid="shell-logout">
          Logout
        </button>
      ) : null}
    </div>
  );
}
