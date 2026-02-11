import { describe, expect, it } from "vitest";
import { toUiError } from "./errors";
import { ChatProtocolError } from "./SSEBackendAdapter";

describe("backend errors mapping", () => {
  it("maps E2002 as E_CSRF and E2003/E2004 as E_AUTH", () => {
    expect(
      toUiError(
        new ChatProtocolError("backend_http_error", "csrf", {
          status: 403,
          backendCode: "E2002",
        })
      )
    ).toMatchObject({ code: "E_CSRF" });
    expect(
      toUiError(
        new ChatProtocolError("backend_http_error", "origin", {
          status: 403,
          backendCode: "E2003",
        })
      )
    ).toMatchObject({ code: "E_AUTH" });
    expect(
      toUiError(
        new ChatProtocolError("backend_http_error", "missing origin", {
          status: 403,
          backendCode: "E2004",
        })
      )
    ).toMatchObject({ code: "E_AUTH" });
  });

  it("maps auth/rate/backends from protocol HTTP errors", () => {
    expect(toUiError(new ChatProtocolError("backend_http_error", "Backend error (401): no")))
      .toMatchObject({ code: "E_AUTH" });
    expect(toUiError(new ChatProtocolError("backend_http_error", "Backend error (429): slow")))
      .toMatchObject({ code: "E_RATE_LIMIT" });
    expect(toUiError(new ChatProtocolError("backend_http_error", "Backend error (503): down")))
      .toMatchObject({ code: "E_BACKEND" });
  });

  it("maps cancellation/network/protocol", () => {
    expect(toUiError(new DOMException("Aborted", "AbortError"))).toMatchObject({
      code: "E_CANCELLED",
    });
    expect(toUiError(new TypeError("Failed to fetch"))).toMatchObject({
      code: "E_NETWORK",
    });
    expect(toUiError(new ChatProtocolError("backend_parse_error", "bad"))).toMatchObject({
      code: "E_PROTOCOL",
    });
  });

  it("maps watchdog timeout as E_NETWORK", () => {
    expect(toUiError(new Error("Stream timed out waiting for events."))).toMatchObject({
      code: "E_NETWORK",
    });
  });
});
