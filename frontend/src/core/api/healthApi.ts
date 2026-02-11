import { endpoints } from "./endpoints";
import { fetchWithTimeout, tryPaths } from "./http";

export type HealthStatus = {
  status?: string;
  build_sha?: string;
  build_time?: string;
  environment?: string;
};

export async function getHealthStatus(): Promise<HealthStatus> {
  return tryPaths(endpoints.health, async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
      timeoutMs: 10000
    });
    if (!res.ok) {
      throw new Error(`Health request failed (${res.status})`);
    }
    return (await res.json()) as HealthStatus;
  });
}
