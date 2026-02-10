import { endpoints } from "../api/endpoints";
import { tryPaths, fetchWithTimeout } from "../api/http";
import { ensureCsrfToken, getCsrfToken } from "../api/csrf";
import { parseSseResponse } from "../api/sse";
import type { ChatRequest, ChatStreamEvent } from "./types";

function extractMeta(obj: any): { conversation_id?: string; run_id?: string } {
  const cid = obj?.conversation_id ?? obj?.conversationId ?? obj?.conversation?.id;
  const rid = obj?.run_id ?? obj?.runId ?? obj?.id;
  return {
    conversation_id: typeof cid === "string" ? cid : undefined,
    run_id: typeof rid === "string" ? rid : undefined
  };
}

function extractDelta(obj: any): string | null {
  // Backend emits: message.delta { delta: "..." }
  const d = obj?.delta ?? obj?.text ?? obj?.content;
  return typeof d === "string" ? d : null;
}

function extractError(obj: any): string | null {
  // Backend emits: error { message: "...", code: "..." }
  const e = obj?.message ?? obj?.error ?? obj?.detail;
  return typeof e === "string" ? e : null;
}

/**
 * Start a chat by creating a run, then stream events from /v1/chat/stream
 */
export async function* streamChat(
  req: ChatRequest,
  signal: AbortSignal
): AsyncGenerator<ChatStreamEvent> {
  await ensureCsrfToken();

  // Step 1: POST /v1/chat to create a run (returns run_id)
  const createRes = await tryPaths(endpoints.chatStream, async (url) => {
    return fetchWithTimeout(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": getCsrfToken() ?? ""
      },
      body: JSON.stringify({
        conversation_id: req.conversation_id,
        input: req.input,
        provider: req.provider,
        model: req.model,
        settings: req.settings,
        stream: true
      }),
      signal
    });
  });

  if (!createRes.ok) {
    const text = await createRes.text();
    yield { type: "error", message: `HTTP ${createRes.status}: ${text}` };
    return;
  }

  const createData = await createRes.json();
  const runId = createData?.run_id ?? createData?.id;
  
  if (!runId) {
    yield { type: "error", message: "No run_id in response" };
    return;
  }

  yield { type: "meta", run_id: runId };

  // Step 2: GET /v1/chat/stream?run_id=xxx to stream events
  const streamUrl = `${endpoints.chatStreamEvents[0]}?run_id=${encodeURIComponent(runId)}`;
  
  const streamRes = await fetchWithTimeout(streamUrl, {
    method: "GET",
    credentials: "include",
    headers: {
      "Accept": "text/event-stream",
      "X-CSRF-Token": getCsrfToken() ?? ""
    },
    signal,
    timeoutMs: 0 as any
  });

  for await (const frame of parseSseResponse(streamRes, signal)) {
    const ev = frame.event || "message";
    const raw = frame.data ?? "";

    // Prefer JSON if possible.
    let obj: any = null;
    try {
      obj = JSON.parse(raw);
    } catch {
      obj = null;
    }

    if (obj) {
      // Handle canonical event: message with type:"delta" or type:"full"
      if (ev === "message") {
        const msgType = obj?.type;
        
        if (msgType === "delta") {
          // Delta: append to assistant bubble
          const delta = extractDelta(obj);
          if (delta) {
            yield { type: "delta", text: delta };
          }
          continue;
        }
        
        if (msgType === "full") {
          // Full message: replace content and optionally attach usage
          yield { 
            type: "full", 
            content: obj?.content || "", 
            message_id: obj?.message_id,
            usage: obj?.usage 
          };
          continue;
        }
      }

      // Legacy event name handling (backward compatibility)
      if (ev === "message.delta" || ev === "delta") {
        const delta = extractDelta(obj);
        if (delta) {
          yield { type: "delta", text: delta };
        }
        continue;
      }

      if (ev === "message.final" || ev === "message.created") {
        // Message complete - emit done
        yield { type: "done" };
        continue;
      }

      if (ev === "error") {
        const err = extractError(obj);
        yield { type: "error", message: err || raw || "Unknown error" };
        continue;
      }

      if (ev === "run.status") {
        const status = obj?.status;
        if (status === "error") {
          yield { type: "error", message: obj?.error_message || "Run failed" };
        } else if (status === "cancelled") {
          yield { type: "stopped" };
        } else if (status === "completed") {
          yield { type: "done" };
        }
        continue;
      }

      if (ev === "stopped") {
        yield { type: "stopped" };
        continue;
      }

      // Meta extraction for any event
      const meta = extractMeta(obj);
      if (meta.conversation_id || meta.run_id) {
        yield { type: "meta", ...meta };
      }
    }

    // Non-JSON fallback by event name
    if (ev === "delta" || ev === "message") yield { type: "delta", text: raw };
    else if (ev === "error") yield { type: "error", message: raw || "error" };
    else if (ev === "done") yield { type: "done" };
    else if (ev === "stopped") yield { type: "stopped" };
  }

  // Ensure done is emitted if stream closes without explicit completion
  yield { type: "done" };
}

/**
 * Retry a message in a conversation using the /v1/chat/retry endpoint
 */
