import { fetchWithCsrf } from "../auth/csrf";
import { getRuntimeConfig } from "../config/runtimeConfig";

type ClientEventType =
  | "run_start"
  | "run_first_delta"
  | "run_done"
  | "run_cancel"
  | "run_error";

type ClientEvent = {
  type: ClientEventType;
  runId: string;
  backendRunId?: string;
  conversationId?: string;
  code?: string;
};

const MAX_QUEUE = 200;
const FLUSH_BATCH_SIZE = 10;
const FLUSH_INTERVAL_MS = 2000;

let queue: ClientEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let overflowWarned = false;

export function emitClientEvent(event: ClientEvent): void {
  // Always keep console telemetry.
  console.info("[client-event]", event);

  const cfg = getRuntimeConfig();
  const flags = (cfg.FEATURE_FLAGS ?? {}) as Record<string, unknown>;
  const enabled = flags.CLIENT_EVENTS_HTTP === true;
  if (!enabled) return;

  const sampleRate = readSampleRate(flags.CLIENT_EVENTS_SAMPLE_RATE);
  if (Math.random() > sampleRate) return;

  if (queue.length >= MAX_QUEUE) {
    queue.shift();
    if (!overflowWarned) {
      overflowWarned = true;
      console.warn("[client-event] queue overflow, dropping oldest events");
    }
  }
  queue.push(event);
  scheduleFlush();
}

function readSampleRate(raw: unknown): number {
  if (typeof raw === "number" && raw >= 0 && raw <= 1) return raw;
  if (typeof raw === "string") {
    const parsed = Number(raw);
    if (!Number.isNaN(parsed) && parsed >= 0 && parsed <= 1) return parsed;
  }
  return 1.0;
}

function scheduleFlush(): void {
  if (flushTimer !== null) return;
  flushTimer = globalThis.setTimeout(() => {
    flushTimer = null;
    void flushQueue();
  }, FLUSH_INTERVAL_MS);
  if (queue.length >= FLUSH_BATCH_SIZE) {
    globalThis.clearTimeout(flushTimer);
    flushTimer = null;
    void flushQueue();
  }
}

async function flushQueue(): Promise<void> {
  if (queue.length === 0) return;
  const flags = (getRuntimeConfig().FEATURE_FLAGS ?? {}) as Record<string, unknown>;
  const clientSampleRate = readSampleRate(flags.CLIENT_EVENTS_SAMPLE_RATE);
  const batch = queue.splice(0, FLUSH_BATCH_SIZE).map(toBackendEvent);
  await postBatch(batch, 0, clientSampleRate);
  if (queue.length > 0) scheduleFlush();
}

function toBackendEvent(event: ClientEvent) {
  return {
    type: event.type,
    run_id: event.runId,
    backend_run_id: event.backendRunId,
    conversation_id: event.conversationId,
    code: event.code,
    ts: new Date().toISOString(),
  };
}

async function postBatch(
  events: Array<Record<string, unknown>>,
  attempt: number,
  clientSampleRate: number
): Promise<void> {
  const baseUrl = getRuntimeConfig().BACKEND_BASE_URL;
  try {
    const res = await fetchWithCsrf(
      `${baseUrl}/v1/client-events`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Client-Events-Sample-Rate": String(clientSampleRate),
        },
        body: JSON.stringify({ events }),
      },
      { baseUrl, retryOnE2002: true }
    );
    if (!res.ok) {
      throw new Error(`Telemetry POST failed (${res.status})`);
    }
  } catch (err) {
    if (attempt < 1) {
      await new Promise((resolve) => setTimeout(resolve, 500));
      await postBatch(events, attempt + 1, clientSampleRate);
    } else {
      console.warn("[client-event] telemetry sink unavailable", err);
    }
  }
}

export function __resetClientEventsForTest(): void {
  queue = [];
  overflowWarned = false;
  if (flushTimer !== null) {
    globalThis.clearTimeout(flushTimer);
    flushTimer = null;
  }
}
