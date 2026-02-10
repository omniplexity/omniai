import { createStore } from "../state/store";
import * as conversationApi from "./conversationApi";

export type ConversationState = {
  conversations: conversationApi.Conversation[];
  currentId: string | null;
  loading: boolean;
  error?: string;
};

export const conversationStore = createStore<ConversationState>({
  conversations: [],
  currentId: null,
  loading: false
});

export function setCurrentConversation(id: string | null) {
  conversationStore.patch({ currentId: id });
}

export async function loadConversations(): Promise<void> {
  conversationStore.patch({ loading: true, error: undefined });

  try {
    const conversations = await conversationApi.listConversations();
    conversationStore.patch({ conversations, loading: false });
  } catch (e: any) {
    conversationStore.patch({
      loading: false,
      error: String(e?.message ?? e)
    });
  }
}

export async function createNewConversation(title?: string): Promise<conversationApi.Conversation> {
  conversationStore.patch({ loading: true, error: undefined });

  try {
    const conversation = await conversationApi.createConversation(title);
    conversationStore.patch({
      conversations: [conversation, ...conversationStore.get().conversations],
      currentId: conversation.id,
      loading: false
    });
    return conversation;
  } catch (e: any) {
    conversationStore.patch({
      loading: false,
      error: String(e?.message ?? e)
    });
    throw e;
  }
}

export async function renameCurrentConversation(title: string): Promise<void> {
  const { currentId, conversations } = conversationStore.get();
  if (!currentId) return;

  conversationStore.patch({ loading: true, error: undefined });

  try {
    const updated = await conversationApi.renameConversation(currentId, title);
    conversationStore.patch({
      conversations: conversations.map(c => c.id === currentId ? updated : c),
      loading: false
    });
  } catch (e: any) {
    conversationStore.patch({
      loading: false,
      error: String(e?.message ?? e)
    });
    throw e;
  }
}

export async function deleteConversationById(id: string): Promise<void> {
  conversationStore.patch({ loading: true, error: undefined });

  try {
    await conversationApi.deleteConversation(id);
    const { currentId, conversations } = conversationStore.get();
    const newConversations = conversations.filter(c => c.id !== id);
    conversationStore.patch({
      conversations: newConversations,
      currentId: currentId === id ? null : currentId,
      loading: false
    });
  } catch (e: any) {
    conversationStore.patch({
      loading: false,
      error: String(e?.message ?? e)
    });
    throw e;
  }
}

export async function deleteCurrentConversation(): Promise<void> {
  const { currentId } = conversationStore.get();
  if (!currentId) return;
  await deleteConversationById(currentId);
}
