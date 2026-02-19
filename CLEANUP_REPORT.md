# OmniAI Cleanup Report

## Scope and approach
- Scope: `omni-web`, `omni-backend`, `omni-contracts`, plus repo-root hygiene.
- Method: evidence-first cleanup only (imports/references/build artifacts), low-risk deletions first, then full validation.
- Note: workspace was already dirty before this pass (`git status` had pre-existing frontend/backend edits and deletions).

## Phase 0: Workspace map
- Workspace packages:
  - `omni-web` (Vite + React SPA)
  - `omni-backend` (FastAPI app, SQLAlchemy, pytest)
  - `omni-contracts` (schemas/models package, pytest)
- Entrypoints:
  - Frontend: `omni-web/src/main.tsx`
  - Backend app: `omni-backend/omni_backend/main.py` (`create_app()` from `omni_backend/app.py`)
  - Contracts package: `omni-contracts/python/...`
- Test runners:
  - Frontend e2e: Playwright (`omni-web/tests/e2e`)
  - Backend: pytest (`omni-backend/tests`)
  - Contracts: pytest (`omni-contracts/tests`)

## Phase 1: Baseline checks (before new cleanup edits)

### Frontend (`omni-web`)
- `npm ci` -> exit `0` (success)
- `npm run build` -> exit `0` (success)
- `npx playwright test` -> exit `0` (6 passed)

### Backend (`omni-backend`)
- Install method: `python -m pip install -e .[dev]` (from `pyproject.toml`) -> exit `0`
- `pytest -q` -> exit `1` (pre-existing failures, not introduced by this cleanup):
  - `tests/test_v2.py::test_run_service_seq_monotonicity` (`RunService.create_run()` missing `thread_id`)
  - `tests/test_v2.py::test_run_service_get_events_after`
  - `tests/test_v2.py::test_run_service_cursor_format`
  - `tests/test_v2.py::test_v2_run_crud` (422 != 200)
  - `tests/test_v2.py::test_v2_events_api`

### Contracts (`omni-contracts`)
- `python -m pip install -e .` -> exit `0`
- `pytest -q` -> exit `0` (116 passed)

## Phase 2: Candidate removals inventory (evidence-first)

| Path | Category | Evidence | Risk | Action |
|---|---|---|---|---|
| `omni-web/tsconfig.tsbuildinfo` | Build artifact | `git ls-files` showed it as tracked artifact | LOW | Deleted |
| `omni-web/CLEANUP.md` | Duplicate local doc | Local package-level note from prior work; superseded by repo-level report | LOW | Removed locally (untracked) |
| `.right-sidebar`/`RightSidebar` remnants | Deprecated UI | `rg` matches only in tests/report, not runtime code | LOW | Keep tests; no runtime remnants to delete |
| `omni-backend/fix_user.py`, `set_pass.py`, `update_user.py` | Utility scripts | Not imported, but may be operational/manual scripts | MED | Kept (no safe proof of obsolescence) |
| Backend route helpers and v2 modules | Runtime paths | Referenced by app/tests; backend baseline currently failing in v2 | HIGH | Kept; no cleanup changes applied |

## Phase 3: Executed cleanup changes

### Removed files
- `omni-web/tsconfig.tsbuildinfo`
  - Reason: generated TypeScript build cache should not be versioned.
- `omni-web/CLEANUP.md` (local, untracked)
  - Reason: duplicate package-local note replaced with repo-root report.

### Hygiene updates
- `.gitignore`
  - Added `*.tsbuildinfo`
  - Added local SQLite artifacts:
    - `omni-backend/omniai_dev.db`
    - `omniai_dev.db`

## Phase 4: Validation after cleanup edits

### Frontend
- `cd omni-web && npm run build` -> exit `0`
- `cd omni-web && npx playwright test` -> exit `0` (6 passed)

### Backend
- `cd omni-backend && pytest -q` -> still exit `1` with same pre-existing 5 failing v2 tests.
- No backend cleanup deletions were applied while backend baseline was red.

### Contracts
- `cd omni-contracts && pytest -q` -> exit `0` (116 passed)

## Risk notes
- Backend has existing v2 test failures unrelated to this cleanup pass; removing backend code/files without first restoring green baseline would be unsafe.
- This pass intentionally constrained changes to low-risk frontend/repo hygiene and documentation of evidence.

## Rollback guidance
- Revert cleanup-only changes:
  - `git checkout -- .gitignore`
  - `git restore --staged --worktree CLEANUP_REPORT.md` (if needed)
  - `git restore --staged --worktree omni-web/tsconfig.tsbuildinfo` (if restoring deleted file)
