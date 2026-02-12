import { endpoints } from "../api/endpoints";
import { requestSession, toApiError } from "../api/client";

export type Project = {
  id: string;
  name: string;
  instructions: string | null;
  created_at: string;
  updated_at: string;
};

export async function listProjects(): Promise<Project[]> {
  const url = endpoints.projects?.[0] ?? "/v1/projects";
  const res = await requestSession(url, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw await toApiError(res, "server_error", `List projects failed (${res.status})`);
  }
  return (await res.json()) as Project[];
}
