export type SSEEvent = {
  id?: string;
  event?: string;
  data: string;
};

export async function* parseSSE(
  reader: ReadableStreamDefaultReader<Uint8Array>
): AsyncGenerator<SSEEvent, void, void> {
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let eventId: string | undefined;
  let eventName: string | undefined;
  let dataLines: string[] = [];

  const flushEvent = (): SSEEvent | null => {
    if (dataLines.length === 0) return null;
    const evt: SSEEvent = { data: dataLines.join("\n") };
    if (eventId !== undefined) evt.id = eventId;
    if (eventName) evt.event = eventName;
    eventId = undefined;
    eventName = undefined;
    dataLines = [];
    return evt;
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

    while (true) {
      const nl = buffer.indexOf("\n");
      if (nl === -1) break;
      const line = buffer.slice(0, nl);
      buffer = buffer.slice(nl + 1);

      if (line === "") {
        const evt = flushEvent();
        if (evt) yield evt;
        continue;
      }

      if (line.startsWith(":")) continue;

      if (line.startsWith("event:")) {
        eventName = line.slice("event:".length).trim();
        continue;
      }

      if (line.startsWith("id:")) {
        const rawId = line.slice("id:".length).trim();
        eventId = rawId;
        continue;
      }

      if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trimStart());
      }
    }
  }

  const tail = buffer.trim();
  if (tail.startsWith("data:")) {
    dataLines.push(tail.slice("data:".length).trimStart());
  }
  const evt = flushEvent();
  if (evt) yield evt;
}
