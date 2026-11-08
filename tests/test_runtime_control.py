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


def test_cancel_during_revision_prevents_another_judge_dispatch(monkeypatch, tmp_path):
    from test_pipeline import configure_fake_agents, DENIAL_TEXT, POLICY_TEXT
    from orchestrator import main
    from agents import appeal_writer, judge
    from tools import io_utils
    configure_fake_agents(monkeypatch, [])
    monkeypatch.setattr(io_utils, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(io_utils, "SESSIONS_DIR", tmp_path / "sessions")
    cancelled = [False]
    calls = []
    def review(*args):
        calls.append(1)
        if len(calls) > 1: pytest.fail("Judge dispatched after cancellation during revision")
        return {"overall_score": 0.5, "recommendation": "REVISE"}
    def revise(*args, **kwargs):
        cancelled[0] = True
        return "Please review the supplied claim."
    def check():
        if cancelled[0]: raise PipelineCancelled("Cancelled")
    monkeypatch.setattr(judge, "run", review)
    monkeypatch.setattr(appeal_writer, "revise", revise)
    with pytest.raises(PipelineCancelled): main.run_pipeline("denial", "policy", "cancel_revision", DENIAL_TEXT, POLICY_TEXT, control=check)


def test_unreported_provider_usage_cannot_silently_bypass_budget():
    from tools.runtime_control import PipelineBudgetExceeded
    stats = {"total_calls": 0, "unreported_usage_calls": 0}
    control = RuntimeControl(stats=lambda: dict(stats))
    stats.update(total_calls=1, unreported_usage_calls=1)
    with pytest.raises(PipelineBudgetExceeded): control.check()
