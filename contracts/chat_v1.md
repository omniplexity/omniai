# v1 Chat Contract (Canonical)

Wire-level contract for `/v1/chat/*` endpoints. Both frontend and backend must conform to these shapes exactly.

## Endpoints

### POST /v1/chat — Create Run

**Request:**
```json
{
  "conversation_id": "string (required)",
  "input": "string (required if stream=true and no retry_from_message_id)",
  "stream": true,
  "provider": "string | null",
  "model": "string | null",
  "settings": { "temperature": 0.7, "top_p": 0.9, "max_tokens": 2048 } | null
}
```

**Response (stream=true):**
```json
{ "run_id": "string", "status": "running" }
```

Client must then open `GET /v1/chat/stream?run_id={run_id}` to receive events.

### GET /v1/chat/stream — Stream Events (SSE)

**Query params:**
- `run_id` (required) — run to stream
- `after` (optional) — sequence number; only events with `seq > after` are returned

**Header alternative:** `Last-Event-ID: {seq}` (RFC 6202)

**Response:** `text/event-stream` with canonical events (see below).

### POST /v1/chat/retry — Retry Message

**Request:**
```json
{
  "conversation_id": "string (required)",
  "message_id": "string (required)",
  "provider": "string | null",
  "model": "string | null",
  "settings": { ... } | null
}
```

**Response:**
```json
{ "run_id": "string", "status": "running" }
```

Same streaming flow as POST /v1/chat.

### POST /v1/chat/cancel — Cancel Run

**Request:**
```json
{ "run_id": "string (required)" }
```

**Response:**
```json
{ "status": "cancelled", "run_id": "string" }
```

---

## SSE Event Types

Every SSE frame has the form:
```
id: {seq}
event: {type}
data: {json}

```

### event: message

**Delta (streaming chunk):**
```json
{ "type": "delta", "content": "string" }
```

**Full (complete message):**
```json
{
  "type": "full",
  "content": "string",
  "message_id": "string",
  "usage": { "prompt": 10, "completion": 5, "total": 15 }
}
```

Invariant: deltas append; full replaces. A run that emits both must produce one final assistant message with correct content.

### event: done

```json
{ "status": "completed", "message_id": "string", "run_id": "string" }
```

Terminal. Stream closes after this event.

### event: stopped

```json
{ "run_id": "string" }
```

Terminal. Emitted when run is cancelled (via POST /v1/chat/cancel or user abort). UI must mark the assistant message as `stopped`, not `error`.

### event: error

```json
{ "error": "string", "code": "string" }
```

Terminal. UI must mark the assistant message as `error`.

---

## Security Requirements

| Requirement | Details |
|---|---|
| Authentication | Session cookie (HttpOnly, Secure, SameSite=None for cross-site) |
| CSRF | `X-CSRF-Token` header on all POST requests |
| Origin validation | SSE stream validates `Origin` header against `CORS_ORIGINS` |
| Credentials | `credentials: "include"` on all fetch calls (POST, GET SSE) |
| Isolation | Users can only access their own conversations and runs (404 for others) |

## Keepalive

Server sends `: ping\n\n` comment frames every `sse_ping_interval_seconds` (default 20s) when idle.

## Resumption

Client can reconnect with `?after={last_seq}` to resume from the last received event. Backend persists all events in `chat_run_events` table with monotonic sequence numbers per run.
