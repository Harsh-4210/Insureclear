from agents.appeal_writer import (
    _enforce_valid_denial_posture,
    _valid_denial_posture,
)
from agents.irdai_checker import _apply_valid_denial_guardrail


def test_valid_denial_downgrades_regulatory_assertions_and_escalation():
    result = {
        "potential_insurer_violations": [
            {"violation": "Possible breach", "strength": "strong"}
        ],
        "key_legal_points_for_appeal": [
            {"point": "Cite rule", "argument_strength": "strong"}
        ],
        "appeal_pathway": {
            "recommended_first_step": "ombudsman",
            "estimated_success_probability": "high",
        },
    }

    guarded = _apply_valid_denial_guardrail(
        result, {"rejection_appears_valid": True}
    )

    assert guarded["conflict_metadata"]["regulatory_posture"] == "review_and_explanation"
    assert guarded["potential_insurer_violations"][0]["strength"] == "weak"
    assert guarded["potential_insurer_violations"][0]["assertion_status"] == "review_only"
    assert guarded["key_legal_points_for_appeal"][0]["argument_strength"] == "weak"
    assert guarded["appeal_pathway"]["recommended_first_step"] == "internal_grievance"
    assert guarded["appeal_pathway"]["estimated_success_probability"] == "not_estimated"


def test_writer_guardrail_frames_valid_denial_as_review_request():
    posture = _valid_denial_posture({"rejection_appears_valid": True})
    letter = _enforce_valid_denial_posture(
        "Please review the claim.", {"rejection_appears_valid": True}
    )

    assert "not an aggressive appeal" in posture
    assert "review and explanation" in letter.lower()
    assert "not asserted as violations" in letter


def test_writer_guardrail_does_not_change_challengeable_denial():
    letter = "Please reconsider the denial."
    assert _enforce_valid_denial_posture(
        letter, {"rejection_appears_valid": False}
    ) == letter
