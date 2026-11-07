from agents import auditor, policy_analyst
from tools import io_utils


def test_auditor_receives_complete_denial_and_policy(monkeypatch, tmp_path):
    monkeypatch.setenv("INSURECLEAR_PROMPT_BUDGET", "32000")
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    prompts = []
    monkeypatch.setattr(auditor, "call_llm_json", lambda prompt, **kwargs: prompts.append(prompt) or {})
    denial = "Background. " * 500 + "Claim denied under Clause 8.7."
    policy = "Policy text. " * 500 + "Clause 8.7 excludes the claimed procedure."
    auditor.run(denial, policy, "long_audit")
    assert denial in prompts[0]
    assert policy in prompts[0]


def test_policy_analyst_receives_clauses_after_character_5000(monkeypatch, tmp_path):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    prompts = []
    monkeypatch.setattr(policy_analyst, "call_llm_json", lambda prompt, **kwargs: prompts.append(prompt) or {})
    policy = "Policy text. " * 500 + "Clause 8.7 excludes the claimed procedure."
    policy_analyst.run(policy, {}, "long_policy")
    assert policy in prompts[0]


def test_direct_auditor_call_obeys_prompt_budget_and_reports_omissions(monkeypatch, tmp_path):
    from tools.document_context import estimate_tokens
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setenv("INSURECLEAR_PROMPT_BUDGET", "10000")
    prompts = []
    monkeypatch.setattr(auditor, "call_llm_json", lambda prompt, **kwargs: prompts.append(prompt) or {"insurer_name": "Test"})
    policy = "Generic terms and coverage. " * 2000 + "Clause 8.7: This procedure is not excluded."
    result = auditor.run("Claim denied under Clause 8.7.", policy, "bounded_audit")
    assert estimate_tokens(prompts[0]) + estimate_tokens(auditor.SYSTEM_PROMPT) + 4096 + 512 <= 10000
    assert "This procedure is not excluded." in prompts[0]
    assert result["input_coverage"]["requires_manual_review"]

def test_policy_analyst_receives_contradictory_original_denial_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    prompts = []
    monkeypatch.setattr(policy_analyst, "call_llm_json", lambda prompt, **kwargs: prompts.append((prompt, kwargs)) or {})
    denial = "We closed the claim for a missing summary. We previously acknowledged receipt of that summary."
    policy = "Clause 4.2 requires the summary. Clause 5.1 has a separate accident exception."
    result = policy_analyst.run(policy, {"denial_reason_verbatim": "We closed the claim for a missing summary."},
                                "contradictory_denial", denial)
    prompt, options = prompts[0]
    assert denial in prompt and policy in prompt
    assert "explicitly cross-references" in options["system_prompt"]
    assert result["input_coverage"]["sources"]["denial"]["full_document_included"]

def test_policy_context_reserves_room_for_contract_when_denial_is_long(monkeypatch, tmp_path):
    monkeypatch.setenv("INSURECLEAR_PROMPT_BUDGET", "10000")
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(policy_analyst, "call_llm_json", lambda *args, **kwargs: {})
    denial = "waiting accident period refused matching named facts. " * 1000
    policy = "Contract description. " * 600
    result = policy_analyst.run(policy, {"denial_reason_verbatim": "waiting accident period refused matching named facts"},
                                "adversarial_budget", denial)
    coverage = result["input_coverage"]["sources"]
    assert len(coverage["policy"]["included_chunk_ids"]) >= 2
    assert coverage["denial"]["omitted_chunk_ids"]


def test_literal_document_slot_inside_evidence_is_never_expanded(monkeypatch, tmp_path):
    from tools.document_context import source_marker
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    prompts = []
    monkeypatch.setattr(policy_analyst, "call_llm_json", lambda prompt, **kwargs: prompts.append(prompt) or {})
    marker = source_marker("denial")
    policy_analyst.run(f"Printed literal text {marker}.", {}, "literal_marker", "Actual denial text.")
    assert f"Printed literal text {marker}." in prompts[0]
    assert prompts[0].count("Actual denial text.") == 1
