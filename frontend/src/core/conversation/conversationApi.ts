import { endpoints, conversationEndpoint, conversationMessagesEndpoint } from "../api/endpoints";
import { ApiError } from "../api/errors";
import { ensureCsrfToken, getCsrfToken } from "../api/csrf";
import { classifyHttpError, fetchWithTimeout, readErrorBody, tryPaths } from "../api/http";

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
    const res = await fetchWithTimeout(`${url}?limit=${limit}&offset=${offset}`, {
      method: "GET",
      credentials: "include",
      headers: { "Accept": "application/json" },
      timeoutMs: 15000
    });

    if (!res.ok) {
      const body = await readErrorBody(res);
      throw classifyHttpError(res) instanceof ApiError
        ? new ApiError(classifyHttpError(res).code, `List conversations failed (${res.status})`, res.status, body)
        : new ApiError("unknown", `List conversations failed (${res.status})`, res.status, body);
    }

    return await res.json();
  });
}

export async function createConversation(title = "New Conversation"): Promise<Conversation> {
  await ensureCsrfToken();

  return tryPaths(endpoints.conversations, async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": getCsrfToken() ?? ""
      },
      body: JSON.stringify({ title }),
      timeoutMs: 15000
    });

    if (!res.ok) {
      const body = await readErrorBody(res);
      throw classifyHttpError(res) instanceof ApiError
        ? new ApiError(classifyHttpError(res).code, `Create conversation failed (${res.status})`, res.status, body)
        : new ApiError("unknown", `Create conversation failed (${res.status})`, res.status, body);
    }

    return await res.json();
  });
}

export async function renameConversation(id: string, title: string): Promise<Conversation> {
  await ensureCsrfToken();

  return tryPaths(conversationEndpoint(id), async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "PATCH",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": getCsrfToken() ?? ""
      },
      body: JSON.stringify({ title }),
      timeoutMs: 15000
    });

    if (!res.ok) {
      const body = await readErrorBody(res);
      throw classifyHttpError(res) instanceof ApiError
        ? new ApiError(classifyHttpError(res).code, `Rename conversation failed (${res.status})`, res.status, body)
        : new ApiError("unknown", `Rename conversation failed (${res.status})`, res.status, body);
    }

    return await res.json();
  });
}

export async function deleteConversation(id: string): Promise<void> {
  await ensureCsrfToken();

  return tryPaths(conversationEndpoint(id), async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "DELETE",
      credentials: "include",
      headers: {
        "Accept": "application/json",
        "X-CSRF-Token": getCsrfToken() ?? ""
      },
      timeoutMs: 15000
    });

    if (!res.ok) {
      const body = await readErrorBody(res);
      throw classifyHttpError(res) instanceof ApiError
        ? new ApiError(classifyHttpError(res).code, `Delete conversation failed (${res.status})`, res.status, body)
        : new ApiError("unknown", `Delete conversation failed (${res.status})`, res.status, body);
    }
  });
}

export async function getMessages(conversationId: string): Promise<Message[]> {
  return tryPaths(conversationMessagesEndpoint(conversationId), async (url) => {
    const res = await fetchWithTimeout(url, {
      method: "GET",
      credentials: "include",
      headers: { "Accept": "application/json" },
      timeoutMs: 15000
    });

    if (!res.ok) {
      const body = await readErrorBody(res);
      throw classifyHttpError(res) instanceof ApiError
        ? new ApiError(classifyHttpError(res).code, `Get messages failed (${res.status})`, res.status, body)
        : new ApiError("unknown", `Get messages failed (${res.status})`, res.status, body);
    }

    return await res.json();
  });
}
