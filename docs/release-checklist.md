# Release Checklist

See `docs/v1.0-launch-execution.md` for the full gate execution runbook and
`docs/v1.0-go-no-go.md` for final signoff.

## Pre-release Gates

1. Run Gate A (health + preflight CORS matrix, no creds):
   - Bash: `API_BASE_URL=<url> ORIGINS=<allowed,disallowed> ALLOWED_ORIGINS=<allowed> GATE_A_MODE=preflight bash scripts/launch-gate-a.sh`
   - PowerShell: `$env:API_BASE_URL="<url>"; $env:ORIGINS="<allowed,disallowed>"; $env:ALLOWED_ORIGINS="<allowed>"; $env:GATE_A_MODE="preflight"; .\scripts\launch-gate-a.ps1`
2. Run Gate B (authenticated smoke, allowed origins only):
   - Bash: `API_BASE_URL=<url> ORIGINS=<allowed-only> ALLOWED_ORIGINS=<allowed-only> GATE_A_MODE=smoke SMOKE_USERNAME=<user> SMOKE_PASSWORD=<pass> bash scripts/launch-gate-a.sh`
   - PowerShell: `$env:API_BASE_URL="<url>"; $env:ORIGINS="<allowed-only>"; $env:ALLOWED_ORIGINS="<allowed-only>"; $env:GATE_A_MODE="smoke"; $env:SMOKE_USERNAME="<user>"; $env:SMOKE_PASSWORD="<pass>"; .\scripts\launch-gate-a.ps1`
3. Run frontend static gates:
   - `cd frontend`
   - `npm run typecheck`
   - `npm run test`
   - `npm run build`
4. Run backend seed boundary test:
   - `python -m pytest backend/tests/test_e2e_seed_user.py -q`
5. Validate CI E2E passes with no-secrets deterministic test user.
6. If telemetry is enabled, validate `/v1/client-events` ingest path and rate limit behavior.
7. Verify telemetry sampling response fields (`accepted_count`, `dropped_count`, `effective_sample_rate`) align with configured max/force rates.
8. Verify backend auto-deploy workflow can run unattended:
   - `.github/workflows/deploy-backend-duckdns.yml`
   - Required repository secrets:
     - `DUCKDNS_SSH_HOST`
     - `DUCKDNS_SSH_USER`
     - `DUCKDNS_SSH_KEY`
     - `SMOKE_USERNAME`
     - `SMOKE_PASSWORD`

## Runtime/Config Validation

1. Confirm `runtime-config.json` includes:
   - valid `BACKEND_BASE_URL`
   - expected `FEATURE_FLAGS`
   - `BUILD_INFO.build_sha`
   - `BUILD_INFO.build_timestamp`
   - `BUILD_INFO.runtime_config_hash`
2. Confirm build provenance does not alter route/security fields.

## Security Validation

1. Confirm authenticated `/v1/*` requests enforce:
   - cookie auth
   - `Origin`/`Referer` policy
   - CSRF token header on state-changing requests
2. Confirm stream endpoint (`/v1/chat/stream`) rejects disallowed origins.
3. Confirm cross-site auth cookies from `/v1/auth/csrf/bootstrap` and `/v1/auth/login` include:
   - `Secure`
   - `SameSite=None`
   - `Partitioned`

## Sign-off

1. Update changelog/release notes.
2. Tag release from the tested commit SHA.
3. Store smoke output and CI run link with release record.
