import { createStore } from "../state/store";
import * as authApi from "./authApi";
import { setFlagsFromMeta } from "../config/featureFlags";
import { applyMetaSnapshot } from "../meta/metaStore";

export type AuthStatus = "unknown" | "authenticated" | "anonymous";

export type AuthState = {
  status: AuthStatus;
  user?: { id: string; username: string; role?: string };
  role?: string;
  lastError?: string;
};

export const authStore = createStore<AuthState>({
  status: "unknown"
});

function normalizeMeta(meta: authApi.MetaResponse): { authenticated: boolean; user?: any; role?: string } {
  const authenticated =
    Boolean(meta?.authenticated ?? meta?.auth?.authenticated ?? meta?.user);

  const user = meta?.user ?? meta?.auth?.user;
  const roleFromBool = user?.is_admin === true ? "admin" : undefined;
  const role = meta?.role ?? meta?.user?.role ?? meta?.auth?.role ?? user?.role ?? roleFromBool;
  return { authenticated, user, role };
}

export async function hydrateAuth(): Promise<void> {
  authStore.patch({ status: "unknown", lastError: undefined });

  try {
    const meta = await authApi.getMeta();
    setFlagsFromMeta(meta);
    applyMetaSnapshot(meta);
    const n = normalizeMeta(meta);
    authStore.patch({
      status: n.authenticated ? "authenticated" : "anonymous",
      user: n.user,
      role: n.role
    });
  } catch (e: any) {
    const msg = String(e?.message ?? e);
    const isUnauthorized = String(e?.code ?? "").includes("unauthorized") || String(e?.status ?? "") === "401";
    authStore.patch({
      status: isUnauthorized ? "anonymous" : "anonymous",
      user: undefined,
      role: undefined,
      lastError: isUnauthorized ? undefined : msg
    });
  }
}

export async function doLogin(params: { username: string; password: string; invite_code?: string }) {
  authStore.patch({ lastError: undefined });
  await authApi.login(params);
  await hydrateAuth();
}

export async function doLogout() {
  authStore.patch({ lastError: undefined });
  await authApi.logout();
  authStore.set({ status: "anonymous" });
}
