import { useState } from "preact/hooks";
import { Banner } from "../components/Banner";
import { getRuntimeConfig } from "../core/config/runtimeConfig";
import { doLogin, authStore, hydrateAuth } from "../core/auth/authStore";
import { navigate } from "../core/router/hashRouter";

export function LoginRoute() {
  const cfg = getRuntimeConfig();

  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [invite, setI] = useState("");

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onSubmit(e: Event) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await doLogin({
        username: username.trim(),
        password,
        invite_code: invite.trim() || undefined
      });
      const a = authStore.get();
      if (a.status === "authenticated") navigate("/chat");
      else setErr("Login did not establish a session (check cookies / backend auth).");
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function onRefreshSession() {
    setErr(null);
    setBusy(true);
    try {
      await hydrateAuth();
      const a = authStore.get();
      if (a.status === "authenticated") navigate("/chat");
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div class="page pad">
      <div class="card wide">
        <h1 class="h1">Login</h1>
        <p class="muted">Cookie session + CSRF protected login (invite-only).</p>

        <div class="kv">
          <div class="k">BACKEND_BASE_URL</div>
          <div class="v mono">{cfg.BACKEND_BASE_URL}</div>
        </div>

        {err ? <Banner kind="error" text={err} /> : null}

        <form class="form" onSubmit={onSubmit}>
          <label class="label" for="u">Username</label>
          <input id="u" class="input" value={username} onInput={(e) => setU((e.target as HTMLInputElement).value)} />

          <label class="label" for="p">Password</label>
          <input id="p" class="input" type="password" value={password} onInput={(e) => setP((e.target as HTMLInputElement).value)} />

          <label class="label" for="i">Invite code (optional)</label>
          <input id="i" class="input" value={invite} onInput={(e) => setI((e.target as HTMLInputElement).value)} />

          <div class="row">
            <button class="btn primary" disabled={busy || !username.trim() || !password}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
            <button type="button" class="btn" disabled={busy} onClick={() => void onRefreshSession()}>
              Refresh session
            </button>
          </div>
        </form>

        <p class="muted" style="margin-top:12px;">
          All requests go to the OmniAI backend only; no provider endpoints are contacted from the client.
        </p>
      </div>
    </div>
  );
}
