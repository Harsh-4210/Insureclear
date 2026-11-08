import pytest

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


@pytest.mark.parametrize("letter,source,category", [
    ("Policy Number: POL-123.", "Policy Number: POL-1234.", "unsupported_id"),
    ("Policy Number: POL-123.", "Policy Number: POL-123-9.", "unsupported_id"),
    ("Policy Number: POL-123.", "Policy Number: POL-123/9.", "unsupported_id"),
    ("The amount is INR 1000.", "The amount is INR 10000.", "unsupported_amount"),
    ("Please review Clause 4.2.", "Please review Clause 4.20.", "unsupported_clause"),
    ("Please review Clause 4.2.", "Please review Clause 4.2.1.", "unsupported_clause"),
])
def test_rejects_concrete_claims_that_are_only_prefix_matches(letter, source, category):
    result = validate_appeal_letter(letter, {"denial": source})
    assert not result.valid
    assert category in {issue.category for issue in result.errors}


def test_case_amounts_and_policy_clauses_are_not_grounded_by_regulatory_numbers():
    from tools.regulatory_registry import load_registry
    registry = load_registry()
    clause = next(c for c in registry.clauses if c["id"] == "moratorium")
    result = validate_appeal_letter("I claimed INR 60 under Clause 13.", {"denial": "The hospitalisation claim was denied.", "policy": "Cover depends on the actual policy terms.", "regulatory": clause["text"]})
    assert not result.valid
    assert {"unsupported_amount", "unsupported_clause"} <= {i.category for i in result.errors}


@pytest.mark.parametrize("letter,source,want", [
    ("I claimed INR 2.", "The claim amount is Rs 2 lakh.", False),
    ("I claimed INR 200000.", "The claim amount is Rs 2 lakh.", True),
])
def test_currency_multipliers_do_not_change_case_amounts(letter, source, want):
    assert validate_appeal_letter(letter, {"denial": source}).valid is want


def test_patient_identifier_cannot_be_sourced_from_a_regulatory_circular():
    reference = "IRDAI/HLT/CIR/PRO/84/5/2024"
    result = validate_appeal_letter("Policy Number: " + reference + ".", {"denial": "A claim was denied.", "regulatory": "Official circular " + reference})
    assert not result.valid


def test_dates_in_circular_ids_are_not_patient_dates():
    ref = "IRDAI/HLT/CIR/PRO/84/5/2024"
    result = validate_appeal_letter("Please review circular " + ref + ".", {"denial": "Claim denied.", "regulatory": "Official circular " + ref})
    assert result.valid


def test_equivalent_month_names_numeric_dates_and_unicode_amount_groups():
    result = validate_appeal_letter("The denial dated 20\u202fNov\u202f2025 concerns INR\u202f210,\u202f000. Circular compliance date: 30 September 2024.", {"denial": "Denial dated 20 November 2025 concerns Rs 2,10,000.", "regulatory": "Circular compliance date: 30.9.2024."})
    assert result.valid, result.errors


def test_explicit_regulatory_clause_binding_covers_later_references_without_crossing_policy_scope():
    from tools.regulatory_registry import load_registry
    selected = load_registry().select("other", {}, 8000)
    letter = "IRDAI Master Circular Clause 17(a) governs review. The procedural requirement of Clause 17 is relevant. Clause 19 of the same circular concerns grievances. Under policy Clause 13 I seek cover."
    result = validate_appeal_letter(letter, {"denial": "A claim was denied.", "policy": "Coverage depends on policy terms.", "regulatory": selected.text})
    values = {i.value for i in result.errors if i.category == "unsupported_clause"}
    assert "Clause 17(a)" not in values and "Clause 17" not in values and "Clause 19" not in values
    assert "Clause 13" in values


def test_committee_acronyms_are_not_fabricated_reference_ids():
    result = validate_appeal_letter("Please confirm CRC/PMC approval.", {"denial": "A claim was denied.", "regulatory": "Claims Review Committee (CRC) and Product Management Committee (PMC)."})
    assert result.valid


def test_response_deadline_is_not_supported_by_unrelated_waiting_period():
    result = validate_appeal_letter("Please settle this claim within 15 working days.", {"policy": "A waiting period of 15 days applies to new policies."})
    assert not result.valid
    assert any(issue.category == "unsupported_deadline" for issue in result.issues)


def test_unicode_and_spelled_deadlines_require_source_support():
    for letter in ["Please reply within 15\u202fcalendar days.", "We will escalate after fifteen days.", "Please provide a 15-day response."]:
        assert any(issue.category == "unsupported_deadline" for issue in validate_appeal_letter(letter, {"policy": "Hospital treatment is covered."}).issues)
    assert validate_appeal_letter("Please reply within 15 calendar days.", {"regulatory": "The insurer shall reply within 15 calendar days."}).valid


def test_unsupported_clause_sanitizing_does_not_invent_policy_authority():
    letter = "Clause 99 obliges settlement of every claim. Please review the supplied documents."
    result = validate_appeal_letter(letter, {"policy": "Treatment benefits apply subject to policy terms."})
    cleaned = sanitize_unsupported_references(letter, result)
    assert "applicable policy provision" not in cleaned
    assert "obliges settlement" not in cleaned
    assert "Please review" in cleaned

def test_compared_room_rates_are_not_a_case_law_citation():
    letter = "The charge was Rs. 8,000/day vs.\neligible Rs. 5,000/day."
    result = validate_appeal_letter(letter, {"policy": "Actual charge Rs. 8,000/day. Eligible Rs. 5,000/day."})
    assert result.valid, result.as_dict()


def test_sanitization_removes_case_law_split_across_lines():
    letter = "Please review the policy. I rely on Smith v.\nInsurer. Thank you."
    evidence = {"policy": "Review the relevant policy terms."}
    result = validate_appeal_letter(letter, evidence)
    assert any(issue.category == "invented_case_law" for issue in result.issues)
    sanitized = sanitize_unsupported_references(letter, result)
    assert validate_appeal_letter(sanitized, evidence).valid
    assert "Smith" not in sanitized and "Insurer" not in sanitized
    assert "Please review the policy." in sanitized

@pytest.mark.parametrize("letter", [
    "Operations and Allied Matters of Insurers 2024.",
    """Refrain from further undue reminders.

5. Coverage for pneumonia.""",
    "Protection of policyholders 2024.",
])
def test_currency_detection_does_not_start_inside_an_ordinary_word(letter):
    result = validate_appeal_letter(letter, {"policy": "General inpatient coverage."})
    assert not any(issue.category == "unsupported_amount" for issue in result.issues)


def test_currency_detection_still_flags_an_actual_unsupported_amount():
    result = validate_appeal_letter("Please refund Rs. 5,000.", {"policy": "General inpatient coverage."})
    assert any(issue.category == "unsupported_amount" for issue in result.issues)
