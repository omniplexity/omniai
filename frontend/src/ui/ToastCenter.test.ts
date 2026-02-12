import { h } from "preact";
import render from "preact-render-to-string";
import { beforeEach, describe, expect, it } from "vitest";
import { ToastCenter } from "./ToastCenter";
import { clearToasts, pushToast } from "./toastStore";

describe("ToastCenter", () => {
  beforeEach(() => {
    clearToasts();
  });

  it("renders backend code and request id metadata when present", () => {
    pushToast({
      message: "Request failed",
      backendCode: "E2002",
      requestId: "req-123",
    });

    const html = render(h(ToastCenter, {}));
    expect(html).toContain("Request failed");
    expect(html).toContain("code=E2002");
    expect(html).toContain("request_id=req-123");
  });
});
