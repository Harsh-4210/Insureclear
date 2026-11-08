# InsureClear Production Implementation Plan

> **For agentic workers:** Use `executing-plans` for controller work; `dispatching-parallel-agents` only for independent modules with exclusive files; `test-driven-development` before behavioral code; `verification-before-completion` before completion or commits. Read this design and your task/dependencies. A checkbox requires recorded evidence.

**Goal:** Build an access-controlled, human-reviewed private pilot, qualify a deployment, then scale from measured demand.
**Architecture:** Preserve FastAPI, React/Vite, the bounded Python pipeline and pinned regulatory corpus. Add invite-only accounts, opaque server-side sessions, isolated jobs and immutable human reviews on SQLite for a single-host pilot. Distribute storage/workers later behind explicit capacity gates.
**Tech stack:** Python 3.11+, FastAPI, SQLite, React 18/Vite, pytest/TestClient, Node; standard-library scrypt/secrets. No paid service or cloud purchase required for local implementation.
**Spec:** The Design contract below is binding; the earlier approved retrieval/registry designs remain binding for provenance, budgets and manual legal review.
**Authorization:** On 2026-11-06 the user requested this full plan, immediate execution, progress marking and repository commits, delegating implementation choices. Do not add a plan-handoff pause. Cloud provisioning, public deployment, sending appeals, legal sign-off and Git push/merge require separate authorization/evidence.
**Ledger:** `docs/superpowers/production-implementation-ledger.md`. Keep this plan's dashboard and checkboxes synchronized with verified commits.

## Design contract

### Approach, scope and alternatives

Serve private-pilot claimant users and trained reviewers. A completed model job is a draft; human approval is a separate versioned decision. Alternatives: existing-stack invite-only pilot (implementer choice, selected because demand/budget are undecided); managed identity/PostgreSQL/object storage immediately (deferred until environment/budget choices); shared browser API key (rejected for multi-user access because it does not establish ownership). No automatic insurer submission, blanket legal rules engine, universal accuracy or throughput promise.

### Identity and ownership

- Roles: `claimant`, `reviewer`, `admin`; server-generated immutable `user_id` and `org_id`. Claimants see only their own jobs; reviewer/admin access stays within their organization. Unknown/unauthorized IDs both return 404. No cross-org admin bypass.
- Invite-only operator CLI creates/resets/disables users with a hidden password prompt and explicit organization/role. No default users/passwords, public registration, email delivery or self-service reset. Reset/disable revokes sessions. Consider SSO/MFA before public self-service.
- Password length 12–128, random per-user salt, scrypt `n=131072,r=8,p=1`, maxmem 256 MiB. Persist bounded login throttling before expensive hashing; generic invalid-login responses. Never log credentials/hashes/tokens.
- Sessions: 32+ random bytes, SHA-256 digest stored, absolute 8h expiry. Cookie `insureclear_session`: HttpOnly, SameSite=Lax, Secure by default; explicit HTTP-local-development override. No session/bearer secret in browser storage or Vite variables. Login/logout are no-store.
- Cookie mutations require exact allowed Origin plus `X-CSRF-Token` matching the session-bound value; login validates Origin. Credentialed CORS has an exact allowlist, never wildcard/prefix matching. `GET /api/auth/session` returns public user and CSRF token; `POST /api/auth/login` JSON username/password; `POST /api/auth/logout` revokes session.
- `INSURECLEAR_AUTH_MODE=accounts` fails closed and ignores shared API keys. Preserve documented legacy/local mode for existing tests/CLI only; do not expose Streamlit/CLI publicly as an alternate auth path.
- Account-mode checkpoints/output IDs derive from server job IDs, not caller labels. Migrate nullable owner/org columns without assigning/deleting historical data. Legacy unowned rows are inaccessible in account mode.

### Review, audit and privacy

