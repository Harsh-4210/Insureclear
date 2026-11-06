# InsureClear Production Readiness Plan

This document is the working plan and status tracker for taking the InsureClear
appeal pipeline from evaluation-ready to production-ready. Update the task
checkboxes and evidence sections whenever a milestone is completed.

## Current status

**Last updated:** 2026-11-06

**Current branch:** `codex/evidence-foundations` (local changes, not deployed)

**Local HEAD:** `14ee15f`; final corrections remain in the working tree.

### Completed baseline

- 120 automated tests pass, including source integrity, provider budgets, cache identity,
  Docker-volume compatibility simulation and active Streamlit flows (provider calls mocked).
  See [current result and remaining work](EVIDENCE_FOUNDATIONS_RESULT.md).
- Strict targeted evaluation for `c01` and `c05` passes:
  - Verdict accuracy: 100%.
  - Letter-fact accuracy: 100%.
  - Unsupported-claim rate: 0%.
  - Failed cases: 0.
- Groq key-pool support is implemented for:
  - `GROQ_API_KEYS`
  - `GROQ_API_KEY_1` through `GROQ_API_KEY_N`
- A 429 now cools down only the key that received it. If all keys are
  unavailable, the client waits for the earliest cooldown.
- Agent output validation, structured failures, evidence validation, valid-denial
  guardrails, and bounded evidence correction are implemented.
- Historical pre-foundation strict evaluation completed all 10 cases (not the current working-tree release baseline):
  - Extraction accuracy: 100%.
  - Verdict accuracy: 100%.
  - Letter-fact accuracy: 100%.
  - Unsupported-claim rate: 0%.
  - Failed cases: 0.

### Current evidence-foundation validation

The bounded retrieval and pinned-source registry are implemented. Corpus updates
remain visible outside the mutable Docker data volume, and all interfaces share
evidence/review gates. The final cohort `sp_release_20261106` passes configured
verdict/evidence gates: 10/10 verdicts, 100% tracked extraction/letter facts and
zero detected evidence violations, with no execution failures. It reuses nine
unchanged, reverified reports and reruns one corrected fixture; it is not an
independent second ten-case run. Original failures and answer keys are preserved.

The cohort used 83 successful calls and 281879 reported tokens (5 retries, no
429s). Its 73.75s mean and 147.48s nearest-rank sample p95 do not meet the latency
target. Manual inspection still found reasoning/drafting weaknesses the scorer
does not detect. Nine outputs require review and one requires revision; none is
approved for automatic sending. See [full evidence and limits](EVIDENCE_FOUNDATIONS_RESULT.md).
Production acceptance remains open pending expert quality review, repeat/long/OCR
runs, security/operations checks and a deployment-specific validation.

### Important limitation

Key rotation is not a way to bypass Groq limits. Keys must belong to
independently authorized organizations/projects. Keys under one organization
may still share organization-level RPM, TPM, or daily limits.

## Production acceptance criteria

The pipeline is production-ready only when all of the following are true:

| Area | Acceptance criterion | Status |
|---|---|---|
| Extraction | At least 95% required facts correct on the curated regression set | ☑ |
| Verdicts | 100% verdict accuracy on current synthetic cohort (nine reused) | ☑ |
| Evidence | Zero detected deterministic evidence errors on synthetic cohort; semantic review incomplete | ☐ |
| Regulations | Correct source/version selected for every regulatory claim | ☐ |
| Security | No secrets in source, logs, reports, or committed artifacts | ☐ |
| Reliability | No silent fallback or success-shaped failure | ☑ |
| Performance | p95 case runtime below 90 seconds | ☐ |
| Rate limits | Graceful cooldown, rotation, and retry behavior | ☑ |
| Reproducibility | Same inputs produce equivalent conclusions and evidence | ☐ |
| Operations | Health checks, request IDs, persisted failures, and usable metrics | ☐ |

## Implementation plan and task list

### Phase 1 — Establish a repeatable evaluation baseline

- [x] Define the ten curated evaluation cases.
- [x] Add deterministic scoring for extraction, verdict, letter facts, key
  arguments, unsupported IDs, unsupported claims, judge score, runtime, and
  failure count.
- [x] Add strict command-line regression gates.
- [x] Make failed cases explicit and return a non-zero process status.
- [x] Complete ten-case live evaluation after the pipeline changes; preserve the
  failed fresh run and record the final nine-reused/one-rerun cohort explicitly.
- [x] Save the latest cohort summary and provenance as evaluation evidence.
- [ ] Establish an independent fresh ten-case pass on the eventual release commit.
- [ ] Add a documented CI command that runs the strict gates on every change.

Recommended command:

```powershell
$env:LLM_PROVIDER="groq"
.\.venv\Scripts\python.exe eval\run_eval.py `
  --min-verdict-accuracy 1.0 `
  --max-unsupported-claim-rate 0
```

