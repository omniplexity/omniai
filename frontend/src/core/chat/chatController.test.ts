import { describe, expect, it } from "vitest";
import {
  buildRetrySnapshot,
  createInitialControllerState,
  reduceError,
  reduceStreamChunk,
} from "./chatController";

describe("chat controller reducer", () => {
  it("appends delta chunks", () => {
    const s1 = createInitialControllerState();
    const s2 = reduceStreamChunk(s1, { type: "delta", delta: "hello " });
    const s3 = reduceStreamChunk(s2, { type: "delta", delta: "world" });
    expect(s3.assistantDraft).toBe("hello world");
    expect(s3.isStreaming).toBe(true);
  });

  it("finalizes on done", () => {
    const s1 = reduceStreamChunk(createInitialControllerState(), { type: "delta", delta: "hello" });
    const s2 = reduceStreamChunk(s1, { type: "done" });
    expect(s2.isStreaming).toBe(false);
    expect(s2.isStopped).toBe(true);
  });

  it("captures deterministic retry snapshot", () => {
    const snapshot = buildRetrySnapshot({
      threadId: "thread-1",
      input: "hello",
      retryFromMessageId: "msg-1",
      settings: {
        provider: "lmstudio",
        model: "model-a",
        settings: { temperature: 0.2, top_p: 0.9, max_tokens: 200 },
      },
    });
    expect(snapshot.threadId).toBe("thread-1");
    expect(snapshot.retryFromMessageId).toBe("msg-1");
    expect(snapshot.settings.settings).toEqual({ temperature: 0.2, top_p: 0.9, max_tokens: 200 });
  });

  it("marks errors distinctly", () => {
    const s1 = reduceError(createInitialControllerState(), "failed");
    expect(s1.hasError).toBe(true);
    expect(s1.errorMessage).toBe("failed");
    expect(s1.isStreaming).toBe(false);
  });
});
