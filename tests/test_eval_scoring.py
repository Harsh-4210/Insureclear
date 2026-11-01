from eval.cases import CASES, build_documents
from eval.score import find_unsupported_ids, score_case, summarise
from eval.run_eval import check_regression_gates


CASE = next(c for c in CASES if c["id"] == "c01_moratorium")


def make_report(letter: str, valid: bool, category: str = "non_disclosure") -> dict:
    return {
        "auditor": {
            "insurer_name": "Suraksha Health Insurance Co. Ltd.",
            "policy_number": "SHI4410028731",
            "claim_number": "CLM-SHI-2025-55102",
            "policyholder_name": "Anil Deshmukh",
            "claim_amount": "Rs 2,10,000",
            "denial_reason_category": category,
        },
        "policy_analyst": {"rejection_appears_valid": valid},
        "appeal_letter": letter,
        "pipeline_stats": {"final_score": 0.8, "revision_count": 1, "total_time_seconds": 30},
    }


def test_documents_fit_auditor_window():
    for case in CASES:
        denial, policy = build_documents(case)
        assert len(policy) <= 4000, case["id"]
        assert case["policy_number"] in denial and case["policy_number"] in policy


def test_perfect_report_scores_full_marks():
    letter = (
        "To Suraksha Health. Policy SHI4410028731, claim CLM-SHI-2025-55102, Mr. Deshmukh. "
        "The policy has completed 60 continuous months, so the moratorium applies."
    )
    sources = list(build_documents(CASE))
    result = score_case(make_report(letter, valid=False), CASE, sources)

    assert result["extraction"]["score"] == 1.0
    assert result["verdict"]["correct"] is True
    assert result["letter_facts"]["score"] == 1.0
    assert result["key_argument"]["found"] is True
    assert result["unsupported_ids"] == []


def test_wrong_verdict_missing_argument_and_invented_id_are_caught():
    letter = "Dear Sir, regarding policy SHI4410028731 and claim CLM-SHI-2025-99999, please reconsider."
    sources = list(build_documents(CASE))
    result = score_case(make_report(letter, valid=True, category="other"), CASE, sources)

    assert result["verdict"]["correct"] is False
    assert result["extraction"]["checks"]["denial_category"] is False
    assert result["key_argument"]["found"] is False
    assert result["unsupported_ids"] == ["CLM-SHI-2025-99999"]
    assert result["letter_facts"]["checks"]["claim_number"] is False


def test_find_unsupported_ids_ignores_ids_in_sources():
    assert find_unsupported_ids("See ABC-123 and 12345678.", ["ref abc-123 and 12345678"]) == []


def test_summary_counts_only_cases_with_a_key_argument():
    sources = list(build_documents(CASE))
    good = score_case(make_report("60 months moratorium", valid=False), CASE, sources)
    valid_case = next(c for c in CASES if c["id"] == "c06_hernia_valid")
    no_arg = score_case(make_report("letter", valid=True), valid_case, list(build_documents(valid_case)))

    summary = summarise([good, no_arg])
    assert summary["key_argument_cases"] == 1
    assert summary["key_argument_found"] == 1
    assert summary["verdict_correct"] == 2
    assert summary["verdict_accuracy"] == 1.0
    assert summary["unsupported_claim_rate"] == 0.0


def test_regression_gates_report_accuracy_and_unsupported_claim_failures():
    summary = {"verdict_accuracy": 0.5, "unsupported_claim_rate": 0.25, "failed_cases": 0}
    failures = check_regression_gates(summary, 0.8, 0.1)
    assert len(failures) == 2


def test_regression_gates_include_pipeline_failures():
    failures = check_regression_gates(
        {"verdict_accuracy": 1.0, "unsupported_claim_rate": 0.0, "failed_cases": 1}
    )
    assert failures == ["1 case(s) failed to run"]
