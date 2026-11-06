import json

import pytest

from pathlib import Path

from agents import appeal_writer, auditor, irdai_checker, judge, policy_analyst
from orchestrator import main
from tools import io_utils


DENIAL_TEXT = "The insurer rejected the hospitalisation claim because the procedure was considered excluded."
POLICY_TEXT = "The policy covers eligible hospitalisation subject to documented exclusions and limits."


def configure_fake_agents(monkeypatch, judge_results):
    monkeypatch.setattr(
        auditor,
        "run",
        lambda denial, policy, case_id: {
            "insurer_name": "Test Insurer",
            "treatment_or_procedure": "Test procedure",
            "denial_reason_category": "exclusion",
            "claim_amount": "100000",
        },
    )
    monkeypatch.setattr(
        policy_analyst,
        "run",
        lambda policy, audit, case_id: {
            "rejection_appears_valid": False,
            "rejection_validity_explanation": "The clause requires review.",
            "strongest_counter_arguments": ["The exclusion is unclear."],
            "policy_evidence": [{"quote": POLICY_TEXT}],
        },
    )
    monkeypatch.setattr(
        irdai_checker,
        "run",
        lambda audit, policy, case_id: {
            "appeal_pathway": {
                "recommended_first_step": "Internal grievance",
                "estimated_success_probability": "medium",
            },
            "potential_insurer_violations": [],
        },
    )
    monkeypatch.setattr(appeal_writer, "run", lambda *args: "Initial appeal letter")
    monkeypatch.setattr(appeal_writer, "revise", lambda *args, **kwargs: "Revised appeal letter")
    monkeypatch.setattr(judge, "run", lambda *args: judge_results.pop(0))
    monkeypatch.setattr(main, "get_stats", lambda: {"total_calls": 5, "total_time_seconds": 0.1, "avg_time_per_call": 0.02})


def run_fake_pipeline(monkeypatch, tmp_path, judge_results):
    configure_fake_agents(monkeypatch, judge_results)
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    (tmp_path / "sessions").mkdir(exist_ok=True)
    return main.run_pipeline(
        denial_pdf="denial.txt",
        policy_pdf="policy.txt",
        case_id="test_case",
        denial_text=DENIAL_TEXT,
        policy_text=POLICY_TEXT,
    )


def test_pipeline_execution_and_output_artifacts(monkeypatch, tmp_path):
    result = run_fake_pipeline(
        monkeypatch,
        tmp_path,
        [{"overall_score": 0.9, "recommendation": "APPROVE"}],
    )

    output_dir = Path(result["artifacts"]["output_dir"])
    assert result["source_evidence"]["policy"] == POLICY_TEXT
    assert result["source_evidence"]["denial"] == DENIAL_TEXT
    assert output_dir.is_dir()
    assert Path(result["artifacts"]["appeal_letter_path"]).read_text(encoding="utf-8") == "Initial appeal letter"
    assert Path(result["artifacts"]["full_report_path"]).is_file()
    assert result["pipeline_stats"]["final_recommendation"] == "APPROVE"


def test_judge_threshold_forces_revision(monkeypatch, tmp_path):
    result = run_fake_pipeline(
        monkeypatch,
        tmp_path,
        [{"overall_score": 0.60, "recommendation": "APPROVE", "if_revise_top_changes": ["Add evidence"]},
         {"overall_score": 0.85, "recommendation": "APPROVE"}],
    )

    assert result["pipeline_stats"]["revision_count"] == 1
    assert result["pipeline_stats"]["final_recommendation"] == "APPROVE"
    assert result["pipeline_stats"]["final_score"] == 0.85


def test_revision_loop_retries_until_judge_approves(monkeypatch, tmp_path):
    result = run_fake_pipeline(
        monkeypatch,
        tmp_path,
        [{"overall_score": 0.50, "recommendation": "REVISE", "if_revise_top_changes": ["Fix issue"]},
         {"overall_score": 0.70, "recommendation": "REVISE", "if_revise_top_changes": ["Fix another issue"]},
         {"overall_score": 0.90, "recommendation": "APPROVE"}],
    )

    assert result["pipeline_stats"]["revision_count"] == 2
    assert Path(result["artifacts"]["appeal_letter_path"]).read_text(encoding="utf-8") == "Revised appeal letter"


def test_pipeline_artifact_paths_match_saved_files_across_clock_boundary(monkeypatch, tmp_path):
    real_create = io_utils.create_output_dir
    allocation = 0

    def advancing_create(case_id):
        nonlocal allocation
        allocation += 1
        return real_create(f"{case_id}_{allocation}")

    monkeypatch.setattr(io_utils, "create_output_dir", advancing_create)
    # The orchestrator currently imports its own alias of the directory factory.
    if hasattr(main, "create_output_dir"):
        monkeypatch.setattr(main, "create_output_dir", advancing_create)
    result = run_fake_pipeline(monkeypatch, tmp_path, [
        {"overall_score": 0.9, "recommendation": "APPROVE"},
    ])

    letter_path = Path(result["artifacts"]["appeal_letter_path"])
    report_path = Path(result["artifacts"]["full_report_path"])
    assert letter_path.is_file(), "Reported letter path must contain the saved letter"
    assert report_path.is_file(), "Reported report path must contain the saved report"
    assert json.loads(report_path.read_text(encoding="utf-8")) == result


