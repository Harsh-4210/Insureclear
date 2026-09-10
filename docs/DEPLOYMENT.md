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

The API stores queued jobs in `data/jobs.sqlite3`. Jobs that were marked
`running` when the service stopped are returned to `queued` on the next startup.
The worker processes one job at a time, which protects the Gemini quota and keeps
resource usage predictable.

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
