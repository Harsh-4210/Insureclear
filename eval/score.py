"""
Evaluation Scoring
Deterministic checks of one pipeline report against a case's answer key.
No LLM is used to grade: every check is a string or value comparison,
so the same report always gets the same score.
"""

import re


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _surname(holder: str) -> str:
    return holder.split()[-1].lower()


def score_extraction(auditor: dict, case: dict) -> dict:
    """Did the Auditor pull the six key facts out correctly?"""
    insurer_word = case["insurer"].split()[0].lower()
    checks = {
        "insurer": insurer_word in str(auditor.get("insurer_name") or "").lower(),
        "policy_number": _norm(case["policy_number"]) in _norm(auditor.get("policy_number")),
        "claim_number": _norm(case["claim_number"]) in _norm(auditor.get("claim_number")),
        "policyholder": _surname(case["holder"]) in str(auditor.get("policyholder_name") or "").lower(),
        # "2,10,000" and "Rs 2,10,000.00" both count as correct
        "claim_amount": _digits(auditor.get("claim_amount")) in (
            _digits(case["claim_amount"]), _digits(case["claim_amount"]) + "00"
        ),
        "denial_category": auditor.get("denial_reason_category") in case["answer"]["denial_category"],
    }
    return {"checks": checks, "score": sum(checks.values()) / len(checks)}


def score_verdict(policy_analyst: dict, case: dict) -> dict:
    """Did the Policy Analyst correctly say whether the rejection is valid?"""
    predicted = policy_analyst.get("rejection_appears_valid")
    expected = case["answer"]["rejection_valid"]
    return {"predicted": predicted, "expected": expected, "correct": predicted is expected}


def score_letter_facts(letter: str, case: dict) -> dict:
    """Does the letter carry the right policy number, claim number, name and insurer?"""
    flat = _norm(letter)
    checks = {
        "policy_number": _norm(case["policy_number"]) in flat,
        "claim_number": _norm(case["claim_number"]) in flat,
        "policyholder": _surname(case["holder"]) in letter.lower(),
        "insurer": case["insurer"].split()[0].lower() in letter.lower(),
    }
    return {"checks": checks, "score": sum(checks.values()) / len(checks)}


def score_key_argument(letter: str, case: dict) -> dict:
    """Does the letter make the one argument that wins this case?"""
    terms = case["answer"]["key_terms"]
    if not terms:
        return {"applicable": False, "found": None, "matched": []}
    lower = letter.lower()
    matched = [t for t in terms if t.lower() in lower]
    return {"applicable": True, "found": bool(matched), "matched": matched}


_ID_PATTERN = re.compile(r"\b[A-Z]{2,}[-/][A-Z0-9/-]*\d[A-Z0-9/-]*\b|\b\d{7,}\b")


def find_unsupported_ids(letter: str, sources: list[str]) -> list[str]:
    """
    Reference numbers in the letter (policy/claim style IDs, 7+ digit numbers)
    that do not appear in any source text. These are likely invented.
    """
    source_flat = _norm(" ".join(sources))
    unsupported = []
    for match in _ID_PATTERN.findall(letter):
        if _norm(match) and _norm(match) not in source_flat:
            unsupported.append(match)
    return sorted(set(unsupported))


def score_case(report: dict, case: dict, sources: list[str]) -> dict:
    """All checks for one case."""
    letter = report.get("appeal_letter", "") or ""
    stats = report.get("pipeline_stats", {})
    unsupported_ids = find_unsupported_ids(letter, sources)
    evidence_errors = report.get("evidence_validation", {}).get("errors", [])
    unsupported_claims = evidence_errors or [{"category": "unsupported_id", "value": value} for value in unsupported_ids]
    return {
        "id": case["id"],
        "extraction": score_extraction(report.get("auditor", {}), case),
        "verdict": score_verdict(report.get("policy_analyst", {}), case),
        "letter_facts": score_letter_facts(letter, case),
        "key_argument": score_key_argument(letter, case),
        "unsupported_ids": unsupported_ids,
        "unsupported_claims": unsupported_claims,
        "judge_final_score": stats.get("final_score"),
        "revisions": stats.get("revision_count"),
        "seconds": stats.get("total_time_seconds"),
        "letter_words": len(letter.split()),
    }


def summarise(results: list[dict]) -> dict:
    """Totals across all scored cases."""
    n = len(results)
    if not n:
        return {"cases": 0}
    argued = [r for r in results if r["key_argument"]["applicable"]]
    judge_scores = [r["judge_final_score"] for r in results if isinstance(r["judge_final_score"], (int, float))]
    unsupported_cases = sum(1 for r in results if r.get("unsupported_claims") or r.get("unsupported_ids", []))
    return {
        "cases": n,
        "extraction_accuracy": round(sum(r["extraction"]["score"] for r in results) / n, 3),
        "verdict_correct": sum(r["verdict"]["correct"] for r in results),
        "verdict_accuracy": round(sum(r["verdict"]["correct"] for r in results) / n, 3),
        "letter_fact_accuracy": round(sum(r["letter_facts"]["score"] for r in results) / n, 3),
        "key_argument_found": sum(r["key_argument"]["found"] for r in argued),
        "key_argument_cases": len(argued),
        "letters_with_unsupported_ids": unsupported_cases,
        "unsupported_claim_rate": round(unsupported_cases / n, 3),
        "mean_judge_score": round(sum(judge_scores) / len(judge_scores), 3) if judge_scores else None,
        "mean_revisions": round(sum(r["revisions"] or 0 for r in results) / n, 2),
        "mean_seconds": round(sum(r["seconds"] or 0 for r in results) / n, 1),
    }