- A completed job source snapshot is immutable; reruns create a new job ID. Repeated review initialization compares its supplied fingerprint and raises ReviewConflict if it differs. T06 rechecks the current report fingerprint against this immutable snapshot before edits/decisions/approved export.
- Private reports retain `source_evidence:{denial,policy,regulatory}`, registry fingerprint/selected IDs, coverage, validation and source-bound draft metadata for later edited-letter checks. Treat snapshots as sensitive case data under access/retention controls, never telemetry.
- `GET /api/jobs` lists authorized cases without raw reports/tracebacks. `GET /api/jobs/{id}/review` returns current draft/history. `PUT .../review` accepts `{letter,expected_version,note}`. `POST .../review/decision` accepts `{expected_version,decision,note,checks}` with `approved|changes_requested`. Initial generated draft: version 1, unapproved.
- Transactions bind edits/decisions to expected version, source fingerprint and SHA-256 letter hash; every edit AND decision increments the mutation version, so stale tabs return 409. Preserve immutable versions/events with actor/time/reason. Approval requires same-org reviewer/admin, nonempty current letter, passing deterministic evidence validation, and explicit `facts_checked`, `coverage_checked`, `legal_checked`. Invalid generated letters cannot be approved as-is; valid human corrections preserve the original error history.
- `GET .../download/approved-letter` returns exactly the currently approved version. Any edit invalidates approval. Existing generated downloads remain drafts. No sending endpoint.
- Owner/org-admin deletion rejects running work (409), safely cancels queued work, removes only validated paths within configured private roots, then purges private payload/report/review records. Do not follow symlinks or HTTP-supplied paths. Retention is dry-run by default, explicit apply only, terminal jobs only, with backup-deletion limits documented. Never test deletion on real cases.

### Quality, source and operations

- Policy Analyst is contract-only, requests exact evidence for important arguments, retains negation/accident exceptions and never invents regulatory obligations. Verify quotes against original source slices before calling them verified. Writer/Judge/revisions share verified policy and regulatory evidence. Missing/contradictory evidence requires review; never force a gold verdict.
- Numeric response/escalation deadlines require supplied evidence; otherwise request a response without a number. Sanitization must remove/flag unsupported claims rather than invent policy authority. Structured issues: `unsupported_fact`, `wrong_regulation`, `missing_policy_clause`, `incorrect_verdict`, `unverified_case_law`, `unsupported_deadline`, `policy_evidence_missing`.
- Corpus audit reports integrity, curated coverage, unknown dates/bases/supersession and review needs. Do not invent effective dates. Qualified humans sign governing-version/applicability decisions.
- Per-case telemetry uses stage durations and provider counter deltas, never cumulative process totals or patient facts. Add request IDs, sanitized errors, liveness/readiness, queue depth/admission and cooperative cancellation/time budgets at stage boundaries. In-flight synchronous calls may finish before cancellation is observed; document it.
- Deployment must establish restricted permissions, encrypted storage/backups, secrets management, retention and consent/provider handling. Local private paths alone do not establish encryption or legal compliance.

## Global constraints and agent procedure

- Preserve current `codex/evidence-foundations` checkout; commit earlier corrections separately. No reset, history rewrite, force-push, public deployment, cloud provisioning, sending communications or destructive real-data verification.
- Tests use synthetic fixtures/temp databases. Live provider evaluation uses fictional repo fixtures and pinned public sources only. Retain failures/manifests; never change gold answers to pass.
- Stage explicit source paths. Exclude `.env`, credentials, databases, sessions, logs, outputs, eval results and node_modules. Never print secrets. Commit locally after verification; no push/merge implied.
- Root owns integration files `web/api.py`, `tools/job_store.py`, `orchestrator/main.py`, plan and ledger. Delegated modules have exclusive files and fixed contracts; agents must not spawn agents or commit other agents' work.
- Read relevant code/tests, AGENTS.md if present and latest ledger. Reproduce a bug with `systematic-debugging`; observe the intended RED assertion, implement minimal behavior, run GREEN using `test-driven-development`. Do not weaken safety tests.
- Use `executing-plans` for sequential integration and `dispatching-parallel-agents` for independent modules only. Controller verifies interfaces and review evidence. Reports include changed paths, RED/GREEN commands/results, assumptions/limits and report path.
- Use `requesting-code-review` after major work and final integration; use `receiving-code-review` to verify findings. Fix important issues with regressions/full-suite checks. A reviewer timeout is not approval.
- Use `verification-before-completion` before marking/committing; record command/result/date/scope/commit. Browser work uses `computer-use`; `emil-design-eng` helps app interaction/accessibility checks. Landing-page skills do not apply to these app screens.
- `brainstorming`/`writing-plans` apply to material scope changes. The user already directed execution after this plan. `finishing-a-development-branch` applies only to requested integration; otherwise preserve branch.
- Conditional cloud work, qualified legal decisions and environment acceptance remain unchecked until their exact gates are satisfied. Never claim production readiness from local code completion.

