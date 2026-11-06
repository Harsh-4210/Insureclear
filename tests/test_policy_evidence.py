from tools.policy_evidence import annotate_policy_evidence

POLICY = "Section 3.1: A 30-day waiting period applies except for accidents. Section 1.2: Day-care chemotherapy is covered without a 24-hour admission."


def test_quote_offsets_match_policy():
    quote = "Day-care chemotherapy is covered without a 24-hour admission."
    result = annotate_policy_evidence({"policy_evidence": [{"quote": quote, "clause": "1.2", "argument": "The admission restriction does not apply.", "verified": False, "start": 0}]}, POLICY)
    item = result["policy_evidence"][0]
    assert POLICY[item["start"]:item["end"]] == item["quote"] == quote
    assert item["source_provenance_status"] == "verified_source_only"
    assert quote in result["verified_policy_context"]
    assert not result["policy_review_reasons"]


def test_fabricated_quote_requires_review():
    result = annotate_policy_evidence({"policy_evidence": [{"quote": "Every claim must be paid in 15 days.", "verified": True}]}, POLICY)
    assert result["policy_review_reasons"]
    assert not result["verified_policy_context"]
    assert result["policy_evidence"][0]["source_provenance_status"] == "unmatched"


def test_accident_exception_is_not_inverted_by_evidence():
    quote = "A 30-day waiting period applies except for accidents."
    result = annotate_policy_evidence({"policy_evidence": [{"quote": quote, "argument": "The waiting period applies only to accidents."}]}, POLICY)
    assert quote in result["verified_policy_context"]
    assert "applies only" not in result["verified_policy_context"]
    assert result["policy_evidence"][0]["interpretation_status"] == "requires_review"


def test_missing_and_nonstring_quotes_fail_closed():
    for result in [{}, {"policy_evidence": [{"quote": None, "verified": True}]}, {"policy_evidence": "invented"}]:
        annotated = annotate_policy_evidence(result, POLICY)
        assert annotated["policy_review_reasons"]
        assert not annotated["verified_policy_context"]
