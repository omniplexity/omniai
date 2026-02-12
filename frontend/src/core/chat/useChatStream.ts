import type { ChatApiAdapter } from "../../backend/ChatApiAdapter";
import type { RetrySnapshot } from "./chatController";
import { buildRetrySnapshot } from "./chatController";

export function useChatStream(adapter: ChatApiAdapter) {
  let aborter: AbortController | null = null;
  let backendRunId: string | null = null;
  let snapshot: RetrySnapshot | null = null;

  async function start(params: RetrySnapshot & { onChunk: (chunk: any) => void }) {
    cancel();
    snapshot = buildRetrySnapshot(params);
    aborter = new AbortController();
    backendRunId = null;

    const created = await adapter.createRun({
      conversationId: snapshot.threadId,
      input: snapshot.input,
      retryFromMessageId: snapshot.retryFromMessageId,
      provider: snapshot.settings.provider,
      model: snapshot.settings.model,
      settings: snapshot.settings.settings,
      signal: aborter.signal,
    });
    backendRunId = created.runId;

    for await (const chunk of adapter.streamRun({ runId: created.runId, signal: aborter.signal })) {
      params.onChunk(chunk);
    }
  }

  async function retry(onChunk: (chunk: any) => void) {
    if (!snapshot) return;
    await start({ ...snapshot, onChunk });
  }

  function cancel() {
    aborter?.abort();
    aborter = null;
    const runId = backendRunId;
    backendRunId = null;
    if (runId) {
      void adapter.cancelRun({ runId }).catch(() => undefined);
    }
  }

  return {
    start,
    retry,
    cancel,
    getLastSnapshot: () => snapshot,
  };
}