## Interfaces and dependencies

| Task | Owns / produces | Consumers |
|---|---|---|
| T00 | prior corrections and plan commits | all |
| T01 | verified policy evidence + private source snapshots | T02,T06 |
| T02 | grounded prompts/deadline/quality checks | T10 |
| T03 | auth store/router/operator CLI | T04,T07 |
| T04 | owner/org migration and API authorization | T06,T08 |
| T05 | immutable review store | T06,T07 |
| T06 | authorized review API/approved export | T07,T10 |
| T07 | frontend accounts/cases/review | T10 |
| T08 | lifecycle, retention, cancellation, telemetry | T10,T11 |
| T09 | corpus audit and expert checklist | T11,T12 |
| T10 | CI, manifests and representative evaluation | T11 |
| T11 | local candidate review/build/performance | T12 |
| T12 | authorized environment/pilot acceptance | T13 |
| T13 | demand-triggered distributed architecture | expansion |

## Review focus

- Cross-user/org guessing, legacy rows and cache collisions: T04 denies every read/download/review/delete route and isolates identical display labels.
- Stale reviewer tabs, source changes and edits after approval: T05/T06 bind current version/hash/source and block old approved exports.
- Unicode/negation/OCR and invented deadlines: T01/T02 preserve exact evidence and reject unsupported timing, report uncertainty.
- Cookie attacks/login brute force/disabled users/browser secrets: T03/T07 verify revocation, expiry, CSRF/Origin, secure cookie and secret-free client.
- Cancellation/crashes/deletion races/path escape/private exceptions: T08 uses temporary roots/events and exposes sanitized failures.

## Phase 0 — Preserve the verified baseline

### T00: Baseline and plan (controller)
**Files:** prior pending corrections; this plan; `docs/superpowers/production-implementation-ledger.md`.
- [x] Run full pytest and `git diff --check`; expect 120 passed/no whitespace errors; inspect staged paths for private artifacts.
- [x] Commit prior corrections: `fix: finalize evidence evaluation and deployment safeguards`.
- [x] Self-review coverage/contracts; fresh builder checks significant ambiguity. Commit plan/ledger: `docs: add phased production implementation plan`.
**Done:** command/results and both commit IDs recorded; no private outputs staged.

## Phase 1 — Correctness before feature growth

### T01: Source-bound policy evidence (controller)
**Files:** new `tools/policy_evidence.py`, `tests/test_policy_evidence.py`; modify Policy Analyst, pipeline and corresponding tests.
**Interfaces:** `annotate_policy_evidence(result:dict,policy_text:str)->dict` verifies `policy_evidence:[{quote,clause,argument}]`, records exact offsets, returns `verified_policy_context` and `policy_review_reasons`. Report retains private `source_evidence` snapshots. Invalid quotes are never verified.
- [x] Write `test_quote_offsets_match_policy`, `test_fabricated_quote_requires_review`, accident-exception/negation tests and pipeline snapshot/review tests; run focused pytest and observe intended RED.
- [x] Request contract-only exact evidence, annotate original slices, preserve source snapshots and cap approval for missing evidence. Keep result compatibility and budget guards; invalidate changed prompts/caches.
- [x] Focused/full suites GREEN; record evidence and commit `fix: ground policy arguments in exact source evidence`.

### T02: Grounded writing and deadline checks (controller)
**Files:** Writer, Judge, evidence validator and prompt/pipeline/evidence tests.
**Interfaces:** shared `verified_policy_context` and structured quality issues in existing dictionaries; any optional Judge argument preserves compatibility. Validator emits `unsupported_deadline` for unsupported numeric response/escalation promises.
- [x] Reproduce supplied-wording omission, accident-exception inversion and unsourced 15-day request as deterministic prompt/validator regressions; observe RED. A mocked model is not proof of semantic accuracy.
- [x] Give Writer/Judge/revisions exact policy evidence; distinguish contract from legal leads; prohibit requests for already supplied text. Reject unsupported deadlines; remove/flag unsupported claims without false policy attribution.
- [x] Focused/full suite GREEN; retain human review/failed live history; commit `fix: reject unsupported deadlines and preserve policy grounding`.
**Exit:** reproducible safeguards pass; expert/live semantic evaluation remains required.

