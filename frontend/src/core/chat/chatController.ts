import type { StreamChunk } from "../../backend/ChatApiAdapter";

export type ChatSettingsSnapshot = {
  provider?: string;
  model?: string;
  settings?: Record<string, unknown>;
};

export type RetrySnapshot = {
  threadId: string;
  input: string;
  retryFromMessageId?: string;
  settings: ChatSettingsSnapshot;
};

export type ControllerState = {
  assistantDraft: string;
  isStreaming: boolean;
  isStopped: boolean;
  hasError: boolean;
  errorMessage?: string;
  lastSnapshot: RetrySnapshot | null;
};

export function createInitialControllerState(): ControllerState {
  return {
    assistantDraft: "",
    isStreaming: false,
    isStopped: false,
    hasError: false,
    lastSnapshot: null,
  };
}

export function buildRetrySnapshot(params: RetrySnapshot): RetrySnapshot {
  return {
    threadId: params.threadId,
    input: params.input,
    retryFromMessageId: params.retryFromMessageId,
    settings: {
      provider: params.settings.provider,
      model: params.settings.model,
      settings: structuredClone(params.settings.settings ?? {}),
    },
  };
}

export function reduceStreamChunk(state: ControllerState, chunk: StreamChunk): ControllerState {
  if (chunk.type === "delta") {
    return {
      ...state,
      isStreaming: true,
      assistantDraft: state.assistantDraft + chunk.delta,
    };
  }
  if (chunk.type === "done") {
    return {
      ...state,
      isStreaming: false,
      isStopped: true,
    };
  }
  return state;
}

export function reduceError(state: ControllerState, message: string): ControllerState {
  return {
    ...state,
    isStreaming: false,
    hasError: true,
    errorMessage: message,
  };
}
