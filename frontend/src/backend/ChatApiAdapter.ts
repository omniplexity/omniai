export type StreamMeta = {
  backendRunId?: string;
  conversationId?: string;
  sourceMessageId?: string;
  resultMessageId?: string;
  eventSeq?: number;
  eventTs?: string;
};

export type StreamChunk =
  | { type: "delta"; delta: string }
  | { type: "done" }
  | { type: "meta"; meta: StreamMeta };

export interface ChatApiAdapter {
  createRun(params: {
    conversationId: string;
    input: string;
    retryFromMessageId?: string;
    signal: AbortSignal;
    provider?: string;
    model?: string;
    settings?: Record<string, unknown>;
  }): Promise<{ runId: string; status: string }>;

  streamRun(params: { runId: string; signal: AbortSignal }): AsyncGenerator<
    StreamChunk,
    void,
    void
  >;

  cancelRun(params: { runId: string; signal?: AbortSignal }): Promise<void>;
}
