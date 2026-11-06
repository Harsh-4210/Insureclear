import copy
import json
import sys

import pytest

from eval.cases import CASES, build_documents
from eval.score import find_unsupported_ids, score_case, summarise
from eval.run_eval import check_regression_gates


CASE = next(c for c in CASES if c["id"] == "c01_moratorium")


def make_report(letter: str, valid: bool, category: str = "non_disclosure") -> dict:
    return {
        "auditor": {
            "insurer_name": "Suraksha Health Insurance Co. Ltd.",
            "policy_number": "SHI4410028731",
            "claim_number": "CLM-SHI-2025-55102",
            "policyholder_name": "Anil Deshmukh",
            "claim_amount": "Rs 2,10,000",
            "denial_reason_category": category,
        },
        "policy_analyst": {"rejection_appears_valid": valid},
        "appeal_letter": letter,
        "pipeline_stats": {"final_score": 0.8, "revision_count": 1, "total_time_seconds": 30},
    }


def test_documents_fit_auditor_window():
    for case in CASES:
        denial, policy = build_documents(case)
        assert len(policy) <= 4000, case["id"]
        assert case["policy_number"] in denial and case["policy_number"] in policy


def test_perfect_report_scores_full_marks():
    letter = (
        "To Suraksha Health. Policy SHI4410028731, claim CLM-SHI-2025-55102, Mr. Deshmukh. "
        "The policy has completed 60 continuous months, so the moratorium applies."
    )
    sources = list(build_documents(CASE))
    result = score_case(make_report(letter, valid=False), CASE, sources)

    assert result["extraction"]["score"] == 1.0
    assert result["verdict"]["correct"] is True
    assert result["letter_facts"]["score"] == 1.0
    assert result["key_argument"]["found"] is True
    assert result["unsupported_ids"] == []


def test_wrong_verdict_missing_argument_and_invented_id_are_caught():
    letter = "Dear Sir, regarding policy SHI4410028731 and claim CLM-SHI-2025-99999, please reconsider."
    sources = list(build_documents(CASE))
    result = score_case(make_report(letter, valid=True, category="other"), CASE, sources)

    assert result["verdict"]["correct"] is False
    assert result["extraction"]["checks"]["denial_category"] is False
    assert result["key_argument"]["found"] is False
    assert result["unsupported_ids"] == ["CLM-SHI-2025-99999"]
    assert result["letter_facts"]["checks"]["claim_number"] is False


def test_find_unsupported_ids_ignores_ids_in_sources():
    assert find_unsupported_ids("See ABC-123 and 12345678.", ["ref abc-123 and 12345678"]) == []


def test_summary_counts_only_cases_with_a_key_argument():
    sources = list(build_documents(CASE))
    good = score_case(make_report("60 months moratorium", valid=False), CASE, sources)
    valid_case = next(c for c in CASES if c["id"] == "c06_hernia_valid")
    no_arg = score_case(make_report("letter", valid=True), valid_case, list(build_documents(valid_case)))

    summary = summarise([good, no_arg])
    assert summary["key_argument_cases"] == 1
    assert summary["key_argument_found"] == 1
    assert summary["verdict_correct"] == 2
    assert summary["verdict_accuracy"] == 1.0
    assert summary["unsupported_claim_rate"] == 0.0


def test_regression_gates_report_accuracy_and_unsupported_claim_failures():
    summary = {"verdict_accuracy": 0.5, "unsupported_claim_rate": 0.25, "failed_cases": 0}
    failures = check_regression_gates(summary, 0.8, 0.1)
    assert len(failures) == 2


def test_regression_gates_include_pipeline_failures():
    failures = check_regression_gates(
        {"verdict_accuracy": 1.0, "unsupported_claim_rate": 0.0, "failed_cases": 1}
    )
    assert failures == ["1 case(s) failed to run"]


