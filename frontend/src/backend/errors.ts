import { ChatProtocolError } from "./SSEBackendAdapter";

export type UiErrorCode =
  | "E_AUTH"
  | "E_CSRF"
  | "E_RATE_LIMIT"
  | "E_BACKEND"
  | "E_NETWORK"
  | "E_PROTOCOL"
  | "E_CANCELLED";

export type UiError = {
  code: UiErrorCode;
  message: string;
};

export function toUiError(err: unknown): UiError {
  const e = err as { name?: string; message?: string; code?: string; status?: number };

  if (e?.name === "AbortError") {
    return { code: "E_CANCELLED", message: "Response cancelled by user." };
  }

  if (err instanceof ChatProtocolError) {
    if (err.backendCode === "E2002") {
      return { code: "E_CSRF", message: "Session security token mismatch. Refresh and try again." };
    }
    if (err.backendCode === "E2003" || err.backendCode === "E2004") {
      return { code: "E_AUTH", message: "Origin/session policy blocked the request. Sign in again." };
    }
    if (err.code === "backend_http_error") {
      const status = err.status ?? extractStatus(err.message);
      if (status === 401 || status === 403) {
        return { code: "E_AUTH", message: "Session expired or unauthorized." };
      }
      if (status === 429) {
        return { code: "E_RATE_LIMIT", message: "Rate limit exceeded." };
      }
      if (status !== null && status >= 500) {
        return { code: "E_BACKEND", message: "Backend temporarily unavailable." };
      }
      return { code: "E_BACKEND", message: err.message };
    }
    return { code: "E_PROTOCOL", message: err.message };
  }

  if (e?.name === "TypeError") {
    return { code: "E_NETWORK", message: "Network connection failed." };
  }

  if (typeof e?.status === "number") {
    if (e.status === 401 || e.status === 403) {
      return { code: "E_AUTH", message: "Session expired or unauthorized." };
    }
    if (e.status === 429) {
      return { code: "E_RATE_LIMIT", message: "Rate limit exceeded." };
    }
    if (e.status >= 500) {
      return { code: "E_BACKEND", message: "Backend temporarily unavailable." };
    }
  }

  if (err instanceof Error) {
    if (/stream timed out waiting for events/i.test(err.message ?? "")) {
      return { code: "E_NETWORK", message: "Stream timed out waiting for events." };
    }
    return { code: "E_BACKEND", message: err.message || "Unknown backend error." };
  }

  return { code: "E_BACKEND", message: "Unknown backend error." };
}

function extractStatus(message: string): number | null {
  const m = message.match(/\((\d{3})\)/);
  if (!m) return null;
  return Number(m[1]);
}
