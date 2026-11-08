from agents import appeal_writer, irdai_checker, judge
from tools import io_utils
from tools.regulatory_registry import load_registry
from tools.document_context import estimate_tokens


def evidence_result():
    selected = load_registry().select("pre_existing_condition", {"denial_date": "2025-01-01"})
    return {"verified_source_context": selected.text, "regulatory_evidence": selected.as_dict(), "appeal_pathway": {}, "key_legal_points_for_appeal": [], "potential_insurer_violations": []}


def test_checker_uses_pinned_excerpts_and_rejects_model_verification(monkeypatch, tmp_path):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    prompts = []
    monkeypatch.setattr(irdai_checker, "call_llm_json", lambda prompt, **kwargs: prompts.append(prompt) or {"applicable_regulations": [{"regulation": "invented", "evidence_id": "fake", "verification_status": "verified"}], "appeal_pathway": {}})
    result = irdai_checker.run({"denial_reason_category": "pre_existing_condition"}, {}, "source_checker")
    assert "PINNED OFFICIAL SOURCE EXCERPTS" in prompts[0]
    assert "IRDA/HLT/REG/CIR/194/08/2020" not in prompts[0]
    assert "541" not in prompts[0]
    assert result["verified_source_context"]
    assert result["applicable_regulations"][0]["source_provenance_status"] == "unmatched"
    assert result["applicable_regulations"][0]["verification_status"] == "manual_verification_required"


def test_writer_and_judge_receive_identical_pinned_source_context(monkeypatch, tmp_path):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    evidence = evidence_result()
    writer_prompts, judge_prompts = [], []
    monkeypatch.setattr(appeal_writer, "call_llm", lambda prompt, **kwargs: writer_prompts.append(prompt) or "Please review the claim.")
    monkeypatch.setattr(judge, "call_llm_json", lambda prompt, **kwargs: judge_prompts.append(prompt) or {"overall_score": 0.9, "recommendation": "APPROVE"})
    letter = appeal_writer.run({}, {}, evidence, "shared_evidence")
    judge.run(letter, {}, evidence, "shared_evidence")
    assert evidence["verified_source_context"] in writer_prompts[0]
    assert evidence["verified_source_context"] in judge_prompts[0]
    assert "if not resolved in 15 days" not in writer_prompts[0]