def test_evaluation_recognizes_only_integrity_checked_selected_source_citations():
    from eval import run_eval
    from tools.regulatory_registry import load_registry
    denial, policy = build_documents(CASE)
    selected = load_registry().select("non_disclosure", {})
    report = make_report("See IRDAI/HLT/CIR/PRO/84/5/2024 and FAKE/REG/999/2025.", False)
    report["regulatory_evidence"] = selected.as_dict()
    report["verified_source_context"] = "FAKE/REG/999/2025"
    sources = run_eval.evaluation_sources(denial, policy, report)
    scored = score_case(report, CASE, sources)
    assert scored["unsupported_ids"] == ["FAKE/REG/999/2025"]


def test_resuming_evaluation_rechecks_saved_scores_without_provider_calls(monkeypatch, tmp_path):
    import json
    import sys
    from eval import run_eval
    from tools.regulatory_registry import load_registry
    denial, policy = build_documents(CASE)
    report = make_report("Suraksha Health Policy SHI4410028731 claim CLM-SHI-2025-55102 Deshmukh moratorium IRDAI/HLT/CIR/PRO/84/5/2024.", False)
    report["regulatory_evidence"] = load_registry().select("non_disclosure", {}).as_dict()
    report["evidence_validation"] = {"valid": True, "errors": []}
    stale = score_case(report, CASE, [denial, policy])
    assert stale["unsupported_ids"]
    run_dir = tmp_path / "resumed"
    run_dir.mkdir()
    (run_dir / f"{CASE['id']}.json").write_text(json.dumps({"report": report, "score": stale, "manifest": run_eval.build_evaluation_manifest(CASE, denial, policy)}), encoding="utf-8")
    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(run_eval, "CASES", [CASE])
    def unexpected_call(**kwargs):
        raise AssertionError("A saved report must not call a provider")
    monkeypatch.setattr(run_eval, "run_pipeline", unexpected_call)
    monkeypatch.setattr(run_eval, "_throttle_gemini", lambda: None)
    monkeypatch.setattr(sys, "argv", ["run_eval", "--resume", "resumed", "--min-verdict-accuracy", "1", "--max-unsupported-claim-rate", "0"])
    run_eval.main()
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["cases"] == 1 and summary["unsupported_claim_rate"] == 0
    assert summary["reused_cases"] == 1 and summary["new_cases"] == 0
    assert summary["usage_scope"] == "current_invocation"
    saved = json.loads((run_dir / f"{CASE['id']}.json").read_text())
    assert saved["score_history"] == [stale]
    assert saved["score"]["unsupported_ids"] == []


def test_documents_submitted_fixture_contains_the_evidence_its_answer_requires():
    case = next(c for c in CASES if c["id"] == "c08_documents_submitted")
    denial, policy = build_documents(case)
    acknowledged_upload = denial.split("(Our records show", 1)[1].lower()
    for document in ("claim form", "discharge summary", "final bill", "investigation reports"):
        assert document in acknowledged_upload, f"Already-submitted fixture lacks acknowledged {document}"


def test_key_argument_matching_normalizes_unicode_hyphens():
    from eval.score import score_key_argument
    case = next(c for c in CASES if c["id"] == "c04_day_care")
    result = score_key_argument("The policy covers day\u2011care chemotherapy.", case)
    assert result["found"] and "day-care" in result["matched"]


@pytest.mark.parametrize("manifest", [None, {}])
def test_resume_refuses_unbound_saved_reports_before_scoring_or_provider(monkeypatch, tmp_path, manifest):
    from eval import run_eval
    run_dir = tmp_path / "unbound"
    run_dir.mkdir()
    case_file = run_dir / f"{CASE['id']}.json"
    original = json.dumps({"report": make_report("legacy report", False), "score": {}, "manifest": manifest})
    case_file.write_text(original, encoding="utf-8")
    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(run_eval, "CASES", [CASE])
    monkeypatch.setattr(run_eval, "_throttle_gemini", lambda: None)
    def forbidden(*args, **kwargs):
        pytest.fail("Manifest preflight must run before scoring or provider calls")
    monkeypatch.setattr(run_eval, "score_case", forbidden)
    monkeypatch.setattr(run_eval, "run_pipeline", forbidden)
    monkeypatch.setattr(sys, "argv", ["run_eval", "--resume", "unbound"])
    with pytest.raises(SystemExit, match="manifest"):
        run_eval.main()
    assert case_file.read_text(encoding="utf-8") == original
    assert not (run_dir / "summary.json").exists()


