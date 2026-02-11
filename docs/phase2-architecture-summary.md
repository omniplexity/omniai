# Phase 2 Architecture Summary

## Achieved

- Added provider abstraction boundary via `ChatApiAdapter`.
- Implemented real SSE streaming adapter (`SSEBackendAdapter`) using:
  - `fetch` + `ReadableStream` reader
  - `AbortController`/`AbortSignal`
  - line-buffered SSE `data:` parsing
  - graceful `[DONE]` termination
  - malformed-line tolerance
- Moved streaming authority to store:
  - `isStreaming` state
  - authoritative `cancelStream()` action
  - tracked active `AbortController`
- Wired `MainLayout` to adapter flow:
  - Send -> stream via adapter
  - Cancel button in navbar
  - deterministic retry from stored request message payload
  - explicit cancelled/error assistant bubble outcomes

## Current Boundaries

- UI does not directly parse transport details.
- `MainLayout` depends on `ChatApiAdapter` interface, not transport internals.
- Streaming lifecycle control resides in `chatStore` instead of local UI flags.

## Next-Phase Hooks

- Feature-flag adapter switching:
  - route between `SSEBackendAdapter` and placeholder/mock adapter from runtime config.
- Contract hardening:
  - strict stream chunk validation and stable backend error code mapping.
- Retry evolution:
  - add message branching metadata so retries are first-class conversation operations.
- Reconnect strategy:
  - heartbeat detection and exponential backoff for recoverable stream interruptions.
- Performance guardrails:
  - chunk batching/backpressure controls and max-output/token cutoff policy.
