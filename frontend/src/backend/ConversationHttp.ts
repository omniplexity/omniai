import type { Conversation, ConversationApi, ConversationMessage } from "./ConversationApi";
import { getRuntimeConfig } from "../config/runtimeConfig";
import { requestMutating, requestSession } from "../core/api/client";
import { ChatProtocolError } from "./SSEBackendAdapter";

export class ConversationHttp implements ConversationApi {
  async listConversations(signal?: AbortSignal): Promise<Conversation[]> {
    const base = getRuntimeConfig().BACKEND_BASE_URL;
    const res = await requestSession(`${base}/v1/conversations`, {
      method: "GET",
      signal,
    });
    if (!res.ok) {
      const body = await safeReadError(res);
      throw new ChatProtocolError("backend_http_error", body.message, {
        status: res.status,
        backendCode: body.backendCode ?? undefined,
      });
    }
    return (await res.json()) as Conversation[];
  }

  async createConversation(params: { title: string; signal?: AbortSignal }): Promise<Conversation> {
    const base = getRuntimeConfig().BACKEND_BASE_URL;
    const res = await requestMutating(
      `${base}/v1/conversations`,
      {
        method: "POST",
        signal: params.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: params.title }),
      }
    );
    if (!res.ok) {
      const body = await safeReadError(res);
      throw new ChatProtocolError("backend_http_error", body.message, {
        status: res.status,
        backendCode: body.backendCode ?? undefined,
      });
    }
    return (await res.json()) as Conversation;
  }

  async getMessages(params: { conversationId: string; signal?: AbortSignal }): Promise<ConversationMessage[]> {
    const base = getRuntimeConfig().BACKEND_BASE_URL;
    const res = await requestSession(
      `${base}/v1/conversations/${encodeURIComponent(params.conversationId)}/messages`,
      {
        method: "GET",
        signal: params.signal,
      }
    );
    if (!res.ok) {
      const body = await safeReadError(res);
      throw new ChatProtocolError("backend_http_error", body.message, {
        status: res.status,
        backendCode: body.backendCode ?? undefined,
      });
    }
    return (await res.json()) as ConversationMessage[];
  }
}

async function safeReadError(
  res: Response
): Promise<{ message: string; backendCode: string | null }> {
  try {
    const json = (await res.json()) as { detail?: string; error?: { code?: string; message?: string } };
    return {
      message: json.error?.message ?? json.detail ?? `HTTP ${res.status}`,
      backendCode: json.error?.code ?? null,
    };
  } catch {
    return { message: `HTTP ${res.status}`, backendCode: null };
  }
}
