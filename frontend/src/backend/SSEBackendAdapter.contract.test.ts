import { beforeEach, describe, expect, it, vi } from "vitest";
import { SSEBackendAdapter } from "./SSEBackendAdapter";
import { setRuntimeConfig } from "../config/runtimeConfig";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

describe("SSEBackendAdapter contract", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setRuntimeConfig({ BACKEND_BASE_URL: "http://localhost:8000" });
  });

  it("emits numeric eventSeq for numeric SSE ids", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(
          streamFromChunks([
            "id: 33\nevent: message\ndata: {\"type\":\"delta\",\"content\":\"ok\"}\n\n",
            "event: done\ndata: {\"status\":\"completed\"}\n\n",
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
    expect(metas.some((m) => m.eventSeq === 33)).toBeTruthy();
  });

  it("ignores non-numeric SSE id for eventSeq while still streaming", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(
          streamFromChunks([
            "id: run-abc\nevent: message\ndata: {\"type\":\"delta\",\"content\":\"hello\"}\n\n",
            "event: done\ndata: {\"status\":\"completed\"}\n\n",
          ]),
          { status: 200 }
        )
      )
    );
    const adapter = new SSEBackendAdapter();
    const deltas: string[] = [];
    const metas: Array<Record<string, unknown>> = [];
    for await (const chunk of adapter.streamRun({
      runId: "r2",
      signal: new AbortController().signal,
    })) {
      if (chunk.type === "delta") deltas.push(chunk.delta);
      if (chunk.type === "meta") metas.push(chunk.meta as Record<string, unknown>);
    }
    expect(deltas.join("")).toBe("hello");
    expect(metas.every((m) => !("eventSeq" in m))).toBeTruthy();
  });

  it("supports [DONE] terminal sentinel", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(
          streamFromChunks([
            "event: message\ndata: {\"type\":\"delta\",\"content\":\"ok\"}\n\n",
            "data: [DONE]\n\n",
          ]),
          { status: 200 }
        )
      )
    );
    const adapter = new SSEBackendAdapter();
    const out: string[] = [];
    for await (const chunk of adapter.streamRun({
      runId: "r3",
      signal: new AbortController().signal,
    })) {
      if (chunk.type === "delta") out.push(chunk.delta);
    }
    expect(out.join("")).toBe("ok");
  });

  it("handles absent, non-numeric and numeric ids in one stream", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        new Response(
          streamFromChunks([
            "event: message\ndata: {\"type\":\"delta\",\"content\":\"a\"}\n\n",
            "id: run-1\nevent: message\ndata: {\"type\":\"delta\",\"content\":\"b\"}\n\n",
            "id: 9\nevent: message\ndata: {\"type\":\"delta\",\"content\":\"c\"}\n\n",
            "event: done\ndata: {\"status\":\"completed\"}\n\n",
          ]),
          { status: 200 }
        )
      )
    );
    const adapter = new SSEBackendAdapter();
    const metas: Array<Record<string, unknown>> = [];
    const out: string[] = [];
    for await (const chunk of adapter.streamRun({
      runId: "r4",
      signal: new AbortController().signal,
    })) {
      if (chunk.type === "delta") out.push(chunk.delta);
      if (chunk.type === "meta") metas.push(chunk.meta as Record<string, unknown>);
    }
    expect(out.join("")).toBe("abc");
    expect(metas.some((m) => m.eventSeq === 9)).toBeTruthy();
    expect(metas.filter((m) => "eventSeq" in m).length).toBe(1);
  });
});
