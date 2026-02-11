import { describe, expect, it } from "vitest";
import { parseSSE } from "./sseParser";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function collect(chunks: string[]) {
  const out: Array<{ id?: string; event?: string; data: string }> = [];
  const reader = streamFromChunks(chunks).getReader();
  for await (const evt of parseSSE(reader)) out.push(evt);
  return out;
}

describe("sseParser contract", () => {
  it("parses multiline data with typed event", async () => {
    const events = await collect([
      "id: 12\n",
      "event: message\n",
      "data: line A\n",
      "data: line B\n\n",
    ]);
    expect(events).toEqual([{ id: "12", event: "message", data: "line A\nline B" }]);
  });

  it("keeps non-numeric id as raw string", async () => {
    const events = await collect(["id: run-abc\ndata: hello\n\n"]);
    expect(events).toEqual([{ id: "run-abc", data: "hello" }]);
  });

  it("handles comments and split chunk boundaries", async () => {
    const events = await collect([
      ": ping\n\n",
      "event: message\ndata: {\"type\":\"delta\",\"content\":\"hel",
      "lo\"}\n\n",
      "data: [DONE]\n\n",
    ]);
    expect(events).toEqual([
      { event: "message", data: "{\"type\":\"delta\",\"content\":\"hello\"}" },
      { data: "[DONE]" },
    ]);
  });

  it("parses multiple typed events inside a single chunk", async () => {
    const events = await collect([
      "event: message\ndata: {\"type\":\"delta\",\"content\":\"A\"}\n\nevent: ping\ndata: {}\n\n",
    ]);
    expect(events).toEqual([
      { event: "message", data: "{\"type\":\"delta\",\"content\":\"A\"}" },
      { event: "ping", data: "{}" },
    ]);
  });
});
