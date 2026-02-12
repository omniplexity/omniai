import { endpoints } from "../api/endpoints";
import { ApiError } from "../api/errors";
import { ensureCsrfToken, getCsrfToken, clearCsrfToken } from "../api/csrf";
import { classifyHttpError, fetchWithTimeout, readErrorBody, tryPaths } from "../api/http";
import { getMeta } from "../meta/metaApi";

export type { MetaResponse } from "../meta/metaApi";
export { getMeta };

export async function login(body: { username: string; password: string; invite_code?: string }) {
  await ensureCsrfToken();

  return tryPaths(endpoints.login, async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": getCsrfToken() ?? ""
      },
      body: JSON.stringify(body),
      timeoutMs: 30000
    });

    if (!res.ok) {
      if (res.status === 403 || res.status === 419) clearCsrfToken();
      const bodyText = await readErrorBody(res);
      throw classifyHttpError(res) instanceof ApiError
        ? new ApiError(classifyHttpError(res).code, `Login failed (${res.status})`, res.status, bodyText)
        : new ApiError("unknown", `Login failed (${res.status})`, res.status, bodyText);
    }
    return await res.json().catch(() => ({}));
  });
}

export async function logout() {
  await ensureCsrfToken();

  return tryPaths(endpoints.logout, async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Accept": "application/json",
        "X-CSRF-Token": getCsrfToken() ?? ""
      },
      timeoutMs: 15000
    });

    return res.ok;
  });
}