### Phase 2 — Evidence-grounded generation

- [x] Validate agent output shapes before passing results downstream.
- [x] Detect unsupported IDs, dates, amounts, clauses, case-law references, and
  medical claims.
- [x] Include denial, policy, and regulatory output in the evidence sources.
- [x] Add a bounded evidence-correction pass.
- [x] Add a second bounded correction attempt when the first rewrite remains
  unsupported.
- [x] Detect mutated bare identifiers such as claim and circular references.
- [x] Match labeled identifiers against canonical source identifiers.
- [x] Neutralize unsupported IDs and clauses before emitting a final letter if
  bounded LLM correction does not remove them.
- [x] Neutralize unsupported medical assertions and invented case-law references
  during final deterministic sanitization.
- [x] Accept equivalent policy section references such as `1.2` and
  `Section 1.2` when the source contains the same section number.
- [ ] Add canonical fact comparison against the Auditor output for every
  policy number, claim number, date, amount, and insurer name.
- [x] Ensure a failed final validation cannot be emitted as an approved appeal.
- [x] Add regression cases for altered dates, amounts, clauses, case citations,
  and medical assertions.

### Phase 3 — Regulatory source and legal-rule control

- [x] Keep policy-derived and IRDAI-derived analysis separate in the pipeline
  output.
- [x] Add valid-denial guardrails that force review/explanation posture and
  avoid unsupported success estimates.
- [x] Keep regulatory output available to evidence validation.
- [ ] Build a versioned regulatory source registry containing:
  - Regulation name.
  - Effective date.
  - Exact clause text.
  - Source URL or document identifier.
  - Applicable policy period.
- [ ] Add deterministic conflict detection for waiting periods, moratorium
  periods, coverage limits, policy dates, and other numeric rules.
- [ ] Resolve conflicts in this order:
  1. Current policy wording.
  2. Regulation applicable to the policy date.
  3. Verified regulatory source.
  4. Explicit uncertainty when evidence is unavailable.
- [ ] Require every regulatory claim in a final letter to have a source/version
  reference.
- [x] Do not treat generated IRDAI analysis as an authoritative evidence source
  when no external regulatory source was supplied.
- [ ] Add tests proving that the same input selects the same governing rule.

### Phase 4 — Judge and revision-loop hardening

- [x] Restrict the writer and judge prompts against invented citations,
  unsupported facts, and unverified case law.
- [x] Preserve the evidence set during evidence correction.
- [x] Bound evidence correction attempts.
- [x] Give the Judge a larger structured-output budget and one bounded retry
  when its JSON response is malformed or truncated.
- [ ] Pass the complete evidence map to the Judge.
- [ ] Replace free-form issue handling with structured issue types:
  - `unsupported_fact`
  - `wrong_regulation`
  - `missing_policy_clause`
  - `incorrect_verdict`
  - `unverified_case_law`
- [x] Cap normal quality revisions at two attempts.
- [ ] Stop revising when the letter passes validation and has no critical
  evidence errors.
- [ ] Add a regression test proving that a revision cannot introduce a new
  unsupported legal claim.

### Phase 5 — Groq performance and rate-limit resilience

- [x] Support a Groq key pool with numbered-key configuration.
- [x] Honor server-provided `retry-after` and reset headers.
- [x] Apply cooldowns per key instead of globally.
- [x] Track total calls, tokens, retries, 429s, runtime, and configured key
  count.
- [x] Rotate immediately after a 429 and honor body-level Groq retry durations.
- [x] Bound the Groq reasoning-token budget with
  `GROQ_REASONING_TOKEN_BUDGET`.
- [x] Cap Groq completion output with `GROQ_MAX_OUTPUT_TOKENS` and use a
  lower JSON budget for structured agent responses.
- [x] Give the IRDAI Checker and Policy Analyst sufficient structured-output
  budget while keeping the global Groq cap constrained.
- [x] Retry malformed IRDAI nested structures with a compact schema prompt and
  a bounded three-attempt limit.
- [x] Fall back from native JSON mode only for JSON validation failures.
- [ ] Run the full suite and confirm retry metrics distinguish:
  - First-attempt 429s.
  - Key rotation.
  - Actual repeated attempts.
- [x] Reduce repeated prompt content and bound selected source context.
- [x] Enforce conservative per-stage prompt/output/reasoning budget bounds.
- [x] Bind checkpoints and direct-agent caches to inputs, budgets and source versions.
- [ ] Confirm all production keys are independently authorized and stored only
  in environment variables or a secret manager.
- [ ] Establish release targets:
  - Fewer than 1% failed requests.
  - Fewer than 5% 429 retries.
  - p95 runtime below 90 seconds.
  - No unnecessary duplicate calls.

### Phase 6 — Security and operations

