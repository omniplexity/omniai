import type { ChatRequest, ChatStreamEvent } from "./types";
import { streamChat, retryChat, cancelChat } from "./chatApi";

export type StreamCallbacks = {
  onEvent: (ev: ChatStreamEvent) => void;
  onClosed: () => void;
};

export class ChatController {
  private aborter: AbortController | null = null;
  private lastRequest: ChatRequest | null = null;
  private lastRunId: string | null = null;
  private lastConversationId: string | null = null;
  private lastMessageId: string | null = null;  // For /v1/chat/retry

  isStreaming(): boolean {
    return this.aborter !== null;
  }

  cancel(): void {
    // Abort the SSE stream immediately for fast UX
    this.aborter?.abort();
    this.aborter = null;
    
    // Fire cancel API best-effort for resource control
    if (this.lastRunId) {
      cancelChat(this.lastRunId).catch(err => {
        console.warn("Cancel request failed:", err);
      });
      this.lastRunId = null;
    }
  }

  async send(req: ChatRequest, cb: StreamCallbacks): Promise<void> {
    this.cancel();
    this.lastRequest = structuredClone(req);
    this.lastConversationId = req.conversation_id ?? null;
    this.lastRunId = null;
    this.lastMessageId = null;

    const aborter = new AbortController();
    this.aborter = aborter;

    try {
      // Start streaming - run_id is yielded as first meta event from POST response
      for await (const ev of streamChat(req, aborter.signal)) {
        // Capture run_id from meta event (comes from POST /v1/chat response)
        if (ev.type === "meta" && ev.run_id && !this.lastRunId) {
          this.lastRunId = ev.run_id;
        }
        cb.onEvent(ev);
        if (ev.type === "done" || ev.type === "error") {
          // keep reading until done; but UI can mark error immediately
        }
      }
    } catch (e: any) {
      if (e?.name === "AbortError") {
        cb.onEvent({ type: "stopped" });
      } else {
        cb.onEvent({ type: "error", message: String(e?.message ?? e) });
      }
    } finally {
      this.aborter = null;
      cb.onClosed();
    }
  }

  async retry(conversationId: string, messageId: string, cb: StreamCallbacks): Promise<void> {
    if (!conversationId || !messageId) {
      cb.onEvent({ type: "error", message: "Missing conversation_id or message_id for retry" });
      cb.onClosed();
      return;
    }

    this.cancel();
    this.lastConversationId = conversationId;
    this.lastMessageId = messageId;
    this.lastRunId = null;

    const aborter = new AbortController();
    this.aborter = aborter;

    try {
      // Use /v1/chat/retry endpoint for proper retry semantics
      for await (const ev of retryChat(conversationId, messageId, aborter.signal)) {
        // Capture run_id from meta event (comes from POST /v1/chat/retry response)
        if (ev.type === "meta" && ev.run_id && !this.lastRunId) {
          this.lastRunId = ev.run_id;
        }
        cb.onEvent(ev);
        if (ev.type === "done" || ev.type === "error") {
          // keep reading until done
        }
      }
    } catch (e: any) {
      if (e?.name === "AbortError") {
        cb.onEvent({ type: "stopped" });
      } else {
        cb.onEvent({ type: "error", message: String(e?.message ?? e) });
      }
    } finally {
      this.aborter = null;
      cb.onClosed();
    }
  }
}
