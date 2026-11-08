# Private pilot operations

Status: local implementation; deployment/legal/capacity acceptance is not complete.
Read docs/superpowers/plans/2026-11-06-production-implementation.md and PILOT_ACCEPTANCE.md.

## Accounts and browser access

Set INSURECLEAR_AUTH_MODE=accounts and INSURECLEAR_AUTH_DB to a private persistent
SQLite path. Auth defaults to Secure, HttpOnly, SameSite=Lax cookies. Serve the
frontend/API from the same HTTPS origin with an exact CORS origin allowlist.
Only explicit localhost HTTP development may set INSURECLEAR_AUTH_COOKIE_SECURE=false.
No session token belongs in localStorage, a Vite build variable or a URL.
Legacy shared-key mode and Streamlit/CLI are trusted local operator tools only.

Create users interactively from a terminal with hidden password entry:

```powershell
.\.venv\Scripts\python.exe -m tools.manage_users --db data/auth.sqlite3 create --username operator --org-id pilot-org --role admin
.\.venv\Scripts\python.exe -m tools.manage_users --db data/auth.sqlite3 create --username reviewer --org-id pilot-org --role reviewer
.\.venv\Scripts\python.exe -m tools.manage_users --db data/auth.sqlite3 create --username claimant --org-id pilot-org --role claimant
# Public user IDs from creation output identify reset/disable targets:
.\.venv\Scripts\python.exe -m tools.manage_users --db data/auth.sqlite3 reset --user-id USER_ID
.\.venv\Scripts\python.exe -m tools.manage_users --db data/auth.sqlite3 disable --user-id USER_ID
```

There are no default accounts or passwords, public registration or email recovery.
Password reset/disable revokes sessions. Provision reviewers only after checking
qualifications. Org IDs/roles are operator decisions; accounts cannot self-promote.
MFA/SSO and managed identity remain considerations before public self-service.

## Review and privacy

Generated jobs are drafts. Owners edit; same-org reviewers/admins approve a specific
version after facts, full coverage and legal checks. Every mutation advances its
revision; stale tabs must refresh. Edits invalidate approval. The approved download
serves exactly that approved version and never sends it to an insurer.

Reports retain sensitive denial/policy/selected-regulatory source snapshots for
later edited-letter checks. Protect auth/jobs/review databases, sessions, outputs
and backups with restricted ACLs and encrypted storage appropriate to the chosen
host. This repository does not establish disk encryption, consent, data residency,
provider handling agreements, expert legal sign-off or secure deletion from SSDs.
API responses use no-store; avoid copying case material into general analytics/logs.

## Lifecycle and retention

POST /api/jobs/{id}/cancel is cooperative at stage boundaries. Already in-flight
provider/OCR calls can finish; no instant cancellation promise. The default case
limit is 300 seconds, 20 successful calls and 60000 reported tokens; controls check
between stages, so a single in-flight call can cross a budget. Provider-side HTTP
budgets and timeouts are separate. Admission defaults to 100 globally pending and
3 per named owner; rejected submissions return 429/Retry-After.

Owner/org-admin DELETE /api/jobs/{id} refuses running/cancellation_requested work.
It durably fences new work and review writes, confines cleanup under configured
roots, removes private case records and retains a content-free opaque-ID tombstone.
Unsafe paths or interrupted cleanup leave a deleting record for operator attention;
never bypass the confinement checks or use blanket recursive deletion.

Preview retention without deleting cases:

```powershell
.\.venv\Scripts\python.exe -m tools.retention --db data/jobs.sqlite3 --days 30
# Only after operator has reviewed the preview and approved retention policy:
.\.venv\Scripts\python.exe -m tools.retention --db data/jobs.sqlite3 --days 30 --apply
```

Only old terminal/deleting owned records qualify; active, recent and legacy-unowned
jobs are excluded. The preview does not purge records. Use the configured runtime
storage roots and backing database on the same host. Backups and exported copies
need separate retention controls; file removal/SQLite secure_delete cannot prove
physical erasure. No retention schedule is installed automatically.

## Monitoring, failures and recovery

/health is process liveness. /ready validates DB/corpus/auth configuration and the
presence of provider credentials without paid inference; it does not prove remote
provider availability. Every response has a server-generated X-Request-ID. Private
responses are no-store. Exceptions exposed to the browser are sanitized; raw
provider exception text/patient facts are excluded from operational print output.
Named org admins can read /api/operations for content-free status counts.

The single-host worker holds its OS lock through recovery and processing. Restart
recovers running jobs and finishes pending cancellation. Replays can reuse correctly
fingerprinted checkpoints; distributed exactly-once semantics are not promised.
Do not run multiple hosts against a network SQLite file; Phase 8 defines scale-out.

Persist the data volume and sessions required for resume. Backup the jobs/review
and auth databases consistently; use SQLite backup APIs or stop writers rather
than copying an active database file blindly. Restrict/encrypt backups and test
restore into an isolated environment, including account revocation and exact review
versions. Define alert recipients, provider outages, rollback and deletion-retry
procedures for the chosen host before accepting a pilot. No cloud services,
backup service, alert destination or deployment has been provisioned by this work.


## PDF resource bounds

Digital case PDFs default to at most 200 pages; OCR fallback defaults to at most
40 pages. Extracted text is capped at 500000 characters, with an explicit failure
rather than silent truncation. OCR renders one page at a time with a 2500-pixel
long-edge bound, 30-second raster timeout and 30-second Tesseract attempt timeout.
Cancellation checks run between pages/attempts. These bounds do not make a PDF
parser immune to malicious inputs; deployment isolation/resource limits and
representative OCR quality checks remain acceptance work. Over-limit documents
need a reviewed intake/splitting workflow; do not silently raise limits in production.


## Reproducible dependencies and checks

Use the universal hash-pinned requirements.lock for verified installations,
Docker and CI: python -m pip install --require-hashes -r requirements.lock.
requirements.txt expresses direct requirements and requirements-security.txt
records advisory fix floors. After intentional dependency changes regenerate
with uv pip compile requirements.txt --python-version 3.11 --universal
--generate-hashes --output-file requirements.lock, then run pip check, the full
suite, frontend checks and fresh advisory audits. A zero-advisory result is not
proof of vulnerability absence. Container tags remain mutable upstream inputs;
record built image IDs/digests with release evidence before deployment.

Both Groq and Gemini usage metadata feed case counters. If a successful response
omits usable usage metadata, the next stage fails closed rather than treating
unknown usage as free tokens. Provider-reported totals may still exclude failed
requests; local limits are not a provider billing cap.


## Provider support boundary

This candidate's live verification uses Groq. The optional Gemini path still uses
the deprecated google-generativeai SDK; its vendor reports that support ended in
2025. Before selecting Gemini for a pilot, complete T14 in the implementation
plan: migrate to google-genai, preserve budgets/usage/error behavior, and verify
that provider with authorized synthetic data. A zero-advisory audit does not
qualify an unsupported integration. Official vendor notice:
https://github.com/google-gemini/deprecated-generative-ai-python.
