# Rollback Playbook

## Trigger Conditions

Rollback if any of the following occur after deploy:
- chat streaming fails for valid sessions
- repeated `E2002`, `E2003`, `E2004` after baseline checks
- auth/session loops caused by frontend/runtime mismatch
- severe UI regression affecting send/cancel/retry core flow

## Immediate Actions

1. Identify the last known-good release commit/tag.
2. Redeploy previous frontend artifact bundle.
3. Restore last known-good `runtime-config.json`.
4. Verify backend endpoint health (`/health`) and session endpoints.

## Verification After Rollback

1. Run smoke script:
   - `bash scripts/smoke-frontend.sh ...` or `.\scripts\smoke-frontend.ps1 ...`
2. Confirm:
   - login succeeds
   - create run succeeds
   - stream returns data + terminal event
   - cancel endpoint succeeds
3. Confirm UI diagnostics show expected `BUILD_INFO` for rolled-back version.

## Post-Incident Notes

1. Capture failure symptoms and timeframe.
2. Record exact broken `BUILD_INFO` and runtime config hash.
3. Link failing CI run and smoke output.
4. Open fix-forward ticket before reattempting release.

