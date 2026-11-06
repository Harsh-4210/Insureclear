# Versioned regulatory source registry design

Status: approved by user for implementation. Date: 2026-11-05.

## Intent

Replace unsourced regulatory assertions in model context with traceable,
versioned source evidence. The user authorized verified regulatory sources.
Verification of a document's provenance is distinct from deciding whether its
rule legally applies to an individual case.

## Approaches

1. Existing hard-coded knowledge and manual-verification tags: available now,
   but assertions can be outdated or have no identifiable source.
2. Curated local registry with pinned official artifacts: recommended first
   implementation; deterministic, auditable, testable without live browsing.
3. Live web research for every case: may find newer changes but adds latency,
   nondeterminism, availability problems and difficult trust boundaries.

Use option 2, with an explicit maintenance/import command. The recommendation
has been presented; the user approved this design and implementation. Implement after document
retrieval so the registry can share bounded source formatting.

## Registry and evidence contract

- A schema-versioned registry contains stable source IDs, instrument title and
  reference, publisher, official source URL, publication date, effective range
  where explicitly established, optional supersession links, fetched date,
  artifact SHA-256, extraction version, exact clause references and text offsets.
- Trust is assigned by trusted import/curation code, never by an LLM output or a
  JSON field supplied by a requester. Only allowlisted HTTPS publisher hosts
  qualify for verified-source import. Validate redirects, PDF signatures,
  bounded download sizes/timeouts, content hashes and clause-text presence.
- Official IRDAI, Gazette of India, CIO and government publications may be
  registered, but each entry must identify its type. A parliamentary answer
  summarizing a circular does not count as the circular's complete text.
- Keep exact artifacts and extracted source text separate from interpretations.
  A verified artifact may still have applicability_status=requires_review.
- Unknown effective dates must remain unknown. Do not use publication date as
  effective date by default or assume the newest document governs every policy.
- Rule applicability metadata declares its date basis (policy inception or claim/
  denial date) and supported conditions, curated from the source. Missing or
  ambiguous dates, conflicts, supersession uncertainty or unmet conditions yield
  manual review rather than an automatically selected governing rule.
- First-phase acceptance boundary (implementer choice): verify document provenance
  and exact text only. Every model interpretation and every case-specific legal
  application requires human review, even when its source is genuine. Do not
  implement automatic legal acceptance or a rules engine in this phase.
- Source lookup is deterministic by category/date and bounded to the document
  context budget. Unknown IDs, wrong hashes, fabricated quotes, inaccessible
  artifacts and unresolved versions cannot enter the verified evidence set.
- The IRDAI Checker receives pinned source excerpts and source IDs. Citation
  metadata is populated by code through registry lookup; model-produced URLs,
  references and verified flags are not trusted. A valid source ID establishes
  provenance only; wording still needs evidence/applicability checks.
- The Writer and Judge receive the same verified excerpts and provenance map.
  Final validation receives these excerpts under regulatory evidence, never
  generated IRDAI analysis as a source. Unresolved regulatory claims retain
  manual-review status; do not promote unverified narrative precedents.
- Remove unconditional legacy rule assertions from active model context when
  they lack a verified source. Keep any historical research leads separate and
  explicitly unverified. Remove fixed numeric legal promises in prompts unless
  the selected source establishes them.
- Registry content hash/version and selected evidence must participate in cache
  identity. A changed source cannot reuse outdated regulatory conclusions.
- No case data is sent to public websites for source import. Runtime analysis
  uses the local registry and does not follow user/model-provided URLs.

## Initial research and import limits

Three research artifacts were fetched directly from official publisher hosts and
recorded with SHA-256 hashes in docs/superpowers/research/regulatory:

- Health insurance master circular: IRDAI document 4942918, English attachment,
  17 pages, 962,806 bytes.
- Policyholder interests master circular: IRDAI document 5625747, combined
  attachment version 5.1, 203 pages, 1,999,750 bytes. Its English-only attachment
  is over 91 MB, so research used the smaller official combined document.
- Insurance Products Regulations 2024: Gazette artifact 253325, 38 pages,
  1,095,559 bytes.

The ledger pins retrieved bytes. Source provenance does not establish that an
instrument is complete, still current, or legally applicable to a particular
case. Add only clause evidence actually checked against those pinned artifacts.

Import and seed only documents successfully retrieved from official publishers
and checked against their recorded content. Record failed/unavailable candidates
as requires_manual_verification with no authoritative rule text. Never substitute
a third-party mirror and mark it verified. If full primary artifacts remain
unavailable, ship the tested registry/import capability and clearly report the
unverified seed gap; it is not completion of verified legal coverage.

## Files and interfaces

- tools/regulatory_registry.py: schema validation, local artifact integrity,
  source selection, provenance/evidence rendering and registry fingerprint.
- tools/import_regulatory_source.py: bounded official-artifact import and
  verification report; no automatic in-place replacement of pinned versions.
- data/regulatory/: curated registry metadata and public source artifacts; never
  case documents or secrets.
- agents/irdai_checker.py, agents/appeal_writer.py, agents/judge.py,
  orchestrator/main.py, tools/io_utils.py: shared verified context and cache key.
- Unit/integration tests for the trust boundary and agent context; documentation
  in docs/REGULATORY_SOURCES.md describing what is and is not verified.

## Acceptance criteria

- A valid official source resolves to exact pinned text and a stable evidence ID;
  tampered bytes, unknown references, nonofficial URLs/redirects and bogus quote
  offsets fail verification.
- Effective-range boundaries, missing dates, date-basis choice, conflicts and
  supersession uncertainty are deterministic and visibly require review when
  unresolved.
- A model cannot mark an unregistered circular or precedent verified by echoing
  an official-looking URL or another entry's source ID.
- Writer, Judge and final validator share the same selected source evidence.
  Source/regulatory version changes invalidate cached results.
- Existing valid-denial guardrails remain. Numeric deadlines and moratorium
  assertions cannot come from unsupported hard-coded prompt text.
- Run the complete automated suite and strict live synthetic evaluation. Review
  discrepancies against primary documents; do not rewrite answer keys merely
  to obtain a passing score. Do not claim legal correctness from test accuracy.

## Non-goals and builder choices

No automatic legal advice, blanket applicability guarantee, live per-case web
crawler, comprehensive corpus of all IRDAI/CIO material, or distributed service.
The builder may choose exact dataclasses and JSON layout within this contract.
A qualified review and broader corpus validation remain release work.
