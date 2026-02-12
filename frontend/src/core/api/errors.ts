export type ApiErrorCode =
  | "network_error"
  | "timeout"
  | "unauthorized"
  | "forbidden"
  | "csrf_failed"
  | "rate_limited"
  | "server_error"
  | "unknown";

export class ApiError extends Error {
  code: ApiErrorCode;
  status?: number;
  detail?: unknown;
  backendCode?: string | null;
  requestId?: string | null;

  constructor(
    code: ApiErrorCode,
    message: string,
    status?: number,
    detail?: unknown,
    meta?: { backendCode?: string | null; requestId?: string | null }
  ) {
    super(message);
    this.code = code;
    this.status = status;
    this.detail = detail;
    this.backendCode = meta?.backendCode ?? null;
    this.requestId = meta?.requestId ?? null;
  }
}
