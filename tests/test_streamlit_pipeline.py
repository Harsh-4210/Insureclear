from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from agents import auditor
from orchestrator import main


@pytest.mark.parametrize("recommendation", ["REVIEW_REQUIRED", "VALIDATION_ERROR"])
def test_active_streamlit_uses_shared_effective_pipeline_result(monkeypatch, tmp_path, recommendation):
    calls = []
    def shared_pipeline(**kwargs):
        calls.append(kwargs)
        return {"case_id": kwargs["case_id"], "auditor": {}, "policy_analyst": {}, "irdai_checker": {}, "judge": {"overall_score": 0.9, "recommendation": "APPROVE"}, "appeal_letter": "Review this draft.", "evidence_validation": {"valid": recommendation != "VALIDATION_ERROR", "errors": []}, "input_coverage": {"requires_manual_review": True}, "review_reasons": ["Review source coverage and legal applicability."], "artifacts": {"output_dir": str(tmp_path)}, "pipeline_stats": {"final_score": 0.9, "final_recommendation": recommendation, "revision_count": 0}}
    def bypassed(*args, **kwargs):
        raise AssertionError("Streamlit bypassed shared pipeline")
    monkeypatch.setattr(main, "run_pipeline", shared_pipeline)
    monkeypatch.setattr(auditor, "run", bypassed)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run(timeout=10)
    app.button[0].click().run(timeout=10)
    assert calls, "Active Streamlit generation must use the shared pipeline"
    assert not app.exception
    assert any(recommendation in item.value for item in app.markdown)
