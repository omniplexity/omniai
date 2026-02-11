import type { ChatApiAdapter, StreamChunk } from "./ChatApiAdapter";
import { streamAssistantReply } from "./placeholderApi";

export class PlaceholderAdapter implements ChatApiAdapter {
  async createRun(params: {
    conversationId: string;
    input: string;
    retryFromMessageId?: string;
    signal: AbortSignal;
  }): Promise<{ runId: string; status: string }> {
    if (params.signal.aborted) throw new DOMException("Aborted", "AbortError");
    return {
      runId: `mock_run_${Date.now().toString(36)}`,
      status: "running",
    };
  }

  async *streamRun(params: { runId: string; signal: AbortSignal }): AsyncGenerator<
    StreamChunk,
    void,
    void
  > {
    if (params.signal.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }

    for await (const chunk of streamAssistantReply({
      prompt: `placeholder run ${params.runId}`,
      userMessageId: "placeholder",
    })) {
      if (params.signal.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }
      yield chunk;
    }
  }

  async cancelRun(_params: { runId: string; signal?: AbortSignal }): Promise<void> {
    return;
  }
}
