import pytest

from tools.agent_validation import AgentOutputError, validate_agent_output


def test_irdai_output_rejects_list_instead_of_object():
    with pytest.raises(AgentOutputError, match="IRDAI Checker returned list"):
        validate_agent_output("IRDAI Checker", [])


def test_irdai_output_rejects_non_object_nested_items():
    output = {
        "applicable_regulations": ["not an object"],
        "potential_insurer_violations": [],
        "relevant_precedents": [],
        "key_legal_points_for_appeal": [],
        "procedural_violations": [],
        "what_documents_to_attach": [],
        "appeal_pathway": {},
    }
    with pytest.raises(AgentOutputError, match="non-object items"):
        validate_agent_output("IRDAI Checker", output)


def test_appeal_writer_requires_non_empty_text():
    with pytest.raises(AgentOutputError, match="expected non-empty text"):
        validate_agent_output("Appeal Writer", "")
