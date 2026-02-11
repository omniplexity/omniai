import { useEffect, useMemo, useState } from "preact/hooks";

export type RunStatus = "idle" | "streaming" | "done" | "cancelled" | "error";

export type RunRecord = {
  id: string;
  status: RunStatus;
  requestMessages: Array<{ role: "user" | "assistant"; content: string }>;
  resultAssistantMessageId: string | null;
  backendRunId?: string;
  conversationId?: string;
  sourceMessageId?: string;
  resultMessageId?: string;
  firstEventSeq?: number;
  lastEventSeq?: number;
  retryOfRunId?: string;
  errorCode?: string;
  errorMessage?: string;
  receivedAnyDelta: boolean;
};

export type RunState = {
  activeRunId: string | null;
  lastRunId: string | null;
  runsById: Record<string, RunRecord>;
  messageMetaById: Record<
    string,
    {
      runId: string;
      retryOfRunId?: string;
      parentMessageId?: string;
      branchId?: string;
      backendMessageId?: string;
      pending?: boolean;
      eventSeq?: number;
    }
  >;
};

type Listener = (state: RunState) => void;
const listeners = new Set<Listener>();

let state: RunState = {
  activeRunId: null,
  lastRunId: null,
  runsById: {},
  messageMetaById: {},
};

function emit() {
  for (const listener of listeners) listener(state);
}

function newId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