## Phase 2 — Named users and case isolation

### T03: Invite-only identity/session modules (independent module agent)
**Exclusive files:** create `tools/auth_store.py`, `web/auth.py`, `tools/manage_users.py`, `tests/test_auth_store.py`, `tests/test_auth_api.py`. Do not edit integration files.
**Interfaces:** `AuthStore(db_path)`; `create_user(username,password,org_id,role)->dict`; `login(username,password)->(public_user,raw_session,csrf)`; `session(raw_token)->dict|None` including public fields/csrf; `logout(raw_token)`; `set_password(user_id,password)`; `disable_user(user_id)`. `web.auth.router` mounts auth routes, `current_principal(request:Request)->dict` authenticates and `require_mutation(request,principal)` checks CSRF/Origin. Resolve configured store lazily from `INSURECLEAR_AUTH_DB`; tests inject temporary store. Principal: `user_id,org_id,role,csrf_token`. Legacy mode is controller-owned.
- [x] RED tests: login/generic failures, salted nonplaintext passwords, expiry/logout/reset/disable revocation, persisted throttle, Secure/HttpOnly cookie, exact Origin and CSRF refusal.
- [x] Implement Design contract parameters; bound login body/throttle before hashing; CLI hidden password, explicit role/org. Document development HTTP override. Do not create real accounts or passwords.
- [x] GREEN focused tests; report limits/paths/results; commit owned files `feat: add invite-only account sessions`.

### T04: Ownership on every case route (controller; T03)
**Files:** `tools/job_store.py`, `web/api.py`, API tests, new `tests/test_case_access.py`.
**Interfaces:** backward-compatible `JobStore.create(...,owner_id=None,org_id=None)`; nullable migration; `list_for(principal)->list`; internal-only `get_payload(job_id)->dict`. `get_authorized_job(job_id,principal)` enforces claimant owner or same-org reviewer/admin. Account mode is `INSURECLEAR_AUTH_MODE=accounts`; legacy separately explicit.
- [x] RED tests deny Alice access to Bob status/report/letter/download/review/delete, reviewer cross-org access, account shared-key bypass and legacy unowned rows; same display labels use isolated internal case IDs.
- [x] Mount auth routes, protect all job routes, namespace by random job ID, separate display label; status/list never expose payload, internal paths, raw traceback. Preserve queue recovery behavior.
- [x] Existing/new API/full suite GREEN; commit `feat: enforce case ownership across job routes`.

## Phase 3 — Durable human review and product flow

### T05: Immutable review persistence (independent module agent)
**Exclusive files:** create `tools/review_store.py`, `tests/test_review_store.py` only.
**Interfaces:** `ReviewStore(db_path)`; `initialize(job_id,org_id,letter,source_fingerprint)->dict`; `get(job_id)->dict|None`; `edit(job_id,actor_id,expected_version,letter,note)->dict`; `decide(job_id,actor_id,expected_version,decision,note,checks)->dict`; `delete(job_id)`. `ReviewConflict` signals stale version/source or deleted tombstone. Every initialization/edit/decision checks a durable content-free deletion tombstone inside the same SQLite write transaction; delete writes the tombstone before purging versions/events, preventing recreation by a previously authorized request. T08 fences job claiming with a transactional deleting/cancelled status before filesystem cleanup. `ReviewConflict` signals stale version. Current state includes `version,letter,letter_sha256,status,source_fingerprint,history`; immutable versions/events contain UTC actor/time/reason/hash/source. Transactions serialize writers. API controller supplies authorization/evidence validation; store also checks decision enum/approval confirmations.
- [x] RED tests: initial unapproved draft, stale concurrent editors AND decisions, deletion racing initialization, mismatched repeated initialization, approval bound to exact version/hash, edit invalidates approval, append-only history, source-fingerprint mismatch and isolated safe deletion.
- [x] Implement parameterized SQLite persistence without mutating original generated reports/logging patient text. No real data deletion.
- [x] GREEN focused tests; report contract/results; commit owned files `feat: persist versioned human review decisions`.

