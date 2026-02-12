import type { ChatApiAdapter, StreamChunk, StreamMeta } from "./ChatApiAdapter";
import { getRuntimeConfig } from "../config/runtimeConfig";
import { parseSSE } from "./sseParser";
import { fetchWithCsrf, fetchWithSession } from "../auth/csrf";

export type ChatErrorCode =
  | "backend_http_error"
  | "backend_stream_error"
  | "backend_schema_mismatch"
  | "backend_parse_error";

export class ChatProtocolError extends Error {
  code: ChatErrorCode;
  status?: number;
  backendCode?: string;

  constructor(code: ChatErrorCode, message: string, meta?: { status?: number; backendCode?: string }) {
    super(message);
    this.name = "ChatProtocolError";
    this.code = code;
    this.status = meta?.status;
    this.backendCode = meta?.backendCode;
  }
}

type CanonicalMessageEvent =
  | { type: "delta"; content: string }
  | { type: "full"; content: string; message_id?: string; usage?: Record<string, unknown> };

export class SSEBackendAdapter implements ChatApiAdapter {
  async createRun(params: {
    conversationId: string;
    input: string;
    retryFromMessageId?: string;
    signal: AbortSignal;
    provider?: string;
    model?: string;
    settings?: Record<string, unknown>;
  }): Promise<{ runId: string; status: string }> {
    const base = getRuntimeConfig().BACKEND_BASE_URL;
    const res = await fetchWithCsrf(
      `${base}/v1/chat`,
      {
        method: "POST",
        signal: params.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: params.conversationId,
          input: params.input,
          retry_from_message_id: params.retryFromMessageId,
          provider: params.provider,
          model: params.model,
          settings: params.settings,
          stream: true,
        }),
      },
      { baseUrl: base, retryOnE2002: true }
    );

    if (!res.ok) {
      const body = await safeReadJsonOrText(res);
      throw new ChatProtocolError(
        "backend_http_error",
        `Backend error (${res.status}): ${body.message}`,
        { status: res.status, backendCode: body.backendCode ?? undefined }
      );
    }

    const json = (await res.json()) as { run_id?: string; status?: string };
    if (!json.run_id || !json.status) {
      throw new ChatProtocolError(
        "backend_schema_mismatch",
        "Malformed create-run response from backend."
      );
    }
    return { runId: json.run_id, status: json.status };
  }

  async *streamRun(params: { runId: string; signal: AbortSignal }): AsyncGenerator<
    StreamChunk,
    void,
    void
  > {
    const base = getRuntimeConfig().BACKEND_BASE_URL;
    const res = await fetchWithSession(`${base}/v1/chat/stream?run_id=${encodeURIComponent(params.runId)}`, {
      method: "GET",
      headers: { Accept: "text/event-stream" },
      signal: params.signal,
    }, { baseUrl: base });

    if (!res.ok || !res.body) {
      const body = await safeReadJsonOrText(res);
      throw new ChatProtocolError(
        "backend_http_error",
        `Backend error (${res.status}): ${body.message}`,
        { status: res.status, backendCode: body.backendCode ?? undefined }
      );
    }

    const reader = res.body.getReader();
    for await (const evt of parseSSE(reader)) {
      const payload = evt.data.trim();
      if (!payload) continue;
      if (payload === "[DONE]") {
        yield { type: "done" };
        return;
      }

      const parsed = safeParse(payload);
      if (!parsed) {
        throw new ChatProtocolError(
          "backend_parse_error",
          "Malformed SSE JSON payload from backend."
        );
      }

      const eventType = (evt.event ?? "message").trim();
      if (eventType === "message") {
        const meta = extractMetaFromPayload(parsed, parseEventSeq(evt.id));
        if (Object.keys(meta).length > 0) {
          yield { type: "meta", meta };
        }
        const msg = normalizeCanonicalMessage(parsed);
        if (msg.type === "delta" && msg.content) {
          yield { type: "delta", delta: msg.content };
        }
        continue;
      }

      if (eventType === "done") {
        const meta = extractMetaFromPayload(parsed, parseEventSeq(evt.id));
        if (Object.keys(meta).length > 0) {
          yield { type: "meta", meta };
        }
        yield { type: "done" };
        return;
      }

      if (eventType === "stopped") {
        const meta = extractMetaFromPayload(parsed, parseEventSeq(evt.id));
        if (Object.keys(meta).length > 0) {
          yield { type: "meta", meta };
        }
        throw new DOMException("Aborted", "AbortError");
      }

      if (eventType === "error") {
        const errorObj = parsed as { error?: string; code?: string };
        throw new ChatProtocolError(
          "backend_stream_error",
          errorObj.error ?? "Backend stream error",
          { backendCode: errorObj.code }
        );
      }
    }

    yield { type: "done" };
  }

  async cancelRun(params: { runId: string; signal?: AbortSignal }): Promise<void> {
    const base = getRuntimeConfig().BACKEND_BASE_URL;
    const res = await fetchWithCsrf(
      `${base}/v1/chat/cancel`,
      {
        method: "POST",
        signal: params.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: params.runId }),
      },
      { baseUrl: base, retryOnE2002: true }
    );
    if (!res.ok) {
      const body = await safeReadJsonOrText(res);
      throw new ChatProtocolError(
        "backend_http_error",
        `Backend error (${res.status}): ${body.message}`,
        { status: res.status, backendCode: body.backendCode ?? undefined }
      );
    }
  }
}

