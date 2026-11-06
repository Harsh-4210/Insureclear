# Implementation ledger — plan: docs/superpowers/plans/2026-11-05-evidence-foundations.md

- User approved both designs and implementation on 2026-11-05.
- Baseline: 62 backend tests; live 10/10 verdicts, zero detected unsupported claims; 97.5% letter facts; 88 calls, 312888 tokens.
- Pre-flight: Task 1 produces DocumentContext used by Task 2; Task 3 produces Registry evidence used by Task 4; both versions participate in Task 2/4 cache identity. Signatures agree.
- Ruling: execute inline in the existing Python checkout and preserve the preceding uncommitted review fixes — user requested implementation here; a new checkout would omit those fixes. Use a codex branch for isolation; leave changes reviewable without mixing prior fixes into automatic commits.
- Ruling: legal applicability remains human-reviewed even for pinned official artifacts — provenance alone cannot validate a case-specific legal claim.

- Task 1: complete — 8 document-context tests RED (module missing) to GREEN.
- Task 2: integration RED captured for budgets, REVIEW_REQUIRED and config cache identity.
- Ruling: pre-existing complete-12k-character prompt test sets a 32k budget explicitly — the new conservative 16k limit reserves scaffolding and output; the test should exercise complete inclusion when it fits.

- Task 2: complete — full suite 73 passed; agent budget, coverage and config cache tests RED to GREEN.
- Task 3: registry/import trust tests RED (missing module) to GREEN, 14 passed. Seeded 3 pinned official artifacts and 9 exact health-circular excerpts; companion instruments are catalogued, not represented as fully curated.

- Task 3: complete — 3 official artifacts and 9 exact excerpts pass default-registry verification; 14 integrity tests green.
- Task 4: complete — 91 full-suite tests passed. Shared Checker/Writer/Judge source evidence and registry-version invalidation tests RED to GREEN. Added bounded prompt guards; removed fixed unsourced escalation and moratorium promises from active agent prompts.
- Task 5: post-change live evaluation running as sp_found_20261105; independent whole-change review pending.

- Final review: independent reviewer identified important trust, budget, performance and Streamlit bypass issues before its turn hit a usage limit. The review was not a clean approval.
- Final: fixed repeated decimal-query regex work — regression RED 8600 searches to GREEN bounded set intersections.
- Final: fixed citation source identity/type attribution, stale source fields, non-string IDs and incidental quotes — four registry regressions RED to GREEN.
- Final: fixed case amounts/clauses being supported by unrelated regulatory numbers and unverified caller text entering authoritative evidence — regressions RED to GREEN.
- Final: fixed actual provider output/reasoning/JSON reservation and Groq retry bound — mocked transport regressions RED to GREEN.
- Final: fixed generated legal leads under VERIFIED FACTS and duplicated provenance metadata in model prompts — regressions RED to GREEN; draft output capped at 1200 tokens and requested under 450 words.
- Final: fixed active Streamlit bypass — AppTest proves shared REVIEW_REQUIRED and VALIDATION_ERROR results, RED to GREEN.
- Ruling: user-supplied regulatory_text remains a cache input and unverified lead, but is excluded from authoritative evidence — code cannot establish its official provenance.
- Ruling: exact curated excerpt and compatible instrument type are required before attaching source provenance; legal interpretations still require human review.
- Live sp_found_20261105 failed all 10 cases on ordinary model-prompt bounds before the compact-prompt fixes. Preserve this failed run; a fresh run is required.

- Final review completion: two remaining findings reproduced RED: existing Docker data volumes hide the corpus; direct Checker/Writer caches ignored changed inputs.
- Ruling: bundled immutable corpus moved from data/regulatory to resources/regulatory so existing /app/data volumes cannot mask it. Candidate imports remain mutable and separate.
- Final: direct caches now bind case facts, selected evidence, source version and budget; Writer revisions/sanitization preserve the input hash for correct resume.
