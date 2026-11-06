# Regulatory review checklist

**Status: unreviewed. No qualified legal sign-off or legal acceptance is recorded.**
A coding agent, successful metadata audit or model verdict cannot complete this
checklist. A qualified legal reviewer must make and sign the governing-version,
effective-date, applicability and conflict decisions with reasons and evidence.

## Audit evidence

From the repository root, run the read-only command:

```powershell
.\.venv\Scripts\python.exe -B tools/audit_regulatory_registry.py
```

The JSON output contains public source metadata, pinned hashes, a registry
fingerprint, excerpt locations, coverage counts and unresolved metadata. It emits
no excerpt bodies and writes no files. Exit 0 means the corpus loaded and its
pinned integrity checks passed; it does not mean legal approval. Missing,
corrupt or empty corpora produce exit 1. `--registry PATH` audits a candidate
registry without activating or modifying it.

Integrity is the existing loader's official-host, PDF-header, artifact/text-hash
and exact-offset validation at load time. It is not PDF digital-signature
verification or proof that a source is current or governs a particular claim.
The Python `audit_registry(registry)` callable describes an already loaded
Registry snapshot; it does not reread files. Use the CLI for a fresh file check.

The current pinned corpus has three sources and nine health-circular excerpts.
The policyholder-interest circular and products regulations are catalogued with
zero curated excerpts. Category counts, including `*`, describe selection
metadata; they do not prove subject coverage, legal completeness or applicability.
All nine excerpts have unknown effective bounds and unknown supersession metadata.
A missing upper bound is unresolved metadata, not a finding that a rule expired.
Publication/retrieval dates must never be substituted for effective dates.
A configured `date_basis` is a selection hint requiring legal confirmation.

## Review record (complete for each source/version and applicable excerpt)

Keep case-specific findings in the restricted case review record. This reusable
repository checklist and public audit must not contain patient facts or documents.

| Field | Reviewer entry |
|---|---|
| Record ID and scope (corpus release or restricted case reference) | Unrecorded |
| Candidate code commit and registry version | Unrecorded |
| Registry fingerprint and audit evidence location/hash | Unrecorded |
| Source ID, title, instrument/reference and official URL | Unrecorded |
| Publisher attachment/version, publication and retrieval dates | Unrecorded |
| Pinned PDF SHA-256 and extracted-text SHA-256 | Unrecorded |
| Excerpt IDs, printed clause labels, pages and exact offsets | Unrecorded |
| Governing version and supporting official evidence | Unreviewed |
| Effective-from/to decision, transitions, exceptions and evidence | Unknown / unreviewed |
| Date basis and reasons; relevant case dates and ambiguity | Unreviewed |
| Amendments, rescission, supersession and predecessor/successor evidence | Unknown / unreviewed |
| Companion instruments, hierarchy and conflicts; resolution/evidence/reasons | Unreviewed |
| Curated coverage limits and omitted material affecting decision | Unreviewed |
| Applicability decision, qualifications and reasons | Unreviewed |
| Qualified reviewer's name, role and relevant qualification | Unassigned |
| Review date/time and signed evidence reference | Unsigned |
| Decision (accepted for stated scope / changes required / cannot determine) | Unreviewed |
| Required changes, responsible person and next review trigger/date | Unrecorded |

Record “unknown” or “cannot determine” with the reason when evidence is missing;
do not fabricate a date, a source relationship or a favorable decision.
An explicit decision that no end date or superseding instrument was found must
state the search scope, official evidence and review date. Absence of a
`superseded_by` field is not that decision.

## Qualified review gates

- [ ] Verify the exact pinned official source/version and hashes against the audit fingerprint.
- [ ] Examine full governing instruments, not only the nine selected excerpts; identify coverage gaps and material omissions.
- [ ] Confirm current and historical governing versions, amendments and rescission/supersession against official evidence.
- [ ] Determine effective ranges, transitional provisions, exceptions and the legally relevant date basis with evidence and reasons.
- [ ] Resolve companion-circular provisions, conflicting instruments and hierarchy; document remaining uncertainty.
- [ ] Evaluate case-specific applicability, exact quotation/context and unsupported claims in the restricted review record.
- [ ] Record each decision, limitations, reviewer identity/qualification, date and signed supporting evidence.
- [ ] Require re-review after source/version/hash changes, new official instruments, material case changes or unresolved conflicts.

**Qualified legal acceptance: unchecked.** Corpus maintenance is distinct from
approval of a particular letter. Application approval still requires the current
version/source-bound human review workflow. This document supplies no sign-off.
