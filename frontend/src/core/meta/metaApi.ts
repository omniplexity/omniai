import { endpoints } from "../api/endpoints";
import { ApiError } from "../api/errors";
import { fetchWithTimeout, readErrorBody, tryPaths } from "../api/http";

export type MetaResponse = {
  meta_version?: number;
  authenticated?: boolean;
  user?: { id: string; username: string; role?: string; is_admin?: boolean };
  role?: string;
  auth?: {
    authenticated?: boolean;
    role?: string;
    user?: { id: string; username: string; role?: string; is_admin?: boolean };
  };
  lanes?: Record<string, unknown>;
  features?: Record<string, unknown>;
  flags?: Record<string, unknown>;
};

export async function getMeta(): Promise<MetaResponse> {
  return tryPaths(endpoints.meta, async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
      timeoutMs: 15000
    });

    if (res.status === 401) throw new ApiError("unauthorized", "Unauthorized", 401);
    if (!res.ok) {
      const body = await readErrorBody(res);
      throw new ApiError("server_error", `Meta failed (${res.status})`, res.status, body);
    }
    return await res.json();
  });
}
