export type StreamChunk = { type: "delta"; delta: string } | { type: "done" };

export type PlaceholderRequest = {
  prompt: string;
  userMessageId: string;
};

export async function* streamAssistantReply(
  req: PlaceholderRequest
): AsyncGenerator<StreamChunk, void, void> {
  const text = req.prompt.trim();

  if (text.toLowerCase().includes("error")) {
    await sleep(350);
    throw new Error("Simulated backend error (triggered by prompt).");
  }

  if (Math.random() < 0.06) {
    await sleep(250);
    throw new Error("Simulated transient network failure.");
  }

  const reply = buildReply(text);
  const chunks = chunkString(reply, 12);

  for (const chunk of chunks) {
    await sleep(30 + Math.random() * 50);
    yield { type: "delta", delta: chunk };
  }

  await sleep(120);
  yield { type: "done" };
}

function buildReply(prompt: string): string {
  const lines = [
    "This is a simulated streaming response.",
    "",
    `You said: "${prompt}"`,
    "",
    "Next steps:",
    "- Replace placeholderApi with real backend SSE (/v1/chat).",
    "- Keep deterministic retry/cancel semantics in the Chat Agent.",
  ];
  return lines.join("\n");
}

function chunkString(text: string, size: number): string[] {
  const out: string[] = [];
  let i = 0;
  while (i < text.length) {
    out.push(text.slice(i, i + size));
    i += size;
  }
  return out;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
