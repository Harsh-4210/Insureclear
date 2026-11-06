# Bounded document retrieval design

Status: approved by user for implementation. Date: 2026-11-05.

## Intent

Keep complete source evidence available while limiting per-agent document context,
reducing token usage and making omitted coverage explicit. The user authorized
long-document improvements after the Superpowers review. They have not decided on a scale target yet; no particular volume or hosting
budget has been agreed. Keep this phase suitable for a pilot and reversible.

## Approaches

1. Full-document prompts: current behavior; simplest, but large PDFs can exceed
   context or quota and repeat policy text across agents.
2. Deterministic chunking and lexical retrieval: recommended implementation choice.
   No external database or embedding service; stable source locations, bounded
   prompts, visible omissions. Retrieval cannot guarantee complete policy review.
3. LLM map/reduce over every chunk, or an embedding service: broader coverage or
   semantic matching, but more model calls, operational cost, and evaluation work.
   Retain as a later option after measuring retrieval recall.

The proposed implementation uses option 2. This choice has been presented to the
user; the user approved this document and implementation.

## Behavior and boundaries

- Keep original denial and policy text unchanged for evidence validation and
  input fingerprints. Retrieval is an agent context view, not a source rewrite.
- Short documents that fit the budget are included completely. Preserve current
  agent behavior for these inputs.
- Split long sources deterministically at paragraph/word boundaries, with stable
  source IDs and character start/end offsets. Preserve exact substring text;
  never call a summary an original quotation. Repeated headers and OCR noise
  must not create unbounded prompts or infinite splitting loops.
- Use an explicit conservative token upper bound based on UTF-8 byte length,
  rather than claiming an exact model-specific token count. Include system text,
  prompt scaffolding, source labels, and output reservation in the budget check.
- Defaults proposed by the implementer: 16,000 prompt-budget units, 1,200-unit
  target source chunks, and up to 120 units overlap. Configuration must be
  positive and internally consistent. No new production dependency is required.
- Auditor retrieval ranks chunks using denial facts, identifiers and insurance
  terms; Policy Analyst retrieval also uses Auditor facts and cited clauses.
  Include beginnings/endings and high-priority coverage, exclusion, waiting
  period and benefit-limit sections where the budget permits. Ties are stable
  by source order, and selected chunks are presented in document order.
- If mandatory content cannot fit, explicitly report budget/coverage failure;
  do not silently discard it or claim a complete analysis.
- Store input_coverage in the final report: source IDs, source lengths, total
  and included chunks, selected offsets, omitted IDs, budget method, configured
  limit, actual bound, and retrieval strategy/version. Store no document text in
  operational logs.
- Any omitted source content sets requires_manual_review. An otherwise APPROVE
  final recommendation becomes REVIEW_REQUIRED; preserve existing REVISE and
  VALIDATION_ERROR precedence. The model Judge score remains a model assessment,
  separate from the pipeline's final recommendation.
- Include retrieval version and relevant configuration in checkpoint identity.
  Changing a budget or retrieval behavior must not reuse a prior selection.
- CLI, API and Streamlit use the same pipeline behavior. Existing result fields
  remain; coverage metadata and review reasons are additive. No visual redesign.

## Files and interfaces

- New tools/document_context.py: token-bound estimation, deterministic chunks,
  relevance scoring, bounded selection, and serializable coverage metadata.
- agents/auditor.py and agents/policy_analyst.py consume selected source context;
  keep existing public call signatures unless an optional context parameter is
  needed. Direct agent calls must also enforce the same budget.
- orchestrator/main.py assembles coverage and the effective recommendation;
  tools/io_utils.py binds caches to retrieval configuration/version.
- tests/test_document_context.py and agent/pipeline integration tests cover the
  behavior below. Keep provider calls deterministic in unit tests.

## Acceptance criteria

- Every chunk text equals its recorded source slice, including Unicode input.
- A meaningful clause beyond character 5,000 is retrievable by its number or
  denial-related terms. Explicitly test negation, repeated headers, an exclusion
  near the end, and an exact-limit boundary.
- Returned prompt context stays within its configured upper bound; a single huge
  paragraph, multibyte characters and impossible budgets produce bounded,
  explicit behavior.
- Identical inputs/configuration select identical chunks and reuse valid caches.
  Changed inputs or budgets do not.
- An omitted clause cannot coexist with a pipeline claim of full coverage or
  unconditional APPROVE. Full-source evidence validation remains unchanged.
- Existing full backend tests and frontend build pass; compare strict synthetic
  evaluation before/after, and add long-document retrieval fixtures before
  accepting a release baseline.

## Non-goals and decisions left to the builder

No vector database, embedding provider, distributed worker pool, or new hosting
service in this phase. No throughput promise. The builder may choose internal
class names, scoring weights and helper structure, provided the behavior is
stable, tested and reported. Changes stay local and reviewable until integration.
