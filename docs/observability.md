# Observability

## Client Events Ingest

OmniAI supports optional client-side telemetry ingest via:

- `POST /v1/client-events`

This endpoint is metadata-only and is disabled by default.

## Backend Flags

- `CLIENT_EVENTS_ENABLED=false` (default)
- `CLIENT_EVENTS_MAX_BATCH=50` (default)
- `CLIENT_EVENTS_RPM=120` (default)
- `CLIENT_EVENTS_MAX_SAMPLE_RATE=0.1` (default)
- `CLIENT_EVENTS_FORCE_SAMPLE_RATE` unset by default (optional hard override)
- `CLIENT_EVENTS_SAMPLING_MODE=hash` (default, deterministic)

Enable only in environments where operational telemetry is needed.

## Frontend Flags

Runtime config:

- `FEATURE_FLAGS.CLIENT_EVENTS_HTTP=true` to enable HTTP sink
- `FEATURE_FLAGS.CLIENT_EVENTS_SAMPLE_RATE` optional `0.0-1.0` sampling

When disabled, frontend keeps console-only event logs.

## Privacy Rules

Only metadata fields are sent:

- `type`
- `run_id`
- `backend_run_id`
- `conversation_id`
- `code`
- `ts`

Message content and token payloads must never be emitted.

## Sampling Hierarchy

Server decides effective rate:

1. If `CLIENT_EVENTS_FORCE_SAMPLE_RATE` is set, it is always used.
2. Otherwise: `min(client_reported_rate_or_1.0, CLIENT_EVENTS_MAX_SAMPLE_RATE)`.

Deterministic hash mode uses key:

`{user_id}:{event_type}:{run_id}:{ts}:{event_seq}`

(`event_seq` may be empty when not provided)

## Operational Toggle / Incident Response

1. Disable frontend sink by setting `FEATURE_FLAGS.CLIENT_EVENTS_HTTP=false`.
2. Disable backend ingest with `CLIENT_EVENTS_ENABLED=false`.
3. Emergency volume reduction: set `CLIENT_EVENTS_FORCE_SAMPLE_RATE=0.02`.
4. Validate with smoke script and confirm chat behavior is unaffected.

## Debugging

If ingest is enabled and failing:

1. Check backend logs for `Client event ingested`.
2. Check browser console for:
   - `[client-event] telemetry sink unavailable`
3. Verify CSRF/session headers on `/v1/client-events`.
4. Verify endpoint response fields:
   - `accepted_count`
   - `dropped_count`
   - `effective_sample_rate`