- [ ] Add structured request and case IDs to logs.
- [ ] Confirm logs never contain API keys, authorization headers, or full
  sensitive documents.
- [ ] Add provider-configuration and model-availability health checks.
- [ ] Add storage/database health checks.
- [ ] Add request timeout and cancellation handling.
- [ ] Persist failed cases with explicit error status and diagnostic context.
- [ ] Verify `.env`, evaluation output, sessions, and generated documents are
  excluded or appropriately protected.
- [ ] Run a dedicated security review before deployment.

### Phase 7 — Release validation

- [ ] Run the full ten-case strict evaluation on the release commit.
- [x] Run the complete automated test suite (120 passed on the current tree).
- [ ] Verify no secrets or sensitive generated artifacts are tracked by Git.
- [ ] Verify p95 runtime and rate-limit metrics against the acceptance table.
- [ ] Verify reproducibility with at least two runs of the same deterministic
  cases.
- [ ] Record the release commit, evaluation result directory, and acceptance
  outcome below.

## Verification log

Record each significant run here. Keep result paths relative to the repository
when possible.

| Date | Commit | Scope | Result | Result path/notes |
|---|---|---|---|---|
| 2026-11-01 | `179e0bf` | `c01 c05`, strict gates | Passed | 0% unsupported claims; 2/2 verdicts |
| 2026-11-01 | `5f4ec82` | Automated tests | Passed | 28 tests passed |
| 2026-11-02 | pending | Full ten-case strict gates | Failed | 9 cases scored; verdict accuracy 0.889; unsupported claim rate 0.222; c10 IRDAI top-level list failure |
| 2026-11-02 | pending | Full ten-case strict gates | Failed | 8 cases scored; verdict accuracy 1.0; unsupported claim rate 0.0; c06/c09 exhausted Groq TPM retries |
| 2026-11-05 | pending | Full ten-case strict gates | Failed | 6 cases failed on malformed Judge JSON; 4 scored cases had 0.0 unsupported claims; 0 Groq 429s |
| 2026-11-05 | pending | Full ten-case strict gates | Failed | 9 cases scored; c07 IRDAI output malformed; c09 missing verdict field; c04 unverified regulatory ID counted as evidence |
| 2026-11-05 | pending | Full ten-case strict gates | Failed | 8 cases scored; c05 nested IRDAI items and c06 top-level IRDAI list; 0 Groq 429s |
| 2026-11-05 | pending | Full ten-case strict gates | Failed | 10 cases scored; verdict accuracy 1.0; unsupported-claim rate 0.3; 0 failures and 0 Groq 429s |
| 2026-11-05 | pending | Full ten-case strict gates | Failed | 10 cases scored; verdict accuracy 1.0; unsupported-claim rate 0.2; 0 failures and 0 Groq 429s; two unsupported medical assertions |
| 2026-11-05 | `5e6513f` | Full ten-case strict gates | Passed | 10 cases scored; extraction/verdict/letter facts 1.0; unsupported claims 0.0; failed cases 0; 1 Groq 429; mean Judge score 0.687 |
| 2026-11-05 | working tree on `443d837` | Superpowers review: automated tests and frontend build | Passed | 62 backend tests; frontend build passed; live provider evaluation not rerun; `docs/SUPERPOWERS_REVIEW.md` |
| 2026-11-05 | working tree on `443d837` | Live strict regression after Superpowers fixes | Passed configured gates | `eval/results/sp_base_20261105`; 10/10 verdicts; 0 unsupported claims; letter facts 97.5%; 88 calls; 7 rate-limit retries; see `docs/LIVE_REGRESSION_2026-11-05.md` |
| 2026-11-06 | `14ee15f` + local corrections | Automated tests | Passed | 120 tests; scorer/fixture regressions RED to GREEN |
| 2026-11-06 | working tree | Fresh ten-case live evaluation | Failed verdict gate | `sp_verified_20261106`: 9/10 verdicts; c08 fixture contradiction preserved |
| 2026-11-06 | working tree | Final verified cohort, nine reused/one rerun | Passed configured gates; production limits open | `sp_release_20261106`: 10/10 verdicts; tracked facts 100%; 0 detected evidence violations; p95 147.48s; details in `EVIDENCE_FOUNDATIONS_RESULT.md` |

## Operational commands

Run the automated tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Check the number of configured Groq keys without printing their values:

```powershell
.\.venv\Scripts\python.exe -c "from tools.llm_client import get_stats; print(get_stats()['groq_configured_key_count'])"
```

Run selected cases during focused debugging:

```powershell
.\.venv\Scripts\python.exe eval\run_eval.py --only c01 c05
```

## Definition of done

The production-readiness effort is complete when every unchecked task required
by the acceptance table is completed, the full strict regression run passes on
the release commit, the security review has no unresolved high-severity issue,
and the verification log contains the final result path and metrics.
