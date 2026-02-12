import { endpoints, conversationEndpoint, conversationMessagesEndpoint } from "../api/endpoints";
import { tryPaths } from "../api/http";
import { requestMutating, requestSession, toApiError } from "../api/client";

export interface Conversation {
  id: string;
  title: string;
  provider?: string;
  model?: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: string;
  content: string;
  provider?: string;
  model?: string;
  tokens_prompt?: number;
  tokens_completion?: number;
  created_at: string;
}

export async function listConversations(limit = 50, offset = 0): Promise<Conversation[]> {
  return tryPaths(endpoints.conversations, async (url) => {
    const res = await requestSession(`${url}?limit=${limit}&offset=${offset}`, {
      method: "GET",
      headers: { "Accept": "application/json" },
    });

    if (!res.ok) {
      throw await toApiError(res, "server_error", `List conversations failed (${res.status})`);
    }

    return await res.json();
  });
}

export async function createConversation(title = "New Conversation"): Promise<Conversation> {
  return tryPaths(endpoints.conversations, async (url) => {
    const res = await requestMutating(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify({ title }),
    });

    if (!res.ok) {
      throw await toApiError(res, "server_error", `Create conversation failed (${res.status})`);
    }

    return await res.json();
  });
}

export async function renameConversation(id: string, title: string): Promise<Conversation> {
  return tryPaths(conversationEndpoint(id), async (url) => {
    const res = await requestMutating(url, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify({ title }),
    });

    if (!res.ok) {
      throw await toApiError(res, "server_error", `Rename conversation failed (${res.status})`);
    }

    return await res.json();
  });
}

export async function deleteConversation(id: string): Promise<void> {
  return tryPaths(conversationEndpoint(id), async (url) => {
    const res = await requestMutating(url, {
      method: "DELETE",
      headers: {
        "Accept": "application/json"
      },
    });

    if (!res.ok) {
      throw await toApiError(res, "server_error", `Delete conversation failed (${res.status})`);
    }
  });
}

export async function getMessages(conversationId: string): Promise<Message[]> {
  return tryPaths(conversationMessagesEndpoint(conversationId), async (url) => {
    const res = await requestSession(url, {
      method: "GET",
      headers: { "Accept": "application/json" },
    });

    if (!res.ok) {
      throw await toApiError(res, "server_error", `Get messages failed (${res.status})`);
    }

    return await res.json();
  });
}