@pytest.mark.parametrize("changed_source", ["denial", "policy", "regulatory", "unchanged"])
def test_pipeline_binds_cached_facts_to_complete_inputs(monkeypatch, tmp_path, changed_source):
    real_auditor = auditor.run
    configure_fake_agents(monkeypatch, [
        {"overall_score": 0.9, "recommendation": "APPROVE"},
        {"overall_score": 0.9, "recommendation": "APPROVE"},
    ])
    monkeypatch.setattr(auditor, "run", real_auditor)
    responses = iter([{"insurer_name": "First Insurer"}, {"insurer_name": "Second Insurer"}])
    monkeypatch.setattr(auditor, "call_llm_json", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    (tmp_path / "sessions").mkdir(exist_ok=True)
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    inputs = dict(denial_pdf="text", policy_pdf="text", case_id="same_case",
                  denial_text=DENIAL_TEXT, policy_text=POLICY_TEXT, regulatory_text="Source A")
    first = main.run_pipeline(**inputs)
    if changed_source != "unchanged":
        inputs[f"{changed_source}_text"] += " Changed source."
    second = main.run_pipeline(**inputs)

    assert first["auditor"]["insurer_name"] == "First Insurer"
    expected = "First Insurer" if changed_source == "unchanged" else "Second Insurer"
    assert second["auditor"]["insurer_name"] == expected


@pytest.mark.parametrize("corrected_letter", [
    "Please review the supplied documents.",
    "Please review Clause 99.9.",
])
def test_final_score_reviews_the_letter_after_evidence_changes(monkeypatch, tmp_path, corrected_letter):
    configure_fake_agents(monkeypatch, [])
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    (tmp_path / "sessions").mkdir(exist_ok=True)
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(appeal_writer, "run", lambda *args: "Please review Clause 99.9.")
    monkeypatch.setattr(appeal_writer, "revise", lambda *args, **kwargs: corrected_letter)

    def review(letter, *args):
        # Exercise the real Judge cache so failing to invalidate it is observable.
        cached = io_utils.load_checkpoint("evidence_case", "judge")
        if cached:
            return cached
        scorecard = {"overall_score": 0.9, "recommendation": "APPROVE"}
        if letter != "Please review Clause 99.9.":
            scorecard = {"overall_score": 0.6, "recommendation": "REVISE"}
        io_utils.save_checkpoint("evidence_case", "judge", scorecard)
        return scorecard

    monkeypatch.setattr(judge, "run", review)
    result = main.run_pipeline("text", "text", "evidence_case",
                               denial_text=DENIAL_TEXT, policy_text=POLICY_TEXT)
    assert result["evidence_validation"]["valid"]
    assert "Clause 99.9" not in result["appeal_letter"]
    assert result["pipeline_stats"]["final_score"] == 0.6
    assert result["judge"]["recommendation"] == "REVISE"
    assert result["pipeline_stats"]["final_recommendation"] == "REVISE"


def test_legacy_checkpoints_without_input_binding_are_discarded(monkeypatch, tmp_path):
    real_auditor = auditor.run
    configure_fake_agents(monkeypatch, [{"overall_score": 0.9, "recommendation": "APPROVE"}])
    monkeypatch.setattr(auditor, "run", real_auditor)
    monkeypatch.setattr(auditor, "call_llm_json", lambda *args, **kwargs: {"insurer_name": "Current Insurer"})
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    (tmp_path / "sessions").mkdir(exist_ok=True)
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    io_utils.save_checkpoint("legacy_case", "auditor", {"insurer_name": "Previous Insurer"})
    result = main.run_pipeline("text", "text", "legacy_case", denial_text=DENIAL_TEXT, policy_text=POLICY_TEXT)
    assert result["auditor"]["insurer_name"] == "Current Insurer"


def test_resuming_an_evidence_corrected_letter_uses_its_matching_judge_checkpoint(monkeypatch, tmp_path):
    real_writer_run, real_writer_revise, real_judge = appeal_writer.run, appeal_writer.revise, judge.run
    configure_fake_agents(monkeypatch, [])
    monkeypatch.setattr(appeal_writer, "run", real_writer_run)
    monkeypatch.setattr(appeal_writer, "revise", real_writer_revise)
    monkeypatch.setattr(judge, "run", real_judge)
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    drafts = iter(["Please review Clause 99.9.", "Please review the supplied documents."])
    scores = iter([
        {"overall_score": 0.9, "recommendation": "APPROVE"},
        {"overall_score": 0.85, "recommendation": "APPROVE"},
    ])
    monkeypatch.setattr(appeal_writer, "call_llm", lambda *args, **kwargs: next(drafts))
    monkeypatch.setattr(judge, "call_llm_json", lambda *args, **kwargs: next(scores))
    inputs = dict(denial_pdf="text", policy_pdf="text", case_id="corrected_case",
                  denial_text=DENIAL_TEXT, policy_text=POLICY_TEXT)
    first = main.run_pipeline(**inputs)
    resumed = main.run_pipeline(**inputs)
    assert first["appeal_letter"] == resumed["appeal_letter"] == "Please review the supplied documents."
    assert first["pipeline_stats"]["final_score"] == resumed["pipeline_stats"]["final_score"] == 0.85


def test_incomplete_document_coverage_requires_review_even_with_high_judge_score(monkeypatch, tmp_path):
    configure_fake_agents(monkeypatch, [{"overall_score": 0.9, "recommendation": "APPROVE"}])
    monkeypatch.setattr(auditor, "run", lambda *args: {"insurer_name": "Test", "input_coverage": {"requires_manual_review": True}})
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    result = main.run_pipeline("text", "text", "partial_case", denial_text=DENIAL_TEXT, policy_text=POLICY_TEXT)
    assert result["pipeline_stats"]["final_recommendation"] == "REVIEW_REQUIRED"
    assert result["input_coverage"]["requires_manual_review"]
    assert result["review_reasons"]


def test_context_budget_changes_invalidate_pipeline_cache(monkeypatch, tmp_path):
    configure_fake_agents(monkeypatch, [
        {"overall_score": 0.9, "recommendation": "APPROVE"},
        {"overall_score": 0.9, "recommendation": "APPROVE"},
    ])
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    inputs = dict(denial_pdf="text", policy_pdf="text", case_id="budget_case", denial_text=DENIAL_TEXT, policy_text=POLICY_TEXT)
    main.run_pipeline(**inputs)
    first = io_utils.load_checkpoint("budget_case", "inputs")
    monkeypatch.setenv("INSURECLEAR_PROMPT_BUDGET", "17000")
    main.run_pipeline(**inputs)
    assert first != io_utils.load_checkpoint("budget_case", "inputs")


def test_registry_version_changes_invalidate_pipeline_cache(monkeypatch, tmp_path):
    from types import SimpleNamespace
    configure_fake_agents(monkeypatch, [{"overall_score": 0.9, "recommendation": "APPROVE"}, {"overall_score": 0.9, "recommendation": "APPROVE"}])
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    versions = iter([SimpleNamespace(fingerprint="registry-v1"), SimpleNamespace(fingerprint="registry-v2")])
    monkeypatch.setattr(main, "load_registry", lambda: next(versions), raising=False)
    inputs = dict(denial_pdf="text", policy_pdf="text", case_id="registry_case", denial_text=DENIAL_TEXT, policy_text=POLICY_TEXT)
    main.run_pipeline(**inputs)
    first = io_utils.load_checkpoint("registry_case", "inputs")
    main.run_pipeline(**inputs)
    assert first != io_utils.load_checkpoint("registry_case", "inputs")


def test_unverified_regulatory_argument_is_not_pinned_evidence(monkeypatch, tmp_path):
    configure_fake_agents(monkeypatch, [{"overall_score": 0.9, "recommendation": "APPROVE"}, {"overall_score": 0.9, "recommendation": "APPROVE"}])
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    draft = "Please apply Circular FAKE/REG/999/2025."
    monkeypatch.setattr(appeal_writer, "run", lambda *args: draft)
    monkeypatch.setattr(appeal_writer, "revise", lambda *args, **kwargs: draft)
    result = main.run_pipeline("text", "text", "unverified_source", denial_text=DENIAL_TEXT, policy_text=POLICY_TEXT, regulatory_text="Circular FAKE/REG/999/2025 says this claim must be paid.")
    assert "FAKE/REG/999/2025" not in result["appeal_letter"]
    assert result["pipeline_stats"]["final_recommendation"] != "APPROVE"


def test_missing_policy_quotes_has_structured_review_issue(monkeypatch, tmp_path):
    configure_fake_agents(monkeypatch, [{"overall_score": 0.9, "recommendation": "APPROVE"}])
    monkeypatch.setattr(policy_analyst, "run", lambda *args: {"rejection_appears_valid": False})
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    result = main.run_pipeline("denial", "policy", "missing_policy_evidence", DENIAL_TEXT, POLICY_TEXT)
    assert result["pipeline_stats"]["final_recommendation"] == "REVIEW_REQUIRED"
    assert any(issue["type"] == "policy_evidence_missing" for issue in result["quality_issues"])
