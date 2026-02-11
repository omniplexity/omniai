import { useEffect, useMemo, useState } from "preact/hooks";
import type { Conversation } from "../backend/ConversationApi";

type ConversationState = {
  items: Conversation[];
  activeConversationId: string | null;
  loading: boolean;
};

type Listener = (state: ConversationState) => void;
const listeners = new Set<Listener>();

let state: ConversationState = {
  items: [],
  activeConversationId: null,
  loading: false,
};

function emit() {
  for (const listener of listeners) listener(state);
}

export const conversationStore = {
  getState(): ConversationState {
    return state;
  },

  subscribe(listener: Listener): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  },

  actions: {
    setLoading(loading: boolean): void {
      state = { ...state, loading };
      emit();
    },

    setConversations(items: Conversation[]): void {
      state = { ...state, items };
      emit();
    },

    addConversation(item: Conversation): void {
      state = { ...state, items: [item, ...state.items.filter((c) => c.id !== item.id)] };
      emit();
    },

    setActiveConversationId(id: string | null): void {
      state = { ...state, activeConversationId: id };
      emit();
    },

    reset(): void {
      state = { items: [], activeConversationId: null, loading: false };
      emit();
    },
  },
};

export function useConversationStore(): {
  state: ConversationState;
  actions: typeof conversationStore.actions;
} {
  const [snap, setSnap] = useState<ConversationState>(conversationStore.getState());
  useEffect(() => conversationStore.subscribe(setSnap), []);
  return useMemo(() => ({ state: snap, actions: conversationStore.actions }), [snap]);
}
