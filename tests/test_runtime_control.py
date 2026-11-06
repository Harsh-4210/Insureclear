import pytest
from tools.runtime_control import RuntimeControl, PipelineCancelled, PipelineTimedOut, usage_delta


def test_usage_delta_is_per_case_not_process_lifetime():
    result = usage_delta({"total_calls": 10, "total_tokens": 1000, "total_time_seconds": 20}, {"total_calls": 13, "total_tokens": 1600, "total_time_seconds": 26, "provider": "fake"})
    assert result["total_calls"] == 3 and result["total_tokens"] == 600
    assert result["avg_time_per_call"] == 2 and result["usage_scope"] == "case"


def test_cooperative_cancellation_and_time_limit():
    now = [0.0]
    control = RuntimeControl(cancelled=lambda: False, seconds=10, clock=lambda: now[0])
    control.check()
    now[0] = 11
    with pytest.raises(PipelineTimedOut): control.check()
    with pytest.raises(PipelineCancelled): RuntimeControl(cancelled=lambda: True).check()


def test_pipeline_control_stops_before_any_agent(monkeypatch):
    from orchestrator.main import run_pipeline
    from agents import auditor
    monkeypatch.setattr(auditor, "run", lambda *args: pytest.fail("Agent ran after cancellation"))
    def cancelled(): raise PipelineCancelled("Cancelled")
    with pytest.raises(PipelineCancelled):
        run_pipeline("unused", "unused", "synthetic_cancel", "Enough words of denial text for a case that is already cancelled.", "Enough words of policy text to verify an early cancellation check.", control=cancelled)


def test_pipeline_telemetry_contains_durations_and_does_not_print_patient_facts(monkeypatch, tmp_path, capsys):
    from test_pipeline import run_fake_pipeline
    report = run_fake_pipeline(monkeypatch, tmp_path, [{"overall_score": 0.9, "recommendation": "APPROVE"}])
    assert "Test procedure" not in capsys.readouterr().out
    assert report["pipeline_stats"]["llm_stats"]["usage_scope"] == "case"
    assert "Auditor" in report["pipeline_stats"]["stage_durations_seconds"]
