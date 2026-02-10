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

  constructor(code: ApiErrorCode, message: string, status?: number, detail?: unknown) {
    super(message);
    this.code = code;
    this.status = status;
    this.detail = detail;
  }
}
