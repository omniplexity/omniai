import { describe, expect, it, vi } from "vitest";
import { useChatStream } from "./useChatStream";
import type { ChatApiAdapter } from "../../backend/ChatApiAdapter";

function createAdapter(): ChatApiAdapter {
  return {
    createRun: vi.fn().mockResolvedValue({ runId: "run-1", status: "running" }),
    streamRun: vi.fn().mockImplementation(async function* () {
      yield { type: "delta", delta: "A" as const };
      yield { type: "done" as const };
    }),
    cancelRun: vi.fn().mockResolvedValue(undefined),
  };
}

describe("useChatStream orchestration", () => {
  it("retries with the same snapshot settings", async () => {
    const adapter = createAdapter();
    const stream = useChatStream(adapter);
    const chunks: string[] = [];

    await stream.start({
      threadId: "thread-1",
      input: "hello",
      settings: { provider: "p1", model: "m1", settings: { temperature: 0.3 } },
      onChunk: (chunk) => {
        if (chunk.type === "delta") chunks.push(chunk.delta);
      },
    });
    await stream.retry((chunk) => {
      if (chunk.type === "delta") chunks.push(chunk.delta);
    });

    expect((adapter.createRun as any).mock.calls).toHaveLength(2);
    expect((adapter.createRun as any).mock.calls[1][0].settings).toEqual({ temperature: 0.3 });
    expect((adapter.createRun as any).mock.calls[1][0].provider).toBe("p1");
    expect((adapter.createRun as any).mock.calls[1][0].model).toBe("m1");
  });

  it("applies new settings on next send", async () => {
    const adapter = createAdapter();
    const stream = useChatStream(adapter);

    await stream.start({
      threadId: "thread-1",
      input: "hello",
      settings: { provider: "p1", model: "m1", settings: { temperature: 0.3 } },
      onChunk: () => undefined,
    });
    await stream.start({
      threadId: "thread-1",
      input: "hello again",
      settings: { provider: "p1", model: "m1", settings: { temperature: 0.8 } },
      onChunk: () => undefined,
    });

    expect((adapter.createRun as any).mock.calls[1][0].settings).toEqual({ temperature: 0.8 });
  });

  it("cancel calls adapter cancel immediately", async () => {
    const adapter = createAdapter();
    const stream = useChatStream(adapter);
    await stream.start({
      threadId: "thread-1",
      input: "hello",
      settings: { settings: {} },
      onChunk: () => undefined,
    });
    stream.cancel();
    expect(adapter.cancelRun).toHaveBeenCalledTimes(1);
  });
});
