# Phase 3 Contract-Exact SSE Alignment

## Implemented

- Canonical route alignment: adapter now posts to `.../v1/chat`.
- Dual event-schema support with strict normalization:
  - OmniAI normalized events:
    - `{"type":"delta","delta":"..."}`
    - `{"type":"role","role":"assistant"}`
    - `{"type":"error","message":"..."}`
    - `{"type":"done"}`
  - OpenAI-compatible streamed events:
    - `{"choices":[{"delta":{"content":"..."}}]}`
    - `{"choices":[{"delta":{"role":"assistant"}}]}`
    - `{"choices":[{"finish_reason":"stop"}]}`
    - `data: [DONE]`
- Strict schema enforcement:
  - malformed JSON => protocol parse error
  - unsupported shape => protocol schema mismatch error
  - backend error event => stream error
- Stable error-code normalization in UI:
  - `backend_http_error`
  - `backend_stream_error`
  - `backend_schema_mismatch`
  - `backend_parse_error`
- Cancellation hardening:
  - store remains authority for stream state
  - abort uses `AbortController`
  - abort is surfaced as cancel message, not backend failure
  - stream cleanup always clears active abort controller

## Protocol Validation Checklist

- Verify `/v1/chat` responds with `Content-Type: text/event-stream`.
- Verify `Cache-Control: no-cache` (or equivalent no-buffering headers).
- Verify each chunk is framed as `data: ...` and newline-delimited.
- Verify backend flushes regularly during token generation.
- Verify backend emits final `data: [DONE]` or terminal done event.
- Verify client cancellation closes stream promptly server-side.
