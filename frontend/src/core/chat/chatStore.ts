import { createStore } from "../state/store";
import type { ChatMessage } from "./types";

export type ThreadChatState = {
  threadId: string; // "new" allowed until backend returns a real id
  messages: ChatMessage[];
  streaming: boolean;
  lastError?: string;
};

type ChatState = {
  byThread: Record<string, ThreadChatState>;
};

export const chatStore = createStore<ChatState>({
  byThread: {}
});

export function getThreadState(threadId: string): ThreadChatState {
  const s = chatStore.get().byThread[threadId];
  if (s) return s;
  const init: ThreadChatState = { threadId, messages: [], streaming: false };
  chatStore.patch({ byThread: { ...chatStore.get().byThread, [threadId]: init } });
  return init;
}

export function setThreadStreaming(threadId: string, streaming: boolean) {
  const s = getThreadState(threadId);
  const next = { ...s, streaming, lastError: undefined };
  chatStore.patch({ byThread: { ...chatStore.get().byThread, [threadId]: next } });
}

export function setThreadError(threadId: string, msg?: string) {
  const s = getThreadState(threadId);
  const next = { ...s, streaming: false, lastError: msg };
  chatStore.patch({ byThread: { ...chatStore.get().byThread, [threadId]: next } });
}

export function upsertMessages(threadId: string, messages: ChatMessage[]) {
  const s = getThreadState(threadId);
  const next = { ...s, messages };
  chatStore.patch({ byThread: { ...chatStore.get().byThread, [threadId]: next } });
}

export function appendMessage(threadId: string, m: ChatMessage) {
  const s = getThreadState(threadId);
  upsertMessages(threadId, [...s.messages, m]);
}

export function patchMessage(threadId: string, id: string, patch: Partial<ChatMessage>) {
  const s = getThreadState(threadId);
  upsertMessages(
    threadId,
    s.messages.map((x) => (x.id === id ? { ...x, ...patch } : x))
  );
}

export function migrateThread(oldId: string, newId: string) {
  const state = chatStore.get();
  const old = state.byThread[oldId];
  if (!old) return;
  const byThread = { ...state.byThread };
  delete byThread[oldId];
  byThread[newId] = { ...old, threadId: newId };
  chatStore.patch({ byThread });
}
