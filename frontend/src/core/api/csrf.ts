import { getRuntimeConfig } from "../../config/runtimeConfig";
import {
  clearCsrfTokenCache,
  getCsrfToken as getToken,
} from "./client";

let _csrfToken: string | null = null;

export function getCsrfToken(): string | null {
  return _csrfToken;
}

export function clearCsrfToken() {
  _csrfToken = null;
  clearCsrfTokenCache();
}

export async function ensureCsrfToken(): Promise<void> {
  if (_csrfToken) return;
  const baseUrl = getRuntimeConfig().BACKEND_BASE_URL;
  _csrfToken = await getToken(baseUrl);
}