export async function* retryChat(
  conversationId: string,
  messageId: string,
  signal: AbortSignal
): AsyncGenerator<ChatStreamEvent> {
  await ensureCsrfToken();

  // Step 1: POST /v1/chat/retry to create a retry run (returns run_id)
  const retryRes = await tryPaths(endpoints.chatRetry, async (url) => {
    return fetchWithTimeout(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": getCsrfToken() ?? ""
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        message_id: messageId
      }),
      signal
    });
  });

  if (!retryRes.ok) {
    const text = await retryRes.text();
    yield { type: "error", message: `HTTP ${retryRes.status}: ${text}` };
    return;
  }

  const retryData = await retryRes.json();
  const runId = retryData?.run_id ?? retryData?.id;
  
  if (!runId) {
    yield { type: "error", message: "No run_id in retry response" };
    return;
  }

  yield { type: "meta", run_id: runId, conversation_id: conversationId };

  // Step 2: GET /v1/chat/stream?run_id=xxx to stream events
  const streamUrl = `${endpoints.chatStreamEvents[0]}?run_id=${encodeURIComponent(runId)}`;
  
  const streamRes = await fetchWithTimeout(streamUrl, {
    method: "GET",
    credentials: "include",
    headers: {
      "Accept": "text/event-stream",
      "X-CSRF-Token": getCsrfToken() ?? ""
    },
    signal,
    timeoutMs: 0 as any
  });

  // Reuse the same event parsing logic from streamChat
  for await (const frame of parseSseResponse(streamRes, signal)) {
    const ev = frame.event || "message";
    const raw = frame.data ?? "";

    let obj: any = null;
    try {
      obj = JSON.parse(raw);
    } catch {
      obj = null;
    }

    if (obj) {
      // Handle canonical event: message with type:"delta" or type:"full"
      if (ev === "message") {
        const msgType = obj?.type;
        
        if (msgType === "delta") {
          const delta = extractDelta(obj);
          if (delta) {
            yield { type: "delta", text: delta };
          }
          continue;
        }
        
        if (msgType === "full") {
          yield { 
            type: "full", 
            content: obj?.content || "", 
            message_id: obj?.message_id,
            usage: obj?.usage 
          };
          continue;
        }
      }

      // Legacy event name handling
      if (ev === "message.delta" || ev === "delta") {
        const delta = extractDelta(obj);
        if (delta) {
          yield { type: "delta", text: delta };
        }
        continue;
      }

      if (ev === "message.final" || ev === "message.created") {
        yield { type: "done" };
        continue;
      }

      if (ev === "error") {
        const err = extractError(obj);
        yield { type: "error", message: err || raw || "Unknown error" };
        continue;
      }

      if (ev === "run.status") {
        const status = obj?.status;
        if (status === "error") {
          yield { type: "error", message: obj?.error_message || "Run failed" };
        } else if (status === "cancelled") {
          yield { type: "stopped" };
        } else if (status === "completed") {
          yield { type: "done" };
        }
        continue;
      }

      if (ev === "stopped") {
        yield { type: "stopped" };
        continue;
      }

      const meta = extractMeta(obj);
      if (meta.conversation_id || meta.run_id) {
        yield { type: "meta", ...meta };
      }
    }

    if (ev === "delta" || ev === "message") yield { type: "delta", text: raw };
    else if (ev === "error") yield { type: "error", message: raw || "error" };
    else if (ev === "done") yield { type: "done" };
    else if (ev === "stopped") yield { type: "stopped" };
  }

  yield { type: "done" };
}

/**
 * Cancel a running stream (best-effort)
 */
export async function cancelChat(runId: string): Promise<void> {
  await ensureCsrfToken();

  await tryPaths(endpoints.chatCancel, async (url) => {
    return fetchWithTimeout(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRF-Token": getCsrfToken() ?? ""
      },
      body: JSON.stringify({ run_id: runId }),
      timeoutMs: 5000
    });
  });
  // Ignore response - best-effort
}

// Optional best-effort history (safe if backend lacks these endpoints).
export async function tryLoadMessages(conversationId: string): Promise<any[] | null> {
  const replace = (p: string) => p.replace("{id}", encodeURIComponent(conversationId));

  // Try /messages first
  try {
    const msgs = await tryPaths(endpoints.conversationMessages.map(replace), async (url) => {
      const res = await fetchWithTimeout(url, {
        method: "GET",
        credentials: "include",
        headers: { "Accept": "application/json" },
        timeoutMs: 15000
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    });
    return Array.isArray(msgs) ? msgs : (Array.isArray((msgs as any)?.items) ? (msgs as any).items : null);
  } catch {
    // Try conversation detail as fallback
    try {
      const convo = await tryPaths(endpoints.conversationGet.map(replace), async (url) => {
        const res = await fetchWithTimeout(url, {
          method: "GET",
          credentials: "include",
          headers: { "Accept": "application/json" },
          timeoutMs: 15000
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      });
      const m = (convo as any)?.messages ?? (convo as any)?.items;
      return Array.isArray(m) ? m : null;
    } catch {
      return null;
    }
  }
}