### T06: Review API and approved export (controller; T01,T04,T05)
**Files:** new `web/reviews.py`, `tests/test_review_api.py`; integrate API.
**Interfaces:** routes from Design contract; SHA-256 fingerprint of canonical private snapshot plus registry fingerprint. Initialize idempotently from generated report. Edited letter max 50000 chars; validate using stored original snapshots. Reviewer/admin only may decide, requiring mutation CSRF/Origin, three checks, unchanged source fingerprint/current version and valid evidence. Owners may edit their own drafts. A missing snapshot refuses approval.
- [x] RED TestClient tests: owner editing, reviewer exact-version approval, claimant refusal, stale 409, invalid evidence 422, edit invalidates export, cross-org denial, changed/missing source refusal and approved-download byte equality.
- [x] Implement authorized review queue/routes; return actionable validation issues; preserve model Judge assessment separately from human decision.
- [x] Focused/full suite GREEN; commit `feat: add evidence-checked review and approved letter export`.

### T07: Account/case/review UI (frontend agent after API contract stabilizes)
**Files:** existing App/CSS, focused components/client tests, frontend Dockerfile, Compose/nginx integration (coordinate ownership with controller).
**Interfaces:** same-origin `/api` default; credentialed fetch, CSRF in memory. Flow: login -> authorized case list -> case result -> review editor -> reviewer confirmations/decision -> approved export. Logout clears private state/polling. New edit removes approved download. Show expired session, stale revision, validation and polling errors visibly.
- [x] Add meaningful client credential/CSRF and version-aware action tests. Browser-check failed login, claimant isolation and stale editor when available.
- [x] Remove VITE_API_KEY from browser/build/Compose; same-origin nginx API proxy, configured development base URL. Preserve app style; labels/keyboard focus/busy states and clear draft/approved status required. Never expose shared secrets as browser configuration.
- [x] Frontend tests/build and backend integration GREEN; actual browser flow recorded, not inferred. Commit `feat: add account and reviewer workflows to the app`.

## Phase 4 — Privacy, resilience and observable operation

### T08: Lifecycle, retention and operations (controller; T04,T06)
**Files:** API/JobStore, new `tools/case_lifecycle.py`, `tools/retention.py`, `tools/runtime_control.py`, pipeline telemetry helpers/tests; deployment/env docs.
**Interfaces:** cancel flag and `POST /api/jobs/{id}/cancel`: queued -> cancelled; running -> cancellation_requested, checked at stage boundaries. `DELETE /api/jobs/{id}` rejects active work, safely races against claims, confines filesystem cleanup to verified roots. Retention CLI `--days N` lists eligible terminal cases by server time; `--apply` explicitly deletes, never active cases. `/ready` checks DB/corpus/provider configuration without inference; `/health` liveness. Request ID header, safe operational errors, authenticated content-free queue metrics. Configure queue ceiling/per-principal admission; 429 includes Retry-After. Digital PDFs max 200 pages, OCR max 40, extracted text max 500000 characters; render one page at a time with max long edge 2500 pixels and 30-second raster/Tesseract timeouts. Explicitly fail over-limit inputs; do not silently truncate.
- [x] RED cancellation-before-provider, running deletion refusal, queued claim/delete race, traversal/symlink cleanup refusal, retention dry-run/no active deletion, expiry boundary tests.
- [x] RED per-case provider delta, stage duration, request ID, readiness failure, private-error redaction and admission-ceiling tests.
- [x] Implement minimal safe controls, cooperative time/cancel boundary semantics, source-free logs and deployment docs. Do not claim immediate interruption of synchronous provider/OCR work, disk encryption or backup erasure.
- [x] Focused/full tests GREEN; commit separate lifecycle/telemetry patches. Record external filesystem ACL/encryption/backup/residency/consent obligations.

## Phase 5 — Corpus maintenance and meaningful evaluation

### T09: Corpus audit and expert checklist (controller)
**Files:** new `tools/audit_regulatory_registry.py`, `tests/test_registry_audit.py`, `docs/REGULATORY_REVIEW_CHECKLIST.md`; regulatory docs.
**Interfaces:** `audit_registry(registry)->dict` emits source integrity/counts, missing effective ranges/date basis/supersession and explicit legal-review needs. CLI metadata only, nonzero for corrupt corpus. Checklist records named reviewer/date/source/version/decision/evidence; never invent sign-off.
- [x] RED default three-source/nine-excerpt audit, unknown-date preservation and tampered-byte rejection tests.
- [x] Implement audit/checklist; GREEN tests/default audit; commit `feat: audit regulatory coverage and review requirements`.
- [ ] Qualified legal reviewer signs governing dates/versions/applicability/conflicts. Leave unchecked without actual sign-off; coding agents cannot complete this obligation.


