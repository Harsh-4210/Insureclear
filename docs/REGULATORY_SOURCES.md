# Regulatory source registry

The runtime registry is `resources/regulatory/registry.json`. Its pinned artifacts and
page-text extractions are public regulatory material, separate from case inputs.
The registry checks allowlisted official HTTPS URLs, PDF file headers, SHA-256
integrity, extraction hashes, and exact page/character offsets. It does not
cryptographically validate a PDF digital signature or approve legal applicability.

## Current curated scope

| Artifact | Official publisher record | Pinned version | Runtime use |
|---|---|---|---|
| Health Insurance master circular, 2024 | [IRDAI document 4942918](https://irdai.gov.in/document-detail?documentId=4942918) | English attachment 1.0, 17 pages | Nine exact excerpts, with explicit selection and omission metadata |
| Protection of Policyholders' Interests master circular, 2024 | [IRDAI document 5625747](https://irdai.gov.in/document-detail?documentId=5625747) | Combined attachment 5.1, 203 pages | Catalogued and integrity checked; not fully clause-curated |
| Insurance Products Regulations, 2024 | [Gazette artifact 253325](https://egazette.gov.in/WriteReadData/2024/253325.pdf) | Gazette publication, 38 pages | Catalogued and integrity checked; not fully clause-curated |

Artifacts were retrieved from official publisher hosts on 2026-11-05. Exact
attachment URLs, publication metadata, file hashes, extracted-text hashes and
selected offsets are in the registry. This is a pinned research corpus, not a
claim to cover every applicable instrument or subsequent amendment.

The nine health-circular excerpts cover effective-date qualifications, companion
circular context, portability, moratorium, cashless approval, discharge,
claim-review/reason requirements, document collection and grievances. Selection
uses a bounded context and reports omitted evidence. Unknown effective ranges,
ambiguous dates, conflicts and every case-specific legal interpretation require
human review. Publication date is not automatically an effective date.

## Trust boundary

The Checker, Writer and Judge receive the same selected primary excerpts. The
final validator uses pinned excerpt text rather than generated regulatory
analysis. Caller-supplied `regulatory_text` is treated as an unverified lead and
excluded from authoritative validation. Patient amounts and policy clauses must
be grounded in case sources, not unrelated regulatory numbers.

A model cannot assign itself a verified citation. Code links provenance only for
an exact curated quote and a registered evidence ID of a compatible instrument
type. Source identity, URL, page and hash come from the registry; model-supplied
source fields are discarded. Curated parent/subclause labels preserve printed PDF
structure, so references such as 17(a) can be resolved without treating arbitrary
regulatory digits as patient facts. A circular cannot verify an invented court or
Ombudsman precedent. `verified_source_only` refers to the exact source quotation;
`manual_verification_required` and `requires_review` still apply to interpretation.

Unverified numeric promises and narrative precedents from the old hard-coded
knowledge base are no longer sent as authoritative regulatory context. They
remain historical research material in `tools/irdai_knowledge.py`, not verified
runtime evidence.

## Updating the corpus

Use `python tools/import_regulatory_source.py --help` for the bounded official-PDF
import command. Supply an official PDF attachment URL, not a listing webpage.
Imports create a new candidate directory with source bytes, extracted page text
and hashes. They do not overwrite a pinned source or automatically activate legal
rules. An operator must curate metadata, exact clauses, date basis, effective
ranges and supersession relationships before a candidate enters the registry.

The default download limit is 12 MB. The official English-only policyholder
circular is over 91 MB; this corpus uses the smaller official combined attachment.
Never silently replace an official artifact with a third-party mirror. Registry
or document-context configuration changes invalidate the pipeline checkpoint set.

## Release limits

A qualified reviewer must confirm governing versions and applicability. The
current corpus has no curated case-law orders, no complete rule engine, and no
automatic legal approval. Consult the official IRDAI and CIO publications when
expanding the corpus. See the approved design and implementation ledger in
`docs/superpowers/` for scope and verification evidence.

## Metadata audit and qualified review

Run `python -B tools/audit_regulatory_registry.py` from the repository root for a
fresh, read-only integrity/coverage audit of the pinned corpus. It emits metadata
JSON, counts catalogued sources separately from curated excerpts, preserves
unknown effective bounds/date bases/supersession, and always requires human
applicability review. Exit 0 verifies loader-time integrity only; corrupt, missing
or empty corpora return nonzero. `--registry PATH` inspects a candidate without
activating it. The callable `audit_registry(registry)` inspects an already loaded
snapshot and does not reread artifact files or verify PDF digital signatures.

Use [REGULATORY_REVIEW_CHECKLIST.md](REGULATORY_REVIEW_CHECKLIST.md) to record the
qualified reviewer's identity/date, governing source/version, effective-date and
date-basis evidence, supersession, conflicts, decision and reasons. No legal
acceptance has been recorded by the implementation. Unknown dates and absent
supersession metadata remain unresolved; publication dates are not effective-date
substitutes. Zero curated excerpts for a catalogued source is a coverage gap,
not evidence that the source is irrelevant.
