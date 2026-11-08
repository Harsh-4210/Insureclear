from types import SimpleNamespace
import pytest
from tools import llm_client


def fake_gemini(monkeypatch, configs):
    class Model:
        def __init__(self, **kwargs):
            pass
        def generate_content(self, prompt):
            return SimpleNamespace(text='{"ok": true}')
    def config(**kwargs):
        configs.append(kwargs)
        return kwargs
    monkeypatch.setattr(llm_client, "PROVIDER", "gemini")
    monkeypatch.setattr(llm_client, "genai", SimpleNamespace(GenerativeModel=Model, GenerationConfig=config))
    monkeypatch.setattr(llm_client, "_init", lambda: None)


def test_gemini_native_json_honors_requested_output_reservation(monkeypatch):
    configs = []
    fake_gemini(monkeypatch, configs)
    assert llm_client._call_native_json("Return JSON", "system", 1, 512) == {"ok": True}
    assert configs[0]["max_output_tokens"] == 512


def test_appended_json_instructions_are_included_in_dispatch_budget(monkeypatch):
    fake_gemini(monkeypatch, [])
    monkeypatch.setenv("INSURECLEAR_PROMPT_BUDGET", "800")
    with pytest.raises(ValueError, match="budget"):
        llm_client.call_llm_json("x" * 100, max_output_tokens=100)


def test_groq_reasoning_reserve_is_included_at_dispatch(monkeypatch):
    monkeypatch.setattr(llm_client, "PROVIDER", "groq")
    monkeypatch.setattr(llm_client, "GROQ_REASONING_TOKEN_BUDGET", 500)
    monkeypatch.setenv("GROQ_API_KEYS", "test-key")
    monkeypatch.setenv("INSURECLEAR_PROMPT_BUDGET", "2200")
    response = SimpleNamespace(status_code=200, json=lambda: {"choices": [{"message": {"content": "ok"}}]}, text="ok")
    monkeypatch.setattr(llm_client.httpx, "post", lambda *args, **kwargs: response)
    with pytest.raises(ValueError, match="budget"):
        llm_client._call_groq("x" * 1000, "", 0.1, 500, False, 1)


def test_native_groq_json_honors_transport_retry_bound(monkeypatch):
    monkeypatch.setattr(llm_client, "PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEYS", "test-key")
    calls = []
    monkeypatch.setattr(llm_client.time, "sleep", lambda *args: None)
    response = SimpleNamespace(status_code=500, text="temporary", headers={})
    monkeypatch.setattr(llm_client.httpx, "post", lambda *args, **kwargs: calls.append(1) or response)
    with pytest.raises(RuntimeError):
        llm_client._call_native_json("Return JSON", "", 1, 100)
    assert len(calls) == 1


@pytest.mark.parametrize("native", [False, True])
def test_gemini_accounts_successful_response_tokens(monkeypatch, native):
    fake_gemini(monkeypatch, [])
    class Model:
        def __init__(self, **kwargs): pass
        def generate_content(self, prompt): return SimpleNamespace(text='{"ok": true}', usage_metadata=SimpleNamespace(total_token_count=123))
    monkeypatch.setattr(llm_client.genai, "GenerativeModel", Model)
    monkeypatch.setattr(llm_client, "_total_tokens", 0)
    if native: llm_client._call_native_json("Return JSON", "system", 1, 512)
    else: llm_client.call_llm("Return text", max_retries=1, max_output_tokens=512)
    assert llm_client.get_stats()["total_tokens"] == 123

@pytest.mark.parametrize("native", [False, True])
def test_gemini_sends_instructions_separately_from_untrusted_text(monkeypatch, native):
    fake_gemini(monkeypatch, [])
    calls = []
    class Model:
        def __init__(self, **kwargs):
            calls.append(kwargs.get("system_instruction"))
        def generate_content(self, prompt):
            calls.append(prompt)
            return SimpleNamespace(text='{"ok": true}')
    monkeypatch.setattr(llm_client.genai, "GenerativeModel", Model)
    if native:
        llm_client._call_native_json("untrusted case text", "trusted instruction", 1, 512)
    else:
        llm_client.call_llm("untrusted case text", "trusted instruction", max_retries=1, max_output_tokens=512)
    assert calls == ["trusted instruction", "untrusted case text"]
