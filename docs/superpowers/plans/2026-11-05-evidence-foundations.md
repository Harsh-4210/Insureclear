# Document Retrieval and Source Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Bound agent document context and share pinned official regulatory evidence through the pipeline.
**Architecture:** Deterministic source chunks with explicit coverage; a local, integrity-checked registry that verifies provenance and keeps legal interpretations under human review.
**Tech Stack:** Existing Python, FastAPI, pytest, pdfplumber; no new runtime service.
**Spec:** ../specs/2026-11-05-document-retrieval-design.md and ../specs/2026-11-05-regulatory-registry-design.md.

## Global Constraints

- User approved both designs and explicitly requested implementation.
- Pilot scale; no agreed load/hosting budget. Do not provision infrastructure.
- Existing original source evidence remains intact. No plaintext medical inputs in new logs.
- 16,000 conservative UTF-8 byte-bound prompt units, 1,200-unit source chunks, up to 120 overlap units by default; reserve requested output separately.
- Legal applicability always needs human review; official source provenance is not legal approval.
- Preserve existing interfaces where practical, adding optional context inputs.
- Keep changes reviewable in the current checkout; do not overwrite the preceding review fixes.

## Review Focus

- Non-ASCII and giant unbroken input must stay bounded and terminate.
- Retrieval must find late exact clause references and preserve negation.
- Source hashes, paths, redirects and model-provided IDs must not bypass trust checks.
- Missing/ambiguous dates and apparent source conflicts must require manual review.
- Changed budgets/registry bytes must invalidate checkpoints; direct agent calls need budget guards too.

### Task 1: Deterministic bounded source context

**Files:** tools/document_context.py; tests/test_document_context.py.
**Interfaces:** estimate_tokens(text)->int (UTF-8 upper bound); chunk_document(text, source_id, chunk_units=1200, overlap_units=120)->list[SourceChunk]; select_context(sources, query, budget_units)->DocumentContext; DocumentContext.text and .as_dict().

- [ ] Write tests: exact source-slice offsets, stable IDs, Unicode/unbroken text termination, invalid budgets, bounded output, complete short text and late Clause 8.7 selection with negation retained.
- [ ] Run focused pytest; expected missing module/function or failed required behavior.
- [ ] Implement deterministic byte-bounded splitting/ranking; return selected and omitted metadata.
- [ ] Run focused tests; expected pass. Record verified patch and task result in ledger.

### Task 2: Agent budgets and pipeline coverage

**Files:** agents/auditor.py; agents/policy_analyst.py; tools/io_utils.py; orchestrator/main.py; integration tests.
**Interfaces:** fit_document_prompt(prompt, system_prompt, sources, query, max_output_tokens)->(str, dict); retrieval_fingerprint()->str; prepare_session optional context_fingerprint.

- [ ] Add failing direct-agent prompt budget and pipeline REVIEW_REQUIRED/cache-change tests. Keep existing complete-short-document tests.
- [ ] Run focused pytest; expected failure before behavior exists.
- [ ] Bound full prompts including system/scaffolding/output reserve, retain coverage in agent results, aggregate in report, and cap effective recommendation when any source is omitted. Cache identity includes configuration.
- [ ] Run whole backend suite; expected all pass. Record task result.

### Task 3: Pinned regulatory registry and importer

**Files:** tools/regulatory_registry.py; tools/import_regulatory_source.py; resources/regulatory/; registry tests.
**Interfaces:** load_registry(path=DEFAULT_REGISTRY)->Registry; Registry.fingerprint, .select(category, facts, budget_units), .annotate(result); selected evidence has stable IDs, exact source excerpts, provenance and requires_manual_review.

- [ ] Add failing tests for valid pinned evidence, altered artifact/extracted text, traversal paths, unknown IDs, forged verification fields, absent/ambiguous dates, effective boundaries and bounded official import/redirect checks.
- [ ] Run focused pytest; expected failure.
- [ ] Implement strict schema and source/hash/quote verification. Seed from the three already retrieved official research artifacts, retaining publisher versions and per-clause provenance. Do not auto-approve legal applicability.
- [ ] Run focused tests; expected pass. Record task result.

### Task 4: Shared regulatory evidence throughout generation

**Files:** agents/irdai_checker.py; agents/appeal_writer.py; agents/judge.py; orchestrator/main.py; tools/io_utils.py; tests.
**Interfaces:** optional regulatory_context string/map for Checker, Writer, Judge; pipeline combines selected registry text with user-supplied regulatory_text for evidence validation, preserving provenance distinction.

- [ ] Add failing tests showing fake IDs cannot become verified; Writer/Judge see the same pinned excerpts; legacy unsourced rules are absent; registry changes invalidate caches.
- [ ] Run focused pytest; expected failure.
- [ ] Pass one selected evidence set through agents. Remove hard-coded unsourced numeric promises and narrative precedents from active regulatory context. Set REVIEW_REQUIRED for case-specific legal claims; preserve valid-denial and validation-error precedence.
- [ ] Run full backend suite; expected all pass. Record result.

### Task 5: Final verification and evidence

**Files:** docs/REGULATORY_SOURCES.md; README.md; docs/PRODUCTION_READINESS.md; implementation ledger.

- [ ] Run full pytest and frontend production build; expect success.
- [ ] Request one independent whole-change review against both approved specs; fix important findings with failing regressions before implementation.
- [ ] Run a new live ten-case evaluation with strict verdict/unsupported-claim gates; preserve failures honestly and investigate reproducible defects without weakening the answer key.
- [ ] Record baseline/after metrics, actual coverage, known limitations, scaling recommendations, and local patch status. Keep checkpoint/source data integrity verified.
