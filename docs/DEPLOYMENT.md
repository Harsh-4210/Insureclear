# Deployment Guide

## Local Docker deployment

1. Copy `.env.example` to `.env`.
2. Set `GEMINI_API_KEY`.
3. For a protected deployment, set a long random `INSURECLEAR_API_KEY` and set `INSURECLEAR_REQUIRE_AUTH=true`.
4. Start both services:

```bash
docker compose up --build
```

The API is available at `http://localhost:8000` and the frontend at
`http://localhost:8080`.

The API container installs Poppler, Tesseract, and the Hindi language data so
scanned Indian documents can use the OCR fallback.

## Manual deployment

API:

```bash
uvicorn web.api:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd web/frontend
npm install
VITE_API_BASE_URL=https://api.example.com VITE_API_KEY=... npm run build
```

Serve `web/frontend/dist` with a static web server. Do not put the Gemini key in
frontend variables. `VITE_API_KEY` is an API access key, not the provider secret.

## Persistence and recovery

The API stores queued jobs in `data/jobs.sqlite3`. The active worker holds a
sidecar process lock for the database through recovery, execution, and upload
cleanup. Opening another store does not reset live jobs. After obtaining the
lock, a worker returns orphaned `running` jobs to `queued`; standby workers wait
and take over when the previous owner exits. Keep the sidecar lock file in place
while services are running. This remains a single-host queue.

The worker processes one job at a time, which protects provider quota and keeps
resource usage predictable. Checkpoints are bound to the complete source inputs;
changed inputs or older checkpoints without a source fingerprint trigger a fresh
analysis even when the case ID is unchanged.

Mount `/app/data` to durable storage in production. Uploaded source PDFs are
removed after processing; configure an encrypted backup or retention workflow
only if your legal or operational requirements require retaining them.

## Production checklist

- Use HTTPS at the reverse proxy.
- Set `INSURECLEAR_REQUIRE_AUTH=true` and rotate `INSURECLEAR_API_KEY`.
- Restrict `INSURECLEAR_CORS_ORIGINS` to the actual frontend origin.
- Put the API behind network-level rate limiting as well as the application limiter.
- Use encrypted storage for the SQLite volume and backups.
- Configure log redaction and avoid logging document contents.
- Review generated letters and citations before sending them to an insurer.
- For multiple API replicas, replace SQLite polling with a shared queue and a
  database with appropriate locking.


## Immutable regulatory assets

Bundled official regulatory artifacts live in `/app/resources/regulatory` outside
`/app/data`. Existing data volumes therefore keep jobs and uploads without hiding
new registry versions during image upgrades. Do not mount mutable data volumes
over `/app/resources`. Operator import candidates remain separate from the bundled
curated corpus. Rebuild and restart the service to load a new bundled version.


The root `.dockerignore` excludes credentials, local virtual environments and
private case/session/output directories from image build layers. Provider keys
are supplied at runtime by Compose's `env_file`; they are not bundled in the
image. Keep `resources/regulatory` available in the build context.

The frontend build context has its own `.dockerignore` so Windows host
`node_modules`, local environment files and `dist` are not copied into the
Linux build stage. This is separate from the API root build context.