def test_writer_rejects_impossible_context_instead_of_sending_unbounded_prompt(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setenv("INSURECLEAR_PROMPT_BUDGET", "3000")
    monkeypatch.setattr(appeal_writer, "call_llm", lambda *args, **kwargs: "unexpected")
    with pytest.raises(ValueError, match="budget"):
        appeal_writer.run({}, {}, evidence_result(), "too_large")


def test_revision_does_not_promote_generated_legal_leads_to_verified_facts(monkeypatch, tmp_path):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    prompts = []
    monkeypatch.setattr(appeal_writer, "call_llm", lambda prompt, **kwargs: prompts.append(prompt) or "Please review this claim.")
    regulatory = evidence_result()
    regulatory["key_legal_points_for_appeal"] = [{"point": "Invented binding ruling UNTRUSTED-LEGAL-LEAD"}]
    appeal_writer.revise("Initial appeal", {}, {"policyholder_name": "Known Holder"}, regulatory, "revise_evidence")
    assert "UNTRUSTED-LEGAL-LEAD" not in prompts[0]
    assert "Known Holder" in prompts[0]


def test_provenance_metadata_does_not_bloat_judge_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    regulatory = evidence_result()
    regulatory["key_legal_points_for_appeal"] = [{"point": "review", "quoted_text": "x" * 12000, "official_source_url": "https://irdai.gov.in/" + "a" * 2000}]
    prompts = []
    monkeypatch.setattr(judge, "call_llm_json", lambda prompt, **kwargs: prompts.append(prompt) or {"overall_score": 0.9, "recommendation": "APPROVE"})
    result = judge.run("Please review the supplied case facts.", {}, regulatory, "compact_judge")
    assert result["overall_score"] == 0.9
    assert "x" * 1000 not in prompts[0]


def test_direct_checker_cache_binds_facts_selected_evidence_and_budget(monkeypatch, tmp_path):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    calls = []
    def generate(prompt, **kwargs):
        calls.append(prompt)
        return {"appeal_pathway": {"reasoning": f"response-{len(calls)}"}}
    monkeypatch.setattr(irdai_checker, "call_llm_json", generate)
    facts = {"denial_reason_category": "pre_existing_condition", "denial_date": "2025-01-01"}
    first = irdai_checker.run(facts, {}, "direct_checker_cache")
    same = irdai_checker.run(facts, {}, "direct_checker_cache")
    assert same == first and len(calls) == 1
    monkeypatch.setenv("INSURECLEAR_REGULATORY_BUDGET", "2500")
    changed = irdai_checker.run({**facts, "denial_reason_category": "documentation_missing"}, {}, "direct_checker_cache")
    assert len(calls) == 2
    assert changed["appeal_pathway"]["reasoning"] == "response-2"
    assert changed["regulatory_evidence"]["context_units"] <= 2500


def test_direct_writer_cache_binds_case_facts_and_regulatory_evidence(monkeypatch, tmp_path):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    drafts = iter(["First claimant draft", "Second claimant draft"])
    monkeypatch.setattr(appeal_writer, "call_llm", lambda *args, **kwargs: next(drafts))
    regulatory = evidence_result()
    first = appeal_writer.run({"policyholder_name": "First Holder"}, {}, regulatory, "direct_writer_cache")
    assert appeal_writer.run({"policyholder_name": "First Holder"}, {}, regulatory, "direct_writer_cache") == first
    changed = appeal_writer.run({"policyholder_name": "Second Holder"}, {}, regulatory, "direct_writer_cache")
    assert changed == "Second claimant draft"


def test_writer_judge_and_revision_share_verified_policy_wording(monkeypatch, tmp_path):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    quote = "Section 1.2: Day-care chemotherapy is covered without a 24-hour admission."
    evidence = evidence_result()
    evidence["verified_policy_context"] = quote
    prompts = []
    monkeypatch.setattr(appeal_writer, "call_llm", lambda prompt, **kwargs: prompts.append(prompt) or "Please review the claim.")
    monkeypatch.setattr(judge, "call_llm_json", lambda prompt, **kwargs: prompts.append(prompt) or {"overall_score": 0.9, "recommendation": "APPROVE"})
    appeal_writer.run({}, {"verified_policy_context": quote}, evidence, "policy_writer")
    appeal_writer.revise("Original letter", {}, {}, evidence, "policy_revision")
    judge.run("Final letter", {}, evidence, "policy_judge")
    assert len(prompts) == 3 and all(quote in prompt for prompt in prompts)
    assert all("already supplied" in prompt for prompt in prompts)


import pytest

@pytest.mark.parametrize("revision", [False, True])
def test_writer_removes_only_known_internal_policy_markers(monkeypatch, tmp_path, revision):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    context = "[policy:12:72]\nSection 1.2 covers day-care treatment without a 24-hour stay."
    regulatory = evidence_result(); regulatory["verified_policy_context"] = context
    monkeypatch.setattr(appeal_writer, "call_llm", lambda *args, **kwargs: "Section 1.2 covers treatment. [policy:12:72] Unknown [policy:99:100].")
    if revision:
        letter = appeal_writer.revise("Initial letter", {}, {}, regulatory, "strip_revision")
    else:
        letter = appeal_writer.run({}, {"verified_policy_context": context}, regulatory, "strip_initial")
    assert "[policy:12:72]" not in letter
    assert "[policy:99:100]" in letter
    assert "Section 1.2" in letter

@pytest.mark.parametrize("stage", ["judge", "irdai_checker"])
def test_cached_review_requires_current_system_instructions(monkeypatch, tmp_path, stage):
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    module = judge if stage == "judge" else irdai_checker
    calls = []

    def generate(_prompt, **kwargs):
        calls.append(kwargs["system_prompt"])
        if stage == "judge":
            return {"overall_score": .9, "recommendation": "APPROVE"}
        return {"appeal_pathway": {"reasoning": "Synthetic result"}}

    monkeypatch.setattr(module, "call_llm_json", generate)
    args = ("Review the supplied evidence.", {}, {}, "review_cache") if stage == "judge" else ({}, {}, "review_cache")
    module.run(*args)
    module.run(*args)
    assert len(calls) == 1
    monkeypatch.setattr(module, "SYSTEM_PROMPT", module.SYSTEM_PROMPT + "\nUpdated review instruction.")
    module.run(*args)
    assert len(calls) == 2
