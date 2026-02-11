export type SseFrame = { event: string; data: string };

async function readChunkWithAbort(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  signal: AbortSignal
): Promise<ReadableStreamReadResult<Uint8Array>> {
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");

  return await Promise.race([
    reader.read(),
    new Promise<never>((_, reject) => {
      const onAbort = () => {
        signal.removeEventListener("abort", onAbort);
        reject(new DOMException("Aborted", "AbortError"));
      };
      signal.addEventListener("abort", onAbort, { once: true });
    }),
  ]);
}

export async function* parseSseResponse(
  res: Response,
  signal: AbortSignal
): AsyncGenerator<SseFrame> {
  if (!res.ok || !res.body) {
    const t = await res.text().catch(() => "");
    throw new Error(`SSE HTTP ${res.status}: ${t}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");

  let buf = "";
  let event = "message";
  let data = "";

  const flush = (): SseFrame | null => {
    if (!data) return null;
    const out = { event, data: data.replace(/\n$/, "") };
    event = "message";
    data = "";
    return out;
  };

  while (true) {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");

    const { value, done } = await readChunkWithAbort(reader, signal);
    if (done) break;

    buf += decoder.decode(value, { stream: true });

    while (true) {
      const idx = buf.indexOf("\n");
      if (idx < 0) break;

      const line = buf.slice(0, idx).replace(/\r$/, "");
      buf = buf.slice(idx + 1);

      if (line === "") {
        const out = flush();
        if (out) yield out;
        continue;
      }
      if (line.startsWith(":")) continue; // comment
      if (line.startsWith("event:")) {
        event = line.slice("event:".length).trim() || "message";
        continue;
      }
      if (line.startsWith("data:")) {
        data += line.slice("data:".length).trimStart() + "\n";
        continue;
      }
      // ignore id:, retry:
    }
  }

  const out = flush();
  if (out) yield out;
}
