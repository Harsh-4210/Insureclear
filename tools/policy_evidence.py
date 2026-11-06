"""Exact policy-source provenance, deliberately separate from interpretation."""
from copy import deepcopy

POLICY_EVIDENCE_VERSION = 1


def annotate_policy_evidence(result: dict, policy_text: str) -> dict:
    result = deepcopy(result)
    entries = result.get("policy_evidence")
    entries = entries if isinstance(entries, list) else []
    verified, annotated, reasons = [], [], []
    if not entries:
        reasons.append("Policy arguments lack exact policy excerpts; review the original wording.")
    if len(entries) > 3:
        reasons.append("Additional policy evidence was omitted from the bounded evidence map.")
    for index, entry in enumerate(entries[:3]):
        item = {key: entry.get(key) for key in ("quote", "clause", "argument")} if isinstance(entry, dict) else {"quote": None}
        quote = item.get("quote")
        start = policy_text.find(quote) if isinstance(quote, str) and 12 <= len(quote) <= 600 else -1
        item["source_provenance_status"] = "unmatched"
        item["interpretation_status"] = "requires_review"
        if start < 0:
            reasons.append(f"Policy evidence {index + 1} does not match an exact bounded source excerpt.")
        else:
            item.update(start=start, end=start + len(quote), source_provenance_status="verified_source_only")
            verified.append(f"[policy:{start}:{start + len(quote)}]\n{quote}")
        annotated.append(item)
    result["policy_evidence"] = annotated
    result["verified_policy_context"] = "\n\n".join(verified)
    result["policy_review_reasons"] = reasons
    result["policy_evidence_version"] = POLICY_EVIDENCE_VERSION
    return result
