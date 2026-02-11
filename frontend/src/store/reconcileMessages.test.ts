import { describe, expect, it } from "vitest";
import { reconcileMessages } from "./reconcileMessages";
import type { RunState } from "./runStore";

function baseRunState(): RunState {
  return {
    activeRunId: null,
    lastRunId: null,
    runsById: {},
    messageMetaById: {},
  };
}

describe("reconcileMessages", () => {
  it("uses server ordering and drops duplicate mapped locals", () => {
    const out = reconcileMessages({
      localMessages: [
        { id: "l1", role: "user", content: "Hello", timestamp: "2026-01-01T00:00:00.000Z" },
        { id: "l2", role: "assistant", content: "World", timestamp: "2026-01-01T00:00:01.000Z" },
      ],
      serverMessages: [
        { id: "b1", role: "user", content: "Hello", created_at: "2026-01-01T00:00:00.000Z" },
        { id: "b2", role: "assistant", content: "World", created_at: "2026-01-01T00:00:02.000Z" },
      ],
      runState: {
        ...baseRunState(),
        messageMetaById: {
          l1: { runId: "r1", backendMessageId: "b1", pending: false },
          l2: { runId: "r1", backendMessageId: "b2", pending: false },
        },
      },
    });
    expect(out.map((m) => m.id)).toEqual(["b1", "b2"]);
  });

  it("keeps recent pending optimistic messages not yet on server", () => {
    const out = reconcileMessages({
      localMessages: [
        { id: "l1", role: "user", content: "Pending text", timestamp: "2026-01-01T00:00:03.000Z" },
      ],
      serverMessages: [],
      runState: {
        ...baseRunState(),
        messageMetaById: {
          l1: { runId: "r1", pending: true },
        },
      },
      nowMs: Date.parse("2026-01-01T00:00:05.000Z"),
    });
    expect(out.map((m) => m.id)).toEqual(["l1"]);
  });

  it("keeps unmatched local messages for failed runs", () => {
    const out = reconcileMessages({
      localMessages: [
        { id: "l1", role: "user", content: "Failed send", timestamp: "2026-01-01T00:00:03.000Z" },
      ],
      serverMessages: [],
      runState: {
        ...baseRunState(),
        runsById: {
          r1: {
            id: "r1",
            status: "error",
            requestMessages: [],
            resultAssistantMessageId: null,
            receivedAnyDelta: false,
          },
        },
        messageMetaById: {
          l1: { runId: "r1", pending: false },
        },
      },
    });
    expect(out.map((m) => m.id)).toEqual(["l1"]);
  });

  it("uses local sequence metadata before server order/signature fallback", () => {
    const out = reconcileMessages({
      localMessages: [
        { id: "l1", role: "assistant", content: "Second", timestamp: "2026-01-01T00:00:03.000Z" },
        { id: "l2", role: "assistant", content: "First", timestamp: "2026-01-01T00:00:02.000Z" },
      ],
      serverMessages: [
        { id: "b2", role: "assistant", content: "First", created_at: "2026-01-01T00:00:02.000Z" },
        { id: "b1", role: "assistant", content: "Second", created_at: "2026-01-01T00:00:03.000Z" },
      ],
      runState: {
        ...baseRunState(),
        messageMetaById: {
          l1: { runId: "r1", backendMessageId: "b1", eventSeq: 2, pending: false },
          l2: { runId: "r1", backendMessageId: "b2", eventSeq: 1, pending: false },
        },
      },
    });
    expect(out.map((m) => m.id)).toEqual(["b2", "b1"]);
  });
});
