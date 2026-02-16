# Local Development Guide

## Prerequisites

- Python 3.12+
- pip

## Setup

```bash
cd omni-backend
pip install -e ".[dev]"
```

## Running the Backend

### One-command start

**Bash/macOS/Linux:**
```bash
./scripts/dev.sh
```

**PowerShell (Windows):**
```powershell
.\scripts\dev.ps1
```

### Manual start

```bash
cd omni-backend
OMNI_ENV=dev python -m uvicorn omni_backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The backend starts at `http://127.0.0.1:8000`.

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /v1/system/health` | V1 health check |
| `GET /v2/health` | V2 health check (includes `db_ok`) |
| `POST /v2/runs` | Create a new run |
| `GET /v2/runs/{id}` | Get run details |
| `POST /v2/runs/{id}/events` | Append event to run |
| `GET /v2/runs/{id}/events` | List events (supports `?after=` cursor) |
| `GET /v2/runs/{id}/events/stream` | SSE stream (supports `Last-Event-ID` header and `?after=` param) |

## Running the Frontend

Start your frontend dev server separately (e.g., Vite):

```bash
cd ../omni-web
npm run dev
# Typically runs on http://localhost:5173
```

The backend CORS is pre-configured for common local ports: 5173, 3000, 8000, 4173, 8080.

## Testing SSE

Quick test with curl:

```bash
# Create a run
RUN_ID=$(curl -s -X POST http://127.0.0.1:8000/v2/runs -H 'Content-Type: application/json' -d '{"status":"active"}' | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Run ID: $RUN_ID"

# Start SSE stream (in one terminal)
curl -N http://127.0.0.1:8000/v2/runs/$RUN_ID/events/stream

# Append events (in another terminal)
curl -X POST "http://127.0.0.1:8000/v2/runs/$RUN_ID/events" -H 'Content-Type: application/json' -d '{"type":"msg","data":{"text":"hello"}}'
```

You should see the event appear in the SSE stream with a heartbeat comment (`: heartbeat`) every 15 seconds when idle.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OMNI_ENV` | `dev` | Environment (`dev` enables auto table creation) |
| `OMNI_HOST` | `127.0.0.1` | Bind host |
| `OMNI_PORT` | `8000` | Bind port |
| `OMNI_V2_DATABASE_URL` | `sqlite+aiosqlite:///./omniai_dev.db` | V2 async database URL |
| `OMNI_V2_CORS_ORIGINS` | local origins | Comma-separated CORS origins |
| `OMNI_SSE_HEARTBEAT_SECONDS` | `15` | SSE heartbeat interval |
| `OMNI_MAX_REQUEST_BYTES` | `2097152` (2MB) | Max request body size |

## Running Tests

```bash
cd omni-backend
python -m pytest tests/ -v
```
