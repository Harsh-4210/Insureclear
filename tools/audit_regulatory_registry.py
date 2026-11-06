"""Read-only, metadata-only audit of a loader-verified regulatory registry.

Source provenance is distinct from a qualified human's legal applicability review.
The callable inspects a Registry snapshot; the CLI freshly verifies pinned files.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import sys

# Support the documented direct script invocation as well as python -m.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.regulatory_registry import DEFAULT_REGISTRY, Registry, RegistryError, load_registry


HUMAN_REVIEW = "human_applicability_review_required"


def audit_registry(registry: Registry) -> dict:
    """Describe coverage/gaps without inferring dates or approving legal rules.

    Pass a Registry returned by load_registry. Integrity refers to validation at
    load time, not a new read of files or verification of a PDF digital signature.
    Unknown bounds, date bases and supersession remain unknown. This function
    never modifies its input or emits excerpt bodies.
    """
    if not registry.sources or not registry.clauses:
        raise RegistryError("Regulatory corpus must contain sources and curated excerpts")

    gaps = {"missing_effective_ranges": [], "missing_effective_from": [],
            "missing_effective_to": [], "missing_date_basis": [],
            "unknown_supersession": [], "recorded_supersession": []}
    source_counts = Counter()
    category_counts = Counter()
    excerpts = []
    for clause in registry.clauses:
        evidence_id = f"{clause['source_id']}:{clause['id']}"
        if clause["source_id"] not in registry.sources:
            raise RegistryError("Excerpt references an unavailable source")
        reasons = [HUMAN_REVIEW]
        effective_from, effective_to = clause.get("effective_from"), clause.get("effective_to")
        for name, value in (("effective_from", effective_from), ("effective_to", effective_to)):
            if value is None:
                gaps[f"missing_{name}"].append(evidence_id)
                reasons.append(f"{name}_unknown")
        if effective_from is None or effective_to is None:
            gaps["missing_effective_ranges"].append(evidence_id)
        basis = clause.get("date_basis")
        if basis not in ("denial_date", "policy_start_date"):
            gaps["missing_date_basis"].append(evidence_id)
            reasons.append("date_basis_missing_or_invalid")
        superseded_by = clause.get("superseded_by")
        if superseded_by:
            supersession_status = "recorded_requires_review"
            gaps["recorded_supersession"].append(evidence_id)
            reasons.append("supersession_requires_review")
        else:
            supersession_status = "unknown"
            gaps["unknown_supersession"].append(evidence_id)
            reasons.append("supersession_unknown")
        source_counts[clause["source_id"]] += 1
        categories = sorted(set(clause["categories"]))
        category_counts.update(categories)
        excerpts.append({
            "evidence_id": evidence_id, "source_id": clause["source_id"],
            "page": clause["page"], "start": clause["start"], "end": clause["end"],
            "clause_references": copy.deepcopy(clause.get("clause_references", [])),
            "categories": categories, "effective_from": effective_from,
            "effective_to": effective_to, "date_basis": basis,
            "superseded_by": copy.deepcopy(superseded_by),
            "supersession_status": supersession_status,
            "applicability_status": "requires_review", "review_reasons": reasons,
        })

    sources = []
    for source_id, source in sorted(registry.sources.items()):
        entry = {key: source.get(key) for key in (
            "id", "title", "reference", "publisher", "publisher_version",
            "official_url", "published_date", "retrieved_date", "artifact_sha256", "text_sha256",
        )}
        entry.update({"excerpt_count": source_counts[source_id],
                      "integrity_status": "verified_at_load",
                      "applicability_status": "requires_review"})
        sources.append(entry)
    uncurated = [source_id for source_id in sorted(registry.sources) if not source_counts[source_id]]
    reasons = [HUMAN_REVIEW, "governing_versions_and_conflicts_require_review"]
    if uncurated:
        reasons.append("catalogued_sources_without_curated_excerpts")
    if any(gaps.values()):
        reasons.append("date_basis_effective_range_or_supersession_requires_review")
    return {
        "registry_fingerprint": registry.fingerprint,
        "integrity_status": "verified_at_load",
        "integrity_scope": "Loader checks official URLs, pinned PDF/text hashes and excerpt offsets; no PDF digital-signature or legal-validity verification. Snapshot audit does not reread files.",
        "source_count": len(sources), "excerpt_count": len(excerpts),
        "coverage": {"sources_with_excerpts": len(sources) - len(uncurated),
                     "sources_without_excerpts": uncurated,
                     "category_excerpt_counts": dict(sorted(category_counts.items())),
                     "scope": "Curated excerpt counts only; categories and wildcard do not establish completeness or legal applicability."},
        "sources": sources, "excerpts": excerpts, "gaps": gaps,
        "requires_manual_review": True, "applicability_status": "requires_review",
        "review_reasons": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY,
                        help="Pinned registry JSON (default: repository corpus)")
    args = parser.parse_args(argv)
    try:
        report = audit_registry(load_registry(args.registry))
    except RegistryError:
        print(json.dumps({"integrity_status": "failed", "requires_manual_review": True,
                          "applicability_status": "requires_review",
                          "review_reasons": [HUMAN_REVIEW],
                          "error": "Regulatory corpus unavailable, empty or failed integrity validation."}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