export const runStore = {
  getState(): RunState {
    return state;
  },

  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  actions: {
    createRun(params: {
      requestMessages: Array<{ role: "user" | "assistant"; content: string }>;
      retryOfRunId?: string;
      conversationId?: string;
      sourceMessageId?: string;
    }): string {
      const id = newId("run");
      const snapshot = params.requestMessages.map((m) => ({ role: m.role, content: m.content }));
      state = {
        ...state,
        activeRunId: id,
        lastRunId: id,
        runsById: {
          ...state.runsById,
          [id]: {
            id,
            status: "idle",
            requestMessages: snapshot,
            resultAssistantMessageId: null,
            conversationId: params.conversationId,
            sourceMessageId: params.sourceMessageId,
            retryOfRunId: params.retryOfRunId,
            receivedAnyDelta: false,
          },
        },
      };
      emit();
      return id;
    },

    startRun(runId: string, assistantMessageId: string): void {
      const run = state.runsById[runId];
      if (!run) return;
      state = {
        ...state,
        activeRunId: runId,
        runsById: {
          ...state.runsById,
          [runId]: {
            ...run,
            status: "streaming",
            resultAssistantMessageId: assistantMessageId,
          },
        },
        messageMetaById: {
          ...state.messageMetaById,
          [assistantMessageId]: {
            runId,
            retryOfRunId: run.retryOfRunId,
          },
        },
      };
      emit();
    },

    markDelta(runId: string): void {
      const run = state.runsById[runId];
      if (!run) return;
      state = {
        ...state,
        runsById: {
          ...state.runsById,
          [runId]: { ...run, receivedAnyDelta: true },
        },
      };
      emit();
    },

    markDone(runId: string): void {
      const run = state.runsById[runId];
      if (!run) return;
      state = {
        ...state,
        activeRunId: state.activeRunId === runId ? null : state.activeRunId,
        runsById: {
          ...state.runsById,
          [runId]: { ...run, status: "done" },
        },
      };
      emit();
    },

    attachBackendRunId(runId: string, backendRunId: string): void {
      const run = state.runsById[runId];
      if (!run || run.backendRunId === backendRunId) return;
      state = {
        ...state,
        runsById: {
          ...state.runsById,
          [runId]: { ...run, backendRunId },
        },
      };
      emit();
    },

    attachConversationId(runId: string, conversationId: string): void {
      const run = state.runsById[runId];
      if (!run || run.conversationId === conversationId) return;
      state = {
        ...state,
        runsById: {
          ...state.runsById,
          [runId]: { ...run, conversationId },
        },
      };
      emit();
    },

    attachSourceMessageId(runId: string, messageId: string): void {
      const run = state.runsById[runId];
      if (!run || run.sourceMessageId === messageId) return;
      state = {
        ...state,
        runsById: {
          ...state.runsById,
          [runId]: { ...run, sourceMessageId: messageId },
        },
      };
      emit();
    },

    attachResultMessageId(runId: string, backendMessageId: string): void {
      const run = state.runsById[runId];
      if (!run || run.resultMessageId === backendMessageId) return;
      state = {
        ...state,
        runsById: {
          ...state.runsById,
          [runId]: { ...run, resultMessageId: backendMessageId },
        },
      };
      emit();
    },

    attachEventSeq(runId: string, seq: number): void {
      const run = state.runsById[runId];
      if (!run) return;
      const firstEventSeq = run.firstEventSeq ?? seq;
      const lastEventSeq = run.lastEventSeq ?? seq;
      const nextLast = seq > lastEventSeq ? seq : lastEventSeq;
      if (run.firstEventSeq === firstEventSeq && run.lastEventSeq === nextLast) return;
      state = {
        ...state,
        runsById: {
          ...state.runsById,
          [runId]: { ...run, firstEventSeq, lastEventSeq: nextLast },
        },
      };
      emit();
    },

    markMessagePending(localMessageId: string, pending: boolean, runId?: string): void {
      const existing = state.messageMetaById[localMessageId];
      if (!existing && !runId) return;
      if (existing?.pending === pending) return;
      state = {
        ...state,
        messageMetaById: {
          ...state.messageMetaById,
          [localMessageId]: {
            runId: existing?.runId ?? runId ?? "",
            ...existing,
            pending,
          },
        },
      };
      emit();
    },

    attachMessageBackendId(localMessageId: string, backendMessageId: string): void {
      const existing = state.messageMetaById[localMessageId];
      if (!existing) return;
      if (existing.backendMessageId === backendMessageId && existing.pending === false) return;
      state = {
        ...state,
        messageMetaById: {
          ...state.messageMetaById,
          [localMessageId]: {
            ...existing,
            backendMessageId,
            pending: false,
          },
        },
      };
      emit();
    },

    attachMessageEventSeq(localMessageId: string, seq: number): void {
      const existing = state.messageMetaById[localMessageId];
      if (!existing) return;
      const nextSeq = existing.eventSeq === undefined ? seq : Math.max(existing.eventSeq, seq);
      if (nextSeq === existing.eventSeq) return;
      state = {
        ...state,
        messageMetaById: {
          ...state.messageMetaById,
          [localMessageId]: {
            ...existing,
            eventSeq: nextSeq,
          },
        },
      };
      emit();
    },

    reconcileMessageMap(localToBackend: Record<string, string>): void {
      const next = { ...state.messageMetaById };
      for (const [localId, backendId] of Object.entries(localToBackend)) {
        const existing = next[localId];
        if (!existing) continue;
        next[localId] = { ...existing, backendMessageId: backendId, pending: false };
      }
      state = { ...state, messageMetaById: next };
      emit();
    },

    markCancelled(runId: string): void {
      const run = state.runsById[runId];
      if (!run) return;
      state = {
        ...state,
        activeRunId: state.activeRunId === runId ? null : state.activeRunId,
        runsById: {
          ...state.runsById,
          [runId]: {
            ...run,
            status: "cancelled",
            errorCode: "E_CANCELLED",
            errorMessage: "Response cancelled by user.",
          },
        },
      };
      emit();
    },

    markError(runId: string, errorCode: string, errorMessage: string): void {
      const run = state.runsById[runId];
      if (!run) return;
      state = {
        ...state,
        activeRunId: state.activeRunId === runId ? null : state.activeRunId,
        runsById: {
          ...state.runsById,
          [runId]: {
            ...run,
            status: "error",
            errorCode,
            errorMessage,
          },
        },
      };
      emit();
    },

    reset(): void {
      state = {
        activeRunId: null,
        lastRunId: null,
        runsById: {},
        messageMetaById: {},
      };
      emit();
    },
  },
};

export function useRunStore(): {
  state: RunState;
  actions: typeof runStore.actions;
} {
  const [snap, setSnap] = useState<RunState>(runStore.getState());
  useEffect(() => runStore.subscribe(setSnap), []);
  return useMemo(() => ({ state: snap, actions: runStore.actions }), [snap]);
}
