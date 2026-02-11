import { beforeEach, describe, expect, it, vi } from "vitest";
import { SSEBackendAdapter } from "./SSEBackendAdapter";
import { setRuntimeConfig } from "../config/runtimeConfig";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
}

describe("SSEBackendAdapter.streamRun", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setRuntimeConfig({ BACKEND_BASE_URL: "http://localhost:8000" });
  });

  it("streams canonical message delta and done", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(
          streamFromChunks([
            "event: message\ndata: {\"type\":\"delta\",\"content\":\"Hello\"}\n\n",
            "event: done\ndata: {\"status\":\"completed\"}\n\n",
          ]),
          { status: 200, headers: { "Content-Type": "text/event-stream" } }
        )
      )
    );

    const adapter = new SSEBackendAdapter();
    const out: string[] = [];
    const metas: unknown[] = [];
    for await (const chunk of adapter.streamRun({
      runId: "r1",
      signal: new AbortController().signal,
    })) {
      if (chunk.type === "delta") out.push(chunk.delta);
      if (chunk.type === "meta") metas.push(chunk.meta);
    }
    expect(out.join("")).toBe("Hello");
    expect(metas).toEqual([]);
  });

  it("handles ping/comments and chunk boundaries", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(
          streamFromChunks([
            ": ping\n\n",
            "event: message\ndata: {\"type\":\"delta\",\"content\":\"A\"",
            "}\n\n",
            "data: [DONE]\n\n",
          ]),
          { status: 200 }
        )
      )
    );

    const adapter = new SSEBackendAdapter();
    const out: string[] = [];
    for await (const chunk of adapter.streamRun({
      runId: "r2",
      signal: new AbortController().signal,
    })) {
      if (chunk.type === "delta") out.push(chunk.delta);
    }
    expect(out.join("")).toBe("A");
  });

  it("emits meta for full message and run identifiers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(
          streamFromChunks([
            "id: 41\nevent: message\ndata: {\"type\":\"full\",\"content\":\"Final\",\"message_id\":\"m_asst_1\",\"source_message_id\":\"m_user_1\",\"conversation_id\":\"c1\"}\n\n",
            "id: 42\nevent: done\ndata: {\"status\":\"completed\",\"run_id\":\"r1\"}\n\n",
          ]),
          { status: 200 }
        )
      )
    );
    const adapter = new SSEBackendAdapter();
    const metas: Array<Record<string, unknown>> = [];
    for await (const chunk of adapter.streamRun({
      runId: "r1",
      signal: new AbortController().signal,
    })) {
      if (chunk.type === "meta") metas.push(chunk.meta as Record<string, unknown>);
    }
    expect(metas.some((m) => m.resultMessageId === "m_asst_1")).toBeTruthy();
    expect(metas.some((m) => m.sourceMessageId === "m_user_1")).toBeTruthy();
    expect(metas.some((m) => m.conversationId === "c1")).toBeTruthy();
    expect(metas.some((m) => m.backendRunId === "r1")).toBeTruthy();
    expect(metas.some((m) => m.eventSeq === 41)).toBeTruthy();
    expect(metas.some((m) => m.eventSeq === 42)).toBeTruthy();
  });

  it("throws on invalid typed metadata fields", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(
          streamFromChunks([
            "event: message\ndata: {\"type\":\"delta\",\"content\":\"x\",\"message_id\":123}\n\n",
          ]),
          { status: 200 }
        )
      )
    );
    const adapter = new SSEBackendAdapter();
    const collect = async () => {
      for await (const _ of adapter.streamRun({ runId: "rX", signal: new AbortController().signal })) {
        // no-op
      }
    };
    await expect(collect()).rejects.toThrow("Metadata field present with invalid type.");
  });
});
