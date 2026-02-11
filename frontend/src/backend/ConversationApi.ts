export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export interface ConversationApi {
  listConversations(signal?: AbortSignal): Promise<Conversation[]>;
  createConversation(params: { title: string; signal?: AbortSignal }): Promise<Conversation>;
  getMessages(params: { conversationId: string; signal?: AbortSignal }): Promise<ConversationMessage[]>;
}
