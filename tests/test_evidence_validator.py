from tools.evidence_validator import sanitize_unsupported_references, validate_appeal_letter


def test_accepts_claims_present_in_sources():
    result = validate_appeal_letter(
        "Policy Number: POL-123. Claim amount: INR 10,000. "
        "The denial dated 01/02/2025 cites Clause 4.2.",
        {
            "denial": "Policy Number: POL-123. Claim amount: INR 10,000. "
            "Denial dated 01/02/2025 under Clause 4.2.",
        },
    )
    assert result.valid
    assert result.errors == []


def test_reports_unsupported_concrete_claims():
    result = validate_appeal_letter(
        "Policy Number: POL-999. Claim amount: INR 99,000. "
        "The denial dated 12/12/2030 violates Clause 9.9. "
        "This was medically necessary. Reliance is placed on Smith v. Insurer.",
        {"denial": "Policy Number: POL-123. Claim amount: INR 10,000."},
    )
    categories = {issue.category for issue in result.errors}
    assert not result.valid
    assert {
        "unsupported_id",
        "unsupported_amount",
        "unsupported_date",
        "unsupported_clause",
        "invented_case_law",
        "unsupported_medical_claim",
    } <= categories


def test_empty_sources_are_an_explicit_validation_error():
    result = validate_appeal_letter("A draft appeal", {})
    assert not result.valid
    assert result.errors[0].category == "missing_sources"


def test_normalizes_unicode_spaces_and_currency_labels():
    result = validate_appeal_letter(
        "The denial dated 20\u202fNov\u202f2025 concerns INR\u202f70,000.",
        {"denial": "The denial dated 20 Nov 2025 concerns Rs 70,000."},
    )
    assert result.valid


def test_rejects_altered_bare_reference_ids():
    result = validate_appeal_letter(
        "Please review claim NGU/HC/2025/40912 and Circular IRDA/IRDAI/2022/.",
        {"denial": "Claim NGI/HC/2025/40912."},
    )
    values = {issue.value for issue in result.errors if issue.category == "unsupported_id"}
    assert "NGU/HC/2025/40912" in values
    assert "IRDA/IRDAI/2022/" in values


def test_accepts_section_prefix_when_number_is_in_policy():
    result = validate_appeal_letter(
        "The policy's Section 1.2 covers the procedure.",
        {"policy": "1.2 Day Care Procedures are covered."},
    )
    assert result.valid


def test_matches_labeled_identifier_against_source_identifier():
    result = validate_appeal_letter(
        "Claim NGI/HC/2025/42277 and Policy NGI7720461893.",
        {"denial": "Claim No: NGI/HC/2025/42277\nPolicy No: NGI7720461893"},
    )
    assert result.valid


def test_sanitizes_unsupported_references():
    result = validate_appeal_letter(
        "Use Clause 3.6 and Circular IRDAI/HLT/CIR/541/2022.",
        {"policy": "Clause 3.1 applies."},
    )
    sanitized = sanitize_unsupported_references("Use Clause 3.6 and Circular IRDAI/HLT/CIR/541/2022.", result)
    assert "Clause 3.6" not in sanitized
    assert "IRDAI/HLT/CIR/541/2022" not in sanitized


def test_sanitizes_unsupported_medical_claims():
    letter = "The treatment was medically necessary and clinically indicated."
    result = validate_appeal_letter(letter, {"denial": "Treatment was denied."})
    sanitized = sanitize_unsupported_references(letter, result)
    assert validate_appeal_letter(sanitized, {"denial": "Treatment was denied."}).valid