def test_manifest_binds_exact_inputs_answers_sources_and_model_without_secrets(monkeypatch):
    from eval import run_eval
    denial, policy = build_documents(CASE)
    manifest = run_eval.build_evaluation_manifest(CASE, denial, policy)
    assert manifest == run_eval.build_evaluation_manifest(dict(reversed(list(CASE.items()))), denial, policy)
    assert manifest != run_eval.build_evaluation_manifest(CASE, denial + " changed", policy)
    assert manifest != run_eval.build_evaluation_manifest(CASE, denial, policy + " changed")
    changed = copy.deepcopy(CASE)
    changed["answer"]["rejection_valid"] = not changed["answer"]["rejection_valid"]
    assert manifest != run_eval.build_evaluation_manifest(changed, denial, policy)
    assert "orchestrator/main.py" in manifest["generation_source_sha256"]
    assert "agents/appeal_writer.py" in manifest["generation_source_sha256"]
    assert "tools/llm_client.py" in manifest["generation_source_sha256"]
    assert manifest["registry_fingerprint"]
    monkeypatch.setenv("GROQ_API_KEY", "never-write-this-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "never-write-this-secret-either")
    assert manifest == run_eval.build_evaluation_manifest(CASE, denial, policy)
    assert "never-write-this-secret" not in json.dumps(manifest)
    monkeypatch.setattr(run_eval.llm_client, "MODEL_NAME", "changed-model")
    assert manifest != run_eval.build_evaluation_manifest(CASE, denial, policy)


@pytest.mark.parametrize("field", ["denial_sha256", "policy_sha256", "answer_sha256", "case_sha256", "generation_source_sha256", "registry_fingerprint", "model", "config", "schema_version"])
def test_resume_refuses_changed_manifest_before_any_new_case(monkeypatch, tmp_path, field):
    from eval import run_eval
    # A new case comes first; checking only as the loop reaches the reused case is too late.
    new_case = next(c for c in CASES if c["id"] != CASE["id"])
    denial, policy = build_documents(CASE)
    manifest = run_eval.build_evaluation_manifest(CASE, denial, policy)
    manifest[field] = "changed"
    run_dir = tmp_path / "mismatch"
    run_dir.mkdir()
    case_file = run_dir / f"{CASE['id']}.json"
    original = json.dumps({"report": make_report("saved", False), "score": {}, "manifest": manifest})
    case_file.write_text(original, encoding="utf-8")
    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(run_eval, "CASES", [new_case, CASE])
    def forbidden(*args, **kwargs):
        pytest.fail("Changed manifest must stop the invocation before any scoring/provider call")
    monkeypatch.setattr(run_eval, "score_case", forbidden)
    monkeypatch.setattr(run_eval, "run_pipeline", forbidden)
    monkeypatch.setattr(run_eval, "_throttle_gemini", forbidden)
    monkeypatch.setattr(sys, "argv", ["run_eval", "--resume", "mismatch"])
    with pytest.raises(SystemExit, match="manifest"):
        run_eval.main()
    assert case_file.read_text(encoding="utf-8") == original
    assert not (run_dir / "summary.json").exists()


def test_manifest_changes_with_runtime_retrieval_and_reasoning_config(monkeypatch):
    from eval import run_eval
    denial, policy = build_documents(CASE)
    monkeypatch.setattr(run_eval.llm_client, "PROVIDER", "groq")
    baseline = run_eval.build_evaluation_manifest(CASE, denial, policy)
    monkeypatch.setenv("INSURECLEAR_PROMPT_BUDGET", "17000")
    assert baseline != run_eval.build_evaluation_manifest(CASE, denial, policy)
    monkeypatch.delenv("INSURECLEAR_PROMPT_BUDGET")
    monkeypatch.setattr(run_eval.llm_client, "GROQ_REASONING_EFFORT", "high")
    assert baseline != run_eval.build_evaluation_manifest(CASE, denial, policy)


def test_new_report_saves_matching_manifest_and_current_invocation_usage(monkeypatch, tmp_path):
    from eval import run_eval
    report = make_report("moratorium", False)
    monkeypatch.setattr(run_eval, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(run_eval, "CASES", [CASE])
    monkeypatch.setattr(run_eval, "_throttle_gemini", lambda: None)
    monkeypatch.setattr(run_eval, "clear_session", lambda _: None)
    monkeypatch.setattr(run_eval.time, "sleep", lambda _: None)
    counters = {"total_calls": 10, "total_tokens": 100, "total_retries": 2, "total_429s": 1}
    monkeypatch.setattr(run_eval.llm_client, "get_stats", lambda: dict(counters))
    def pipeline(**kwargs):
        counters["total_calls"] += 2
        counters["total_tokens"] += 30
        return report
    monkeypatch.setattr(run_eval, "run_pipeline", pipeline)
    monkeypatch.setattr(sys, "argv", ["run_eval"])
    run_eval.main()
    run_dir = next(tmp_path.iterdir())
    saved = json.loads((run_dir / f"{CASE['id']}.json").read_text())
    denial, policy = build_documents(CASE)
    run_eval.verify_evaluation_manifest(saved, run_eval.build_evaluation_manifest(CASE, denial, policy))
    assert saved["usage"]["total_calls"] == 2
    assert saved["usage"]["total_tokens"] == 30
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["llm_calls"] == 2 and summary["total_tokens"] == 30
    assert summary["llm_retries"] == 0 and summary["llm_429s"] == 0
    assert summary["new_cases"] == 1 and summary["reused_cases"] == 0
    assert summary["usage_scope"] == "current_invocation"


@pytest.mark.parametrize("source_path", ["orchestrator/main.py", "agents/appeal_writer.py", "tools/regulatory_registry.py"])
def test_manifest_hashes_generation_source_bytes(monkeypatch, tmp_path, source_path):
    from eval import run_eval
    paths = set(run_eval.GENERATION_SOURCE_PATHS) | {"agents/appeal_writer.py"}
    for name in paths:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original", encoding="utf-8")
    monkeypatch.setattr(run_eval, "PROJECT_ROOT", tmp_path)
    denial, policy = build_documents(CASE)
    baseline = run_eval.build_evaluation_manifest(CASE, denial, policy)
    (tmp_path / source_path).write_text("changed generation contract", encoding="utf-8")
    changed = run_eval.build_evaluation_manifest(CASE, denial, policy)
    assert baseline["generation_source_sha256"][source_path] != changed["generation_source_sha256"][source_path]
    with pytest.raises(ValueError, match="manifest"):
        run_eval.verify_evaluation_manifest({"manifest": baseline}, changed)


def test_manifest_binds_the_verified_registry_fingerprint(monkeypatch):
    from eval import run_eval
    from types import SimpleNamespace
    denial, policy = build_documents(CASE)
    original = run_eval.build_evaluation_manifest(CASE, denial, policy)
    monkeypatch.setattr(run_eval, "load_registry", lambda: SimpleNamespace(fingerprint="different-pinned-registry"))
    changed = run_eval.build_evaluation_manifest(CASE, denial, policy)
    assert original["registry_fingerprint"] != changed["registry_fingerprint"]
    with pytest.raises(ValueError, match="manifest"):
        run_eval.verify_evaluation_manifest({"manifest": original}, changed)


@pytest.mark.parametrize("name,new_value", [
    ("INSURECLEAR_CASE_TIMEOUT_SECONDS", "301"),
    ("INSURECLEAR_CASE_MAX_CALLS", "21"),
    ("INSURECLEAR_CASE_MAX_TOKENS", "60001"),
])
def test_manifest_binds_effective_pipeline_runtime_limits(monkeypatch, name, new_value):
    from eval import run_eval
    denial, policy = build_documents(CASE)
    baseline = run_eval.build_evaluation_manifest(CASE, denial, policy)
    monkeypatch.setenv(name, new_value)
    changed = run_eval.build_evaluation_manifest(CASE, denial, policy)
    assert baseline != changed
