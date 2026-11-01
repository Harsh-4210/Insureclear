"""Validation for structured outputs exchanged between pipeline agents."""

from collections.abc import Mapping


class AgentOutputError(ValueError):
    """Raised when an agent returns a value with an invalid schema."""


def require_mapping(stage: str, value) -> dict:
    if not isinstance(value, Mapping):
        raise AgentOutputError(
            f"{stage} returned {type(value).__name__}; expected a JSON object"
        )
    return dict(value)


def require_text(stage: str, value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentOutputError(
            f"{stage} returned {type(value).__name__}; expected non-empty text"
        )
    return value


def require_list_of_mappings(stage: str, value) -> list[dict]:
    if not isinstance(value, list):
        raise AgentOutputError(
            f"{stage} returned {type(value).__name__}; expected a JSON array"
        )
    invalid = [type(item).__name__ for item in value if not isinstance(item, Mapping)]
    if invalid:
        raise AgentOutputError(
            f"{stage} contains non-object items: {', '.join(invalid)}"
        )
    return [dict(item) for item in value]


def validate_agent_output(stage: str, value):
    """Validate an agent result before it is passed to the next stage."""
    if stage.startswith("Appeal Writer"):
        return require_text(stage, value)

    result = require_mapping(stage, value)
    if stage == "IRDAI Checker":
        for field in (
            "applicable_regulations",
            "potential_insurer_violations",
            "relevant_precedents",
            "key_legal_points_for_appeal",
        ):
            if field in result:
                result[field] = require_list_of_mappings(
                    f"{stage}.{field}", result[field]
                )
        for field in ("procedural_violations", "what_documents_to_attach"):
            if field in result and not isinstance(result[field], list):
                raise AgentOutputError(f"{stage}.{field} must be a JSON array")
        if "appeal_pathway" in result and not isinstance(result["appeal_pathway"], Mapping):
            raise AgentOutputError(f"{stage}.appeal_pathway must be a JSON object")
    elif stage == "Policy Analyst":
        for field in ("relevant_waiting_periods",):
            if field in result:
                result[field] = require_list_of_mappings(
                    f"{stage}.{field}", result[field]
                )
        for field in ("relevant_exclusions", "mis_selling_indicators", "strongest_counter_arguments"):
            if field in result and not isinstance(result[field], list):
                raise AgentOutputError(f"{stage}.{field} must be a JSON array")
    elif stage == "Judge":
        for field in ("hallucination_flags", "missing_elements", "weak_arguments", "if_revise_top_changes"):
            if field in result and not isinstance(result[field], list):
                raise AgentOutputError(f"{stage}.{field} must be a JSON array")
    return result
