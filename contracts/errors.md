# OmniAI Stable Error Code Registry (Phase 0 Baseline)

This registry defines stable error codes for `/v1/*` responses.

## Canonical Envelope

All `/v1/*` errors must use:

```json
{
  "error": {
    "code": "E5000",
    "message": "Internal server error",
    "detail": null,
    "request_id": "..."
  }
}
```

`detail` is optional and user-safe. Stack traces must never be returned.

## Existing Numeric Codes (Retained)

- `E2000`: authentication required
- `E2001`: authorization denied
- `E3000`: provider failure / upstream proxy issue
- `E4040`: resource not found
- `E4220`: validation error
- `E5000`: internal server error
- `E4010`, `E4030`, `E4290`, `E4000` etc.: HTTPException-derived fallback codes (`E{status}0`)

## Stable Semantic Codes (Phase 0 Reserved)

- `E_CAPABILITY_DISABLED`: feature/capability exists but is disabled by server policy/flags
- `E_RATE_LIMITED`: request or stream limit exceeded
- `E_PROVIDER_TIMEOUT`: provider timed out
- `E_PROVIDER_MODEL_NOT_FOUND`: requested model unavailable
- `E_CSRF_INVALID`: CSRF token missing/invalid
- `E_SESSION_INVALID`: session missing/expired

## Notes

- Existing numeric codes are backward-compatible and remain valid.
- Semantic codes can be adopted endpoint-by-endpoint without changing HTTP statuses.
