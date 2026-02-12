import { endpoints } from "../api/endpoints";
import { clearCsrfToken } from "../api/csrf";
import { tryPaths } from "../api/http";
import { getMeta } from "../meta/metaApi";
import { requestMutating, toApiError } from "../api/client";

export type { MetaResponse } from "../meta/metaApi";
export { getMeta };

export async function login(body: { username: string; password: string; invite_code?: string }) {
  return tryPaths(endpoints.login, async (url) => {
    const res = await requestMutating(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      if (res.status === 403) clearCsrfToken();
      throw await toApiError(res, "server_error", `Login failed (${res.status})`);
    }
    return await res.json().catch(() => ({}));
  });
}

export async function logout() {
  return tryPaths(endpoints.logout, async (url) => {
    const res = await requestMutating(url, {
      method: "POST",
      headers: {
        "Accept": "application/json"
      },
    });

    return res.ok;
  });
}
