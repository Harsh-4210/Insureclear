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
