import { useEffect, useMemo, useState } from "preact/hooks";

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
};

export type ChatState = {
  messages: ChatMessage[];
  streamingAssistantId: string | null;
  isStreaming: boolean;
};

type Listener = (s: ChatState) => void;

const listeners = new Set<Listener>();

let state: ChatState = {
  messages: [],
  streamingAssistantId: null,
  isStreaming: false,
};

let activeAbortController: AbortController | null = null;

function emit() {
  for (const listener of listeners) listener(state);
}

function nowIso(): string {
  return new Date().toISOString();
}

function newId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random()
    .toString(36)
    .slice(2, 10)}`;
}

export const chatStore = {
  getState(): ChatState {
    return state;
  },

  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  actions: {
    addUserMessage(content: string): string {
      const id = newId("msg_user");
      const msg: ChatMessage = {
        id,
        role: "user",
        content,
        timestamp: nowIso(),
      };
      state = { ...state, messages: [...state.messages, msg] };
      emit();
      return id;
    },

    startAssistantMessage(initialContent: string): string {
      const id = newId("msg_asst");
      const msg: ChatMessage = {
        id,
        role: "assistant",
        content: initialContent,
        timestamp: nowIso(),
      };
      state = {
        ...state,
        messages: [...state.messages, msg],
        streamingAssistantId: id,
        isStreaming: true,
      };
      emit();
      return id;
    },

    appendAssistantDelta(messageId: string, delta: string): void {
      state = {
        ...state,
        messages: state.messages.map((m) =>
          m.id === messageId ? { ...m, content: m.content + delta } : m
        ),
      };
      emit();
    },

    replaceMessageContent(messageId: string, content: string): void {
      state = {
        ...state,
        messages: state.messages.map((m) =>
          m.id === messageId ? { ...m, content } : m
        ),
      };
      emit();
    },

    setMessages(messages: ChatMessage[]): void {
      state = {
        ...state,
        messages,
      };
      emit();
    },

    finalizeAssistantMessage(messageId: string): void {
      const nextStreamingId =
        state.streamingAssistantId === messageId ? null : state.streamingAssistantId;

      state = {
        ...state,
        streamingAssistantId: nextStreamingId,
        isStreaming: nextStreamingId !== null,
        messages: state.messages.map((m) =>
          m.id === messageId ? { ...m, timestamp: nowIso() } : m
        ),
      };
      emit();
    },

    setAbortController(controller: AbortController | null): void {
      activeAbortController = controller;
    },

    cancelStream(): void {
      if (activeAbortController) {
        activeAbortController.abort();
        activeAbortController = null;
      }

      state = {
        ...state,
        streamingAssistantId: null,
        isStreaming: false,
      };
      emit();
    },

    reset(): void {
      activeAbortController = null;
      state = {
        messages: [],
        streamingAssistantId: null,
        isStreaming: false,
      };
      emit();
    },
  },
};

export function useChatStore(): {
  state: ChatState;
  actions: typeof chatStore.actions;
} {
  const [snap, setSnap] = useState<ChatState>(chatStore.getState());

  useEffect(() => chatStore.subscribe(setSnap), []);

  return useMemo(
    () => ({
      state: snap,
      actions: chatStore.actions,
    }),
    [snap]
  );
}