### T10: CI and honest evaluation (controller)
**Files:** `.github/workflows/ci.yml`, eval harness/tests, readiness docs, new `docs/PILOT_ACCEPTANCE.md`.
**Interfaces:** offline Linux CI Python tests + npm ci/test/build without provider secrets. Separate manual synthetic live gate. Each report binds input/answer/prompt/source/model hashes and per-case usage; resume refuses changed inputs/answers/sources. Summary states reused/new reports, runtime/errors and current-invocation usage.
- [x] RED resume refusal on changed fixture/answer/source, long late-clause inputs, Unicode deadline and malformed-response regression tests.
- [x] Implement manifests/CI, offline suite/frontend build GREEN; commit `ci: verify pilot security and evidence regressions`.
- [ ] Run completely fresh synthetic strict evaluation on candidate code without copied reports; preserve failures. Repeat for equivalent conclusions/evidence, not raw text identity. Record expert semantic rubric separately from keywords.
- [ ] Validate representative consented/redacted long/scanned/multilingual cases and burst/crash recovery before release. No real inputs sent externally without appropriate authorization.


## Phase 6 — Local release candidate and performance

### T11: Independent review, build and capacity qualification (controller/reviewer)
- [x] Offline Windows and Linux Python 3.11/3.13 suites, frontend tests and builds, path/whitespace inspection and advisory scans completed. Current counts and candidate-specific results are recorded in docs/PILOT_ACCEPTANCE.md.
- [ ] Fresh independent review of identity/tenancy, review/source/version races, deletion and budget boundaries. Important findings require observed RED/GREEN regressions and full-suite pass; document unresolved impact.
- [x] Built API/frontend images. Fresh, upgraded, reopened, and restored synthetic volumes passed. The persistent-host overlay passed read-only API persistence and HTTPS integration with a verified local test CA. Public-host certificate and storage checks remain external gates.
- [ ] Profile stage timings/tokens, optimize measured repeated work; burst test under shared provider quotas. Targets: p95 queue-to-result <90s, <1% execution failures, no duplicate effects. Unmet targets stay open; agree pilot load before asserting capacity.
- [ ] Commit verified progress; hash-link candidate code/results/checklist. Keep branch local; no push/merge/deploy implied.

## Phase 7 — Private deployment and pilot acceptance (external gates)

### T12: Operator/expert sign-off
- [ ] Operator chooses hosting region/budget, expected users/peaks, retention, reviewer roles and turnaround objective. Do not guess production business settings.
- [ ] Qualified reviewers approve data/consent/provider handling and legal applicability. Establish actual encrypted storage, least-privilege secrets, HTTPS, backups/restore, alerts and incident/rollback runbook.
- [ ] Operator provisions accounts with CLI; verify HTTPS Secure cookies, Origin/CSRF, cross-account denial, exact approved export. Never expose legacy Streamlit/CLI publicly.
- [ ] Receive explicit deployment authorization before publishing/provisioning. Run environment smoke tests/restore drill and a limited monitored pilot.
- [ ] Sign PILOT_ACCEPTANCE against candidate commit and archived evidence; failed gates remain release blockers.

## Phase 8 — Conditional scale-out

### T13: Expand from measured bottlenecks
**Trigger:** observed arrivals/service times exceed approved single-host budget or availability/tenant needs demand separation. First produce an environment-specific reviewed design; this plan does not authorize purchases.
- [ ] Separate API/workers with shared leases/heartbeats/idempotency, retry classification, dead letters, crash recovery and cross-worker cancellation.
- [ ] Migrate users/jobs/reviews/audit to PostgreSQL with backfill/tenant constraints/rollback/restore. Test two workers claiming one job and lease takeover.
- [ ] Move inputs/checkpoints/artifacts to encrypted private object storage, tenant keys and expiring authorized downloads; preserve source hashes/retention/deletion.
- [ ] Separate OCR/LLM pools; shared organization-quota scheduler, tenant fairness/admission and correctly namespaced caches. Test retry storms; extra keys do not create independent quota.
- [ ] Add SSO/MFA/managed identity, org administration, billing/partner/batch APIs only when needed. Introduce semantic retrieval only after recall evaluation justifies it.
- [ ] Load/failover/isolation/restore-test chosen capacity; approve revised cost/service objectives. Roadmap ranges are planning examples, not measured promises.

