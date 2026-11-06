# Implementation ledger — plan: docs/superpowers/plans/2026-11-06-production-implementation.md

- 2026-11-06: user requested complete phased agent plan, immediate execution, checked progress and local commits.
- Ruling: immediate execution was explicitly requested; no extra plan-handoff pause. Existing-stack invite-only pilot is the implementer choice; hosting, legal sign-off and deployment are external gates. Cost: defaults may need operator adjustment.
- Ruling: preserve current codex/evidence-foundations checkout and commit prior corrections separately. Cost: scopes share a branch but remain separate commits.
- Ruling: controller integrates inline; independent modules use exclusive-file delegation under dispatching-parallel-agents. Cost: controller must verify all interfaces/security gates.
- Pre-flight: T03 principals feed T04/T06; T05 review versions feed T06/T07; T01 private snapshots feed edited-letter validation/retention. Contracts pin names/types and source privacy before implementation.
- T00: baseline suite and fresh builder check pending.

- T00: complete — full baseline 120 passed, git diff --check clean. Prior corrections committed caed8d4. Plan/ledger commit follows this recorded check.
- Builder check: three important contract gaps resolved before implementation: all review mutations advance expected_version; snapshots are immutable per job with mismatched initialization rejected; durable deletion tombstones fence every review write and job status fences worker claims. Tests explicitly cover all three.
- Ruling: decisions increment the same mutation revision as edits; use content-free durable review deletion tombstones. Cost: clients must refresh after decisions and deletion metadata survives private-record purge to prevent resurrection.

- Plan committed e3ff3d2 after builder gaps resolved.
- T01/T02 complete locally: exact policy quote/offset provenance and missing-evidence review gate; private original source snapshots; Writer/Judge/revision shared policy wording; contextual Unicode/spelled deadline rejection; unsupported legal clauses removed without invented policy attribution; versioned prompt/cache invalidation. Nine added regressions observed RED then GREEN.
- Verification: 129 existing/new pipeline tests passed; excluded only T03/T05 agents' independent work-in-progress test files. Full integrated suite follows module handoff. This does not prove model semantics; expert/live acceptance remains open.
- Ruling: deadline support requires matching timing and response/payment/escalation context, so an unrelated waiting-period number cannot support a reply deadline. Cost: conservative false positives need human correction.

- T03 and T05 module agents stopped on usage limits before commits; controller inspected files and verified tests directly. T03 27 passed; T05 30 passed after fixing interrupted test parameter and reproducing/fixing bool/float revision acceptance RED to GREEN.
- T03 module complete: named invite-only accounts, actual scrypt, digest sessions, reset/disable revocation, exact Origin/CSRF, cookie security, persisted throttle and hidden-prompt CLI. T05 module complete: immutable mutations, optimistic concurrency, exact approval hashes and durable deletion fences. Integration/independent security review remain pending; no real accounts/data created.

- T03 committed 14fdd19; T05 committed ab935a8 (module contracts and test evidence included).
- T04: account auth mounted; shared keys cannot bypass cookie identity, all case reads/downloads authorize owner/org, unowned legacy rows hidden, per-job internal namespaces isolate display labels, status/report projections remove internal paths/tracebacks. Case-access regressions observed RED then focused API/JobStore/access 9 passed.
- T04 integrated verification: complete full suite 190 passed in 25.74s. No provider calls or real accounts were used.

- T04 committed f752399. Independent identity/ownership review confirmed contracts substantially implemented and found important wildcard credentialed CORS and private-response caching gaps. Both reproduced RED and fixed (explicit-origin configuration validation; no-store + Vary Cookie on private API responses). Decoder RecursionError is normalized for Python-version portability; no claim it failed on local Python 3.13.
- T06: versioned edit/decision API and exact approved export implemented; same-org reviewer role, CSRF and all three confirmations required. Edited-letter validation uses immutable private source snapshots; source mismatch, stale versions and missing/invalid evidence block approval. Race regression reproduced validation of old version followed by approval of new version, fixed by matching request to the validated version before transactional decision.
- T06 integrated verification: full suite 198 passed in 25.33s; important review findings fixed with regressions. No public deployment or legal approval claimed.