function extractMetaFromPayload(payload: unknown, eventSeq?: number): StreamMeta {
  const e = payload as Record<string, unknown>;
  const meta: StreamMeta = {};
  if (eventSeq !== undefined) meta.eventSeq = eventSeq;

  const runId = pickString(e.run_id);
  if (runId !== undefined) meta.backendRunId = runId;

  const convId = pickString(e.conversation_id);
  if (convId !== undefined) meta.conversationId = convId;

  const sourceId = pickString(e.source_message_id) ?? pickString(e.input_message_id);
  if (sourceId !== undefined) meta.sourceMessageId = sourceId;

  const resultId = pickString(e.message_id);
  if (resultId !== undefined) meta.resultMessageId = resultId;

  const eventTs = pickString(e.event_ts) ?? pickString(e.timestamp);
  if (eventTs !== undefined) meta.eventTs = eventTs;

  return meta;
}

function parseEventSeq(eventId: string | undefined): number | undefined {
  if (!eventId) return undefined;
  if (!/^\d+$/.test(eventId)) return undefined;
  return Number(eventId);
}

function pickString(value: unknown): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value === "string") return value;
  throw new ChatProtocolError(
    "backend_schema_mismatch",
    "Metadata field present with invalid type."
  );
}

function normalizeCanonicalMessage(obj: unknown): CanonicalMessageEvent {
  const e = obj as Record<string, unknown>;
  if (e?.type === "delta" && typeof e.content === "string") {
    return { type: "delta", content: e.content };
  }
  if (e?.type === "full" && typeof e.content === "string") {
    return { type: "full", content: e.content };
  }
  throw new ChatProtocolError(
    "backend_schema_mismatch",
    "Unsupported canonical message event schema."
  );
}

function safeParse(payload: string): unknown | null {
  try {
    return JSON.parse(payload);
  } catch {
    return null;
  }
}

async function safeReadJsonOrText(
  res: Response
): Promise<{ message: string; backendCode: string | null }> {
  try {
    const json = (await res.json()) as { detail?: string; error?: { code?: string; message?: string } };
    return {
      message: json.error?.message ?? json.detail ?? "Unknown error",
      backendCode: json.error?.code ?? null,
    };
  } catch {
    try {
      return { message: (await res.text()) || "Unknown error", backendCode: null };
    } catch {
      return { message: "Unknown error", backendCode: null };
    }
  }
}
