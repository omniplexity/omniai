import { describe, expect, it } from "vitest";
import { parseSSE } from "./sseParser";

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

async function collect(chunks: string[]) {
  const reader = streamFromChunks(chunks).getReader();
  const out: Array<{ id?: string; event?: string; data: string }> = [];
  for await (const evt of parseSSE(reader)) out.push(evt);
  return out;
}

describe("sseParser", () => {
  it("handles multiline data + comments + done sentinel", async () => {
    const events = await collect([
      ": ping\n",
      "id: 7\n",
      "event: message\n",
      "data: line1\n",
      "data: line2\n\n",
      "data: [DONE]\n\n",
    ]);
    expect(events).toEqual([
      { id: "7", event: "message", data: "line1\nline2" },
      { data: "[DONE]" },
    ]);
  });

  it("handles arbitrary chunk boundaries and multiple events", async () => {
    const events = await collect([
      "data: {\"type\":\"delta\",\"delta\":\"hel",
      "lo\"}\n\n",
      "data: {\"type\":\"delta\",\"delta\":\" world\"}\n\n",
    ]);
    expect(events).toEqual([
      { data: '{"type":"delta","delta":"hello"}' },
      { data: '{"type":"delta","delta":" world"}' },
    ]);
  });

  it("accepts non-numeric id without failing parser", async () => {
    const events = await collect(["id: abc\ndata: hi\n\n"]);
    expect(events).toEqual([{ id: "abc", data: "hi" }]);
  });
});
