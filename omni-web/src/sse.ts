export type SseClientOptions<T> = {
  getCursor: () => number;
  setCursor: (cursor: number) => void;
  onEvent: (event: T, eventName: string, id: number) => void;
  onHeartbeat?: (payload: unknown) => void;
  parse?: (raw: string) => T;
  withCredentials?: boolean;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
};

export type SseClient = { close: () => void };

export function createSseClient<T>(urlBase: string, options: SseClientOptions<T>): SseClient {
  let closed = false;
  let es: EventSource | null = null;
  let backoff = options.initialBackoffMs ?? 500;
  const maxBackoff = options.maxBackoffMs ?? 5000;
  let reconnectTimer: number | null = null;

  const parse = options.parse ?? ((raw: string) => JSON.parse(raw) as T);

  const open = () => {
    if (closed) return;
    const url = `${urlBase}${urlBase.includes("?") ? "&" : "?"}after_seq=${options.getCursor()}`;
    es = new EventSource(url, { withCredentials: options.withCredentials ?? true });

    es.addEventListener("heartbeat", (ev) => {
      try {
        options.onHeartbeat?.(JSON.parse((ev as MessageEvent).data));
      } catch {
        options.onHeartbeat?.(null);
      }
    });

    const handle = (name: string) => (ev: Event) => {
      const msg = ev as MessageEvent;
      const id = Number(msg.lastEventId || 0);
      if (id > 0) options.setCursor(id);
      options.onEvent(parse(msg.data), name, id);
    };

    es.addEventListener("run_event", handle("run_event"));
    es.addEventListener("activity", handle("activity"));
    es.addEventListener("notification", handle("notification"));

    es.onopen = () => {
      backoff = options.initialBackoffMs ?? 500;
    };
    es.onerror = () => {
      es?.close();
      es = null;
      if (closed) return;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        open();
      }, backoff);
      backoff = Math.min(maxBackoff, backoff * 2);
    };
  };

  open();
  return {
    close: () => {
      closed = true;
      es?.close();
      es = null;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    },
  };
}
