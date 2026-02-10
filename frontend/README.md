# OmniAI Frontend (v1)

## Goals (v1)
- Static SPA hosted on GitHub Pages.
- No secrets in client; frontend talks only to OmniAI backend.
- Runtime config loaded from `runtime-config.json` at startup.
- Hash routing (`/#/...`) to avoid GitHub Pages 404s.

## Local dev
1. Create a `frontend/public/runtime-config.json` (copy from example):
   ```bash
   cp frontend/public/runtime-config.example.json frontend/public/runtime-config.json
   ```
2. Edit `runtime-config.json` to set your backend URL.
3. Run:
   ```bash
   cd frontend
   npm i
   npm run dev
   ```

## Build
```bash
cd frontend
npm run build
```
Output is `frontend/dist/`.

## Deploy (two-repo model)

1. Copy contents of `frontend/dist/` into the GitHub Pages repo root.
2. Place `runtime-config.json` in the Pages repo root next to `index.html` so it can be updated without rebuilding.

## Phase 0 "done" checks

1. **Dev boot**:
   - `npm run dev` loads app.
   - Missing `runtime-config.json` produces a blocking startup error.

2. **Pages routing**:
   - Built `dist/` works when served statically.
   - Hash routes `/#/login` and `/#/chat` render without server rewrites.
   - Optional `404.html` redirects non-hash paths to `/#/`.

3. **Security invariants**:
   - No secrets in code.
   - No references to provider endpoints.
