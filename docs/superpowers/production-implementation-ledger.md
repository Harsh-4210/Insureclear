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
