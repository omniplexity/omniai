# Smoke Commands

## Environment Inputs

- `BASE_URL` or `API_BASE_URL`: backend base URL
- `ORIGIN`: expected frontend origin (for Origin/CSRF policy)
- `GATE_A_MODE`: `preflight` (default) or `smoke`
- `ALLOWED_ORIGINS`: CSV allowlist used to score each tested origin as allowed/disallowed
- `E2E_USERNAME`: test username
- `E2E_PASSWORD`: test password
- `SMOKE_USERNAME` / `SMOKE_PASSWORD`: optional aliases used in `GATE_A_MODE=smoke`
  - Keep these as operational secrets (environment/CI secret store), never committed in repo.

## Linux/macOS (bash)

```bash
export BASE_URL="https://omniplexity.duckdns.org"
export ORIGIN="https://<your-pages-origin>"
export E2E_USERNAME="ci_e2e_user"
export E2E_PASSWORD="ci_e2e_pass"
bash scripts/smoke-frontend.sh
```

Gate A matrix helper:

```bash
ORIGINS="https://omniplexity.github.io,https://your.custom.domain" \
API_BASE_URL="https://omniplexity.duckdns.org" \
ALLOWED_ORIGINS="https://omniplexity.github.io,https://your.custom.domain" \
GATE_A_MODE="preflight" \
bash scripts/launch-gate-a.sh
```

## Windows (PowerShell)

```powershell
$env:BASE_URL = "https://omniplexity.duckdns.org"
$env:ORIGIN = "https://<your-pages-origin>"
$env:E2E_USERNAME = "ci_e2e_user"
$env:E2E_PASSWORD = "ci_e2e_pass"
.\scripts\smoke-frontend.ps1
```

Gate A matrix helper:

```powershell
$env:ORIGINS = "https://omniplexity.github.io,https://your.custom.domain"
$env:API_BASE_URL = "https://omniplexity.duckdns.org"
$env:ALLOWED_ORIGINS = "https://omniplexity.github.io,https://your.custom.domain"
$env:GATE_A_MODE = "preflight"
.\scripts\launch-gate-a.ps1
```

Gate A authenticated smoke mode (allowed origin only):

```bash
ORIGINS="https://omniplexity.github.io" \
ALLOWED_ORIGINS="https://omniplexity.github.io" \
API_BASE_URL="https://omniplexity.duckdns.org" \
GATE_A_MODE="smoke" \
SMOKE_USERNAME="your_smoke_user" \
SMOKE_PASSWORD="your_smoke_password" \
bash scripts/launch-gate-a.sh
```

```powershell
$env:ORIGINS = "https://omniplexity.github.io"
$env:ALLOWED_ORIGINS = "https://omniplexity.github.io"
$env:API_BASE_URL = "https://omniplexity.duckdns.org"
$env:GATE_A_MODE = "smoke"
$env:SMOKE_USERNAME = "your_smoke_user"
$env:SMOKE_PASSWORD = "your_smoke_password"
.\scripts\launch-gate-a.ps1
```

Gate A evidence bundling (matrix + per-origin logs + env summary):

```bash
bash scripts/bundle-gate-a.sh
```

```powershell
.\scripts\bundle-gate-a.ps1
```

## Expected Successful Output

- bootstrap returns `csrf_token` and sets `omni_csrf` cookie
- login succeeds
- conversation creation returns `id`
- run creation returns `run_id`
- stream includes `data:` and terminal marker (`[DONE]` or done event)
- cancel request returns success

## Common Failures

- `E2002`: CSRF mismatch/token missing.
  - verify `X-CSRF-Token` and `omni_csrf` cookie.
- `E2003` / `E2004`: Origin/Referer policy block.
  - verify `Origin` header matches allowed frontend origin.
- Gate A matrix disallowed origin:
  - expected to pass by showing *absence* of `Access-Control-Allow-Origin` and `Access-Control-Allow-Credentials`.
- Stream fails with no events:
  - verify backend run exists and stream URL uses valid `run_id`.

## Telemetry Sampling Sanity Check (Optional)

When telemetry ingest is enabled, verify response includes:

- `accepted_count`
- `dropped_count`
- `effective_sample_rate`

Example expected behavior:

- client reports `1.0`, backend max `0.1` -> `effective_sample_rate` should be `0.1`.
- backend force `0.02` -> `effective_sample_rate` should be `0.02` regardless of client header.
