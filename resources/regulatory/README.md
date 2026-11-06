# Pinned public regulatory corpus

`registry.json` is the curated index. `artifacts/` contains the exact official
PDFs and their extracted page-text JSON. These files are public sources, not
medical claim documents. Their hashes and source URLs are validated by
`tools/regulatory_registry.py` before use.

Three source artifacts are catalogued; only nine health-circular excerpts are
currently clause-curated. Source provenance and legal applicability are separate:
every case-specific interpretation still requires human review. See
`docs/REGULATORY_SOURCES.md` for trust boundaries, import steps and limits.

Operator imports go into a separate candidate directory. Do not place personal
case files or provider credentials here.