## Provider maintenance gate — conditional Gemini activation

### T14: Supported Gemini SDK before enabling Gemini in a pilot
**Trigger:** operator selects Gemini. Current live candidate verification uses Groq only. Container startup exposed an actual legacy SDK end-of-support warning; the official repository confirms support ended in 2025. Zero known package advisories is not active vendor support.
**Files:** `tools/llm_client.py`, direct requirements/security lock, provider transport/budget tests and pilot docs.
**Interfaces:** preserve `call_llm`, `call_llm_json`, `get_stats` and existing env model selection. Use the supported `google-genai` Client/models.generate_content API, native JSON config/output reservation and actual usage metadata; load only the selected provider SDK. Do not silently change model IDs or legal/source behavior.
- [ ] Read current official Google migration/client documentation; replace the deprecated dependency and regenerate the universal hash lock. Verify selected model availability/config before activation.
- [ ] Observe RED then GREEN for text/native JSON, malformed JSON, rate/retry/timeout behavior, exact output reserves, prompt bounds, successful/unknown usage, and no raw secret/document logs. Keep Groq regressions green.
- [ ] Run full offline suite/images/audits and provider-specific synthetic live verification after operator authorization for that destination/credential. Bind new SDK/lock/source hashes and preserve old results. Do not mark Gemini production-qualified from mocked tests or Groq runs.
**Skills:** systematic-debugging, test-driven-development, requesting-code-review and verification-before-completion. Official source: https://github.com/google-gemini/deprecated-generative-ai-python and https://github.com/googleapis/python-genai.

## Status dashboard

| Task | Status | Evidence / dependency |
|---|---|---|
| T00 | complete | 120 tests; baseline caed8d4; builder findings resolved; plan commit in Git history |
| T01–T02 | complete locally | 129 pipeline/evidence tests passed; semantic/live acceptance remains T10 |
| T03 | complete locally | 27 identity tests; T04 integration complete |
| T04 | complete locally | case reads/downloads scoped by owner/org; full integrated suite recorded in ledger |
| T05 | complete module | 30 review transaction tests |
| T06 | complete locally | version/source-bound API; approval race regression fixed |
| T07 | complete locally | 16 client tests/build, synthetic browser flow and local HTTPS integration; external host acceptance pending |
| T08 | complete locally | 245 passed/1 Windows symlink skip; PDF bounds added; deployment checks remain open |
| T09 | audit code complete | 28 focused tests; 3 pinned sources/9 excerpts; legal sign-off unchecked |
| T10 | offline code complete | manifest/CI tests green; two fresh live runs and representative expert review pending |
| T11 | qualification in progress | model/source fixes committed; offline tests, images, advisory checks and synthetic HTTPS/restore passed; final strict runs and host acceptance remain open |
| T12 | external gate | operator/legal/environment decisions and deployment permission |
| T13 | conditional | measured scale trigger and environment-specific design |
| T14 | conditional provider gate | migrate legacy SDK before Gemini activation; current live verification is Groq |

## Verification and completion

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --tb=short --show-capture=no
# web/frontend:
npm ci
npm test
npm run build
# Repository root; synthetic only:
.\.venv\Scripts\python.exe -B eval/run_eval.py --min-verdict-accuracy 1 --max-unsupported-claim-rate 0
.\.venv\Scripts\python.exe -B tools/audit_regulatory_registry.py
git diff --check
git diff --cached --stat
```

Done means behavior verified, dependency contracts agree, important review issues
fixed, plan/ledger updated and explicit-path commit exists. Implemented code and
external acceptance are different statuses. A document cannot make software
foolproof; it makes assumptions, proof obligations and remaining risks visible.

## Primary references checked 2026-11-06

- [OWASP passwords](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [OWASP sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [FastAPI cookies](https://fastapi.tiangolo.com/advanced/response-cookies/)
- [PostgreSQL locking](https://www.postgresql.org/docs/current/sql-select.html)
- [Groq limits](https://console.groq.com/docs/rate-limits)
- [S3 temporary access](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)
