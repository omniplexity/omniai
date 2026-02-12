# Phase 0 Plan: Contract + Flag + CI Baseline

## Scope

Lock v1 baseline without adding new `/api/*` routes and keep new behavior additive.

## Tasks

- [ ] Add Phase index doc and this execution plan.
- [ ] Normalize `contracts/`:
  - [ ] `contracts/openapi.yaml` includes canonical `/v1` server and `/meta`.
  - [ ] `contracts/schemas/error.json` defines canonical error envelope.
  - [ ] `contracts/errors.md` defines stable error code registry.
  - [ ] `contracts/flags.json` defines server-authoritative flags/defaults.
  - [ ] `contracts/endpoints.md` classifies endpoints by lane (UI/Public/Dev/Legacy).
- [ ] Harden backend meta + error formatting:
  - [ ] `/v1/meta` includes build info, lane metadata, authoritative flags.
  - [ ] Error envelope consistency for meta/auth routes in `/v1/*`.
  - [ ] Add/extend tests for meta and error envelope shape.
- [ ] Frontend boot baseline:
  - [ ] Boot sequence loads runtime config then `/v1/meta` via central API layer.
  - [ ] Shell renders with persistent backend-unreachable banner (retry supported).
  - [ ] Unit tests for boot/meta success/failure behavior.
- [ ] Playwright + CI baseline:
  - [ ] Smoke covers login -> send -> stream -> cancel -> retry (no duplicates).
  - [ ] CI triggers include `contracts/**` and keep deterministic seeded-user path.

## Acceptance Criteria

- Backend:
  - `pytest` passes.
  - `/v1/meta` returns `meta_version`, `server.build_*`, `lanes`, `features`, `flags`.
  - `/v1/*` auth/meta error responses use canonical envelope.
  - No new `/api/*` routes are introduced.
- Frontend:
  - `npm run build` passes.
  - App startup does not hard-crash when backend is unreachable.
  - Persistent banner is visible with retry action.
- E2E/CI:
  - Playwright smoke passes in deterministic Chromium run.
  - CI runs backend tests, frontend build, and Playwright smoke on relevant changes.

## Verification Commands

- Backend:
  - `python -m pytest -q backend/tests/test_v1_meta.py backend/tests/test_v1_error_envelope.py backend/tests/test_auth_sessions.py`
  - `python -m pytest -q`
- Frontend:
  - `cd frontend && npm ci`
  - `cd frontend && npm run build`
  - `cd frontend && npm run test`
- Playwright local smoke:
  - Start backend with:
    - `ENVIRONMENT=test`
    - `COOKIE_SECURE=false`
    - `COOKIE_SAMESITE=lax`
    - `PROVIDER_MODE=mock`
    - `E2E_SEED_USER=1`
    - `E2E_USERNAME=<user>`
    - `E2E_PASSWORD=<pass>`
  - Run:
    - `cd frontend && npx playwright test tests/e2e/chat-stream.spec.ts --project=chromium`

## Rollback

- Keep new flags default `false` unless required for existing baseline behavior.
- Revert Phase 0 commits in reverse order if needed.
- Server remains authoritative through `/v1/meta`; disable new capability via flags first.
- Use `docs/PHASE_B_VERIFICATION.md` after rollback to confirm cross-site/session behavior.

## Phase 1 Frontend Closure Checklist

- [ ] Canonical API client in `frontend/src/core/api/client.ts` is used for session + mutating calls.
- [ ] CSRF flow is single-path (`/v1/auth/csrf/bootstrap`), with E2002 refresh+retry once.
- [ ] 401 handling triggers `/v1/meta` sync path only.
- [ ] Frontend has no references to `/api/auth/csrf/bootstrap`.
- [ ] `npm run test` and `npm run build` are green after migration.
- [ ] Legacy `/api/auth/csrf/bootstrap` behavior remains explicitly verified in backend tests (compat mode).
