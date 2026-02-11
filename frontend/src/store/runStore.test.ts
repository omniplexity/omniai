import { beforeEach, describe, expect, it } from "vitest";
import { runStore } from "./runStore";

describe("runStore", () => {
  beforeEach(() => {
    runStore.actions.reset();
  });

  it("tracks run lifecycle and cancellation state", () => {
    const runId = runStore.actions.createRun({
      requestMessages: [{ role: "user", content: "hello" }],
    });
    runStore.actions.startRun(runId, "asst_1");
    runStore.actions.markDelta(runId);
    runStore.actions.markCancelled(runId);

    const st = runStore.getState();
    expect(st.activeRunId).toBeNull();
    expect(st.runsById[runId]?.status).toBe("cancelled");
    expect(st.runsById[runId]?.errorCode).toBe("E_CANCELLED");
  });

  it("preserves immutable request snapshot and retry lineage", () => {
    const source = [{ role: "user" as const, content: "first" }];
    const runA = runStore.actions.createRun({ requestMessages: source });
    const first = source[0];
    if (!first) throw new Error("missing source message");
    first.content = "mutated";

    const runASnapshot = runStore.getState().runsById[runA]?.requestMessages;
    expect(runASnapshot?.[0]?.content).toBe("first");

    const runB = runStore.actions.createRun({
      requestMessages: runASnapshot ?? [],
      retryOfRunId: runA,
    });
    expect(runStore.getState().runsById[runB]?.retryOfRunId).toBe(runA);
  });

  it("tracks result message id and pending/backend message mapping", () => {
    const runId = runStore.actions.createRun({
      requestMessages: [{ role: "user", content: "hello" }],
      sourceMessageId: "local_u1",
    });
    runStore.actions.startRun(runId, "local_a1");
    runStore.actions.markMessagePending("local_u1", true, runId);
    runStore.actions.attachMessageBackendId("local_u1", "backend_u1");
    runStore.actions.attachResultMessageId(runId, "backend_a1");
    runStore.actions.attachMessageBackendId("local_a1", "backend_a1");

    const st = runStore.getState();
    expect(st.runsById[runId]?.resultMessageId).toBe("backend_a1");
    expect(st.messageMetaById["local_u1"]?.backendMessageId).toBe("backend_u1");
    expect(st.messageMetaById["local_u1"]?.pending).toBe(false);
  });

  it("tracks event sequence monotonically for run and message metadata", () => {
    const runId = runStore.actions.createRun({
      requestMessages: [{ role: "user", content: "hello" }],
      sourceMessageId: "local_u1",
    });
    runStore.actions.startRun(runId, "local_a1");
    runStore.actions.markMessagePending("local_u1", true, runId);
    runStore.actions.attachEventSeq(runId, 10);
    runStore.actions.attachEventSeq(runId, 7);
    runStore.actions.attachEventSeq(runId, 12);
    runStore.actions.attachMessageEventSeq("local_u1", 11);
    runStore.actions.attachMessageEventSeq("local_u1", 9);

    const st = runStore.getState();
    expect(st.runsById[runId]?.firstEventSeq).toBe(10);
    expect(st.runsById[runId]?.lastEventSeq).toBe(12);
    expect(st.messageMetaById["local_u1"]?.eventSeq).toBe(11);
  });
});
