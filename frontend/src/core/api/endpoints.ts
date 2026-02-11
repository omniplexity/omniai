// OmniAI v1 API - Canonical endpoints only
// Fallbacks removed for production stability
export const endpoints = {
  // Authentication
  meta: ["/v1/meta"],
  csrfBootstrap: ["/v1/auth/csrf/bootstrap"],
  me: ["/v1/auth/me"],
  login: ["/v1/auth/login"],
  logout: ["/v1/auth/logout"],

  // Chat (streaming + retry/cancel)
  chatStream: ["/v1/chat"],
  chatStreamEvents: ["/v1/chat/stream"],
  chatRetry: ["/v1/chat/retry"],
  chatCancel: ["/v1/chat/cancel"],

  // Conversations
  conversations: ["/v1/conversations"],
  conversationGet: ["/v1/conversations/{id}"],
  conversationMessages: ["/v1/conversations/{id}/messages"],
  conversationRename: ["/v1/conversations/{id}"],
  conversationDelete: ["/v1/conversations/{id}"],
  conversationBranch: ["/v1/conversations/{id}/branch"],

  // Providers
  providers: ["/v1/providers"],
  models: ["/v1/models"],

  // Memory
  memory: ["/v1/memory"],
  memorySearch: ["/v1/memory/search"],

  // Tools
  tools: ["/v1/tools"],
  toolsExecute: ["/v1/tools/execute"],

  // Ops (admin-only)
  opsDuckdnsStatus: ["/v1/ops/duckdns/status"],
  opsDuckdnsLogs: ["/v1/ops/duckdns/logs"],
  opsDuckdnsUpdate: ["/v1/ops/duckdns/update"],
  opsDuckdnsTest: ["/v1/ops/duckdns/test"],
};

export function conversationEndpoint(id: string): string[] {
  return [`/v1/conversations/${id}`];
}

export function conversationMessagesEndpoint(conversationId: string): string[] {
  return [`/v1/conversations/${conversationId}/messages`];
}
